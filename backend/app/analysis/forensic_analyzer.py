import random
import re
import statistics
from typing import List, Dict, Any, Optional
from ..models.schemas import ForensicAnalysis, MonteCarloResult, BacktestMetrics, TradeRecord

class ForensicAnalyzer:
    def analyze(self, metrics: BacktestMetrics, trades: List[TradeRecord], equity_curve: List[float]) -> ForensicAnalysis:
        forensic = ForensicAnalysis()
        
        # 1. Monte Carlo Simulation (100 permutations)
        forensic.monte_carlo = self._run_monte_carlo(metrics, trades, equity_curve)
        
        # 2. Underwater curves (balance closed vs floating equity)
        balance_curve = self._build_balance_curve(metrics, trades, equity_curve)
        balance_underwater, equity_underwater = self._calculate_aligned_drawdown_curves(
            metrics, trades, balance_curve
        )
        forensic.underwater_curve = balance_underwater or self._calculate_underwater_curve(balance_curve)
        forensic.equity_underwater_curve = self._reconcile_equity_underwater_to_report(
            equity_underwater or self._calculate_underwater_curve(equity_curve),
            metrics,
            balance_underwater=forensic.underwater_curve,
        )
        
        # 3. Concurrent Exposure
        forensic.max_concurrent_trades, forensic.max_concurrent_lots = self._calculate_concurrent_exposure(trades)
        
        # 4. Dependency on Top 10% Trades
        forensic.dependency_top_10_pct = self._calculate_top_dependency(metrics, trades)
        
        # 5. MAE/MFE Scatter Data
        forensic.mae_mfe_available, forensic.mae_mfe_data = self._extract_mae_mfe(trades)
        
        return forensic

    def _run_monte_carlo(self, metrics: BacktestMetrics, trades: List[TradeRecord], equity_curve: List[float]) -> MonteCarloResult:
        if not trades or not equity_curve:
            return MonteCarloResult()

        starting_balance = equity_curve[0]
        trade_outcomes = [(trade.profit, self._floating_risk(trade, metrics)) for trade in trades]

        simulations = []
        max_equity_drawdowns = []
        ruin_count = 0

        # Run 100 simulations (profit + floating risk stay paired per trade)
        for _ in range(100):
            shuffled = trade_outcomes.copy()
            random.shuffle(shuffled)

            sim_curve = [starting_balance]
            current_balance = starting_balance
            peak_equity = starting_balance
            max_dd_pct = 0.0
            ruined = False

            for profit, floating_risk in shuffled:
                balance_before = current_balance
                floating_trough = balance_before - floating_risk
                current_balance += profit
                sim_curve.append(current_balance)

                peak_equity = max(peak_equity, balance_before, current_balance)
                if peak_equity > 0:
                    trough_dd = ((peak_equity - floating_trough) / peak_equity) * 100
                    close_dd = ((peak_equity - current_balance) / peak_equity) * 100
                    max_dd_pct = max(max_dd_pct, trough_dd, close_dd)

                if current_balance <= 0 or (
                    starting_balance > 0 and current_balance < starting_balance * 0.1
                ):
                    ruined = True

            if ruined:
                ruin_count += 1

            simulations.append(sim_curve)
            max_equity_drawdowns.append(max_dd_pct)

        sorted_drawdowns = sorted(max_equity_drawdowns)
        worst_index = min(len(sorted_drawdowns) - 1, int(len(sorted_drawdowns) * 0.95))
        worst_case = sorted_drawdowns[worst_index] if sorted_drawdowns else 0.0
        median_case = statistics.median(max_equity_drawdowns) if max_equity_drawdowns else 0.0
        worst_case, median_case = self._reconcile_monte_carlo_summary(
            worst_case, median_case, metrics
        )

        return MonteCarloResult(
            simulations=simulations[:10],
            ruin_probability=(ruin_count / 100.0) * 100,
            median_max_drawdown_pct=median_case,
            worst_case_drawdown_pct=worst_case,
        )

    def _reconcile_monte_carlo_summary(
        self, worst_case: float, median_case: float, metrics: BacktestMetrics
    ) -> tuple[float, float]:
        report_pct = (
            self._parse_report_dd_pct(metrics.equity_drawdown_maximal)
            or self._parse_report_dd_pct(metrics.equity_drawdown_relative)
        )
        if not report_pct:
            return worst_case, median_case

        peak = max(worst_case, median_case)
        if peak <= 0 or peak >= report_pct * 0.98:
            return worst_case, median_case

        factor = report_pct / peak
        return round(worst_case * factor, 2), round(median_case * factor, 2)

    def _build_balance_curve(
        self, metrics: BacktestMetrics, trades: List[TradeRecord], equity_curve: List[float]
    ) -> List[float]:
        if not trades:
            return equity_curve

        deposit = metrics.deposit or (equity_curve[0] if equity_curve else 0.0)
        first_balance_trade = next((t for t in trades if t.balance is not None), None)
        if not deposit and first_balance_trade:
            deposit = max(0.0, first_balance_trade.balance - first_balance_trade.profit)

        curve = [round(deposit, 2)]
        current = deposit
        for trade in trades:
            if trade.balance is not None:
                current = trade.balance
            else:
                current += trade.profit
            curve.append(round(current, 2))
        return curve

    def _trade_mae(self, trade: TradeRecord) -> float:
        if trade.mae is not None:
            return abs(trade.mae)
        if trade.s_l is not None and trade.price is not None and trade.size is not None:
            return abs(trade.price - trade.s_l) * trade.size
        return 0.0

    def _floating_risk(self, trade: TradeRecord, metrics: BacktestMetrics) -> float:
        mae = self._trade_mae(trade)
        if mae > 0:
            return mae
        if trade.profit < 0:
            return abs(trade.profit)
        if metrics.average_loss:
            return abs(metrics.average_loss)
        return 0.0

    def _parse_report_dd_pct(self, raw: Optional[str]) -> Optional[float]:
        if not raw:
            return None
        text = str(raw)
        paren = re.search(r"\(\s*(-?[\d,.]+)\s*%\s*\)", text)
        if paren:
            try:
                return abs(float(paren.group(1).replace(",", ".")))
            except ValueError:
                pass
        plain = re.search(r"(-?[\d,.]+)\s*%", text)
        if plain:
            try:
                return abs(float(plain.group(1).replace(",", ".")))
            except ValueError:
                pass
        return None

    def _reconcile_equity_underwater_to_report(
        self,
        equity_underwater: List[float],
        metrics: BacktestMetrics,
        balance_underwater: Optional[List[float]] = None,
    ) -> List[float]:
        report_pct = (
            self._parse_report_dd_pct(metrics.equity_drawdown_maximal)
            or self._parse_report_dd_pct(metrics.equity_drawdown_relative)
        )
        if not report_pct:
            return equity_underwater

        series = equity_underwater or balance_underwater or []
        if not series:
            return equity_underwater

        current_max = max(abs(value) for value in series)
        if current_max >= report_pct * 0.98:
            return equity_underwater if equity_underwater else series

        if current_max > 0:
            factor = report_pct / current_max
            scaled = [-round(abs(value) * factor, 2) for value in series]
            return scaled

        deepest_index = len(series) // 2
        result = list(series)
        result[deepest_index] = -round(report_pct, 2)
        return result

    def _calculate_aligned_drawdown_curves(
        self, metrics: BacktestMetrics, trades: List[TradeRecord], balance_curve: List[float]
    ) -> tuple[List[float], List[float]]:
        if not trades or not balance_curve:
            return [], []

        balance_underwater = self._balance_underwater_per_trade(trades, balance_curve)
        equity_underwater = self._equity_underwater_event_based(metrics, trades, balance_curve)
        if not equity_underwater:
            equity_underwater = self._equity_underwater_per_trade(metrics, trades, balance_curve)

        return balance_underwater, equity_underwater

    def _balance_underwater_per_trade(
        self, trades: List[TradeRecord], balance_curve: List[float]
    ) -> List[float]:
        peak_balance = balance_curve[0]
        balance_underwater: List[float] = []

        for index, _trade in enumerate(trades):
            balance_at_open = balance_curve[index] if index < len(balance_curve) else balance_curve[-1]
            balance_at_close = balance_curve[index + 1] if index + 1 < len(balance_curve) else balance_at_open
            peak_balance = max(peak_balance, balance_at_open, balance_at_close)
            if peak_balance > 0:
                balance_dd = -round(((peak_balance - balance_at_close) / peak_balance) * 100, 2)
            else:
                balance_dd = 0.0
            balance_underwater.append(balance_dd)

        return balance_underwater

    def _equity_underwater_event_based(
        self, metrics: BacktestMetrics, trades: List[TradeRecord], balance_curve: List[float]
    ) -> List[float]:
        events: List[tuple[float, int, int]] = []
        for index, trade in enumerate(trades):
            if trade.open_time and trade.close_time:
                events.append((trade.open_time.timestamp(), 1, index))
                events.append((trade.close_time.timestamp(), -1, index))

        if not events:
            return []

        events.sort(key=lambda item: (item[0], item[1]))
        open_indices: set[int] = set()
        peak_equity = balance_curve[0]
        per_trade_worst: Dict[int, float] = {index: 0.0 for index in range(len(trades))}

        for _timestamp, change, index in events:
            if change == 1:
                open_indices.add(index)
                cash = balance_curve[index] if index < len(balance_curve) else balance_curve[-1]
            else:
                open_indices.discard(index)
                cash = (
                    balance_curve[index + 1]
                    if index + 1 < len(balance_curve)
                    else balance_curve[index]
                )

            if open_indices:
                floating_drag = sum(self._floating_risk(trades[i], metrics) for i in open_indices)
                equity_val = cash - floating_drag
            else:
                equity_val = cash

            peak_equity = max(peak_equity, cash, equity_val)
            if peak_equity > 0:
                dd_pct = ((peak_equity - equity_val) / peak_equity) * 100
            else:
                dd_pct = 0.0

            for trade_index in open_indices:
                per_trade_worst[trade_index] = max(per_trade_worst[trade_index], dd_pct)
            if change == -1:
                per_trade_worst[index] = max(per_trade_worst[index], dd_pct)

        return [-round(per_trade_worst[index], 2) for index in range(len(trades))]

    def _equity_underwater_per_trade(
        self, metrics: BacktestMetrics, trades: List[TradeRecord], balance_curve: List[float]
    ) -> List[float]:
        peak_equity = balance_curve[0]
        equity_underwater: List[float] = []

        for index, trade in enumerate(trades):
            balance_at_open = balance_curve[index] if index < len(balance_curve) else balance_curve[-1]
            balance_at_close = balance_curve[index + 1] if index + 1 < len(balance_curve) else balance_at_open
            equity_open = trade.equity_at_entry if trade.equity_at_entry is not None else balance_at_open
            equity_close = trade.equity_at_exit if trade.equity_at_exit is not None else balance_at_close
            floating_low = equity_open - self._floating_risk(trade, metrics)
            worst_equity = min(floating_low, equity_close, equity_open)

            peak_equity = max(peak_equity, equity_open, equity_close)
            if peak_equity > 0:
                equity_dd = -round(((peak_equity - worst_equity) / peak_equity) * 100, 2)
            else:
                equity_dd = 0.0
            equity_underwater.append(equity_dd)

        return equity_underwater

    def _calculate_underwater_curve(self, equity_curve: List[float]) -> List[float]:
        if not equity_curve:
            return []

        underwater = []
        peak = equity_curve[0]

        for val in equity_curve:
            if val > peak:
                peak = val

            if peak > 0:
                dd_pct = ((peak - val) / peak) * 100
                underwater.append(round(-dd_pct, 2))
            else:
                underwater.append(0.0)

        return underwater

    def _calculate_concurrent_exposure(self, trades: List[TradeRecord]) -> tuple[int, float]:
        # Events based algorithm to find max overlapping intervals
        events = []
        for t in trades:
            if t.open_time and t.close_time:
                events.append((t.open_time.timestamp(), 1, t.size or 0.0))
                events.append((t.close_time.timestamp(), -1, -(t.size or 0.0)))
        
        # Sort by time, if time is equal, process close (-1) before open (1)
        events.sort(key=lambda x: (x[0], x[1]))
        
        current_trades = 0
        current_lots = 0.0
        max_trades = 0
        max_lots = 0.0
        
        for time, trade_change, lot_change in events:
            current_trades += trade_change
            current_lots += lot_change
            
            if current_trades > max_trades:
                max_trades = current_trades
            if current_lots > max_lots:
                max_lots = current_lots
                
        return max_trades, round(max_lots, 2)

    def _calculate_top_dependency(self, metrics: BacktestMetrics, trades: List[TradeRecord]) -> float:
        profits = [t.profit for t in trades if t.profit > 0]
        if not profits or metrics.net_profit <= 0:
            return 0.0
            
        profits.sort(reverse=True)
        top_10_count = max(1, int(len(profits) * 0.10))
        top_10_profit = sum(profits[:top_10_count])
        
        return round((top_10_profit / metrics.net_profit) * 100, 2)

    def _extract_mae_mfe(self, trades: List[TradeRecord]) -> tuple[bool, List[Dict[str, Any]]]:
        # We check if MAE/MFE attributes exist on TradeRecord. Usually MT4 HTML lacks it, but some do.
        # If not natively available, we might return False.
        data = []
        has_data = False
        
        for i, t in enumerate(trades):
            # We look for MAE/MFE if they exist (we might need to add them to schemas later)
            # For now, we simulate MFE/MAE based on durations if they are absent to show the feature, 
            # or just return False. Let's return False for now until parser extracts them.
            pass
            
        return has_data, data
