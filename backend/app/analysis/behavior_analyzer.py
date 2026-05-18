import numpy as np
from typing import List, Dict, Tuple
from ..models.schemas import TradeRecord, BehaviorAnalysis

class BehaviorAnalyzer:
    def analyze(self, trades: List[TradeRecord]) -> BehaviorAnalysis:
        if not trades:
            return BehaviorAnalysis()
            
        analysis = BehaviorAnalysis()
        
        # Extract trade details for analysis
        lots = [t.size for t in trades if t.size and t.size > 0]
        profits = [t.profit for t in trades]
        durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
        
        if lots:
            analysis.avg_lot = round(float(np.mean(lots)), 4)
            analysis.min_lot = round(float(np.min(lots)), 4)
            analysis.max_lot = round(float(np.max(lots)), 4)
            analysis.lot_std_dev = round(float(np.std(lots)), 4)
        
        # 1. Detect Martingale
        analysis.is_martingale, analysis.martingale_confidence = self._detect_martingale(trades)
        
        # 2. Detect Grid
        analysis.is_grid, analysis.grid_confidence = self._detect_grid(trades)

        # 3. Detect hedging and averaging patterns
        analysis.is_hedging, analysis.hedging_confidence = self._detect_hedging(trades)
        analysis.is_averaging_down, analysis.averaging_confidence = self._detect_averaging_down(trades)
        
        # 4. Detect Scalping
        if durations:
            avg_duration = np.mean(durations)
            if avg_duration < 5: # Less than 5 minutes
                analysis.is_scalping = True
                analysis.scalping_confidence = round(min(100, (5 - avg_duration) * 20 + 50), 2)
        
        # 5. Detect Lot Escalation vs balance-based auto lot growth
        analysis.lot_escalation_factor = round(analysis.max_lot / analysis.min_lot, 2) if analysis.min_lot > 0 else 0.0
        lot_growth_events = 0
        loss_linked_growth = 0
        profit_linked_growth = 0

        for i in range(1, len(trades)):
            prev = trades[i - 1]
            curr = trades[i]
            prev_size = prev.size or 0
            curr_size = curr.size or 0
            if prev_size <= 0 or curr_size <= 0:
                continue

            if curr_size > prev_size * 1.05:
                lot_growth_events += 1

                same_symbol_overlap = bool(
                    prev.item
                    and curr.item
                    and prev.item == curr.item
                    and prev.type == curr.type
                    and prev.open_time
                    and prev.close_time
                    and curr.open_time
                    and curr.open_time < prev.close_time
                )

                if prev.profit < 0 or same_symbol_overlap:
                    loss_linked_growth += 1
                elif prev.profit > 0:
                    profit_linked_growth += 1

        if lot_growth_events:
            balance_based_ratio = profit_linked_growth / lot_growth_events
            loss_based_ratio = loss_linked_growth / lot_growth_events
            analysis.balance_based_lot_growth_detected = balance_based_ratio >= 0.6 and loss_based_ratio == 0
            analysis.lot_escalation_detected = loss_based_ratio >= 0.5 and not analysis.balance_based_lot_growth_detected
                
        # 6. Overtrading
        dated_trades = [t for t in trades if t.open_time or t.close_time]
        if dated_trades:
            first_time = dated_trades[0].open_time or dated_trades[0].close_time
            last_time = dated_trades[-1].close_time or dated_trades[-1].open_time
            days = (last_time - first_time).days if first_time and last_time else 1
            trades_per_day = len(trades) / max(1, days)
            if trades_per_day > 20 or (len(trades) > 500 and days <= 30):
                analysis.overtrading_detected = True

        analysis.dangerous_recovery_system = bool(
            (analysis.is_martingale and analysis.lot_escalation_detected)
            or (analysis.is_grid and analysis.is_averaging_down)
        )
                
        # 7. Session Distribution
        analysis.session_distribution = self._calculate_sessions(trades)
        
        return analysis

    def _detect_martingale(self, trades: List[TradeRecord]) -> Tuple[bool, float]:
        # Martingale increases lot size after a loss
        escalations = 0
        losses_followed_by_increase = 0
        
        for i in range(1, len(trades)):
            previous_size = trades[i - 1].size or 0
            current_size = trades[i].size or 0
            if trades[i-1].profit < 0 and previous_size > 0 and current_size > 0:
                if current_size > previous_size * 1.05:
                    losses_followed_by_increase += 1
                escalations += 1
        
        if escalations == 0: return False, 0.0
        
        ratio = losses_followed_by_increase / escalations
        is_detected = ratio > 0.6 and len(trades) > 5
        confidence = ratio * 100
        
        return is_detected, confidence

    def _detect_grid(self, trades: List[TradeRecord]) -> Tuple[bool, float]:
        # Grid trading has multiple trades open at the same time with similar spacing
        if len(trades) < 5: return False, 0.0
        
        overlapping = 0
        for i in range(len(trades)):
            if not trades[i].open_time or not trades[i].close_time:
                continue
            concurrent = 0
            for j in range(len(trades)):
                if i == j: continue
                if trades[j].open_time and \
                   trades[j].open_time > trades[i].open_time and \
                   trades[j].open_time < trades[i].close_time:
                    concurrent += 1
            if concurrent >= 3:
                overlapping += 1
                
        same_symbol_clusters = 0
        for symbol in {t.item for t in trades if t.item}:
            symbol_trades = [t for t in trades if t.item == symbol]
            if len(symbol_trades) >= 5:
                price_diffs = [
                    abs(symbol_trades[i].price - symbol_trades[i - 1].price)
                    for i in range(1, len(symbol_trades))
                    if symbol_trades[i].price and symbol_trades[i - 1].price
                ]
                if len(price_diffs) >= 4 and np.std(price_diffs) <= max(np.mean(price_diffs) * 0.35, 0.00001):
                    same_symbol_clusters += 1
        
        ratio = (overlapping + same_symbol_clusters) / len(trades)
        is_detected = ratio > 0.2 or same_symbol_clusters >= 1
        confidence = min(100, ratio * 250 + same_symbol_clusters * 25)
        
        return is_detected, confidence

    def _detect_hedging(self, trades: List[TradeRecord]) -> Tuple[bool, float]:
        if len(trades) < 2:
            return False, 0.0

        opposite_overlap = 0
        checked = 0
        for i, trade in enumerate(trades):
            if not trade.open_time or not trade.close_time:
                continue
            checked += 1
            for other in trades[i + 1 :]:
                if not other.open_time or not other.close_time:
                    continue
                if trade.item == other.item and trade.type != other.type:
                    overlaps = other.open_time < trade.close_time and trade.open_time < other.close_time
                    if overlaps:
                        opposite_overlap += 1
                        break

        if checked == 0:
            buys = sum(1 for t in trades if t.type == "buy")
            sells = sum(1 for t in trades if t.type == "sell")
            ratio = min(buys, sells) / max(1, buys + sells)
            return ratio > 0.35, round(ratio * 180, 2)

        ratio = opposite_overlap / checked
        return ratio > 0.15, round(min(100, ratio * 250), 2)

    def _detect_averaging_down(self, trades: List[TradeRecord]) -> Tuple[bool, float]:
        additions = 0
        losing_additions = 0
        running_profit_by_symbol: Dict[str, float] = {}

        for trade in trades:
            symbol = trade.item or "Unknown"
            running_profit = running_profit_by_symbol.get(symbol, 0.0)
            if running_profit < 0 and trade.profit < 0:
                losing_additions += 1
            if running_profit < 0:
                additions += 1
            running_profit_by_symbol[symbol] = running_profit + trade.profit

        if additions == 0:
            return False, 0.0

        ratio = losing_additions / additions
        return ratio > 0.45 and additions >= 3, round(min(100, ratio * 160), 2)

    def _calculate_sessions(self, trades: List[TradeRecord]) -> Dict[str, int]:
        sessions = {"Asian": 0, "London": 0, "New York": 0, "Overlap": 0}
        for t in trades:
            if not t.open_time: continue
            hour = t.open_time.hour
            
            # Simplified session hours (UTC)
            if 0 <= hour < 8: sessions["Asian"] += 1
            elif 8 <= hour < 12: sessions["London"] += 1
            elif 12 <= hour < 16: sessions["Overlap"] += 1
            else: sessions["New York"] += 1
            
        return sessions
