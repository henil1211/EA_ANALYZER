import re
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..models.schemas import (
    ActionItem,
    BacktestMetrics,
    BehaviorAnalysis,
    DataQualityAssessment,
    DepositScenario,
    DrawdownRecoveryStats,
    ExtendedAnalysisResult,
    LossCluster,
    LotEscalationPoint,
    MonthlyHeatmapCell,
    PropFirmCheckResult,
    PropFirmRuleResult,
    SessionStats,
    SymbolSpreadInsight,
    VerdictEvidence,
    WhatIfDefaults,
)
from .forensic_analyzer import ForensicAnalyzer

PROP_FIRM_PRESETS = [
    {"id": "ftmo", "name": "FTMO (Classic)", "daily_loss_pct": 5.0, "max_dd_pct": 10.0},
    {"id": "mff", "name": "MyForexFunds", "daily_loss_pct": 5.0, "max_dd_pct": 12.0},
    {"id": "fundednext", "name": "FundedNext", "daily_loss_pct": 5.0, "max_dd_pct": 10.0},
    {"id": "the5ers", "name": "The5ers", "daily_loss_pct": 4.0, "max_dd_pct": 6.0},
]


class ExtendedAnalyzer:
    def analyze(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List,
        equity_curve: List[float],
        ai_verdict: str,
        report_type: str,
    ) -> ExtendedAnalysisResult:
        balance_curve = self._balance_curve(metrics, trades, equity_curve)
        equity_dd_pct = self._equity_dd_pct(metrics)
        balance_dd_pct = self._balance_dd_pct(metrics, balance_curve)

        return ExtendedAnalysisResult(
            prop_firm_check=self._prop_firm_check(metrics, trades, balance_curve, equity_dd_pct),
            monthly_heatmap=self._monthly_heatmap(trades),
            drawdown_recovery=self._drawdown_recovery(balance_curve, trades),
            loss_clusters=self._loss_clusters(trades),
            lot_escalation=self._lot_escalation(trades),
            session_breakdown=self._session_breakdown(trades, behavior),
            symbol_spread=self._symbol_spread(metrics, trades),
            deposit_scenarios=self._deposit_scenarios(metrics, equity_dd_pct, balance_dd_pct),
            verdict_evidence=self._verdict_evidence(metrics, behavior, ai_verdict, equity_dd_pct, balance_dd_pct),
            data_quality=self._data_quality(metrics, trades, report_type),
            action_checklist=self._action_checklist(metrics, behavior, equity_dd_pct, balance_dd_pct),
            what_if_defaults=WhatIfDefaults(
                deposit=metrics.deposit or 10000,
                max_drawdown_pct=round(equity_dd_pct, 2),
                daily_loss_pct=5.0,
                target_profit_pct=10.0,
            ),
        )

    def _balance_curve(self, metrics: BacktestMetrics, trades: List, equity_curve: List[float]) -> List[float]:
        return ForensicAnalyzer()._build_balance_curve(metrics, trades, equity_curve)

    def _parse_dd_pct(self, raw: Optional[str]) -> Optional[float]:
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

    def _equity_dd_pct(self, metrics: BacktestMetrics) -> float:
        return (
            self._parse_dd_pct(metrics.equity_drawdown_maximal)
            or self._parse_dd_pct(metrics.equity_drawdown_relative)
            or metrics.maximal_drawdown_pct
            or 0.0
        )

    def _balance_dd_pct(self, metrics: BacktestMetrics, balance_curve: List[float]) -> float:
        parsed = self._parse_dd_pct(metrics.balance_drawdown_maximal) or self._parse_dd_pct(
            metrics.balance_drawdown_relative
        )
        if parsed:
            return parsed
        if not balance_curve or not metrics.deposit:
            return metrics.maximal_drawdown_pct or 0.0
        peak = balance_curve[0]
        max_dd = 0.0
        for value in balance_curve:
            peak = max(peak, value)
            if peak > 0:
                max_dd = max(max_dd, (peak - value) / peak * 100)
        return round(max_dd, 2)

    def _daily_returns(self, trades: List) -> Dict[str, float]:
        daily: Dict[str, float] = defaultdict(float)
        for trade in trades:
            dt = trade.close_time or trade.open_time
            if not dt:
                continue
            key = dt.strftime("%Y-%m-%d")
            daily[key] += trade.profit
        return daily

    def _prop_firm_check(
        self,
        metrics: BacktestMetrics,
        trades: List,
        balance_curve: List[float],
        equity_dd_pct: float,
    ) -> PropFirmCheckResult:
        deposit = metrics.deposit or (balance_curve[0] if balance_curve else 10000)
        daily = self._daily_returns(trades)
        worst_day_pct = 0.0
        if deposit > 0 and daily:
            worst_day_pct = round(abs(min(daily.values())) / deposit * 100, 2)

        rules: List[PropFirmRuleResult] = []
        for preset in PROP_FIRM_PRESETS:
            violations: List[str] = []
            details: List[str] = []

            if equity_dd_pct > preset["max_dd_pct"]:
                violations.append(
                    f"Max equity drawdown {equity_dd_pct:.2f}% exceeds {preset['max_dd_pct']:.1f}% limit"
                )
            else:
                details.append(f"Equity drawdown {equity_dd_pct:.2f}% within {preset['max_dd_pct']:.1f}% cap")

            if worst_day_pct > preset["daily_loss_pct"]:
                violations.append(
                    f"Worst day loss {worst_day_pct:.2f}% exceeds {preset['daily_loss_pct']:.1f}% daily limit"
                )
            else:
                details.append(f"Worst day {worst_day_pct:.2f}% within daily limit")

            if metrics.profit_factor < 1 and metrics.total_trades > 20:
                violations.append(f"Profit factor {metrics.profit_factor:.2f} below 1.0")

            rules.append(
                PropFirmRuleResult(
                    firm_id=preset["id"],
                    firm_name=preset["name"],
                    passed=len(violations) == 0,
                    daily_loss_limit_pct=preset["daily_loss_pct"],
                    max_drawdown_limit_pct=preset["max_dd_pct"],
                    violations=violations,
                    details=details,
                )
            )

        return PropFirmCheckResult(
            deposit=deposit,
            overall_pass=any(r.passed for r in rules),
            rules=rules,
            worst_day_loss_pct=worst_day_pct,
            max_equity_drawdown_pct=equity_dd_pct,
        )

    def _monthly_heatmap(self, trades: List) -> List[MonthlyHeatmapCell]:
        buckets: Dict[Tuple[int, int], Dict[str, float]] = defaultdict(lambda: {"profit": 0.0, "trades": 0})
        for trade in trades:
            dt = trade.close_time or trade.open_time
            if not dt:
                continue
            key = (dt.year, dt.month)
            buckets[key]["profit"] += trade.profit
            buckets[key]["trades"] += 1

        cells: List[MonthlyHeatmapCell] = []
        for (year, month), data in sorted(buckets.items()):
            cells.append(
                MonthlyHeatmapCell(
                    year=year,
                    month=month,
                    profit=round(data["profit"], 2),
                    trades=int(data["trades"]),
                    drawdown_pct=0.0,
                )
            )
        return cells

    def _drawdown_recovery(self, balance_curve: List[float], trades: List) -> DrawdownRecoveryStats:
        if len(balance_curve) < 2:
            return DrawdownRecoveryStats()

        peak = balance_curve[0]
        longest = 0
        current_streak = 0
        recovery_lengths: List[int] = []
        underwater_points = 0
        total_points = max(len(balance_curve) - 1, 1)

        for value in balance_curve[1:]:
            if value >= peak:
                if current_streak > 0:
                    recovery_lengths.append(current_streak)
                current_streak = 0
                peak = value
            else:
                current_streak += 1
                underwater_points += 1
                longest = max(longest, current_streak)

        return DrawdownRecoveryStats(
            longest_underwater_trades=longest,
            average_recovery_trades=round(statistics.mean(recovery_lengths), 1) if recovery_lengths else 0.0,
            underwater_periods=len(recovery_lengths),
            time_underwater_pct=round(underwater_points / total_points * 100, 1),
        )

    def _loss_clusters(self, trades: List, window_hours: float = 4.0) -> List[LossCluster]:
        losses = [t for t in trades if t.profit < 0 and (t.close_time or t.open_time)]
        if not losses:
            return []

        losses.sort(key=lambda t: t.close_time or t.open_time)
        clusters: List[LossCluster] = []
        window = timedelta(hours=window_hours)
        batch: List = [losses[0]]

        for trade in losses[1:]:
            if (trade.close_time or trade.open_time) - (batch[-1].close_time or batch[-1].open_time) <= window:
                batch.append(trade)
            else:
                clusters.append(self._cluster_from_batch(batch))
                batch = [trade]
        clusters.append(self._cluster_from_batch(batch))
        return sorted(clusters, key=lambda c: c.total_loss)[:8]

    def _cluster_from_batch(self, batch: List) -> LossCluster:
        start = batch[0].close_time or batch[0].open_time
        end = batch[-1].close_time or batch[-1].open_time
        duration = (end - start).total_seconds() / 60 if start and end else 0
        return LossCluster(
            start_time=start.isoformat() if start else "",
            end_time=end.isoformat() if end else "",
            loss_count=len(batch),
            total_loss=round(sum(t.profit for t in batch), 2),
            duration_minutes=round(duration, 1),
        )

    def _lot_escalation(self, trades: List) -> List[LotEscalationPoint]:
        points: List[LotEscalationPoint] = []
        cumulative = 0.0
        for index, trade in enumerate(trades):
            cumulative += trade.profit
            points.append(
                LotEscalationPoint(
                    index=index + 1,
                    lot=round(trade.size or 0, 4),
                    cumulative_profit=round(cumulative, 2),
                )
            )
        return points[-200:] if len(points) > 200 else points

    def _session_name(self, dt: Optional[datetime]) -> str:
        if not dt:
            return "Unknown"
        hour = dt.hour
        if 0 <= hour < 8:
            return "Asian"
        if 8 <= hour < 16:
            return "London"
        return "New York"

    def _session_breakdown(self, trades: List, behavior: BehaviorAnalysis) -> List[SessionStats]:
        buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"trades": 0, "profit": 0.0, "wins": 0})
        for trade in trades:
            session = self._session_name(trade.open_time or trade.close_time)
            buckets[session]["trades"] += 1
            buckets[session]["profit"] += trade.profit
            if trade.profit > 0:
                buckets[session]["wins"] += 1

        stats: List[SessionStats] = []
        for session, data in buckets.items():
            trades_n = int(data["trades"])
            stats.append(
                SessionStats(
                    session=session,
                    trades=trades_n,
                    profit=round(data["profit"], 2),
                    win_rate=round(data["wins"] / trades_n * 100, 1) if trades_n else 0.0,
                )
            )
        return sorted(stats, key=lambda s: s.profit, reverse=True)

    def _symbol_spread(self, metrics: BacktestMetrics, trades: List) -> SymbolSpreadInsight:
        symbols: Dict[str, float] = defaultdict(float)
        for trade in trades:
            symbols[trade.item or "Unknown"] += trade.profit

        dominant = max(symbols, key=symbols.get) if symbols else metrics.symbol
        concentration = 0.0
        total_abs = sum(abs(v) for v in symbols.values())
        if total_abs > 0 and dominant:
            concentration = round(abs(symbols[dominant]) / total_abs * 100, 1)

        spread_note = metrics.backtest_spread or "Not reported"
        sensitivity = "High" if "high" in spread_note.lower() or concentration > 85 else "Moderate" if concentration > 60 else "Low"

        return SymbolSpreadInsight(
            primary_symbol=metrics.symbol or dominant or "Unknown",
            symbol_profit_breakdown={k: round(v, 2) for k, v in sorted(symbols.items(), key=lambda x: -abs(x[1]))[:6]},
            backtest_spread=spread_note,
            spread_sensitivity=sensitivity,
            symbol_concentration_pct=concentration,
            notes=[
                f"{concentration:.0f}% of absolute P/L concentrated in {dominant}."
                if concentration > 60
                else "Profit is diversified across symbols.",
                f"Reported spread: {spread_note}.",
            ],
        )

    def _deposit_scenarios(
        self, metrics: BacktestMetrics, equity_dd_pct: float, balance_dd_pct: float
    ) -> List[DepositScenario]:
        base = metrics.deposit or 10000
        presets = [5000, 10000, 25000, 50000, 100000]
        scenarios: List[DepositScenario] = []
        for deposit in presets:
            scale = deposit / base if base > 0 else 1.0
            scenarios.append(
                DepositScenario(
                    label=f"${deposit:,.0f}",
                    deposit=float(deposit),
                    scaled_max_dd_pct=round(equity_dd_pct, 2),
                    scaled_net_profit=round(metrics.net_profit * scale, 2),
                    prop_viable=equity_dd_pct <= 10 and balance_dd_pct <= 10,
                )
            )
        return scenarios

    def _verdict_evidence(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        verdict: str,
        equity_dd_pct: float,
        balance_dd_pct: float,
    ) -> List[VerdictEvidence]:
        evidence: List[VerdictEvidence] = []
        pf = metrics.profit_factor or 0
        evidence.append(
            VerdictEvidence(
                rule="Profit factor",
                value=f"{pf:.2f}",
                impact="pass" if pf >= 1.3 else "warn" if pf >= 1 else "fail",
            )
        )
        evidence.append(
            VerdictEvidence(
                rule="Equity drawdown",
                value=f"{equity_dd_pct:.2f}%",
                impact="pass" if equity_dd_pct < 8 else "warn" if equity_dd_pct < 12 else "fail",
            )
        )
        hidden_gap = equity_dd_pct - balance_dd_pct
        evidence.append(
            VerdictEvidence(
                rule="Hidden floating risk",
                value=f"{hidden_gap:.2f}% gap (equity vs balance)",
                impact="pass" if hidden_gap < 2 else "warn" if hidden_gap < 5 else "fail",
            )
        )
        if behavior.is_martingale:
            evidence.append(
                VerdictEvidence(rule="Martingale detected", value="Yes", impact="fail")
            )
        if behavior.dangerous_recovery_system:
            evidence.append(
                VerdictEvidence(rule="Dangerous recovery", value="Detected", impact="fail")
            )
        evidence.append(
            VerdictEvidence(
                rule="Sample size",
                value=f"{metrics.total_trades or 0} trades",
                impact="pass" if (metrics.total_trades or 0) >= 100 else "warn" if (metrics.total_trades or 0) >= 30 else "fail",
            )
        )
        evidence.append(
            VerdictEvidence(
                rule="Final verdict",
                value=verdict,
                impact="pass" if verdict == "PASS" else "warn" if verdict == "CAUTION" else "fail",
            )
        )
        return evidence

    def _data_quality(
        self, metrics: BacktestMetrics, trades: List, report_type: str
    ) -> DataQualityAssessment:
        score = 50
        signals: List[str] = []
        limitations: List[str] = []

        if trades:
            score += 15
            signals.append(f"{len(trades)} trades parsed")
        else:
            limitations.append("No trade list extracted")

        if metrics.equity_drawdown_maximal:
            score += 15
            signals.append("MT5 equity drawdown metrics present")
        else:
            limitations.append("Equity drawdown estimated from balance")

        mae_count = sum(1 for t in trades if t.mae is not None)
        if mae_count > len(trades) * 0.5:
            score += 15
            signals.append(f"MAE data on {mae_count} trades")
        elif mae_count > 0:
            score += 5
            signals.append(f"Partial MAE ({mae_count} trades)")
        else:
            limitations.append("No per-trade MAE — floating risk estimated")

        timed = sum(1 for t in trades if t.open_time and t.close_time)
        if timed > len(trades) * 0.8:
            score += 10
            signals.append("Trade timestamps available")
        else:
            limitations.append("Limited timestamps — session/cluster analysis reduced")

        if "MT5" in report_type or "MT4" in report_type:
            score += 5
            signals.append(f"Native report parser: {report_type}")

        score = min(100, score)
        if score >= 80:
            level, label = "high", "High confidence"
        elif score >= 55:
            level, label = "medium", "Moderate confidence"
        else:
            level, label = "low", "Low confidence — interpret with caution"

        return DataQualityAssessment(
            score=score,
            label=label,
            level=level,
            signals=signals,
            limitations=limitations,
        )

    def _action_checklist(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        equity_dd_pct: float,
        balance_dd_pct: float,
    ) -> List[ActionItem]:
        items: List[ActionItem] = []
        idx = 0

        def add(text: str, priority: str, category: str) -> None:
            nonlocal idx
            idx += 1
            items.append(ActionItem(id=f"action-{idx}", text=text, priority=priority, category=category))

        if equity_dd_pct > 10:
            add(f"Cap equity drawdown below 10% (currently {equity_dd_pct:.1f}%)", "high", "Risk")
        if equity_dd_pct - balance_dd_pct > 3:
            add("Add hard stop or reduce hold time — large hidden floating drawdown", "high", "Risk")
        if behavior.is_martingale or behavior.lot_escalation_detected:
            add("Disable or cap lot escalation / martingale logic", "high", "Strategy")
        if behavior.is_grid:
            add("Review grid spacing and max simultaneous positions", "high", "Strategy")
        if (metrics.total_trades or 0) < 50:
            add("Collect more trades before live deployment (under 50 samples)", "medium", "Validation")
        if metrics.profit_factor < 1.2:
            add(f"Improve profit factor above 1.2 (currently {metrics.profit_factor:.2f})", "medium", "Edge")
        if metrics.win_rate < 45:
            add("Tighten entries or improve R:R — win rate below 45%", "medium", "Edge")
        add("Forward-test on demo for minimum 3 months before funded account", "medium", "Prop firm")
        add("Log daily P/L and enforce prop-firm daily loss limit in EA", "low", "Operations")
        add("Re-run audit after parameter changes", "low", "Operations")
        return items
