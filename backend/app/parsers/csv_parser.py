import io
import re
from datetime import datetime
from typing import List, Tuple, Optional

import pandas as pd

from ..models.schemas import BacktestMetrics, TradeRecord


class CSVParser:
    def parse(self, csv_content: bytes) -> Tuple[BacktestMetrics, List[TradeRecord]]:
        # Handle different CSV encodings
        try:
            content_str = csv_content.decode('utf-8')
        except:
            content_str = csv_content.decode('latin1')
            
        df = pd.read_csv(io.StringIO(content_str))
        
        # Clean column names
        df.columns = [self._clean_header(col) for col in df.columns]
        
        trades = []
        metrics = BacktestMetrics()
        
        # Mapping common CSV headers to our schema (including suffix versions)
        mapping = {
            'ticket': ['ticket', 'order', 'id', 'deal', 'position', 'trade_id', 'order_id', 'ticket_id', 'ticket_1', 'order_1'],
            'open_time': ['open_time', 'time_open', 'opentime', 'entry_time', 'time', 'date_time', 'open_date', 'entry_date', 'time_1', 'open_time_1'],
            'direction': ['direction', 'entry_exit', 'in_out'],
            'type': ['type', 'action', 'side', 'direction', 'trade_direction', 'buy_sell'],
            'size': ['size', 'lots', 'lot', 'lot_size', 'volume', 'vol', 'size_1', 'lots_1', 'volume_1'],
            'item': ['item', 'symbol', 'asset', 'symbol_1', 'item_1'],
            'price': ['price', 'open_price', 'price_open', 'entry_price', 'entry', 'open', 'price_1', 'open_price_1'],
            'profit': ['profit', 'net_profit', 'gain', 'p_l', 'pl', 'profit_loss', 'profit_lots', 'result', 'trade_result', 'net_p_l', 'gross_p_l', 'profit_1'],
            'close_time': ['close_time', 'time_close', 'closetime', 'exit_time', 'close_date', 'exit_date', 'time_1', 'close_time_1', 'exit_time_1', 'close'],
            'close_price': ['close_price', 'price_close', 'exit_price', 'exit', 'close_price_1', 'exit_price_1', 'price_1', 'close_1'],
            'swap': ['swap', 'rollover', 'swap_1'],
            'commission': ['commission', 'fee', 'comm', 'fees', 'commission_1'],
            's_l': ['s_l', 'sl', 'stop_loss', 'stoploss', 'stop', 's_l_1', 'sl_1', 'stop_loss_1'],
            't_p': ['t_p', 'tp', 'take_profit', 'takeprofit', 'target', 't_p_1', 'tp_1', 'take_profit_1'],
            'balance': ['balance', 'equity_at_exit', 'equity_exit', 'balance_1'],
            'comment': ['comment', 'strategy_tag', 'setup', 'comment_1'],
            'magic_number': ['magic_number', 'magic', 'magicnumber'],
            'spread_at_entry': ['spread_at_entry', 'spread', 'entry_spread'],
            'requested_price': ['requested_price', 'order_send_price', 'request_price'],
            'fill_price': ['fill_price', 'filled_price'],
            'slippage': ['slippage'],
            'news_time': ['news_time', 'event_time', 'calendar_time'],
            'news_event': ['news_event', 'event'],
            'news_impact': ['news_impact', 'impact'],
            'volatility_at_entry': ['volatility_at_entry', 'atr_at_entry', 'entry_volatility'],
            'entry_signal_strength': ['entry_signal_strength', 'signal_strength'],
            'market_regime': ['market_regime', 'regime'],
            'equity_at_entry': ['equity_at_entry', 'equity_entry'],
            'equity_at_exit': ['equity_at_exit', 'equity_exit'],
            'mfe': ['mfe', 'max_profit'],
            'mae': ['mae', 'max_drawdown_mae'],
            'entry_efficiency': ['entry_efficiency'],
            'exit_efficiency': ['exit_efficiency'],
            'trailing_stop_efficiency': ['trailing_stop_efficiency'],
            'rejected_orders': ['rejected_orders'],
            'order_modification_count': ['order_modification_count', 'modification_count'],
            'strategy_tag': ['strategy_tag', 'setup_type'],
            'partial_close_id': ['partial_close_id', 'parent_ticket'],
            'partial_close_fraction': ['partial_close_fraction', 'close_fraction']
        }

        # ──────────────────────────────────────────────────────────────────────
        # Value-Based Dynamic Disambiguation
        # Highly robust way to distinguish column roles when headers are ambiguous
        # ──────────────────────────────────────────────────────────────────────
        date_cols = []
        price_cols = []
        for col in df.columns:
            non_nulls = df[col].dropna().head(10).tolist()
            if not non_nulls:
                continue
            
            date_cnt = 0
            num_cnt = 0
            for val in non_nulls:
                val_str = str(val).strip()
                if self._parse_date(val_str) is not None:
                    date_cnt += 1
                try:
                    float(val_str.replace(",", ""))
                    num_cnt += 1
                except ValueError:
                    pass
            
            # If >60% match date formats, it's a date column
            if date_cnt >= len(non_nulls) * 0.6:
                date_cols.append(col)
            # If >80% match float formats, it's a numeric column
            elif num_cnt >= len(non_nulls) * 0.8:
                price_cols.append(col)

        # 1. If we have two distinct date columns, map first to open_time, second to close_time
        if len(date_cols) >= 2:
            mapping['open_time'] = [date_cols[0]] + mapping['open_time']
            mapping['close_time'] = [date_cols[1]] + mapping['close_time']
        elif len(date_cols) == 1:
            # If only one date column, treat it as open_time
            mapping['open_time'] = [date_cols[0]] + mapping['open_time']

        # 2. Filter price columns (exclude target SL/TP/profit/swap/commission/balance fields and ticket/size info)
        candidate_prices = [
            c for c in price_cols 
            if not any(x in c for x in ['sl', 's_l', 'tp', 't_p', 'profit', 'swap', 'commission', 'fee', 'balance', 'ticket', 'size', 'lot', 'volume', 'order', 'id', 'deal', 'position', 'magic'])
        ]
        if len(candidate_prices) >= 2:
            mapping['price'] = [candidate_prices[0]] + mapping['price']
            mapping['close_price'] = [candidate_prices[1]] + mapping['close_price']
        elif len(candidate_prices) == 1:
            mapping['price'] = [candidate_prices[0]] + mapping['price']

        # 3. Detect if Deal History (with separate entry/exit deals)
        direction_col = None
        for opt in mapping['direction']:
            if opt in df.columns:
                direction_col = opt
                break
        is_deal_history = False
        if direction_col:
            unique_dirs = set(df[direction_col].dropna().astype(str).str.strip().str.lower())
            if "in" in unique_dirs and ("out" in unique_dirs or "out by" in unique_dirs):
                is_deal_history = True

        if is_deal_history:
            open_deals = {}
            open_by_symbol = {}
            for _, row in df.iterrows():
                try:
                    if not self._row_has_trade_data(row, mapping):
                        continue
                    item_value = str(self._get_val(row, mapping['item'], '')).strip().lower()
                    type_value = str(self._get_val(row, mapping['type'], '')).strip().lower()
                    direction_value = str(self._get_val(row, mapping['direction'], '')).strip().lower()
                    if type_value in {"balance", "credit"}:
                        balance_value = self._float_or_none(self._get_val(row, mapping['balance'], None))
                        if balance_value is not None and not metrics.deposit:
                            metrics.deposit = balance_value
                        continue
                    if item_value in {"balance", "credit"}:
                        continue

                    if direction_value == "in":
                        symbol = str(self._get_val(row, mapping['item'], 'Unknown')).strip().upper()
                        ticket_key = self._get_val(row, ['position', 'position_id', 'order', 'deal', 'ticket'], None)
                        row_dict = row.to_dict()
                        if ticket_key:
                            open_deals[str(ticket_key)] = row_dict
                        open_by_symbol.setdefault(symbol, []).append(row_dict)
                        continue

                    # Process Exit (direction == "out")
                    opening_row = None
                    ticket_key = self._get_val(row, ['position', 'position_id', 'order', 'deal', 'ticket'], None)
                    if ticket_key and str(ticket_key) in open_deals:
                        opening_row = open_deals.pop(str(ticket_key))
                        symbol = str(self._get_val(row, mapping['item'], 'Unknown')).strip().upper()
                        if symbol in open_by_symbol and opening_row in open_by_symbol[symbol]:
                            open_by_symbol[symbol].remove(opening_row)
                    else:
                        symbol = str(self._get_val(row, mapping['item'], 'Unknown')).strip().upper()
                        candidates = open_by_symbol.get(symbol, [])
                        if candidates:
                            closing_type = str(self._get_val(row, mapping['type'], '')).strip().lower()
                            opposite = "sell" if "buy" in closing_type else "buy"
                            found_idx = 0
                            for idx, candidate in enumerate(candidates):
                                candidate_type = str(self._get_val(candidate, mapping['type'], '')).strip().lower()
                                if opposite in candidate_type:
                                    found_idx = idx
                                    break
                            opening_row = candidates.pop(found_idx)
                            op_key = self._get_val(opening_row, ['position', 'position_id', 'order', 'deal', 'ticket'], None)
                            if op_key and str(op_key) in open_deals:
                                open_deals.pop(str(op_key))

                    if opening_row is not None:
                        parsed_sl = self._float_or_none(self._get_val(row, mapping['s_l'], None)) or self._float_or_none(self._get_val(opening_row, mapping['s_l'], None))
                        parsed_tp = self._float_or_none(self._get_val(row, mapping['t_p'], None)) or self._float_or_none(self._get_val(opening_row, mapping['t_p'], None))
                        if parsed_sl == 0.0:
                            parsed_sl = None
                        if parsed_tp == 0.0:
                            parsed_tp = None

                        trade = TradeRecord(
                            type=self._get_val(opening_row, mapping['type'], 'buy'),
                            size=float(self._get_val(row, mapping['size'], 0.01)),
                            item=self._get_val(row, mapping['item'], 'Unknown'),
                            price=float(self._get_val(opening_row, mapping['price'], 0)),
                            profit=self._float_or_zero(self._get_val(row, mapping['profit'], 0)),
                            ticket=str(self._get_val(row, mapping['ticket'], '')),
                            close_price=self._float_or_none(self._get_val(row, mapping['price'], None)),
                            s_l=parsed_sl,
                            t_p=parsed_tp,
                            swap=self._float_or_zero(self._get_val(row, mapping['swap'], 0)),
                            commission=self._float_or_zero(self._get_val(row, mapping['commission'], 0)),
                            balance=self._float_or_none(self._get_val(row, mapping['balance'], None)),
                            comment=self._str_or_none(self._get_val(row, mapping['comment'], None)) or self._str_or_none(self._get_val(opening_row, mapping['comment'], None)),
                            magic_number=self._str_or_none(self._get_val(row, mapping['magic_number'], None)) or self._str_or_none(self._get_val(opening_row, mapping['magic_number'], None)),
                        )

                        open_time_str = self._get_val(opening_row, mapping['open_time'], None)
                        if open_time_str:
                            trade.open_time = self._parse_date(str(open_time_str))

                        close_time_str = self._get_val(row, mapping['open_time'], None)
                        if close_time_str:
                            trade.close_time = self._parse_date(str(close_time_str))

                        if trade.open_time and trade.close_time:
                            trade.duration_minutes = (trade.close_time - trade.open_time).total_seconds() / 60

                        # Smart Comment Fallback
                        if trade.comment:
                            comment_lower = trade.comment.lower()
                            if not trade.t_p:
                                tp_match = re.search(r'\btp\s*[:=]?\s*([\d.]+)', comment_lower)
                                if tp_match:
                                    try:
                                        trade.t_p = float(tp_match.group(1))
                                    except ValueError:
                                        pass
                            if not trade.s_l:
                                sl_match = re.search(r'\bsl\s*[:=]?\s*([\d.]+)', comment_lower)
                                if sl_match:
                                    try:
                                        trade.s_l = float(sl_match.group(1))
                                    except ValueError:
                                        pass

                        if trade.close_price is None and trade.t_p and abs(trade.profit) > 0:
                            trade.close_price = trade.t_p

                        trades.append(trade)
                except Exception:
                    continue
        else:
            for _, row in df.iterrows():
                try:
                    if not self._row_has_trade_data(row, mapping):
                        continue

                    item_value = str(self._get_val(row, mapping['item'], '')).strip().lower()
                    type_value = str(self._get_val(row, mapping['type'], '')).strip().lower()
                    direction_value = str(self._get_val(row, mapping['direction'], '')).strip().lower()
                    if type_value in {"balance", "credit"}:
                        balance_value = self._float_or_none(self._get_val(row, mapping['balance'], None))
                        if balance_value is not None and not metrics.deposit:
                            metrics.deposit = balance_value
                        continue
                    if item_value in {"balance", "credit"}:
                        continue
                    if direction_value == "in":
                        continue
                    if not item_value and direction_value not in {"out", ""}:
                        continue
                    if not item_value and self._float_or_none(self._get_val(row, mapping['profit'], None)) is not None:
                        continue

                    # Parse stop loss and take profit safely
                    parsed_sl = self._float_or_none(self._get_val(row, mapping['s_l'], None))
                    parsed_tp = self._float_or_none(self._get_val(row, mapping['t_p'], None))
                    # Avoid capturing 0 or 0.0 as real SL/TP bounds
                    if parsed_sl == 0.0:
                        parsed_sl = None
                    if parsed_tp == 0.0:
                        parsed_tp = None

                    trade = TradeRecord(
                        type=self._get_val(row, mapping['type'], 'buy'),
                        size=float(self._get_val(row, mapping['size'], 0.01)),
                        item=self._get_val(row, mapping['item'], 'Unknown'),
                        price=float(self._get_val(row, mapping['price'], 0)),
                        profit=self._float_or_zero(self._get_val(row, mapping['profit'], 0)),
                        ticket=str(self._get_val(row, mapping['ticket'], '')),
                        close_price=self._float_or_none(self._get_val(row, mapping['close_price'], None)),
                        s_l=parsed_sl,
                        t_p=parsed_tp,
                        swap=self._float_or_zero(self._get_val(row, mapping['swap'], 0)),
                        commission=self._float_or_zero(self._get_val(row, mapping['commission'], 0)),
                        balance=self._float_or_none(self._get_val(row, mapping['balance'], None)),
                        comment=self._str_or_none(self._get_val(row, mapping['comment'], None)),
                        magic_number=self._str_or_none(self._get_val(row, mapping['magic_number'], None)),
                        spread_at_entry=self._float_or_none(self._get_val(row, mapping['spread_at_entry'], None)),
                        requested_price=self._float_or_none(self._get_val(row, mapping['requested_price'], None)),
                        fill_price=self._float_or_none(self._get_val(row, mapping['fill_price'], None)),
                        slippage=self._float_or_none(self._get_val(row, mapping['slippage'], None)),
                        news_event=self._str_or_none(self._get_val(row, mapping['news_event'], None)),
                        news_impact=self._str_or_none(self._get_val(row, mapping['news_impact'], None)),
                        volatility_at_entry=self._float_or_none(self._get_val(row, mapping['volatility_at_entry'], None)),
                        entry_signal_strength=self._float_or_none(self._get_val(row, mapping['entry_signal_strength'], None)),
                        market_regime=self._str_or_none(self._get_val(row, mapping['market_regime'], None)),
                        equity_at_entry=self._float_or_none(self._get_val(row, mapping['equity_at_entry'], None)),
                        equity_at_exit=self._float_or_none(self._get_val(row, mapping['equity_at_exit'], None)),
                        mfe=self._float_or_none(self._get_val(row, mapping['mfe'], None)),
                        mae=self._float_or_none(self._get_val(row, mapping['mae'], None)),
                        entry_efficiency=self._float_or_none(self._get_val(row, mapping['entry_efficiency'], None)),
                        exit_efficiency=self._float_or_none(self._get_val(row, mapping['exit_efficiency'], None)),
                        trailing_stop_efficiency=self._float_or_none(self._get_val(row, mapping['trailing_stop_efficiency'], None)),
                        rejected_orders=self._int_or_none(self._get_val(row, mapping['rejected_orders'], None)),
                        order_modification_count=self._int_or_none(self._get_val(row, mapping['order_modification_count'], None)),
                        strategy_tag=self._str_or_none(self._get_val(row, mapping['strategy_tag'], None)),
                        partial_close_id=self._str_or_none(self._get_val(row, mapping['partial_close_id'], None)),
                        partial_close_fraction=self._float_or_none(self._get_val(row, mapping['partial_close_fraction'], None)),
                    )

                    # Parse times
                    open_time_str = self._get_val(row, mapping['open_time'], None)
                    if open_time_str:
                        trade.open_time = self._parse_date(str(open_time_str))

                    close_time_str = self._get_val(row, mapping['close_time'], None)
                    if close_time_str:
                        trade.close_time = self._parse_date(str(close_time_str))
                    news_time_str = self._get_val(row, mapping['news_time'], None)
                    if news_time_str:
                        trade.news_time = self._parse_date(str(news_time_str))

                    if trade.open_time and trade.close_time:
                        trade.duration_minutes = (trade.close_time - trade.open_time).total_seconds() / 60

                    # ──────────────────────────────────────────────────────────────
                    # Smart Comment Extraction Fallback
                    # If SL or TP column is missing/zero, search inside comment
                    # ──────────────────────────────────────────────────────────────
                    if trade.comment:
                        comment_lower = trade.comment.lower()
                        if not trade.t_p:
                            tp_match = re.search(r'\btp\s*[:=]?\s*([\d.]+)', comment_lower)
                            if tp_match:
                                try:
                                    trade.t_p = float(tp_match.group(1))
                                except ValueError:
                                    pass
                        if not trade.s_l:
                            sl_match = re.search(r'\bsl\s*[:=]?\s*([\d.]+)', comment_lower)
                            if sl_match:
                                try:
                                    trade.s_l = float(sl_match.group(1))
                                except ValueError:
                                    pass

                    # If close_price is missing, try to reconstruct it from TP comment
                    if trade.close_price is None and trade.t_p and abs(trade.profit) > 0:
                        # If comment contains tp and profit is positive, trade likely exited exactly at tp
                        trade.close_price = trade.t_p

                    trades.append(trade)
                except Exception:
                    continue
                
        # Calculate basic metrics from trades
        if trades:
            metrics.total_trades = len(trades)
            metrics.net_profit = sum(t.profit for t in trades)
            metrics.symbol = self._most_common([t.item for t in trades if t.item and t.item != "Unknown"])
            first_equity_entry = next((t.equity_at_entry for t in trades if t.equity_at_entry is not None), None)
            first_balance_trade = next((t for t in trades if t.balance is not None), None)
            if metrics.deposit:
                pass
            elif first_equity_entry is not None:
                metrics.deposit = first_equity_entry
            elif first_balance_trade:
                metrics.deposit = first_balance_trade.balance - first_balance_trade.profit
            profits = [t.profit for t in trades if t.profit > 0]
            losses = [abs(t.profit) for t in trades if t.profit < 0]
            durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
            
            metrics.gross_profit = sum(profits)
            metrics.gross_loss = sum(losses)
            if metrics.gross_loss > 0:
                metrics.profit_factor = round(metrics.gross_profit / metrics.gross_loss, 2)
            
            metrics.expected_payoff = round(metrics.net_profit / len(trades), 2)
            metrics.win_rate = round((len(profits) / len(trades)) * 100, 2) if trades else 0
            metrics.average_profit = round(sum(profits) / len(profits), 2) if profits else 0.0
            metrics.average_loss = round(sum(losses) / len(losses), 2) if losses else 0.0
            if metrics.average_loss > 0:
                metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)
            if durations:
                metrics.average_trade_duration = round(sum(durations) / len(durations), 2)
            self._apply_drawdown_and_streaks(metrics, trades)
            
        return metrics, trades

    def _get_val(self, row, options, default):
        for opt in options:
            if opt in row:
                value = row[opt]
                try:
                    if pd.isna(value):
                        continue
                except Exception:
                    pass
                if value == "":
                    continue
                return value
        return default

    def _clean_header(self, value) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"\([^)]*\)", "", text)
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_")

    def _row_has_trade_data(self, row, mapping) -> bool:
        meaningful = 0
        for key in ("profit", "price", "close_price", "open_time", "close_time", "item", "ticket"):
            value = self._get_val(row, mapping[key], None)
            if value not in (None, ""):
                meaningful += 1
        return meaningful >= 2 or self._get_val(row, mapping["profit"], None) not in (None, "")

    def _float_or_zero(self, value) -> float:
        parsed = self._float_or_none(value)
        return parsed if parsed is not None else 0.0

    def _float_or_none(self, value) -> Optional[float]:
        try:
            if value is None or pd.isna(value) or value == "":
                return None
            return float(str(value).replace(",", ""))
        except Exception:
            return None

    def _int_or_none(self, value) -> Optional[int]:
        parsed = self._float_or_none(value)
        return int(parsed) if parsed is not None else None

    def _str_or_none(self, value) -> Optional[str]:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        text = str(value).strip()
        return text or None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        cleaned_str = date_str.strip()
        if re.match(r'^\d+(\.\d+)?$', cleaned_str):
            return None
        formats = [
            '%Y.%m.%d %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%d.%m.%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y %H:%M',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        try:
            parsed = pd.to_datetime(date_str, errors="coerce")
            if pd.notna(parsed):
                return parsed.to_pydatetime()
        except Exception:
            pass
        return None

    def _apply_drawdown_and_streaks(self, metrics: BacktestMetrics, trades: List[TradeRecord]):
        equity = metrics.deposit or 0.0
        peak = equity
        max_dd = 0.0
        wins = losses = max_wins = max_losses = 0
        for trade in trades:
            if trade.equity_at_exit is not None:
                equity = trade.equity_at_exit
            elif trade.balance is not None:
                equity = trade.balance
            else:
                equity += trade.profit
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
            if trade.profit > 0:
                wins += 1
                losses = 0
            elif trade.profit < 0:
                losses += 1
                wins = 0
            max_wins = max(max_wins, wins)
            max_losses = max(max_losses, losses)
        metrics.maximal_drawdown = round(max_dd, 2)
        metrics.maximal_drawdown_pct = round((max_dd / metrics.deposit) * 100, 2) if max_dd and metrics.deposit else 0.0
        metrics.consecutive_wins_max = max_wins
        metrics.consecutive_losses_max = max_losses

    def _most_common(self, values: List[str]) -> Optional[str]:
        if not values:
            return None
        return max(set(values), key=values.count)
