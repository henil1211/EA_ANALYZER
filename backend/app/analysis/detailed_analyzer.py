import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import BacktestMetrics, BehaviorAnalysis, DetailedAnalysisResult, DetailedMetric, TradeRecord


class DetailedAnalyzer:
    """Builds a transparent metric inventory from uploaded MT4/MT5 report data."""

    def analyze(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
        equity_curve: List[float],
    ) -> DetailedAnalysisResult:
        profits = [trade.profit for trade in trades]
        wins = [profit for profit in profits if profit > 0]
        losses = [abs(profit) for profit in profits if profit < 0]
        total_trades = metrics.total_trades or len(trades)
        deposit = metrics.deposit or (equity_curve[0] if equity_curve else 0.0)
        net_profit = metrics.net_profit or sum(profits)
        gross_profit = metrics.gross_profit or sum(wins)
        gross_loss = abs(metrics.gross_loss) or sum(losses)
        profit_factor = metrics.profit_factor or (gross_profit / gross_loss if gross_loss else 0.0)
        average_win = metrics.average_profit or (sum(wins) / len(wins) if wins else 0.0)
        average_loss = metrics.average_loss or (sum(losses) / len(losses) if losses else 0.0)
        expectancy = metrics.expected_payoff or (sum(profits) / total_trades if total_trades else 0.0)
        max_dd_money = metrics.maximal_drawdown or self._max_drawdown(equity_curve)
        max_dd_pct = metrics.maximal_drawdown_pct or self._pct(max_dd_money, deposit)
        sharpe = metrics.sharpe_ratio or self._sharpe(profits)
        sortino = self._sortino(profits)
        omega = self._omega(profits)
        ulcer = self._ulcer_index(equity_curve)
        calmar = self._calmar(net_profit, deposit, max_dd_pct, trades)
        recovery_factor = metrics.recovery_factor or (net_profit / max_dd_money if max_dd_money else 0.0)
        tail_ratio = average_loss / average_win if average_win else 0.0
        gain_to_pain = gross_profit / sum(abs(min(0, p)) for p in profits) if losses else 0.0
        breakeven_count = len([profit for profit in profits if abs(profit) < 0.01])
        turnover = sum(abs(trade.size) for trade in trades)
        round_turn_cost = sum(abs(trade.commission) + abs(trade.swap) + abs(trade.taxes) for trade in trades)
        cost_efficiency = round_turn_cost / gross_profit * 100 if gross_profit else 0.0
        underwater = self._underwater_periods(equity_curve)
        intervals = self._trade_intervals(trades)
        hold_stats = self._hold_time_by_result(trades)
        session_stats = self._bucket_stats(trades, lambda trade: self._session(trade.open_time or trade.close_time))
        day_stats = self._bucket_stats(trades, lambda trade: (trade.open_time or trade.close_time).strftime("%A") if (trade.open_time or trade.close_time) else "Unknown")
        strategy_stats = self._bucket_stats(trades, lambda trade: self._strategy_tag(trade))
        risk_of_ruin = self._risk_of_ruin(metrics, profit_factor, max_dd_pct, trades, behavior)
        equity_r2 = self._equity_r_squared(equity_curve)
        long_short = self._direction_stats(trades)

        # ── Drawdowns Calculation ──
        # 1. Max Equity Drawdown
        max_equity_dd = max_dd_money
        max_equity_dd_pct = max_dd_pct

        # 2. Max Balance Drawdown
        balance_curve = [deposit]
        for t in trades:
            if t.balance is not None:
                balance_curve.append(t.balance)
            else:
                balance_curve.append(balance_curve[-1] + t.profit)
        max_bal_dd = 0.0
        peak_bal = balance_curve[0]
        for value in balance_curve:
            peak_bal = max(peak_bal, value)
            max_bal_dd = max(max_bal_dd, peak_bal - value)
        max_bal_dd_pct = self._pct(max_bal_dd, deposit)

        # 3. Max & Average Floating Drawdown
        max_floating_dd = 0.0
        peak_equity = deposit
        mae_values = []
        for index, trade in enumerate(trades):
            equity_entry = equity_curve[index] if index < len(equity_curve) else deposit
            peak_equity = max(peak_equity, equity_entry)
            
            mae_val = 0.0
            if trade.mae is not None:
                mae_val = abs(trade.mae)
            elif trade.s_l is not None and trade.price is not None and trade.size is not None:
                mae_val = abs(trade.price - trade.s_l) * trade.size
            
            mae_values.append(mae_val)
            lowest_floating_equity = equity_entry - mae_val
            max_floating_dd = max(max_floating_dd, peak_equity - lowest_floating_equity)
        
        avg_floating_dd = sum(mae_values) / len(mae_values) if mae_values else 0.0
        avg_floating_dd_pct = self._pct(avg_floating_dd, deposit)

        available_count = 0
        derived_count = 0

        def metric(key: str, label: str, value: Any, status: str = "available", description: Optional[str] = None) -> DetailedMetric:
            nonlocal available_count, derived_count
            if status == "available":
                available_count += 1
            if status == "derived":
                derived_count += 1
            return DetailedMetric(key=key, label=label, value=value, status=status, description=description)

        summary_cards = [
            metric("trade_rows", "Trade Rows Parsed", total_trades, "available", "Closed trades parsed from the uploaded report."),
            metric("coverage", "Report Coverage", f"{self._months_covered(trades):.1f} months", "derived", "Calendar span based on first and last trade timestamps."),
            metric("net_profit", "Net Profit", self._money(net_profit), "available", "Total net profit reported or reconstructed from trades."),
            metric("risk_of_ruin", "Risk of Ruin", f"{risk_of_ruin}%", "derived", "Approximate capital failure risk from drawdown, PF, and recovery behavior."),
            metric("expectancy", "Expectancy", self._money(expectancy), "derived", "Average expected profit per trade."),
            metric("profit_factor", "Profit Factor", self._ratio(profit_factor), "available", "Gross profit divided by gross loss."),
        ]

        # ── Pre-compute aggregate summaries for "per trade" fields ──
        entry_prices = [t.price for t in trades if t.price]
        exit_prices = [t.close_price for t in trades if t.close_price is not None]
        open_times = sorted(t.open_time for t in trades if t.open_time)
        close_times = sorted(t.close_time for t in trades if t.close_time)
        sl_trades = [t for t in trades if t.s_l is not None]
        tp_trades = [t for t in trades if t.t_p is not None]
        r_values = [t.profit / self._risk_amount(t) for t in trades if self._risk_amount(t)]
        comments = [t.comment for t in trades if t.comment]
        day_of_month_vals = [(t.open_time or t.close_time).day for t in trades if (t.open_time or t.close_time)]

        entry_price_text = f"avg {sum(entry_prices)/len(entry_prices):.5f}, min {min(entry_prices):.5f}, max {max(entry_prices):.5f}" if entry_prices else "N/A"
        exit_price_text = f"avg {sum(exit_prices)/len(exit_prices):.5f}, min {min(exit_prices):.5f}, max {max(exit_prices):.5f}" if exit_prices else "N/A"
        open_time_text = f"{open_times[0].strftime('%Y.%m.%d')} → {open_times[-1].strftime('%Y.%m.%d')}" if open_times else "N/A"
        close_time_text = f"{close_times[0].strftime('%Y.%m.%d')} → {close_times[-1].strftime('%Y.%m.%d')}" if close_times else "N/A"
        profit_loss_text = f"total {self._money(net_profit)}, avg {self._money(net_profit / total_trades if total_trades else 0)}"
        comment_text = f"{len(comments)} tagged" + (f" — {', '.join(sorted(set(comments))[:3])}" if comments else "") if comments else "No comments in report"
        dom_text = f"min day {min(day_of_month_vals)}, max day {max(day_of_month_vals)}" if day_of_month_vals else "N/A"
        tod_text = f"{open_times[0].strftime('%H:%M')} earliest, {max(open_times, key=lambda d: d.hour * 60 + d.minute).strftime('%H:%M')} latest" if open_times else "N/A"

        # MAE/MFE: use actual data if present, else estimate from SL/TP
        mae_text = self._numeric_summary(trades, "mae")
        if not mae_text and sl_trades:
            mae_vals = [abs(t.price - t.s_l) * t.size for t in sl_trades if t.price and t.size]
            if mae_vals:
                mae_text = f"SL-based: avg {sum(mae_vals)/len(mae_vals):.2f}, max {max(mae_vals):.2f} ({len(sl_trades)} trades with SL)"
        mfe_text = self._numeric_summary(trades, "mfe")
        if not mfe_text and tp_trades:
            mfe_vals = [abs(t.t_p - t.price) * t.size for t in tp_trades if t.price and t.size]
            if mfe_vals:
                mfe_text = f"TP-based: avg {sum(mfe_vals)/len(mfe_vals):.2f}, max {max(mfe_vals):.2f} ({len(tp_trades)} trades with TP)"

        r_multiple_text = f"avg {sum(r_values)/len(r_values):.2f}R, best {max(r_values):.2f}R, worst {min(r_values):.2f}R ({len(r_values)} trades)" if r_values else "No SL data for R calc"
        ticket_text = f"{total_trades} unique trades" + (f" (#{trades[0].ticket} → #{trades[-1].ticket})" if trades and trades[0].ticket and trades[-1].ticket else "")

        metric_groups: Dict[str, List[DetailedMetric]] = {
            "Core Trade Fields": [
                metric("ticket", "Ticket", ticket_text, "available", "MT ticket/order id parsed from report."),
                metric("symbol", "Symbol", metrics.symbol or self._first_item(trades), "available"),
                metric("magic_number", "Magic Number", self._field_summary(trades, "magic_number") or "Not in report", "available" if self._has_field(trades, "magic_number") else "unavailable", "Standard MT HTML history usually does not include magic number; XLSX/CSV logs can provide it."),
                metric("lot_size", "Lot Size", f"avg {behavior.avg_lot:g}, range {behavior.min_lot:g} – {behavior.max_lot:g}, σ {behavior.lot_std_dev:g}" if behavior.max_lot else "N/A", "available"),
                metric("trade_direction", "Type / Trade Direction", long_short["summary"], "available"),
                metric("entry_price", "Entry Price", entry_price_text, "available", "Aggregate of entry prices across all trades."),
                metric("exit_price", "Exit Price", exit_price_text, "available", "Aggregate of exit prices across all trades."),
                metric("open_time", "Open Time", open_time_text, "available", "Date range of trade entries."),
                metric("close_time", "Close Time", close_time_text, "available", "Date range of trade exits."),
                metric("profit_loss", "Profit / Loss", profit_loss_text, "available", f"{len(wins)} wins, {len(losses)} losses."),
                metric("comment", "Comment / Strategy Tag", comment_text, "available" if comments else "derived"),
            ],
            "Risk & Drawdown": [
                metric("balance_drawdown_absolute", "Balance Drawdown Absolute", metrics.balance_drawdown_absolute or self._money(max_bal_dd), "available" if metrics.balance_drawdown_absolute is not None else "derived", "Maximum absolute balance drawdown in account currency."),
                metric("balance_drawdown_maximal", "Balance Drawdown Maximal", metrics.balance_drawdown_maximal or self._drawdown(max_bal_dd, max_bal_dd_pct), "available" if metrics.balance_drawdown_maximal is not None else "derived", "Maximum peak-to-trough decline in closed balance."),
                metric("balance_drawdown_relative", "Balance Drawdown Relative", metrics.balance_drawdown_relative or f"{max_bal_dd_pct:.2f}% ({self._money(max_bal_dd)})", "available" if metrics.balance_drawdown_relative is not None else "derived", "Maximum relative decline in closed balance."),
                metric("equity_drawdown_absolute", "Equity Drawdown Absolute", metrics.equity_drawdown_absolute or self._money(max_equity_dd), "available" if metrics.equity_drawdown_absolute is not None else "derived", "Maximum absolute equity drawdown in account currency."),
                metric("equity_drawdown_maximal", "Equity Drawdown Maximal", metrics.equity_drawdown_maximal or self._drawdown(max_equity_dd, max_equity_dd_pct), "available" if metrics.equity_drawdown_maximal is not None else "derived", "Maximum peak-to-trough decline in account equity."),
                metric("equity_drawdown_relative", "Equity Drawdown Relative", metrics.equity_drawdown_relative or f"{max_equity_dd_pct:.2f}% ({self._money(max_equity_dd)})", "available" if metrics.equity_drawdown_relative is not None else "derived", "Maximum relative decline in account equity."),
                metric("ulcer_index", "Ulcer Index", self._ratio(ulcer), "derived"),
                metric("underwater_period", "Underwater Period", f"{underwater['longest']} trades longest", "derived"),
                metric("average_drawdown_duration", "Average Drawdown Duration", f"{underwater['average']:.1f} trades", "derived"),
                metric("tail_ratio", "Tail Ratio", self._ratio(tail_ratio), "derived", "Average loss divided by average win."),
                metric("risk_of_ruin", "Risk of Ruin", f"{risk_of_ruin}%", "derived"),
            ],
            "Performance Ratios": [
                metric("average_win", "Average Win", self._money(average_win), "derived"),
                metric("average_loss", "Average Loss", self._money(-average_loss), "derived"),
                metric("sharpe_ratio", "Sharpe Ratio", self._ratio(sharpe), "available" if metrics.sharpe_ratio else "derived"),
                metric("sortino_ratio", "Sortino Ratio", self._ratio(sortino), "derived"),
                metric("omega_ratio", "Omega Ratio", self._ratio(omega), "derived"),
                metric("calmar_ratio", "Calmar Ratio", self._ratio(calmar), "derived"),
                metric("recovery_factor", "Recovery Factor", self._ratio(recovery_factor), "available" if metrics.recovery_factor else "derived"),
                metric("gain_to_pain", "Gain-to-Pain Ratio", self._ratio(gain_to_pain), "derived"),
                metric("kelly_fraction", "Kelly Fraction", f"{self._kelly(metrics, average_win, average_loss):.2f}%", "derived"),
                metric("expectancy", "Expectancy", self._money(expectancy), "derived"),
            ],
            "Timing & Sessions": [
                metric("duration", "Duration", f"{metrics.average_trade_duration:.1f} min avg" if metrics.average_trade_duration else hold_stats["average"], "available" if metrics.average_trade_duration else "derived"),
                metric("day_of_week", "Day of Week", self._best_worst(day_stats), "derived"),
                metric("day_of_month", "Day of Month", dom_text, "derived"),
                metric("session", "Session / Time Classification", self._best_worst(session_stats), "derived"),
                metric("time_of_day", "Time of Day", tod_text, "available" if open_times else "unavailable"),
                metric("trade_interval", "Trade Interval", intervals, "derived"),
                metric("average_hold_profit_loss", "Average Hold Time Per Profit/Loss", f"wins {hold_stats['wins']}, losses {hold_stats['losses']}", "derived"),
                metric("consecutive_wins_losses", "Consecutive Wins / Losses", f"{metrics.consecutive_wins_max or self._streak(trades, True)} wins / {metrics.consecutive_losses_max or self._streak(trades, False)} losses", "available" if metrics.consecutive_wins_max or metrics.consecutive_losses_max else "derived"),
                metric("maximum_losing_period_days", "Maximum Losing Period (Days)", f"{self._max_losing_period_days(trades):.1f} days", "derived"),
            ],
            "Costs & Execution": [
                metric("commission", "Commission", self._money(sum(trade.commission for trade in trades)), "available"),
                metric("swap", "Swap", self._money(sum(trade.swap for trade in trades)), "available"),
                metric("turnover", "Turnover", f"{turnover:.2f} lots", "derived", "Sum of traded lots from parsed rows."),
                metric("round_turn_cost_efficiency", "Round-Turn Cost Efficiency", f"{cost_efficiency:.2f}%", "derived"),
                metric("spread_at_entry", "Spread at Entry", self._numeric_summary(trades, "spread_at_entry") or "Not in report", "available" if self._has_field(trades, "spread_at_entry") else "unavailable", "Needs tick data or broker execution log."),
                metric("slippage_distribution", "Slippage Distribution", self._numeric_summary(trades, "slippage") or "Not in report", "available" if self._has_field(trades, "slippage") else "unavailable"),
                metric("fill_quality", "Fill Quality", self._fill_quality(trades) or "Not in report", "derived" if self._has_field(trades, "requested_price") and self._has_field(trades, "fill_price") else "unavailable"),
                metric("rejected_orders", "Rejected Orders", self._numeric_total(trades, "rejected_orders") if self._has_field(trades, "rejected_orders") else "Not in report", "available" if self._has_field(trades, "rejected_orders") else "unavailable"),
                metric("order_modification_count", "Order Modification Count", self._numeric_total(trades, "order_modification_count") if self._has_field(trades, "order_modification_count") else "Not in report", "available" if self._has_field(trades, "order_modification_count") else "unavailable"),
            ],
            "Advanced Trade Quality": [
                metric("mfe", "Max Favorable Excursion (MFE)", mfe_text or "No TP/tick data", "available" if self._has_field(trades, "mfe") else ("derived" if mfe_text else "unavailable"), "Estimated from take-profit distance when tick data is unavailable."),
                metric("entry_efficiency", "Entry Efficiency", self._numeric_summary(trades, "entry_efficiency") or "Not in report", "available" if self._has_field(trades, "entry_efficiency") else "unavailable"),
                metric("exit_efficiency", "Exit Efficiency", self._numeric_summary(trades, "exit_efficiency") or "Not in report", "available" if self._has_field(trades, "exit_efficiency") else "unavailable"),
                metric("trailing_stop_efficiency", "Trailing Stop Efficiency", self._numeric_summary(trades, "trailing_stop_efficiency") or "Not in report", "available" if self._has_field(trades, "trailing_stop_efficiency") else "unavailable"),
                metric("partial_closes", "Partial Closes Tracking", self._partial_close_note(trades), "derived", "MT4 split tickets are grouped heuristically by symbol/time/comment."),
                metric("partial_close_efficiency", "Partial Close Efficiency", self._numeric_summary(trades, "partial_close_fraction") or "Not in report", "derived" if self._has_field(trades, "partial_close_fraction") else "unavailable"),
                metric("breakeven_trades", "Breakeven Trades", f"{breakeven_count} trades ({breakeven_count/total_trades*100:.1f}%)" if total_trades else "0", "derived"),
                metric("r_multiple", "Risk (R) / R-Multiple", r_multiple_text, "derived" if r_values else "unavailable"),
            ],
            "Market & Portfolio Context": [
                metric("market_regime", "Market Regime", self._field_summary(trades, "market_regime") or self._infer_regime_summary(metrics), "available" if self._has_field(trades, "market_regime") else "derived"),
                metric("volatility_at_entry", "Volatility at Entry", self._numeric_summary(trades, "volatility_at_entry") or "Not in report", "available" if self._has_field(trades, "volatility_at_entry") else "unavailable"),
                metric("news_proximity", "News Proximity", self._news_summary(trades) or "Not in report", "available" if self._has_field(trades, "news_time") or self._has_field(trades, "news_event") else "unavailable"),
                metric("beta", "Beta to Major Index", "Not in report", "unavailable"),
                metric("alpha", "Alpha", "Not in report", "unavailable"),
                metric("pairwise_trade_correlation", "Pairwise Trade Correlation", self._trade_autocorrelation(profits), "derived"),
                metric("equity_curve_r_squared", "Equity Curve R-Squared", self._ratio(equity_r2), "derived"),
                metric("win_rate_by_setup", "Win Rate by Setup", self._setup_win_rates(strategy_stats), "derived"),
                metric("scalps_vs_swings", "Auto-Detect Scalps vs Swings", "Scalping" if behavior.is_scalping else "Swing/Intraday", "derived"),
            ],
        }

        unavailable_metrics = [
            item
            for group in metric_groups.values()
            for item in group
            if item.status == "unavailable"
        ]

        trade_rows = self._trade_rows(trades, metrics, equity_curve)
        summary = (
            f"Detailed Analysis mapped {total_trades} trades and {available_count + derived_count} available/derived fields. "
            f"{len(unavailable_metrics)} requested fields need tick data, news calendar data, or broker/order logs and are marked clearly."
        )

        return DetailedAnalysisResult(
            summary=summary,
            summary_cards=summary_cards,
            metric_groups=metric_groups,
            trade_rows=trade_rows,
            total_trade_rows=total_trades,
            unavailable_metrics=unavailable_metrics,
        )

    def _trade_rows(self, trades: List[TradeRecord], metrics: BacktestMetrics, equity_curve: List[float]) -> List[Dict[str, Any]]:
        rows = []
        previous_close: Optional[datetime] = None
        for index, trade in enumerate(trades):
            equity_entry = equity_curve[index] if index < len(equity_curve) else None
            equity_exit = equity_curve[index + 1] if index + 1 < len(equity_curve) else trade.balance
            risk = self._risk_amount(trade)
            dt = trade.open_time or trade.close_time
            interval = (trade.open_time - previous_close).total_seconds() / 60 if previous_close and trade.open_time else None
            previous_close = trade.close_time or previous_close
            rows.append(
                {
                    "ticket": trade.ticket,
                    "symbol": trade.item or metrics.symbol,
                    "magic_number": trade.magic_number,
                    "lot_size": trade.size,
                    "type": trade.type,
                    "spread_at_entry": trade.spread_at_entry,
                    "entry_price": trade.price,
                    "exit_price": trade.close_price,
                    "open_time": trade.open_time.isoformat(sep=" ") if trade.open_time else None,
                    "close_time": trade.close_time.isoformat(sep=" ") if trade.close_time else None,
                    "profit_loss": round(trade.profit, 2),
                    "stop_loss": trade.s_l,
                    "take_profit": trade.t_p,
                    "swap": trade.swap,
                    "commission": trade.commission,
                    "comment": trade.comment,
                    "duration": f"{trade.duration_minutes:.1f} min" if trade.duration_minutes is not None else None,
                    "day_of_week": dt.strftime("%A") if dt else None,
                    "day_of_month": dt.day if dt else None,
                    "session": self._session(dt),
                    "equity_at_entry": round(trade.equity_at_entry or equity_entry, 2) if (trade.equity_at_entry is not None or equity_entry is not None) else None,
                    "equity_at_exit": round(trade.equity_at_exit or equity_exit, 2) if (trade.equity_at_exit is not None or equity_exit is not None) else None,
                    "risk_r": round(risk, 5) if risk else None,
                    "r_multiple": round(trade.profit / risk, 2) if risk else None,
                    "trade_interval": f"{interval:.1f} min" if interval is not None else None,
                    "strategy_tag": trade.strategy_tag or self._strategy_tag(trade),
                    "market_regime": trade.market_regime or self._regime_label(trade, metrics),
                    "news_proximity": self._trade_news_text(trade),
                    "volatility_at_entry": trade.volatility_at_entry,
                    "mae": trade.mae,
                    "mfe": trade.mfe,
                    "entry_signal_strength": trade.entry_signal_strength,
                    "entry_efficiency": trade.entry_efficiency,
                    "exit_efficiency": trade.exit_efficiency,
                    "trailing_stop_efficiency": trade.trailing_stop_efficiency,
                    "fill_quality": self._trade_fill_quality(trade),
                    "slippage_distribution": trade.slippage,
                    "order_modification_count": trade.order_modification_count,
                    "partial_close_tracking": self._partial_close_key(trade),
                    "rejected_orders": trade.rejected_orders,
                }
            )
        return rows

    def _risk_amount(self, trade: TradeRecord) -> float:
        if trade.s_l is None or not trade.price or not trade.size:
            return 0.0
        return abs(trade.price - trade.s_l) * trade.size

    def _session(self, dt: Optional[datetime]) -> str:
        if not dt:
            return "Unknown"
        if 0 <= dt.hour < 8:
            return "Asia"
        if 8 <= dt.hour < 12:
            return "London"
        if 12 <= dt.hour < 16:
            return "London/NY Overlap"
        return "New York"

    def _regime_label(self, trade: TradeRecord, metrics: BacktestMetrics) -> str:
        if trade.duration_minutes is not None and trade.duration_minutes < 15:
            return "Fast/scalp regime"
        if metrics.win_rate >= 60 and metrics.risk_reward_ratio and metrics.risk_reward_ratio < 1:
            return "Mean-reversion inferred"
        if metrics.risk_reward_ratio >= 1.2:
            return "Trend/breakout inferred"
        return "Mixed/unknown"

    def _strategy_tag(self, trade: TradeRecord) -> str:
        if trade.comment:
            return trade.comment[:60]
        if trade.duration_minutes is not None and trade.duration_minutes < 15:
            return "Scalp"
        if trade.duration_minutes is not None and trade.duration_minutes > 240:
            return "Swing"
        return "Unlabeled setup"

    def _partial_close_key(self, trade: TradeRecord) -> Optional[str]:
        if not trade.ticket and not trade.comment:
            return None
        return f"{trade.item}:{trade.comment or trade.ticket}"

    def _partial_close_note(self, trades: List[TradeRecord]) -> str:
        groups: Dict[str, int] = defaultdict(int)
        for trade in trades:
            key = self._partial_close_key(trade)
            if key:
                groups[key] += 1
        linked = sum(1 for count in groups.values() if count > 1)
        return f"{linked} possible linked groups" if linked else "No clear split-ticket groups detected"

    def _has_field(self, trades: List[TradeRecord], field: str) -> bool:
        return any(getattr(trade, field, None) not in (None, "") for trade in trades)

    def _numeric_values(self, trades: List[TradeRecord], field: str) -> List[float]:
        values = []
        for trade in trades:
            value = getattr(trade, field, None)
            if value is None or value == "":
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        return values

    def _numeric_summary(self, trades: List[TradeRecord], field: str) -> Optional[str]:
        values = self._numeric_values(trades, field)
        if not values:
            return None
        return f"avg {sum(values) / len(values):.2f}, min {min(values):.2f}, max {max(values):.2f}"

    def _numeric_total(self, trades: List[TradeRecord], field: str) -> int:
        return int(sum(self._numeric_values(trades, field)))

    def _field_summary(self, trades: List[TradeRecord], field: str) -> Optional[str]:
        values = [str(getattr(trade, field, "")).strip() for trade in trades if getattr(trade, field, None) not in (None, "")]
        if not values:
            return None
        unique = sorted(set(values))
        return ", ".join(unique[:3]) + (f" +{len(unique) - 3} more" if len(unique) > 3 else "")

    def _news_summary(self, trades: List[TradeRecord]) -> Optional[str]:
        count = len([trade for trade in trades if trade.news_time or trade.news_event])
        if not count:
            return None
        high = len([trade for trade in trades if (trade.news_impact or "").lower() == "high"])
        return f"{count} trades with news data, {high} high-impact"

    def _fill_quality(self, trades: List[TradeRecord]) -> Optional[str]:
        slippage = self._numeric_values(trades, "slippage")
        if slippage:
            avg = sum(abs(value) for value in slippage) / len(slippage)
            return f"avg absolute slippage {avg:.2f}"
        deltas = []
        for trade in trades:
            if trade.requested_price is not None and trade.fill_price is not None:
                deltas.append(abs(trade.fill_price - trade.requested_price))
        if not deltas:
            return None
        return f"avg fill delta {sum(deltas) / len(deltas):.5f}"

    def _trade_fill_quality(self, trade: TradeRecord) -> Optional[str]:
        if trade.slippage is not None:
            return f"slip {trade.slippage:g}"
        if trade.requested_price is not None and trade.fill_price is not None:
            return f"delta {abs(trade.fill_price - trade.requested_price):.5f}"
        return None

    def _trade_news_text(self, trade: TradeRecord) -> Optional[str]:
        if not trade.news_time and not trade.news_event:
            return None
        parts = []
        if trade.news_time:
            parts.append(trade.news_time.isoformat(sep=" "))
        if trade.news_event:
            parts.append(trade.news_event)
        if trade.news_impact:
            parts.append(trade.news_impact)
        return " / ".join(parts)

    def _max_drawdown(self, equity_curve: List[float]) -> float:
        peak = equity_curve[0] if equity_curve else 0.0
        worst = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            worst = max(worst, peak - value)
        return round(worst, 2)

    def _ulcer_index(self, equity_curve: List[float]) -> float:
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        drawdowns = []
        for value in equity_curve:
            peak = max(peak, value)
            drawdowns.append(((peak - value) / peak * 100) if peak else 0.0)
        return math.sqrt(sum(dd * dd for dd in drawdowns) / len(drawdowns)) if drawdowns else 0.0

    def _underwater_periods(self, equity_curve: List[float]) -> Dict[str, float]:
        peak = equity_curve[0] if equity_curve else 0.0
        current = 0
        periods: List[int] = []
        for value in equity_curve:
            if value >= peak:
                peak = value
                if current:
                    periods.append(current)
                    current = 0
            else:
                current += 1
        if current:
            periods.append(current)
        return {
            "longest": max(periods) if periods else 0,
            "average": sum(periods) / len(periods) if periods else 0.0,
        }

    def _sharpe(self, profits: List[float]) -> float:
        if len(profits) < 2:
            return 0.0
        avg = sum(profits) / len(profits)
        variance = sum((profit - avg) ** 2 for profit in profits) / (len(profits) - 1)
        stdev = math.sqrt(variance)
        return (avg / stdev) * math.sqrt(len(profits)) if stdev else 0.0

    def _sortino(self, profits: List[float]) -> float:
        downside = [profit for profit in profits if profit < 0]
        if not profits or not downside:
            return 0.0
        avg = sum(profits) / len(profits)
        downside_dev = math.sqrt(sum(profit * profit for profit in downside) / len(downside))
        return (avg / downside_dev) * math.sqrt(len(profits)) if downside_dev else 0.0

    def _omega(self, profits: List[float]) -> float:
        gains = sum(profit for profit in profits if profit > 0)
        pains = abs(sum(profit for profit in profits if profit < 0))
        return gains / pains if pains else 0.0

    def _calmar(self, net_profit: float, deposit: float, dd_pct: float, trades: List[TradeRecord]) -> float:
        months = self._months_covered(trades)
        if not deposit or not dd_pct or months <= 0:
            return 0.0
        period_return_pct = net_profit / deposit * 100
        annual_return_pct = period_return_pct * (12 / months)
        return annual_return_pct / dd_pct if dd_pct else 0.0

    def _risk_of_ruin(self, metrics: BacktestMetrics, profit_factor: float, max_dd_pct: float, trades: List[TradeRecord], behavior: BehaviorAnalysis) -> int:
        score = 10
        if metrics.net_profit <= 0 or profit_factor < 1:
            score += 35
        score += min(30, int(max_dd_pct * 1.2))
        score += 20 if behavior.is_martingale or behavior.lot_escalation_detected else 0
        score += min(15, self._streak(trades, False) * 3)
        return max(0, min(100, score))

    def _kelly(self, metrics: BacktestMetrics, average_win: float, average_loss: float) -> float:
        if not average_win or not average_loss:
            return 0.0
        win_prob = (metrics.win_rate or 0.0) / 100
        payoff = average_win / average_loss
        kelly = win_prob - ((1 - win_prob) / payoff) if payoff else 0.0
        return max(0.0, min(100.0, kelly * 100))

    def _equity_r_squared(self, equity_curve: List[float]) -> float:
        if len(equity_curve) < 3:
            return 0.0
        xs = list(range(len(equity_curve)))
        mean_x = sum(xs) / len(xs)
        mean_y = sum(equity_curve) / len(equity_curve)
        ss_xx = sum((x - mean_x) ** 2 for x in xs)
        if not ss_xx:
            return 0.0
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, equity_curve)) / ss_xx
        intercept = mean_y - slope * mean_x
        ss_tot = sum((y - mean_y) ** 2 for y in equity_curve)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, equity_curve))
        return max(0.0, min(1.0, 1 - ss_res / ss_tot)) if ss_tot else 0.0

    def _months_covered(self, trades: List[TradeRecord]) -> float:
        dates = sorted((trade.open_time or trade.close_time) for trade in trades if trade.open_time or trade.close_time)
        if len(dates) < 2:
            return 0.0
        return ((dates[-1] - dates[0]).days + 1) / 30.44

    def _trade_intervals(self, trades: List[TradeRecord]) -> str:
        intervals = []
        previous_close: Optional[datetime] = None
        for trade in trades:
            if previous_close and trade.open_time:
                intervals.append((trade.open_time - previous_close).total_seconds() / 60)
            if trade.close_time:
                previous_close = trade.close_time
        if not intervals:
            return "N/A"
        return f"{sum(intervals) / len(intervals):.1f} min avg"

    def _hold_time_by_result(self, trades: List[TradeRecord]) -> Dict[str, str]:
        win_durations = [trade.duration_minutes for trade in trades if trade.profit > 0 and trade.duration_minutes is not None]
        loss_durations = [trade.duration_minutes for trade in trades if trade.profit < 0 and trade.duration_minutes is not None]
        all_durations = win_durations + loss_durations
        return {
            "average": f"{sum(all_durations) / len(all_durations):.1f} min avg" if all_durations else "N/A",
            "wins": f"{sum(win_durations) / len(win_durations):.1f} min" if win_durations else "N/A",
            "losses": f"{sum(loss_durations) / len(loss_durations):.1f} min" if loss_durations else "N/A",
        }

    def _bucket_stats(self, trades: List[TradeRecord], key_fn) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"profit": 0.0, "count": 0, "wins": 0})
        for trade in trades:
            key = key_fn(trade) or "Unknown"
            stats[key]["profit"] += trade.profit
            stats[key]["count"] += 1
            stats[key]["wins"] += 1 if trade.profit > 0 else 0
        return dict(stats)

    def _best_worst(self, stats: Dict[str, Dict[str, float]]) -> str:
        if not stats:
            return "N/A"
        best = max(stats, key=lambda key: stats[key]["profit"])
        worst = min(stats, key=lambda key: stats[key]["profit"])
        return f"best {best}, worst {worst}"

    def _setup_win_rates(self, stats: Dict[str, Dict[str, float]]) -> str:
        if not stats:
            return "N/A"
        parts = []
        for key, value in list(stats.items())[:3]:
            rate = value["wins"] / value["count"] * 100 if value["count"] else 0.0
            parts.append(f"{key}: {rate:.1f}%")
        return "; ".join(parts)

    def _direction_stats(self, trades: List[TradeRecord]) -> Dict[str, str]:
        buy = len([trade for trade in trades if "buy" in (trade.type or "").lower()])
        sell = len([trade for trade in trades if "sell" in (trade.type or "").lower()])
        return {"summary": f"Buy {buy} / Sell {sell}"}

    def _streak(self, trades: List[TradeRecord], wins: bool) -> int:
        longest = current = 0
        for trade in trades:
            ok = trade.profit > 0 if wins else trade.profit < 0
            if ok:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    def _max_losing_period_days(self, trades: List[TradeRecord]) -> float:
        longest = current = 0.0
        start: Optional[datetime] = None
        last: Optional[datetime] = None
        for trade in trades:
            dt = trade.close_time or trade.open_time
            if trade.profit < 0 and dt:
                start = start or dt
                last = dt
                current = max(0.0, (last - start).total_seconds() / 86400)
                longest = max(longest, current)
            else:
                start = None
                current = 0.0
        return longest

    def _first_item(self, trades: List[TradeRecord]) -> str:
        return next((trade.item for trade in trades if trade.item), "N/A")

    def _pct(self, value: float, base: float) -> float:
        return (value / base) * 100 if value and base else 0.0

    def _money(self, value: float) -> str:
        return f"${value:,.2f}"

    def _ratio(self, value: float) -> str:
        return f"{value:.2f}" if value else "N/A"

    def _drawdown(self, money: float, pct: float) -> str:
        if money and pct:
            return f"{self._money(money)} ({pct:.2f}%)"
        if pct:
            return f"{pct:.2f}%"
        if money:
            return self._money(money)
        return "N/A"

    def _infer_regime_summary(self, metrics: BacktestMetrics) -> str:
        parts = []
        if metrics.win_rate >= 60 and metrics.risk_reward_ratio and metrics.risk_reward_ratio < 1:
            parts.append("Mean-reversion inferred")
        elif metrics.risk_reward_ratio >= 1.2:
            parts.append("Trend/breakout inferred")
        else:
            parts.append("Mixed regime")
        if metrics.average_trade_duration:
            if metrics.average_trade_duration < 15:
                parts.append("fast execution")
            elif metrics.average_trade_duration > 240:
                parts.append("swing-style holds")
        return ", ".join(parts)

    def _trade_autocorrelation(self, profits: List[float]) -> str:
        if len(profits) < 10:
            return "Too few trades"
        n = len(profits)
        mean = sum(profits) / n
        var = sum((p - mean) ** 2 for p in profits)
        if var == 0:
            return "No variance"
        cov = sum((profits[i] - mean) * (profits[i + 1] - mean) for i in range(n - 1))
        autocorr = cov / var
        if abs(autocorr) < 0.15:
            return f"Low correlation ({autocorr:.3f}) — trades appear independent"
        elif autocorr > 0:
            return f"Positive ({autocorr:.3f}) — streaky wins/losses"
        else:
            return f"Negative ({autocorr:.3f}) — alternating pattern"

