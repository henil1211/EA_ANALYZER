import random
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..models.schemas import (
    AIAnalysisResult,
    BacktestMetrics,
    BehaviorAnalysis,
    HiddenDetailsResult,
    HiddenInsight,
    ScoreData,
    TradeRecord,
)


class AIAnalyzer:
    """
    Local rules engine for all dashboard sections.
    Every score and paragraph is derived from the uploaded report metrics and
    parsed trades; it does not inject demo trades or canned performance data.
    """

    async def analyze(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
    ) -> AIAnalysisResult:
        trade_count = metrics.total_trades or len(trades)
        dd_pct = metrics.maximal_drawdown_pct
        dd_money = metrics.maximal_drawdown
        drawdown_for_scoring = dd_pct or self._pct(dd_money, metrics.deposit)
        pf = metrics.profit_factor
        win_rate = metrics.win_rate
        net_profit = metrics.net_profit
        avg_duration = metrics.average_trade_duration
        risk_reward = metrics.risk_reward_ratio

        profitability_score = self._profitability_score(metrics, trade_count)
        risk_score = self._risk_score(metrics, behavior)
        stability_score = self._stability_score(metrics, behavior, trades)
        survivability_score = self._survivability_score(metrics, behavior, trade_count)
        prop_score = self._prop_firm_score(metrics, behavior, trade_count)

        overall = round(
            profitability_score.score * 0.25
            + risk_score.score * 0.25
            + stability_score.score * 0.2
            + survivability_score.score * 0.15
            + prop_score.score * 0.15
        )

        verdict, verdict_color = self._verdict(overall, behavior, drawdown_for_scoring, pf, trade_count)
        strengths = self._strengths(metrics, behavior, trade_count)
        weaknesses = self._weaknesses(metrics, behavior, trade_count)
        hidden_risks = self._hidden_risks(metrics, behavior, trade_count)
        recommendations = self._recommendations(metrics, behavior, trade_count)
        overfit_probability, overfit_indicators = self._overfitting(metrics, behavior, trade_count, trades)

        risk_analysis = self._risk_analysis(metrics, behavior, drawdown_for_scoring, trade_count)
        broker_requirements, slippage, broker_dependency = self._broker_requirements(
            metrics, behavior, avg_duration, trade_count
        )
        prop_safety = self._prop_firm_safety(metrics, behavior, prop_score.score)
        survivability_text, lifetime = self._survivability_text(metrics, behavior, survivability_score.score)
        behavior_summary = self._behavior_summary(behavior, trades, trade_count)
        equity_analysis = self._equity_analysis(metrics, trades, drawdown_for_scoring)
        hidden_details = self._forensic_hidden_details(metrics, behavior, trades, trade_count, overfit_probability)

        return AIAnalysisResult(
            verdict=verdict,
            verdict_color=verdict_color,
            overall_score=overall,
            executive_summary=(
                f"Uploaded report analysis for {metrics.symbol or 'the strategy'}: "
                f"{trade_count} trades, net profit {self._money(net_profit)}, "
                f"profit factor {self._value_or_na(pf)}, win rate {self._pct_text(win_rate)}, "
                f"and max drawdown {self._drawdown_text(dd_money, dd_pct)}. Verdict: {verdict}."
            ),
            profitability_score=profitability_score,
            risk_score=risk_score,
            stability_score=stability_score,
            survivability_score=survivability_score,
            prop_firm_score=prop_score,
            strengths=strengths,
            weaknesses=weaknesses,
            hidden_risks=hidden_risks,
            recommendations=recommendations,
            risk_analysis=risk_analysis,
            broker_requirements=broker_requirements,
            prop_firm_safety=prop_safety,
            slippage_sensitivity=slippage,
            broker_dependency_level=broker_dependency,
            long_term_survivability=survivability_text,
            estimated_account_lifetime=lifetime,
            overfitting_probability=overfit_probability,
            overfitting_indicators=overfit_indicators,
            trade_behavior_summary=behavior_summary,
            equity_analysis=equity_analysis,
            hidden_details=hidden_details,
        )

    def _hidden_details(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
        trade_count: int,
        overfit_probability: int,
    ) -> HiddenDetailsResult:
        profits = [trade.profit for trade in trades]
        wins = [p for p in profits if p > 0]
        losses = [abs(p) for p in profits if p < 0]
        total_profit = sum(wins)
        total_loss = sum(losses)
        durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
        equity = self._equity_values(metrics, trades)
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        top_profit_share = self._top_profit_share(wins, metrics.net_profit)
        worst_cluster_loss, worst_cluster_count = self._worst_loss_cluster(trades)
        recovery_trades = self._drawdown_recovery_trades(equity)
        session_profit = self._session_profit(trades)
        weekday_profit = self._weekday_profit(trades)
        weak_day, weak_day_value = self._weakest_bucket(weekday_profit)
        best_session, best_session_value = self._strongest_bucket(session_profit)
        live_slippage_hit = self._live_stress_cost(metrics, trades)
        minimum_capital = self._minimum_capital(metrics, trades)
        capital_base = self._capital_base(metrics, trades)
        largest_win = max(wins) if wins else 0.0
        largest_loss = max(losses) if losses else 0.0
        avg_profit = metrics.average_profit or (sum(wins) / len(wins) if wins else 0.0)
        avg_loss = metrics.average_loss or (sum(losses) / len(losses) if losses else 0.0)
        tail_ratio = (avg_loss / avg_profit) if avg_profit else 0.0
        lot_profile = self._lot_profile(behavior, trades)
        personality = self._personality(metrics, behavior, durations, dd_pct)
        hidden_strengths = self._hidden_strengths(metrics, behavior, trades, top_profit_share, recovery_trades)
        hidden_weaknesses = self._hidden_weaknesses(metrics, behavior, trades, top_profit_share, worst_cluster_loss, capital_base)

        hidden_risk_score = 100
        hidden_risk_score -= min(30, int(dd_pct))
        hidden_risk_score -= 25 if behavior.is_martingale else 0
        hidden_risk_score -= 15 if behavior.is_grid else 0
        hidden_risk_score -= 15 if behavior.lot_escalation_detected else 0
        hidden_risk_score -= 15 if top_profit_share > 40 else 0
        hidden_risk_score -= 10 if tail_ratio > 1.5 else 0
        hidden_risk_score -= 10 if trade_count < 100 else 0
        hidden_risk_score = max(0, min(100, hidden_risk_score))
        verdict = "Clean" if hidden_risk_score >= 80 else "Watchlist" if hidden_risk_score >= 60 else "High Risk" if hidden_risk_score >= 40 else "Dangerous"

        insights = [
            self._insight(
                "recovery-system",
                "Recovery System Detection",
                "Recovery detected" if behavior.is_martingale or behavior.dangerous_recovery_system else "Controlled",
                "critical" if behavior.is_martingale else "warning" if behavior.lot_escalation_detected else "positive",
                f"{behavior.martingale_confidence:.0f}% confidence" if behavior.is_martingale else "No loss-multiply pattern confirmed",
                "Checks whether lot size expands after losses.",
                [
                    f"Lot range: {behavior.min_lot:g} to {behavior.max_lot:g}.",
                    f"Lot escalation factor: {behavior.lot_escalation_factor:g}x.",
                ],
                "Disable loss-based lot multiplication and use fixed fractional sizing." if behavior.is_martingale else "Keep monitoring lot changes during losing streaks.",
            ),
            self._insight(
                "grid-averaging",
                "Grid / Averaging Behavior",
                "Detected" if behavior.is_grid or behavior.is_averaging_down else "Not confirmed",
                "critical" if behavior.is_grid and behavior.is_averaging_down else "warning" if behavior.is_grid or behavior.is_averaging_down else "positive",
                f"Grid {behavior.grid_confidence:.0f}% / averaging {behavior.averaging_confidence:.0f}%",
                "Looks for repeated entries and adding exposure while under pressure.",
                [
                    f"Grid confidence: {behavior.grid_confidence:.0f}%.",
                    f"Averaging confidence: {behavior.averaging_confidence:.0f}%.",
                ],
                "Add maximum exposure caps and trend filters." if behavior.is_grid or behavior.is_averaging_down else "No grid action needed from parsed trades.",
            ),
            self._insight(
                "lot-scaling",
                "Lot Scaling Pattern",
                lot_profile[0],
                lot_profile[1],
                lot_profile[2],
                "Explains whether the EA uses fixed, compounding, or aggressive sizing.",
                lot_profile[3],
                lot_profile[4],
            ),
            self._insight(
                "worst-loss-sequence",
                "Worst Losing Sequence Risk",
                "Stress cluster found" if worst_cluster_loss else "No loss cluster",
                "critical" if worst_cluster_loss > capital_base * 0.2 and capital_base else "warning" if worst_cluster_loss else "positive",
                f"{self._money(-worst_cluster_loss)} across {worst_cluster_count} trades" if worst_cluster_loss else "N/A",
                "Shows the deepest consecutive realized losing pressure.",
                [
                    f"Longest loss streak: {metrics.consecutive_losses_max or self._longest_loss_streak(trades)}.",
                    f"Worst consecutive loss cluster: {self._money(-worst_cluster_loss)}.",
                ],
                "Reduce position sizing around repeated losses." if worst_cluster_loss else "No immediate cluster action needed.",
            ),
            self._insight(
                "profit-dependency",
                "Profit Dependency",
                "Concentrated" if top_profit_share > 40 else "Distributed",
                "warning" if top_profit_share > 40 else "positive",
                f"Top 5 wins = {top_profit_share:.1f}% of net profit",
                "Checks whether performance depends on a small number of trades.",
                [
                    f"Largest win: {self._money(largest_win)}.",
                    f"Winning trades: {len(wins)} of {trade_count}.",
                ],
                "Test without top outlier trades to confirm the edge." if top_profit_share > 40 else "Profit distribution is not dominated by only the top winners.",
            ),
            self._insight(
                "tail-risk",
                "Hidden Tail Risk",
                "Loss tail heavy" if tail_ratio > 1.2 else "Balanced",
                "warning" if tail_ratio > 1.2 else "positive",
                f"Avg loss / avg win = {tail_ratio:.2f}x" if avg_profit else "N/A",
                "Compares normal wins against normal losses.",
                [
                    f"Average win: {self._money(avg_profit)}.",
                    f"Average loss: {self._money(-avg_loss)}.",
                    f"Largest loss: {self._money(-largest_loss)}.",
                ],
                "Improve stop logic or reduce loss size." if tail_ratio > 1.2 else "Average loss size is under control relative to wins.",
            ),
            self._insight(
                "duration-profile",
                "Trade Duration Profile",
                "Scalping" if durations and sum(durations) / len(durations) < 10 else "Intraday/Swing" if durations else "Unavailable",
                "warning" if behavior.is_scalping else "info",
                f"{(sum(durations) / len(durations)):.1f} min average" if durations else "No paired open/close times",
                "Classifies how long trades are normally held.",
                [
                    f"Parsed durations: {len(durations)} trades.",
                    f"Scalping flag: {'yes' if behavior.is_scalping else 'no'}.",
                ],
                "Use low-spread, low-latency execution." if behavior.is_scalping else "Duration profile does not require special action.",
            ),
            self._insight(
                "session-dependency",
                "Session Dependency",
                "Concentrated" if best_session and total_profit and best_session_value / max(abs(metrics.net_profit), 1) > 0.5 else "Mixed",
                "info",
                f"{best_session}: {self._money(best_session_value)}" if best_session else "Unavailable",
                "Finds which trading session contributes most.",
                [f"{k}: {self._money(v)}" for k, v in session_profit.items()] or ["Session timestamps were not available."],
                "Forward test during the dominant session separately." if best_session else "Add timestamps to report for session diagnostics.",
            ),
            self._insight(
                "weekday-weakness",
                "Day-of-Week Weakness",
                "Weak day found" if weak_day and weak_day_value < 0 else "No negative weekday",
                "warning" if weak_day and weak_day_value < 0 else "positive",
                f"{weak_day}: {self._money(weak_day_value)}" if weak_day else "Unavailable",
                "Looks for weekday-specific drawdown or expectancy problems.",
                [f"{k}: {self._money(v)}" for k, v in weekday_profit.items()] or ["Weekday timestamps were not available."],
                f"Consider filtering or reducing risk on {weak_day}." if weak_day and weak_day_value < 0 else "No weekday filter required from parsed data.",
            ),
            self._insight(
                "drawdown-recovery-speed",
                "Drawdown Recovery Speed",
                "Slow recovery" if recovery_trades and recovery_trades > 50 else "Fast/normal" if recovery_trades else "Unavailable",
                "warning" if recovery_trades and recovery_trades > 50 else "info",
                f"{recovery_trades} trades" if recovery_trades else "N/A",
                "Measures how long it took to recover from the worst equity dip.",
                [
                    f"Max drawdown: {self._drawdown_text(metrics.maximal_drawdown, metrics.maximal_drawdown_pct)}.",
                    f"Recovery factor: {self._value_or_na(metrics.recovery_factor)}.",
                ],
                "Lower risk or improve exits if recovery takes too many trades." if recovery_trades and recovery_trades > 50 else "Recovery speed is acceptable from the parsed curve.",
            ),
            self._insight(
                "equity-curve-quality",
                "Equity Curve Quality",
                "Spike driven" if top_profit_share > 40 else "Steady" if metrics.profit_factor > 1 else "Unstable",
                "warning" if top_profit_share > 40 or metrics.profit_factor < 1 else "positive",
                f"PF {metrics.profit_factor:.2f}, DD {dd_pct:.2f}%",
                "Grades whether the equity curve is smooth or dependent on jumps.",
                [
                    f"Top profit concentration: {top_profit_share:.1f}%.",
                    f"Net profit: {self._money(metrics.net_profit)}.",
                ],
                "Inspect curve without top winners." if top_profit_share > 40 else "Curve quality does not show major concentration risk.",
            ),
            self._insight(
                "overfitting-warning",
                "Overfitting Warning",
                "Elevated" if overfit_probability > 50 else "Normal",
                "warning" if overfit_probability > 50 else "positive",
                f"{overfit_probability}%",
                "Estimates curve-fitting probability from sample size and performance shape.",
                [
                    f"Trades: {trade_count}.",
                    f"Win rate: {self._pct_text(metrics.win_rate)}.",
                ],
                "Run out-of-sample and different spread tests." if overfit_probability > 50 else "Overfitting signal is not dominant.",
            ),
            self._insight(
                "prop-red-flags",
                "Prop Firm Red Flags",
                "Red flags" if behavior.is_martingale or behavior.is_grid or dd_pct > 10 else "Mostly clean",
                "critical" if behavior.is_martingale or behavior.is_grid else "warning" if dd_pct > 10 else "positive",
                f"DD {dd_pct:.2f}%",
                "Highlights rules that funded accounts often reject.",
                [
                    f"Martingale: {'yes' if behavior.is_martingale else 'no'}.",
                    f"Grid: {'yes' if behavior.is_grid else 'no'}.",
                    f"Overtrading: {'yes' if behavior.overtrading_detected else 'no'}.",
                ],
                "Reduce drawdown and remove toxic sizing before prop use." if behavior.is_martingale or behavior.is_grid or dd_pct > 10 else "No major prop restriction trigger detected.",
            ),
            self._insight(
                "broker-sensitivity",
                "Broker Sensitivity",
                "High" if behavior.is_scalping or live_slippage_hit > 25 else "Moderate" if live_slippage_hit > 10 else "Low",
                "warning" if behavior.is_scalping or live_slippage_hit > 25 else "info",
                f"Stress hit approx {live_slippage_hit:.1f}%",
                "Estimates how much spread/slippage can damage expectancy.",
                [
                    f"Expected payoff: {self._money(metrics.expected_payoff)}.",
                    f"Average duration: {metrics.average_trade_duration:.1f} min.",
                ],
                "Use raw spreads and VPS execution." if behavior.is_scalping or live_slippage_hit > 25 else "Standard ECN execution should be reasonable.",
            ),
            self._insight(
                "live-performance-estimate",
                "Realistic Live Performance Estimate",
                "Robust" if live_slippage_hit < 15 and metrics.profit_factor > 1.5 else "Sensitive",
                "warning" if live_slippage_hit >= 15 or metrics.profit_factor < 1.3 else "positive",
                f"Expected payoff after stress: {self._money(metrics.expected_payoff * (1 - live_slippage_hit / 100))}",
                "Applies a simple cost stress to reported expectancy.",
                [
                    f"Backtest expected payoff: {self._money(metrics.expected_payoff)}.",
                    f"Assumed stress reduction: {live_slippage_hit:.1f}%.",
                ],
                "Retest with higher spread/commission settings." if live_slippage_hit >= 15 else "Live-cost buffer appears acceptable.",
            ),
            self._insight(
                "capital-requirement",
                "Capital Requirement Estimate",
                "High capital need" if minimum_capital > capital_base * 1.5 and capital_base else "Within current scale",
                "warning" if minimum_capital > capital_base * 1.5 and capital_base else "info",
                self._money(minimum_capital),
                "Suggests safer capital using historical drawdown with buffer.",
                [
                    f"Capital base used: {self._money(capital_base)}.",
                    f"Max drawdown amount: {self._money(metrics.maximal_drawdown)}.",
                ],
                "Scale down lots or increase capital buffer." if minimum_capital > capital_base * 1.5 and capital_base else "Current capital is not below the simple buffer estimate.",
            ),
            self._insight(
                "ea-personality",
                "EA Personality Profile",
                personality[0],
                personality[1],
                personality[2],
                "A plain-English profile of how the strategy behaves.",
                personality[3],
                personality[4],
            ),
            self._insight(
                "hidden-strengths",
                "Hidden Strengths",
                "Strengths found" if hidden_strengths else "Limited",
                "positive" if hidden_strengths else "info",
                f"{len(hidden_strengths)} strengths",
                "Strengths that are not obvious in a standard report.",
                hidden_strengths or ["No strong hidden strength detected beyond the headline metrics."],
                "Preserve these behaviors during optimization.",
            ),
            self._insight(
                "hidden-weaknesses",
                "Hidden Weaknesses",
                "Weaknesses found" if hidden_weaknesses else "Clean",
                "warning" if hidden_weaknesses else "positive",
                f"{len(hidden_weaknesses)} weaknesses",
                "Weaknesses that are easy to miss in MT4/MT5 summaries.",
                hidden_weaknesses or ["No major hidden weakness detected from parsed trades."],
                "Prioritize these issues before live deployment." if hidden_weaknesses else "Continue monitoring with forward tests.",
            ),
            self._insight(
                "hidden-risk-verdict",
                "Pass/Fail Hidden Risk Verdict",
                verdict,
                "positive" if hidden_risk_score >= 80 else "warning" if hidden_risk_score >= 50 else "critical",
                f"{hidden_risk_score}/100",
                "Overall hidden-risk score from trade behavior, drawdown, concentration, and sizing.",
                [
                    f"Drawdown score input: {dd_pct:.2f}%.",
                    f"Top-win concentration: {top_profit_share:.1f}%.",
                    f"Tail ratio: {tail_ratio:.2f}x.",
                ],
                "Only scale after forward testing." if hidden_risk_score < 80 else "Hidden-risk profile is acceptable, but still forward test.",
            ),
        ]

        return HiddenDetailsResult(
            hidden_risk_score=hidden_risk_score,
            verdict=verdict,
            summary=f"Hidden risk verdict: {verdict} with score {hidden_risk_score}/100 across {len(insights)} diagnostics.",
            insights=insights,
        )

    def _profitability_score(self, metrics: BacktestMetrics, trade_count: int) -> ScoreData:
        score = 50
        pf = metrics.profit_factor
        expectancy = metrics.expected_payoff

        if metrics.net_profit > 0:
            score += 15
        else:
            score -= 25
        if pf >= 2:
            score += 25
        elif pf >= 1.5:
            score += 18
        elif pf >= 1.1:
            score += 8
        elif pf > 0:
            score -= 20
        if expectancy > 0:
            score += 10
        elif expectancy < 0:
            score -= 10
        if trade_count < 30:
            score -= 10

        details = [
            f"Net result: {self._money(metrics.net_profit)}.",
            f"Profit factor: {self._value_or_na(pf)}.",
            f"Expected payoff: {self._money(expectancy)} per trade." if expectancy else "Expected payoff was not available in the report.",
        ]
        return self._score("Profitability", score, f"Net: {self._money(metrics.net_profit)}", details)

    def _risk_score(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis) -> ScoreData:
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        balance_dd = metrics.balance_drawdown_maximal or self._drawdown(metrics.maximal_drawdown, dd_pct)
        equity_dd = metrics.equity_drawdown_maximal or self._drawdown(metrics.maximal_drawdown, dd_pct)
        score = 100
        if dd_pct >= 30:
            score -= 55
        elif dd_pct >= 20:
            score -= 40
        elif dd_pct >= 10:
            score -= 25
        elif dd_pct >= 5:
            score -= 12
        if behavior.is_martingale:
            score -= 30
        if behavior.is_grid:
            score -= 18
        if behavior.lot_escalation_detected:
            score -= 15

        details = [
            f"Balance drawdown: {balance_dd}.",
            f"Equity drawdown: {equity_dd}.",
            f"Max drawdown used for scoring: {self._drawdown_text(metrics.maximal_drawdown, metrics.maximal_drawdown_pct)}.",
            f"Recovery factor: {self._value_or_na(metrics.recovery_factor)}.",
            "Lot escalation detected." if behavior.lot_escalation_detected else "No major lot escalation detected from parsed trades.",
        ]
        if behavior.balance_based_lot_growth_detected:
            details.insert(3, "Lot growth appears balance/profit based and is not treated as martingale-style escalation.")
        summary = f"Balance DD: {balance_dd} · Equity DD: {equity_dd}"
        return self._score("Risk Management", score, summary, details)

    def _stability_score(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trades: List[TradeRecord]
    ) -> ScoreData:
        score = 55
        if metrics.win_rate >= 60:
            score += 18
        elif metrics.win_rate >= 45:
            score += 8
        elif metrics.win_rate > 0:
            score -= 12
        if metrics.sharpe_ratio >= 1.5:
            score += 20
        elif metrics.sharpe_ratio >= 0.8:
            score += 10
        elif metrics.sharpe_ratio < 0 and metrics.sharpe_ratio != 0:
            score -= 20
        if behavior.overtrading_detected:
            score -= 15
        if self._longest_loss_streak(trades) >= 5 or metrics.consecutive_losses_max >= 5:
            score -= 12

        details = [
            f"Win rate: {self._pct_text(metrics.win_rate)}.",
            f"Sharpe ratio: {self._value_or_na(metrics.sharpe_ratio)}.",
            f"Maximum consecutive losses: {metrics.consecutive_losses_max or self._longest_loss_streak(trades) or 'N/A'}.",
        ]
        return self._score("Stability", score, "Consistency audit", details)

    def _survivability_score(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int
    ) -> ScoreData:
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        score = 85
        score -= min(55, int(dd_pct * 1.5))
        if metrics.profit_factor and metrics.profit_factor < 1.2:
            score -= 20
        if behavior.dangerous_recovery_system:
            score -= 35
        if trade_count < 50:
            score -= 8

        details = [
            f"Capital stress level is based on {self._drawdown_text(metrics.maximal_drawdown, metrics.maximal_drawdown_pct)}.",
            "Dangerous recovery behavior detected." if behavior.dangerous_recovery_system else "No dangerous recovery pattern confirmed.",
            f"Trade sample: {trade_count} parsed/report trades.",
        ]
        return self._score("Survivability", score, "Long-run risk", details)

    def _prop_firm_score(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int
    ) -> ScoreData:
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        score = 90
        if dd_pct > 10:
            score -= min(60, int((dd_pct - 10) * 4))
        if behavior.is_martingale:
            score -= 45
        if behavior.is_grid:
            score -= 25
        if behavior.overtrading_detected:
            score -= 10
        if trade_count < 30:
            score -= 8

        details = [
            f"Drawdown versus common 10 percent overall limits: {self._pct_text(dd_pct)}.",
            "Martingale/grid rules risk present." if behavior.is_martingale or behavior.is_grid else "No martingale/grid ban trigger confirmed.",
            f"Sample size considered: {trade_count} trades.",
        ]
        return self._score("Prop Firm Compatibility", score, "Rule compatibility", details)

    def _verdict(
        self, overall: int, behavior: BehaviorAnalysis, dd_pct: float, pf: float, trade_count: int
    ) -> tuple[str, str]:
        if behavior.dangerous_recovery_system or behavior.is_martingale or dd_pct >= 30:
            return "DANGEROUS", "#ef4444"
        if overall < 45 or (pf and pf < 1.0):
            return "FAIL", "#f97316"
        if overall < 70 or dd_pct >= 12 or trade_count < 30:
            return "CAUTION", "#f59e0b"
        return "PASS", "#22c55e"

    def _risk_analysis(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, dd_pct: float, trade_count: int
    ) -> str:
        parts = [
            f"Risk was calculated from the uploaded report using {trade_count} trades and {self._drawdown_text(metrics.maximal_drawdown, metrics.maximal_drawdown_pct)} max drawdown."
        ]
        if dd_pct >= 20:
            parts.append("Drawdown is high enough to threaten funded-account and compounding use.")
        elif dd_pct >= 10:
            parts.append("Drawdown is moderate; position sizing should be reduced before scaling capital.")
        else:
            parts.append("Drawdown is contained relative to typical backtest risk thresholds.")
        if behavior.is_martingale or behavior.lot_escalation_detected:
            parts.append("Position sizing behavior shows recovery pressure, so losses can compound quickly.")
        if metrics.recovery_factor:
            parts.append(f"Recovery factor is {metrics.recovery_factor}, which indicates how much profit was produced per drawdown unit.")
        return " ".join(parts)

    def _broker_requirements(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, avg_duration: float, trade_count: int
    ) -> tuple[str, str, str]:
        if behavior.is_scalping or (avg_duration and avg_duration < 10):
            slippage = "High" if avg_duration and avg_duration >= 2 else "Critical"
            dependency = "High"
            text = "The strategy behaves like a short-duration system, so raw spreads, low commission, reliable fills, and VPS latency near the broker server are important."
        elif trade_count > 300 and metrics.expected_payoff and metrics.expected_payoff < 3:
            slippage = "Medium"
            dependency = "Medium"
            text = "The edge per trade is small, so spread and commission changes can materially affect the result."
        else:
            slippage = "Low"
            dependency = "Low"
            text = "Execution sensitivity appears moderate from the uploaded report; standard regulated ECN/STP conditions should be sufficient."
        return text, slippage, dependency

    def _prop_firm_safety(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, score: int) -> str:
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        if behavior.is_martingale or behavior.is_grid:
            return "Prop firm risk is poor because martingale/grid style behavior is commonly restricted or manually reviewed."
        if dd_pct > 10:
            return "Prop firm risk is elevated because max drawdown is above a common 10 percent overall limit."
        if dd_pct > 5:
            return "Prop firm compatibility is possible, but daily loss limits need tighter lot sizing and stop control."
        if score >= 75:
            return "Prop firm compatibility looks acceptable based on drawdown, sizing behavior, and trade sample."
        return "Prop firm compatibility is uncertain because the report lacks enough safety margin."

    def _survivability_text(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, score: int
    ) -> tuple[str, str]:
        if score >= 80:
            return "Stable: risk and profitability metrics support continued forward testing.", "12+ months if live execution matches the backtest"
        if score >= 60:
            return "Moderate: strategy can survive, but only with conservative sizing and broker-cost control.", "6-12 months under controlled sizing"
        if behavior.dangerous_recovery_system:
            return "Fragile: recovery-based behavior can fail suddenly during one-sided markets.", "1-3 months without risk redesign"
        return "High Risk: report metrics do not show enough capital protection.", "3-6 months unless drawdown is reduced"

    def _behavior_summary(self, behavior: BehaviorAnalysis, trades: List[TradeRecord], trade_count: int) -> str:
        detected = []
        if behavior.is_martingale:
            detected.append(f"martingale ({behavior.martingale_confidence:.0f}% confidence)")
        if behavior.is_grid:
            detected.append(f"grid ({behavior.grid_confidence:.0f}% confidence)")
        if behavior.is_hedging:
            detected.append(f"hedging ({behavior.hedging_confidence:.0f}% confidence)")
        if behavior.is_scalping:
            detected.append(f"scalping ({behavior.scalping_confidence:.0f}% confidence)")
        if behavior.lot_escalation_detected:
            detected.append(f"lot escalation ({behavior.lot_escalation_factor}x max/min)")

        base = f"Behavior analysis used {trade_count or len(trades)} report trades."
        if detected:
            return f"{base} Detected patterns: {', '.join(detected)}."
        return f"{base} No high-risk trade behavior was confirmed from the parsed data."

    def _equity_analysis(self, metrics: BacktestMetrics, trades: List[TradeRecord], dd_pct: float) -> str:
        if not trades:
            return "The report did not expose a full trade table, so the equity view is limited to opening deposit and final reported result."
        loss_streak = self._longest_loss_streak(trades)
        if dd_pct >= 20:
            return f"Equity curve has severe stress: reported drawdown is {self._pct_text(dd_pct)} and the longest parsed loss streak is {loss_streak}."
        if loss_streak >= 5:
            return f"Equity curve needs caution: the longest parsed loss streak is {loss_streak}, which can pressure live psychology and prop limits."
        return f"Equity curve is based on parsed trade profit/balance data; longest parsed loss streak is {loss_streak}."

    def _overfitting(
        self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int, trades: List[TradeRecord]
    ) -> tuple[int, List[str]]:
        probability = 20
        indicators: List[str] = []
        if trade_count < 50:
            probability += 25
            indicators.append("Small trade sample reduces statistical confidence.")
        if metrics.profit_factor >= 3 and trade_count < 200:
            probability += 20
            indicators.append("Very high profit factor on a limited sample can indicate curve fitting.")
        if metrics.win_rate >= 80:
            probability += 15
            indicators.append("Very high win rate should be checked against average loss size.")
        if behavior.is_grid or behavior.is_martingale:
            probability += 10
            indicators.append("Recovery systems can hide tail risk in historical tests.")
        if self._longest_win_streak(trades) >= max(10, trade_count * 0.2):
            probability += 10
            indicators.append("Long winning streak may be regime-specific.")
        return min(95, probability), indicators

    def _strengths(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int) -> List[str]:
        strengths = []
        if metrics.net_profit > 0:
            strengths.append(f"Positive net profit of {self._money(metrics.net_profit)}.")
        if metrics.profit_factor >= 1.5:
            strengths.append(f"Profit factor of {metrics.profit_factor} shows a positive gross profit/loss ratio.")
        if metrics.maximal_drawdown_pct and metrics.maximal_drawdown_pct < 10:
            strengths.append(f"Reported drawdown is contained at {metrics.maximal_drawdown_pct}%.")
        if trade_count >= 100:
            strengths.append(f"Trade sample is meaningful at {trade_count} trades.")
        if not behavior.is_martingale and not behavior.is_grid:
            strengths.append("No martingale or grid pattern was confirmed from parsed trades.")
        return strengths[:5]

    def _weaknesses(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int) -> List[str]:
        weaknesses = []
        if metrics.net_profit <= 0:
            weaknesses.append("Net profit is not positive in the uploaded report.")
        if metrics.profit_factor and metrics.profit_factor < 1.2:
            weaknesses.append("Profit factor is too close to breakeven.")
        if metrics.maximal_drawdown_pct >= 10:
            weaknesses.append(f"Drawdown of {metrics.maximal_drawdown_pct}% limits scalability.")
        if behavior.lot_escalation_detected:
            weaknesses.append(f"Lot sizing expands up to {behavior.lot_escalation_factor}x.")
        if trade_count < 50:
            weaknesses.append(f"Only {trade_count} trades were available, so confidence is limited.")
        return weaknesses[:5]

    def _hidden_risks(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int) -> List[str]:
        risks = []
        if behavior.is_martingale:
            risks.append("Martingale recovery can look smooth until a rare losing sequence appears.")
        if behavior.is_grid:
            risks.append("Grid exposure can accumulate during trending markets.")
        if behavior.is_scalping:
            risks.append("Scalping performance may degrade with spread, commission, and slippage.")
        if metrics.expected_payoff and metrics.expected_payoff < 2 and trade_count > 100:
            risks.append("Small expectancy per trade leaves little room for live execution costs.")
        if metrics.maximal_drawdown_pct == 0 and metrics.maximal_drawdown == 0:
            risks.append("The report did not expose drawdown clearly, so capital risk may be underreported.")
        return risks

    def _recommendations(self, metrics: BacktestMetrics, behavior: BehaviorAnalysis, trade_count: int) -> List[str]:
        recs = []
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        if dd_pct > 10:
            recs.append("Lower risk per trade until max drawdown is below 10 percent for prop-firm style use.")
        if behavior.is_martingale:
            recs.append("Replace loss-based lot multiplication with fixed fractional or volatility-adjusted sizing.")
        if behavior.is_grid:
            recs.append("Add hard exposure caps and trend filters before allowing multiple entries.")
        if metrics.profit_factor and metrics.profit_factor < 1.3:
            recs.append("Improve entry/exit filtering because the profit factor is close to breakeven.")
        if trade_count < 100:
            recs.append("Validate on a larger out-of-sample period before trusting the strategy.")
        if not recs:
            recs.append("Forward test with the same symbol, spread, commission, and lot sizing shown in the report.")
        return recs

    def _insight(
        self,
        insight_id: str,
        title: str,
        status: str,
        severity: str,
        value: str,
        summary: str,
        evidence: List[str],
        recommendation: str,
    ) -> HiddenInsight:
        return HiddenInsight(
            id=insight_id,
            title=title,
            status=status,
            severity=severity,
            value=value,
            summary=summary,
            evidence=evidence[:4],
            recommendation=recommendation,
        )

    def _equity_values(self, metrics: BacktestMetrics, trades: List[TradeRecord]) -> List[float]:
        start = metrics.deposit or 0.0
        values = [start]
        current = start
        for trade in trades:
            current = trade.balance if trade.balance is not None else current + trade.profit
            values.append(current)
        return values

    def _top_profit_share(self, wins: List[float], net_profit: float) -> float:
        if not wins or net_profit <= 0:
            return 0.0
        top = sum(sorted(wins, reverse=True)[:5])
        return round((top / net_profit) * 100, 2)

    def _worst_loss_cluster(self, trades: List[TradeRecord]) -> Tuple[float, int]:
        worst = current = 0.0
        current_count = worst_count = 0
        for trade in trades:
            if trade.profit < 0:
                current += abs(trade.profit)
                current_count += 1
                if current > worst:
                    worst = current
                    worst_count = current_count
            else:
                current = 0.0
                current_count = 0
        return round(worst, 2), worst_count

    def _drawdown_recovery_trades(self, equity: List[float]) -> Optional[int]:
        if len(equity) < 3:
            return None
        peak = equity[0]
        trough_index = peak_index = 0
        worst_drop = 0.0
        current_peak_index = 0
        for index, value in enumerate(equity):
            if value > peak:
                peak = value
                current_peak_index = index
            drop = peak - value
            if drop > worst_drop:
                worst_drop = drop
                peak_index = current_peak_index
                trough_index = index
        if worst_drop <= 0:
            return 0
        recovery_level = equity[peak_index]
        for index in range(trough_index + 1, len(equity)):
            if equity[index] >= recovery_level:
                return index - trough_index
        return len(equity) - trough_index - 1

    def _session_profit(self, trades: List[TradeRecord]) -> Dict[str, float]:
        sessions: Dict[str, float] = {"Asian": 0.0, "London": 0.0, "Overlap": 0.0, "New York": 0.0}
        for trade in trades:
            dt = trade.open_time or trade.close_time
            if not dt:
                continue
            hour = dt.hour
            if 0 <= hour < 8:
                session = "Asian"
            elif 8 <= hour < 12:
                session = "London"
            elif 12 <= hour < 16:
                session = "Overlap"
            else:
                session = "New York"
            sessions[session] += trade.profit
        return {key: round(value, 2) for key, value in sessions.items() if value}

    def _weekday_profit(self, trades: List[TradeRecord]) -> Dict[str, float]:
        weekdays: Dict[str, float] = defaultdict(float)
        for trade in trades:
            dt = trade.open_time or trade.close_time
            if dt:
                weekdays[dt.strftime("%A")] += trade.profit
        return {key: round(value, 2) for key, value in weekdays.items()}

    def _strongest_bucket(self, values: Dict[str, float]) -> Tuple[Optional[str], float]:
        if not values:
            return None, 0.0
        key = max(values, key=lambda item: values[item])
        return key, values[key]

    def _weakest_bucket(self, values: Dict[str, float]) -> Tuple[Optional[str], float]:
        if not values:
            return None, 0.0
        key = min(values, key=lambda item: values[item])
        return key, values[key]

    def _live_stress_cost(self, metrics: BacktestMetrics, trades: List[TradeRecord]) -> float:
        trade_count = metrics.total_trades or len(trades)
        if not trade_count or not metrics.expected_payoff:
            return 0.0
        avg_lot = sum(t.size for t in trades if t.size) / max(1, len([t for t in trades if t.size]))
        rough_cost = max(1.0, avg_lot * 10.0)
        return round(min(80.0, abs(rough_cost / metrics.expected_payoff) * 100), 2)

    def _minimum_capital(self, metrics: BacktestMetrics) -> float:
        capital_base = self._capital_base(metrics, trades)
        if capital_base <= 0:
            return round(metrics.maximal_drawdown * 3, 2) if metrics.maximal_drawdown else 0.0
        buffer = max(capital_base, metrics.maximal_drawdown * 3)
        if metrics.maximal_drawdown_pct:
            buffer = max(buffer, metrics.maximal_drawdown / max(metrics.maximal_drawdown_pct / 100, 0.01) * 1.25)
        return round(buffer, 2)

    def _capital_base(self, metrics: BacktestMetrics, trades: List[TradeRecord]) -> float:
        values = [metrics.deposit or 0.0]
        for trade in trades:
            if trade.balance is not None:
                values.append(float(trade.balance))
            if trade.equity_at_exit is not None:
                values.append(float(trade.equity_at_exit))
            if trade.equity_at_entry is not None:
                values.append(float(trade.equity_at_entry))
        positive_values = [value for value in values if value > 0]
        return round(max(positive_values), 2) if positive_values else 0.0

    def _lot_profile(self, behavior: BehaviorAnalysis, trades: List[TradeRecord]) -> Tuple[str, str, str, List[str], str]:
        lots = [trade.size for trade in trades if trade.size > 0]
        if not lots:
            return "Unavailable", "info", "No lot data", ["No parsed lot sizes were available."], "Upload reports with lot/volume columns for lot profiling."
        ratio = max(lots) / min(lots) if min(lots) else 0.0
        if ratio >= 10:
            status, severity = "Aggressive scaling", "critical"
        elif ratio >= 3:
            status, severity = "Compounding/scaling", "warning"
        else:
            status, severity = "Stable sizing", "positive"
        evidence = [
            f"Minimum lot: {min(lots):g}.",
            f"Maximum lot: {max(lots):g}.",
            f"Average lot: {sum(lots) / len(lots):.2f}.",
        ]
        recommendation = "Add a maximum lot cap and retest worst losing streaks." if ratio >= 3 else "Lot range is controlled."
        return status, severity, f"{ratio:.2f}x max/min", evidence, recommendation

    def _personality(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        durations: List[float],
        dd_pct: float,
    ) -> Tuple[str, str, str, List[str], str]:
        avg_duration = sum(durations) / len(durations) if durations else metrics.average_trade_duration
        if behavior.is_martingale:
            label, severity = "Recovery / martingale-like", "critical"
        elif behavior.is_grid:
            label, severity = "Grid or mean-reversion", "warning"
        elif avg_duration and avg_duration < 10:
            label, severity = "Fast scalper", "warning"
        elif dd_pct > 15:
            label, severity = "High-return high-drawdown system", "warning"
        else:
            label, severity = "Directional / controlled-risk EA", "positive"
        return (
            label,
            severity,
            f"PF {metrics.profit_factor:.2f}, DD {dd_pct:.2f}%",
            [
                f"Average duration: {avg_duration:.1f} min." if avg_duration else "Duration unavailable.",
                f"Win rate: {self._pct_text(metrics.win_rate)}.",
                f"Expected payoff: {self._money(metrics.expected_payoff)}.",
            ],
            "Match broker, spread, and capital plan to this EA personality.",
        )

    def _hidden_strengths(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
        top_profit_share: float,
        recovery_trades: Optional[int],
    ) -> List[str]:
        strengths = []
        if metrics.profit_factor >= 1.5:
            strengths.append(f"Profit factor remains healthy at {metrics.profit_factor:.2f}.")
        if metrics.win_rate >= 55:
            strengths.append(f"Win rate is structurally positive at {metrics.win_rate:.2f}%.")
        if top_profit_share and top_profit_share < 30:
            strengths.append("Profit is not overly dependent on only the top five winners.")
        if recovery_trades is not None and recovery_trades <= 20:
            strengths.append(f"Worst drawdown recovered within {recovery_trades} trades.")
        if not behavior.is_martingale and not behavior.is_grid:
            strengths.append("No martingale/grid signature confirmed from parsed trades.")
        return strengths[:5]

    def _hidden_weaknesses(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
        top_profit_share: float,
        worst_cluster_loss: float,
        capital_base: float,
    ) -> List[str]:
        weaknesses = []
        if behavior.is_martingale:
            weaknesses.append("Lot size increases after losses, creating recovery-system risk.")
        if behavior.is_grid:
            weaknesses.append("Repeated overlapping entries can accumulate trend exposure.")
        if behavior.lot_escalation_detected:
            weaknesses.append(f"Lot escalation reaches {behavior.lot_escalation_factor:.2f}x.")
        if top_profit_share > 40:
            weaknesses.append(f"Top five winners contribute {top_profit_share:.1f}% of net profit.")
        if metrics.average_loss and metrics.average_profit and metrics.average_loss > metrics.average_profit:
            weaknesses.append("Average loss is larger than average win.")
        if worst_cluster_loss and capital_base and worst_cluster_loss > capital_base * 0.2:
            weaknesses.append("Worst consecutive loss cluster is large versus starting capital.")
        return weaknesses[:5]

    def _forensic_hidden_details(
        self,
        metrics: BacktestMetrics,
        behavior: BehaviorAnalysis,
        trades: List[TradeRecord],
        trade_count: int,
        overfit_probability: int,
    ) -> HiddenDetailsResult:
        trade_count = trade_count or len(trades)
        profits = [trade.profit for trade in trades]
        wins = [profit for profit in profits if profit > 0]
        losses = [abs(profit) for profit in profits if profit < 0]
        durations = [trade.duration_minutes for trade in trades if trade.duration_minutes is not None]
        lots = [trade.size for trade in trades if trade.size > 0]
        equity = self._equity_values(metrics, trades)
        dd_pct = metrics.maximal_drawdown_pct or self._pct(metrics.maximal_drawdown, metrics.deposit)
        dd_money = metrics.maximal_drawdown or self._max_drawdown_money(equity)
        avg_duration = (sum(durations) / len(durations)) if durations else metrics.average_trade_duration
        avg_win = metrics.average_profit or (sum(wins) / len(wins) if wins else 0.0)
        avg_loss = metrics.average_loss or (sum(losses) / len(losses) if losses else 0.0)
        rr = metrics.risk_reward_ratio or ((avg_win / avg_loss) if avg_loss else 0.0)
        win_rate = metrics.win_rate or ((len(wins) / trade_count) * 100 if trade_count else 0.0)
        expected_payoff = metrics.expected_payoff or ((sum(profits) / trade_count) if trade_count else 0.0)
        gross_profit = metrics.gross_profit or sum(wins)
        gross_loss = abs(metrics.gross_loss) or sum(losses)
        pf = metrics.profit_factor or ((gross_profit / gross_loss) if gross_loss else 0.0)
        net_profit = metrics.net_profit or sum(profits)
        deposit = metrics.deposit or (equity[0] if equity else 0.0)
        top_profit_share = self._top_profit_share(wins, net_profit)
        worst_cluster_loss, worst_cluster_count = self._worst_loss_cluster(trades)
        longest_loss_streak = metrics.consecutive_losses_max or self._longest_loss_streak(trades)
        recovery_trades = self._drawdown_recovery_trades(equity)
        session_profit = self._session_profit(trades)
        weekday_profit = self._weekday_profit(trades)
        hour_profit, hour_count = self._time_buckets(trades, "hour")
        month_profit, _ = self._time_buckets(trades, "month")
        best_session, best_session_value = self._strongest_bucket(session_profit)
        worst_session, worst_session_value = self._weakest_bucket(session_profit)
        worst_day, worst_day_value = self._weakest_bucket(weekday_profit)
        worst_hour, worst_hour_value = self._weakest_bucket(hour_profit)
        worst_month, worst_month_value = self._weakest_bucket(month_profit)
        underwater = self._underwater_stats(equity)
        monte_carlo = self._monte_carlo_projection(metrics, profits)
        chunk_edges = self._chunk_expectancy(profits)
        direction = self._directional_bias(trades)
        reliability_score, reliability_label, limitations = self._analysis_reliability(metrics, trades, durations)

        lot_ratio = (max(lots) / min(lots)) if lots and min(lots) else 0.0
        avg_lot = (sum(lots) / len(lots)) if lots else behavior.avg_lot
        after_loss_increases = 0
        after_loss_checks = 0
        cascade_losses = 0
        for prev, current in zip(trades, trades[1:]):
            if prev.profit < 0 and prev.size and current.size:
                after_loss_checks += 1
                if current.size > prev.size * 1.05:
                    after_loss_increases += 1
                    if current.profit < 0:
                        cascade_losses += 1
        soft_martingale_probability = min(
            100,
            int(
                max(behavior.martingale_confidence, 0)
                + (25 if behavior.lot_escalation_detected else 0)
                + (20 if lot_ratio >= 3 else 0)
                + (25 * after_loss_increases / after_loss_checks if after_loss_checks else 0)
            ),
        )
        broker_cost = self._broker_cost_proxy(avg_lot)
        one_pip_hit = broker_cost * trade_count
        two_pip_hit = one_pip_hit * 2
        one_pip_net = net_profit - one_pip_hit
        two_pip_net = net_profit - two_pip_hit
        broker_sensitivity_pct = min(100.0, self._pct(one_pip_hit, abs(net_profit)) if net_profit else 100.0)
        ruin_risk = self._risk_of_ruin_score(
            metrics=metrics,
            dd_pct=dd_pct,
            pf=pf,
            win_rate=win_rate,
            longest_loss_streak=longest_loss_streak,
            soft_martingale_probability=soft_martingale_probability,
            monte_carlo_survival=monte_carlo["survival_rate"],
        )

        scalping_score = min(100, int((behavior.scalping_confidence or 0) + (35 if avg_duration and avg_duration < 10 else 0)))
        session_total_abs = sum(abs(value) for value in session_profit.values()) or 0.0
        session_concentration = (abs(best_session_value) / session_total_abs * 100) if session_total_abs and best_session else 0.0
        hour_concentration = (max(hour_count.values()) / trade_count * 100) if hour_count and trade_count else 0.0
        rollover_loss = sum(
            trade.profit
            for trade in trades
            if (trade.open_time or trade.close_time) and (trade.open_time or trade.close_time).hour in {22, 23, 0, 1}
        )
        friday_loss = sum(
            trade.profit
            for trade in trades
            if (trade.open_time or trade.close_time) and (trade.open_time or trade.close_time).strftime("%A") == "Friday"
        )
        tail_ratio = (avg_loss / avg_win) if avg_win else 0.0
        stability_score = max(
            0,
            min(
                100,
                int(
                    100
                    - min(35, dd_pct)
                    - min(20, underwater["ulcer_index"] * 1.5)
                    - (15 if top_profit_share > 40 else 0)
                    - (15 if worst_cluster_loss and capital_base and worst_cluster_loss > capital_base * 0.2 else 0)
                ),
            ),
        )
        capital_required = max(
            self._minimum_capital(metrics, trades),
            capital_base + dd_money * 2 if capital_base else dd_money * 3,
            capital_base + monte_carlo["p95_drawdown"] * 1.5 if capital_base else monte_carlo["p95_drawdown"] * 2,
        )
        live_survival_score = max(
            0,
            min(
                100,
                int(
                    100
                    - ruin_risk * 0.45
                    - overfit_probability * 0.2
                    - min(25, dd_pct)
                    - (15 if broker_sensitivity_pct > 30 else 0)
                    - (10 if trade_count < 100 else 0)
                    + (10 if pf >= 1.7 else 0)
                ),
            ),
        )
        if net_profit <= 0 or (pf and pf < 1):
            live_survival_score = min(live_survival_score, 35)
        hidden_safety_score = max(
            0,
            min(
                100,
                int(
                    live_survival_score * 0.45
                    + stability_score * 0.25
                    + (100 - overfit_probability) * 0.15
                    + (100 - soft_martingale_probability) * 0.15
                ),
            ),
        )
        if net_profit <= 0 or (pf and pf < 1):
            hidden_safety_score = min(hidden_safety_score, 32)
        confidence_score = max(
            15,
            min(
                95,
                int(
                    reliability_score * 0.75
                    + (10 if lots else 0)
                    + (10 if durations else 0)
                    + (5 if abs(net_profit) > max(deposit * 0.02, 1) else 0)
                ),
            ),
        )
        verdict = (
            "Institutional Grade"
            if hidden_safety_score >= 82
            else "Forward-Test Ready"
            if hidden_safety_score >= 68
            else "Watchlist"
            if hidden_safety_score >= 52
            else "High Risk"
            if hidden_safety_score >= 35
            else "Dangerous"
        )

        traits = []
        if scalping_score >= 55:
            traits.append("scalping")
        if avg_duration and avg_duration >= 240:
            traits.append("swing trading")
        if behavior.is_grid:
            traits.append("grid")
        if soft_martingale_probability >= 55:
            traits.append("soft martingale")
        if lots and len(lots) > 8 and lots[-1] < statistics.mean(lots[: max(1, len(lots) // 3)]) * 0.8:
            traits.append("anti-martingale/de-risking")
        if win_rate >= 62 and rr and rr < 1:
            traits.append("mean reversion")
        if win_rate <= 55 and rr >= 1.3:
            traits.append("trend following")
        if avg_duration and avg_duration <= 60 and rr >= 1.2:
            traits.append("breakout")
        if hour_concentration >= 45:
            traits.append("time-filter")
        if session_concentration >= 55:
            traits.append("session-based")
        if behavior.is_hedging:
            traits.append("hedging")
        if behavior.is_averaging_down:
            traits.append("averaging down")
        if soft_martingale_probability >= 45 or behavior.dangerous_recovery_system:
            traits.append("recovery system")
        if scalping_score >= 70 and win_rate >= 75 and abs(expected_payoff) < broker_cost * 3:
            traits.append("arbitrage-like")
        if not traits:
            traits.append("directional controlled-risk")
        personality_text = f"This EA behaves like a {' + '.join(traits[:4])} strategy."

        market_text = "trade-distribution inference"
        if "mean reversion" in traits or behavior.is_grid:
            market_bias = "low-volatility ranging markets"
            market_risk = "prolonged one-way trends"
        elif "trend following" in traits or "breakout" in traits:
            market_bias = "directional expansion markets"
            market_risk = "choppy ranging markets"
        else:
            market_bias = "mixed market conditions"
            market_risk = "regime shifts that differ from this backtest"

        profit_chunks = [edge for edge in chunk_edges if edge is not None]
        first_edge = profit_chunks[0] if profit_chunks else 0.0
        last_edge = profit_chunks[-1] if profit_chunks else 0.0
        edge_degradation = first_edge > 0 and last_edge < first_edge * 0.6
        dna = {
            "Aggression": min(100, int(dd_pct * 2 + lot_ratio * 8 + (25 if behavior.overtrading_detected else 0))),
            "Stability": stability_score,
            "Recovery Dependence": min(100, int(soft_martingale_probability * 0.7 + behavior.grid_confidence * 0.3)),
            "Volatility Tolerance": max(0, min(100, int(100 - dd_pct - tail_ratio * 18 - (20 if behavior.is_grid else 0)))),
            "Scalping Sensitivity": scalping_score,
            "Overfit Risk": overfit_probability,
        }

        insights = [
            self._insight(
                "strategy-personality",
                "Strategy Personality Detection",
                traits[0].title(),
                "critical" if soft_martingale_probability >= 70 else "warning" if scalping_score >= 70 or behavior.is_grid else "info",
                f"{len(traits)} traits",
                personality_text,
                [
                    f"Average trade duration: {avg_duration:.1f} min." if avg_duration else "Average trade duration was not available.",
                    f"Win rate/RR: {self._pct_text(win_rate)} / {rr:.2f}.",
                    f"Lot range: {min(lots):g} to {max(lots):g}." if lots else "Lot data was not available.",
                    f"Detected traits: {', '.join(traits)}.",
                ],
                "Use this personality label to decide broker, symbol, session filters, and allowed drawdown before live use.",
            ),
            self._insight(
                "hidden-risk",
                "Hidden Risk Detection",
                "High hidden risk" if ruin_risk >= 65 else "Moderate hidden risk" if ruin_risk >= 35 else "Controlled",
                "critical" if ruin_risk >= 65 else "warning" if ruin_risk >= 35 else "positive",
                f"Ruin risk {ruin_risk}%",
                "Combines soft martingale, tail risk, stability, and capital survival risk hidden behind headline profit.",
                [
                    f"Soft martingale probability: {soft_martingale_probability}%.",
                    f"AI stability score: {stability_score}/100.",
                    f"Monte Carlo {self._rate_text(monte_carlo['survival_rate'], 'stress pass')}.",
                    f"Analysis reliability: {reliability_label} ({reliability_score}/100).",
                    f"Max DD: {self._drawdown_text(dd_money, dd_pct)}.",
                ],
                "Reduce lot escalation and retest the worst historical drawdown with at least 2x to 3x capital buffer.",
            ),
            self._insight(
                "market-condition",
                "Market Condition Analysis",
                market_bias.title(),
                "warning" if behavior.is_grid or soft_martingale_probability >= 55 else "info",
                market_text,
                f"The report suggests the EA works best in {market_bias} and is most vulnerable during {market_risk}.",
                [
                    f"Best session: {best_session or 'N/A'} {self._money(best_session_value)}.",
                    f"Worst session: {worst_session or 'N/A'} {self._money(worst_session_value)}.",
                    f"Profit factor: {pf:.2f}.",
                    f"Tail ratio avg loss/avg win: {tail_ratio:.2f}x.",
                ],
                "Forward-test separately on trending, ranging, high-volatility, and low-volatility periods before scaling.",
            ),
            self._insight(
                "time-weakness",
                "Time-Based Weakness Analysis",
                "Weak window found" if (worst_hour is not None and worst_hour_value < 0) or friday_loss < 0 or rollover_loss < 0 else "No major time leak",
                "warning" if (worst_hour is not None and worst_hour_value < 0) or friday_loss < 0 or rollover_loss < 0 else "positive",
                f"{worst_hour}:00" if worst_hour is not None else "N/A",
                "Finds the hours, weekdays, months, and rollover windows where the EA loses the most money.",
                [
                    f"Worst hour: {worst_hour}:00 = {self._money(worst_hour_value)}." if worst_hour is not None else "Hourly timestamps unavailable.",
                    f"Worst weekday: {worst_day or 'N/A'} = {self._money(worst_day_value)}.",
                    f"Worst month: {worst_month or 'N/A'} = {self._money(worst_month_value)}.",
                    f"Rollover 22:00-01:00 result: {self._money(rollover_loss)}.",
                ],
                "Add risk reduction or no-trade filters around the weakest hour/day if this pattern repeats in forward tests.",
            ),
            self._insight(
                "trade-sequence",
                "Trade Sequence Intelligence",
                "Cascade risk" if cascade_losses >= 3 or worst_cluster_count >= 5 else "Controlled sequence",
                "critical" if cascade_losses >= 5 else "warning" if cascade_losses >= 3 or worst_cluster_count >= 5 else "positive",
                f"{worst_cluster_count} loss cluster",
                "Checks whether one bad trade tends to trigger a recovery cascade or deeper losing sequence.",
                [
                    f"Worst consecutive loss cluster: {self._money(-worst_cluster_loss)}.",
                    f"Longest loss streak: {longest_loss_streak}.",
                    f"Lot increases after losses: {after_loss_increases}/{after_loss_checks}.",
                    f"Worst DD recovery: {recovery_trades if recovery_trades is not None else 'N/A'} trades.",
                ],
                "Put a hard stop on consecutive recovery attempts and pause trading after the detected loss-cluster depth.",
            ),
            self._insight(
                "broker-sensitivity",
                "Broker Sensitivity Analysis",
                "Highly sensitive" if broker_sensitivity_pct >= 35 or scalping_score >= 70 else "Moderate" if broker_sensitivity_pct >= 15 else "Low",
                "critical" if broker_sensitivity_pct >= 60 else "warning" if broker_sensitivity_pct >= 15 or scalping_score >= 70 else "positive",
                f"+1 cost hit {broker_sensitivity_pct:.1f}%",
                "Simulates simple spread/slippage pressure using parsed trade count and average lot from the uploaded report.",
                [
                    f"+1 pip/point proxy net: {self._money(one_pip_net)}.",
                    f"+2 pip/point proxy net: {self._money(two_pip_net)}.",
                    f"Execution delay risk: {'high' if avg_duration and avg_duration < 10 else 'normal'}.",
                    f"Expected payoff: {self._money(expected_payoff)}.",
                ],
                "Retest with worse spread, commission, and slippage. Do not trust this EA on a wider-spread broker until it survives the stress test.",
            ),
            self._insight(
                "parameter-robustness",
                "Parameter Robustness Analysis",
                "Optimization-risk signals" if overfit_probability >= 65 else "Needs validation" if overfit_probability >= 40 else "Reasonable",
                "critical" if overfit_probability >= 75 else "warning" if overfit_probability >= 40 else "positive",
                f"{overfit_probability}%",
                "Detects optimization-risk indicators from sample size, extreme metrics, and equity shape. True overfit confirmation needs optimizer, walk-forward, or out-of-sample data.",
                [
                    f"Trade sample: {trade_count}.",
                    f"Profit factor: {pf:.2f}.",
                    f"Top 5 winners share: {top_profit_share:.1f}% of net profit.",
                    f"Chunk expectancy first/last: {self._money(first_edge)} / {self._money(last_edge)}.",
                ],
                "Run out-of-sample, walk-forward, and small parameter-shift tests. Avoid using only the best optimizer pass.",
            ),
            self._insight(
                "advanced-drawdown",
                "Advanced Drawdown Analytics",
                "Psychologically hard" if underwater["longest"] >= 100 or underwater["ulcer_index"] >= 10 else "Manageable",
                "warning" if underwater["longest"] >= 100 or underwater["ulcer_index"] >= 10 else "info",
                f"Ulcer {underwater['ulcer_index']:.2f}",
                "Measures how painful the equity curve is beyond max drawdown alone.",
                [
                    f"Longest underwater period: {underwater['longest']} trades.",
                    f"Average recovery period: {underwater['average']:.1f} trades.",
                    f"Drawdown frequency: {underwater['frequency']} periods.",
                    f"Pain index: {underwater['pain_index']:.2f}.",
                ],
                "Use the longest underwater period as the minimum patience window for forward testing and investor expectations.",
            ),
            self._insight(
                "trade-quality",
                "Trade Quality Analysis",
                "Outlier dependent" if top_profit_share >= 40 else "Consistent edge" if pf > 1.4 and expected_payoff > 0 else "Weak edge",
                "warning" if top_profit_share >= 40 or expected_payoff <= 0 else "positive",
                f"Top5 {top_profit_share:.1f}%",
                "Checks profit distribution, expectancy stability, and whether the strategy relies on a few lucky trades.",
                [
                    f"Average win/loss: {self._money(avg_win)} / {self._money(-avg_loss)}.",
                    f"Expected payoff: {self._money(expected_payoff)}.",
                    f"Gross profit/loss: {self._money(gross_profit)} / {self._money(-gross_loss)}.",
                    f"Chunk expectancy: {', '.join(self._money(edge) for edge in profit_chunks[:4]) if profit_chunks else 'N/A'}.",
                ],
                "Check the same report after removing the largest winners and losers to see whether the edge remains.",
            ),
            self._insight(
                "monte-carlo",
                "Monte Carlo Simulation",
                "Strong stress pass" if monte_carlo["survival_rate"] >= 80 else "Fragile stress result" if monte_carlo["survival_rate"] < 55 else "Mixed stress result",
                "critical" if monte_carlo["survival_rate"] < 45 else "warning" if monte_carlo["survival_rate"] < 80 else "positive",
                self._rate_text(monte_carlo["survival_rate"], "stress pass"),
                "Randomizes the parsed trade distribution with skipped trades and cost stress to estimate future path risk. This is a stress pass rate, not a guarantee of live survival.",
                [
                    f"Median final result: {self._money(monte_carlo['median_final'])}.",
                    f"5th percentile final result: {self._money(monte_carlo['p05_final'])}.",
                    f"95th percentile drawdown: {self._money(monte_carlo['p95_drawdown'])}.",
                    f"Simulations: {monte_carlo['runs']}.",
                ],
                "Size the account from the stressed drawdown, not only the historical max drawdown.",
            ),
            self._insight(
                "natural-language-report",
                "AI-Powered Natural Language Report",
                verdict,
                "critical" if hidden_safety_score < 35 else "warning" if hidden_safety_score < 68 else "positive",
                f"{hidden_safety_score}/100",
                (
                    f"{metrics.symbol or 'This EA'} produced {self._money(net_profit)} over {trade_count} trades with PF {pf:.2f}. "
                    f"The hidden profile is {', '.join(traits[:3])}; main live risk is {market_risk}, "
                    f"with survival score {live_survival_score}/100."
                ),
                [
                    f"Report source: uploaded MT4/MT5 parsed data only.",
                    f"Net profit: {self._money(net_profit)}.",
                    f"Max DD: {self._drawdown_text(dd_money, dd_pct)}.",
                    f"Safety verdict: {verdict}.",
                ],
                "Use this paragraph as the plain-English summary, but validate every warning with forward testing.",
            ),
            self._insight(
                "prop-firm",
                "Prop Firm Compatibility Analyzer",
                "Likely rule risk" if dd_pct >= 10 or soft_martingale_probability >= 65 else "Needs daily DD check" if dd_pct >= 5 else "Compatible candidate",
                "critical" if dd_pct >= 10 or soft_martingale_probability >= 65 else "warning" if dd_pct >= 5 else "positive",
                f"DD {dd_pct:.2f}%",
                "Checks common funded-account risks: max drawdown, recovery logic, consistency, and overtrading.",
                [
                    f"Max DD versus common 10% limit: {dd_pct:.2f}%.",
                    f"Recovery/martingale probability: {soft_martingale_probability}%.",
                    f"Overtrading detected: {'yes' if behavior.overtrading_detected else 'no'}.",
                    f"Top 5 winners share: {top_profit_share:.1f}%.",
                ],
                "For prop use, reduce lot size until historical plus Monte Carlo drawdown stays below the firm's daily and overall limits.",
            ),
            self._insight(
                "capital-requirement",
                "Capital Requirement Estimator",
                "Needs more capital" if capital_base and capital_required > capital_base * 1.5 else "Current scale acceptable",
                "warning" if capital_base and capital_required > capital_base * 1.5 else "info",
                self._money(capital_required),
                "Estimates minimum safer capital using reported drawdown, Monte Carlo stress, and recovery-system behavior.",
                [
                    f"Capital base used: {self._money(capital_base)}.",
                    f"Historical max DD money: {self._money(dd_money)}.",
                    f"Monte Carlo p95 DD: {self._money(monte_carlo['p95_drawdown'])}.",
                    f"Recommended buffer: {capital_required / capital_base:.2f}x capital base." if capital_base else "Capital base unavailable.",
                ],
                "Use the recommended capital or reduce lot size proportionally before live deployment.",
            ),
            self._insight(
                "live-survival",
                "Live Trading Survival Score",
                "Strong" if live_survival_score >= 75 else "Moderate" if live_survival_score >= 55 else "Weak",
                "critical" if live_survival_score < 40 else "warning" if live_survival_score < 65 else "positive",
                f"{live_survival_score}/100",
                "Combines robustness, drawdown, broker sensitivity, overfit risk, and recovery dependency into one live score.",
                [
                    f"Broker sensitivity: {broker_sensitivity_pct:.1f}%.",
                    f"Overfit risk: {overfit_probability}%.",
                    f"Stability score: {stability_score}/100.",
                    f"Risk of ruin estimate: {ruin_risk}%.",
                ],
                "Treat this as a go/no-go score for demo and small-capital forward testing.",
            ),
            self._insight(
                "hidden-correlation",
                "Hidden Correlation Analysis",
                "Directional bias" if direction["bias_pct"] >= 65 else "Balanced direction",
                "warning" if direction["bias_pct"] >= 65 else "info",
                f"{direction['bias_pct']:.1f}% bias",
                "Detects whether the backtest depends on one symbol, one direction, or one regime.",
                [
                    f"Buy result/count: {self._money(direction['buy_profit'])} / {direction['buy_count']}.",
                    f"Sell result/count: {self._money(direction['sell_profit'])} / {direction['sell_count']}.",
                    f"Symbol tested: {metrics.symbol or 'N/A'}.",
                    f"Dominant session concentration: {session_concentration:.1f}%.",
                ],
                "Test uncorrelated symbols and opposite market regimes before calling this EA diversified.",
            ),
            self._insight(
                "failure-prediction",
                "Live Degradation Risk",
                "Degradation signals" if edge_degradation or soft_martingale_probability >= 70 else "No major degradation signal",
                "critical" if soft_martingale_probability >= 80 else "warning" if edge_degradation or soft_martingale_probability >= 55 else "positive",
                "Watch" if edge_degradation or soft_martingale_probability >= 55 else "Clear",
                "Looks for degradation signals commonly seen before live underperformance: deeper recovery, shrinking edge, and volatility mismatch.",
                [
                    f"First chunk expectancy: {self._money(first_edge)}.",
                    f"Last chunk expectancy: {self._money(last_edge)}.",
                    f"Cascade losses after lot increases: {cascade_losses}.",
                    f"Recovery depth signal: {soft_martingale_probability}%.",
                ],
                "Pause or lower size if live expectancy falls below the backtest's final chunk expectancy.",
            ),
            self._insight(
                "equity-pattern",
                "Equity Curve Pattern Recognition",
                "Synthetic-smooth risk" if underwater["frequency"] <= 1 and trade_count > 100 and dd_pct < 3 else "Spike driven" if top_profit_share >= 40 else "Organic curve",
                "warning" if top_profit_share >= 40 or (underwater["frequency"] <= 1 and trade_count > 100 and dd_pct < 3) else "positive",
                f"Stability {stability_score}",
                "Classifies the equity curve as smooth, unstable, spike-driven, or suspiciously optimized.",
                [
                    f"Drawdown periods: {underwater['frequency']}.",
                    f"Top 5 winner share: {top_profit_share:.1f}%.",
                    f"Longest underwater: {underwater['longest']} trades.",
                    f"Equity points: {len(equity)}.",
                ],
                "Compare with tick-by-tick modelling and out-of-sample equity to confirm the curve is not optimization luck.",
            ),
            self._insight(
                "backtest-quality",
                "Backtest Quality Verification",
                "Needs verification" if trade_count < 100 or scalping_score >= 70 or abs(expected_payoff) < broker_cost * 2 else "Reasonable sample",
                "warning" if trade_count < 100 or scalping_score >= 70 or abs(expected_payoff) < broker_cost * 2 else "positive",
                f"{trade_count} trades",
                "Checks sample size, fill realism, sub-spread scalping dependence, and broker-dependent profit risk.",
                [
                    f"Sample size: {trade_count}.",
                    f"Average duration: {avg_duration:.1f} min." if avg_duration else "Duration unavailable.",
                    f"Expected payoff versus cost proxy: {self._money(expected_payoff)} / {self._money(broker_cost)}.",
                    "Tick quality/modeling quality is only shown if the uploaded report exposes it.",
                ],
                "Use real tick data, variable spread, commission, and slippage settings before trusting this result live.",
            ),
            self._insight(
                "portfolio-compatibility",
                "Portfolio Compatibility",
                "Single-report mode",
                "info",
                metrics.symbol or "One symbol",
                "Current analysis uses one uploaded report, so true EA-to-EA correlation needs multiple reports.",
                [
                    f"Current symbol: {metrics.symbol or 'N/A'}.",
                    f"Directional bias: {direction['bias_pct']:.1f}%.",
                    f"Session concentration: {session_concentration:.1f}%.",
                    "Multi-report portfolio DD reduction can be added when multiple uploads are enabled.",
                ],
                "Upload several reports in a future portfolio workflow to calculate diversification score and combined drawdown.",
            ),
            self._insight(
                "strategy-dna",
                "Strategy DNA Report",
                "Fingerprint created",
                "warning" if dna["Recovery Dependence"] >= 60 or dna["Overfit Risk"] >= 60 else "positive",
                f"Risk DNA {100 - hidden_safety_score}/100",
                "Creates a compact identity profile for the EA so users can compare strategies quickly.",
                [
                    f"Aggression {dna['Aggression']}/100, Stability {dna['Stability']}/100.",
                    f"Recovery Dependence {dna['Recovery Dependence']}/100, Volatility Tolerance {dna['Volatility Tolerance']}/100.",
                    f"Scalping Sensitivity {dna['Scalping Sensitivity']}/100, Overfit Risk {dna['Overfit Risk']}/100.",
                    f"Personality: {', '.join(traits[:5])}.",
                ],
                "Use this DNA fingerprint to reject EAs that do not match the user's capital, broker, or prop-firm constraints.",
            ),
        ]

        summary = (
            f"Forensic AI reviewed {trade_count} parsed trades from the uploaded report only. "
            f"Hidden safety score is {hidden_safety_score}/100: {verdict}. "
            f"Reliability is {reliability_label} ({reliability_score}/100) with AI confidence {confidence_score}/100. "
            f"Main detected personality: {', '.join(traits[:3])}; key risks are "
            f"martingale/recovery {soft_martingale_probability}%, overfit {overfit_probability}%, "
            f"and Monte Carlo {self._rate_text(monte_carlo['survival_rate'], 'stress pass')}."
        )

        return HiddenDetailsResult(
            hidden_risk_score=hidden_safety_score,
            verdict=verdict,
            summary=summary,
            confidence_score=confidence_score,
            reliability_score=reliability_score,
            reliability_label=reliability_label,
            limitations=limitations,
            insights=insights[:20],
        )

    def _time_buckets(self, trades: List[TradeRecord], kind: str) -> Tuple[Dict[object, float], Dict[object, int]]:
        profits: Dict[object, float] = defaultdict(float)
        counts: Dict[object, int] = defaultdict(int)
        for trade in trades:
            dt = trade.open_time or trade.close_time
            if not dt:
                continue
            if kind == "hour":
                key = dt.hour
            elif kind == "month":
                key = dt.strftime("%b")
            else:
                key = dt.strftime("%A")
            profits[key] += trade.profit
            counts[key] += 1
        return dict(profits), dict(counts)

    def _directional_bias(self, trades: List[TradeRecord]) -> Dict[str, float]:
        buy_profit = sell_profit = 0.0
        buy_count = sell_count = 0
        for trade in trades:
            direction = (trade.type or "").lower()
            if "buy" in direction or direction == "long":
                buy_profit += trade.profit
                buy_count += 1
            elif "sell" in direction or direction == "short":
                sell_profit += trade.profit
                sell_count += 1
        total_abs = abs(buy_profit) + abs(sell_profit)
        bias_pct = (max(abs(buy_profit), abs(sell_profit)) / total_abs * 100) if total_abs else 0.0
        return {
            "buy_profit": round(buy_profit, 2),
            "sell_profit": round(sell_profit, 2),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "bias_pct": round(bias_pct, 2),
        }

    def _chunk_expectancy(self, profits: List[float], chunks: int = 4) -> List[float]:
        if not profits:
            return []
        size = max(1, len(profits) // chunks)
        result = []
        for index in range(0, len(profits), size):
            part = profits[index : index + size]
            if part:
                result.append(round(sum(part) / len(part), 2))
        return result[:chunks]

    def _max_drawdown_money(self, equity: List[float]) -> float:
        peak = equity[0] if equity else 0.0
        worst = 0.0
        for value in equity:
            peak = max(peak, value)
            worst = max(worst, peak - value)
        return round(worst, 2)

    def _underwater_stats(self, equity: List[float]) -> Dict[str, float]:
        if len(equity) < 2:
            return {"longest": 0, "average": 0.0, "frequency": 0, "pain_index": 0.0, "ulcer_index": 0.0}
        peak = equity[0]
        current = 0
        periods = []
        dd_pcts = []
        for value in equity:
            if value >= peak:
                peak = value
                if current:
                    periods.append(current)
                    current = 0
                dd_pcts.append(0.0)
                continue
            current += 1
            dd_pcts.append(((peak - value) / peak * 100) if peak else 0.0)
        if current:
            periods.append(current)
        pain = sum(dd_pcts) / len(dd_pcts) if dd_pcts else 0.0
        ulcer = (sum(value * value for value in dd_pcts) / len(dd_pcts)) ** 0.5 if dd_pcts else 0.0
        return {
            "longest": max(periods) if periods else 0,
            "average": round(sum(periods) / len(periods), 2) if periods else 0.0,
            "frequency": len(periods),
            "pain_index": round(pain, 2),
            "ulcer_index": round(ulcer, 2),
        }

    def _monte_carlo_projection(self, metrics: BacktestMetrics, profits: List[float]) -> Dict[str, float]:
        if not profits:
            return {"runs": 0, "median_final": metrics.deposit, "p05_final": metrics.deposit, "p95_drawdown": 0.0, "survival_rate": 0.0}
        rng = random.Random(42)
        runs = 400
        deposit = metrics.deposit or 0.0
        finals = []
        drawdowns = []
        ruin_threshold = deposit * 0.5 if deposit else -abs(sum(profits))
        avg_abs_trade = sum(abs(profit) for profit in profits) / len(profits)
        cost_stress = avg_abs_trade * 0.02
        for _ in range(runs):
            equity = deposit
            peak = equity
            worst_dd = 0.0
            for _ in profits:
                sampled = rng.choice(profits)
                if rng.random() < 0.03:
                    sampled = 0.0
                sampled -= cost_stress * rng.random()
                equity += sampled
                peak = max(peak, equity)
                worst_dd = max(worst_dd, peak - equity)
            finals.append(equity - deposit)
            drawdowns.append(worst_dd)
        finals_sorted = sorted(finals)
        drawdowns_sorted = sorted(drawdowns)
        survival = sum(1 for final in finals if deposit + final > ruin_threshold) / runs * 100
        return {
            "runs": runs,
            "median_final": round(finals_sorted[runs // 2], 2),
            "p05_final": round(finals_sorted[max(0, int(runs * 0.05) - 1)], 2),
            "p95_drawdown": round(drawdowns_sorted[min(runs - 1, int(runs * 0.95))], 2),
            "survival_rate": round(survival, 2),
        }

    def _risk_of_ruin_score(
        self,
        metrics: BacktestMetrics,
        dd_pct: float,
        pf: float,
        win_rate: float,
        longest_loss_streak: int,
        soft_martingale_probability: int,
        monte_carlo_survival: float,
    ) -> int:
        score = 10
        score += min(35, int(dd_pct * 1.5))
        score += 25 if pf and pf < 1.2 else 10 if pf and pf < 1.5 else 0
        score += 15 if win_rate < 45 else 0
        score += min(20, longest_loss_streak * 3)
        score += int(soft_martingale_probability * 0.25)
        score += max(0, int((80 - monte_carlo_survival) * 0.4))
        if metrics.net_profit <= 0:
            score += 20
        return max(0, min(100, score))

    def _broker_cost_proxy(self, avg_lot: float) -> float:
        return max(0.5, avg_lot * 10.0) if avg_lot else 1.0

    def _analysis_reliability(
        self, metrics: BacktestMetrics, trades: List[TradeRecord], durations: List[float]
    ) -> Tuple[int, str, List[str]]:
        trade_count = metrics.total_trades or len(trades)
        score = 25
        max_score = 100
        limitations: List[str] = []
        dated_trades = [trade for trade in trades if trade.open_time or trade.close_time]
        if dated_trades:
            dates = sorted((trade.open_time or trade.close_time) for trade in dated_trades)
            days_covered = max(1, (dates[-1] - dates[0]).days + 1)
            months_covered = days_covered / 30.44
            if months_covered < 3:
                score = 38
                max_score = 54
                limitations.append(f"Short backtest window: about {months_covered:.1f} months, so regime confidence is low.")
            elif months_covered < 6:
                score = 62
                max_score = 74
                limitations.append(f"Medium backtest window: about {months_covered:.1f} months. Good for a first filter, still needs forward testing.")
            elif months_covered < 12:
                score = 78
                max_score = 88
                limitations.append(f"Strong calendar coverage: about {months_covered:.1f} months of trading history.")
            else:
                score = 86
                max_score = 100
                limitations.append(f"Very strong calendar coverage: about {months_covered:.1f} months of trading history.")

            trades_per_month = trade_count / max(months_covered, 0.1)
            if trade_count and trades_per_month < 5:
                limitations.append(
                    f"Sparse-trading EA: {trade_count} trades over {months_covered:.1f} months. Confidence is judged by time coverage, not trade count alone."
                )
        else:
            if trade_count >= 500:
                score = 68
            elif trade_count >= 200:
                score = 58
            elif trade_count >= 50:
                score = 48
            elif trade_count > 0:
                score = 35
            limitations.append("Backtest date range was not available, so reliability falls back to trade sample and parsed metrics.")

        if trade_count <= 0:
            limitations.append("No parsed trade table was available, so forensic analysis is limited.")

        if durations:
            score += 5
        else:
            limitations.append("Trade duration confidence is limited because paired open/close times were incomplete.")

        if any(trade.size for trade in trades):
            score += 5
        else:
            limitations.append("Lot progression confidence is limited because lot/volume data was not available.")

        if metrics.maximal_drawdown or metrics.maximal_drawdown_pct:
            score += 5
        else:
            limitations.append("Drawdown confidence is limited because the report did not expose max drawdown clearly.")

        if metrics.profit_factor and metrics.expected_payoff:
            score += 3

        if metrics.net_profit < 0 or (metrics.profit_factor and metrics.profit_factor < 1):
            limitations.append("Negative performance means confidence supports rejection or redesign, not live deployment.")

        score = max(0, min(max_score, score))
        if score >= 75:
            label = "Strong"
        elif score >= 55:
            label = "Medium"
        else:
            label = "Low"
        if not limitations:
            limitations.append("Reliability is based on parsed trades, timestamps, lot data, drawdown, and sample size.")
        return score, label, limitations[:4]

    def _rate_text(self, rate: float, label: str) -> str:
        if rate >= 99.5:
            return f">=99% {label}"
        return f"{rate:.1f}% {label}"

    def _score(self, category: str, score: float, summary: str, details: List[str]) -> ScoreData:
        score = max(0, min(100, round(score)))
        if score >= 85:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 55:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"
        return ScoreData(category=category, score=score, grade=grade, summary=summary, details=details)

    def _longest_loss_streak(self, trades: List[TradeRecord]) -> int:
        longest = current = 0
        for trade in trades:
            if trade.profit < 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    def _longest_win_streak(self, trades: List[TradeRecord]) -> int:
        longest = current = 0
        for trade in trades:
            if trade.profit > 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    def _pct(self, value: float, base: float) -> float:
        return round((value / base) * 100, 2) if value and base else 0.0

    def _money(self, value: float) -> str:
        return f"${value:,.2f}"

    def _pct_text(self, value: float) -> str:
        return f"{value:.2f}%" if value else "N/A"

    def _value_or_na(self, value: float) -> str:
        return f"{value:.2f}" if value else "N/A"

    def _drawdown_text(self, money: float, pct: float) -> str:
        if money and pct:
            return f"{self._money(money)} ({pct:.2f}%)"
        if pct:
            return f"{pct:.2f}%"
        if money:
            return self._money(money)
        return "N/A"
