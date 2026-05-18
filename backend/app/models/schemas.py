from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class TradeRecord(BaseModel):
    ticket: Optional[str] = None
    open_time: Optional[datetime] = None
    type: str  # buy, sell
    size: float
    item: str
    price: float
    s_l: Optional[float] = None
    t_p: Optional[float] = None
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    commission: float = 0.0
    taxes: float = 0.0
    swap: float = 0.0
    profit: float
    balance: Optional[float] = None
    comment: Optional[str] = None
    duration_minutes: Optional[float] = None
    magic_number: Optional[str] = None
    spread_at_entry: Optional[float] = None
    requested_price: Optional[float] = None
    fill_price: Optional[float] = None
    slippage: Optional[float] = None
    news_time: Optional[datetime] = None
    news_event: Optional[str] = None
    news_impact: Optional[str] = None
    volatility_at_entry: Optional[float] = None
    entry_signal_strength: Optional[float] = None
    market_regime: Optional[str] = None
    equity_at_entry: Optional[float] = None
    equity_at_exit: Optional[float] = None
    mfe: Optional[float] = None
    mae: Optional[float] = None
    entry_efficiency: Optional[float] = None
    exit_efficiency: Optional[float] = None
    trailing_stop_efficiency: Optional[float] = None
    rejected_orders: Optional[int] = None
    order_modification_count: Optional[int] = None
    strategy_tag: Optional[str] = None
    partial_close_id: Optional[str] = None
    partial_close_fraction: Optional[float] = None

class BacktestMetrics(BaseModel):
    ea_name: Optional[str] = None
    symbol: Optional[str] = None
    period: Optional[str] = None
    deposit: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    expected_payoff: float = 0.0
    maximal_drawdown: float = 0.0
    maximal_drawdown_pct: float = 0.0
    total_trades: int = 0
    short_positions_win_pct: float = 0.0
    long_positions_win_pct: float = 0.0
    win_rate: float = 0.0
    average_profit: float = 0.0
    average_loss: float = 0.0
    consecutive_wins_max: int = 0
    consecutive_losses_max: int = 0
    sharpe_ratio: float = 0.0
    recovery_factor: float = 0.0
    risk_reward_ratio: float = 0.0
    average_trade_duration: float = 0.0
    balance_drawdown_absolute: Optional[str] = None
    balance_drawdown_maximal: Optional[str] = None
    balance_drawdown_relative: Optional[str] = None
    equity_drawdown_absolute: Optional[str] = None
    equity_drawdown_maximal: Optional[str] = None
    equity_drawdown_relative: Optional[str] = None
    backtest_spread: Optional[str] = None

class ScoreData(BaseModel):
    category: str
    score: int
    grade: str
    summary: str
    details: List[str]

class HiddenInsight(BaseModel):
    id: str
    title: str
    status: str
    severity: str
    value: str
    summary: str
    evidence: List[str]
    recommendation: str

class HiddenDetailsResult(BaseModel):
    hidden_risk_score: int
    verdict: str
    summary: str
    confidence_score: int = 0
    reliability_score: int = 0
    reliability_label: str = "Unknown"
    limitations: List[str] = Field(default_factory=list)
    insights: List[HiddenInsight]

class DetailedMetric(BaseModel):
    key: str
    label: str
    value: Any
    status: str = "available"
    description: Optional[str] = None

class DetailedAnalysisResult(BaseModel):
    summary: str
    summary_cards: List[DetailedMetric] = Field(default_factory=list)
    metric_groups: Dict[str, List[DetailedMetric]] = Field(default_factory=dict)
    trade_rows: List[Dict[str, Any]] = Field(default_factory=list)
    total_trade_rows: int = 0
    unavailable_metrics: List[DetailedMetric] = Field(default_factory=list)

class AIAnalysisResult(BaseModel):
    verdict: str  # PASS, CAUTION, FAIL, DANGEROUS
    verdict_color: str
    overall_score: int
    executive_summary: str
    profitability_score: ScoreData
    risk_score: ScoreData
    stability_score: ScoreData
    survivability_score: ScoreData
    prop_firm_score: ScoreData
    strengths: List[str]
    weaknesses: List[str]
    hidden_risks: List[str]
    recommendations: List[str]
    risk_analysis: str
    broker_requirements: str
    prop_firm_safety: str
    slippage_sensitivity: str
    broker_dependency_level: str
    long_term_survivability: str
    estimated_account_lifetime: str
    overfitting_probability: int
    overfitting_indicators: List[str]
    trade_behavior_summary: str
    equity_analysis: str
    hidden_details: HiddenDetailsResult

class BehaviorAnalysis(BaseModel):
    is_martingale: bool = False
    martingale_confidence: float = 0.0
    is_grid: bool = False
    grid_confidence: float = 0.0
    is_hedging: bool = False
    hedging_confidence: float = 0.0
    is_scalping: bool = False
    scalping_confidence: float = 0.0
    is_averaging_down: bool = False
    averaging_confidence: float = 0.0
    lot_escalation_detected: bool = False
    lot_escalation_factor: float = 0.0
    overtrading_detected: bool = False
    dangerous_recovery_system: bool = False
    balance_based_lot_growth_detected: bool = False
    avg_lot: float = 0.0
    min_lot: float = 0.0
    max_lot: float = 0.0
    lot_std_dev: float = 0.0
    session_distribution: Dict[str, int] = {}

class MonteCarloResult(BaseModel):
    simulations: List[List[float]] = Field(default_factory=list)
    ruin_probability: float = 0.0
    median_max_drawdown_pct: float = 0.0
    worst_case_drawdown_pct: float = 0.0

class ForensicAnalysis(BaseModel):
    monte_carlo: MonteCarloResult = Field(default_factory=MonteCarloResult)
    underwater_curve: List[float] = Field(default_factory=list)
    equity_underwater_curve: List[float] = Field(default_factory=list)
    max_concurrent_trades: int = 0
    max_concurrent_lots: float = 0.0
    dependency_top_10_pct: float = 0.0
    mae_mfe_available: bool = False
    mae_mfe_data: List[Dict[str, Any]] = Field(default_factory=list)

class PropFirmRuleResult(BaseModel):
    firm_id: str
    firm_name: str
    passed: bool
    daily_loss_limit_pct: float
    max_drawdown_limit_pct: float
    violations: List[str] = Field(default_factory=list)
    details: List[str] = Field(default_factory=list)

class PropFirmCheckResult(BaseModel):
    deposit: float = 0.0
    overall_pass: bool = False
    rules: List[PropFirmRuleResult] = Field(default_factory=list)
    worst_day_loss_pct: float = 0.0
    max_equity_drawdown_pct: float = 0.0

class MonthlyHeatmapCell(BaseModel):
    year: int
    month: int
    profit: float
    trades: int
    drawdown_pct: float = 0.0

class DrawdownRecoveryStats(BaseModel):
    longest_underwater_trades: int = 0
    average_recovery_trades: float = 0.0
    underwater_periods: int = 0
    time_underwater_pct: float = 0.0

class LossCluster(BaseModel):
    start_time: str
    end_time: str
    loss_count: int
    total_loss: float
    duration_minutes: float

class LotEscalationPoint(BaseModel):
    index: int
    lot: float
    cumulative_profit: float

class SessionStats(BaseModel):
    session: str
    trades: int
    profit: float
    win_rate: float

class SymbolSpreadInsight(BaseModel):
    primary_symbol: str
    symbol_profit_breakdown: Dict[str, float] = Field(default_factory=dict)
    backtest_spread: str = "Unknown"
    spread_sensitivity: str = "Unknown"
    symbol_concentration_pct: float = 0.0
    notes: List[str] = Field(default_factory=list)

class DepositScenario(BaseModel):
    label: str
    deposit: float
    scaled_max_dd_pct: float
    scaled_net_profit: float
    prop_viable: bool

class VerdictEvidence(BaseModel):
    rule: str
    value: str
    impact: str  # pass, warn, fail

class ActionItem(BaseModel):
    id: str
    text: str
    priority: str  # high, medium, low
    category: str

class DataQualityAssessment(BaseModel):
    score: int
    label: str
    level: str
    signals: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

class WhatIfDefaults(BaseModel):
    deposit: float = 10000.0
    max_drawdown_pct: float = 5.0
    daily_loss_pct: float = 5.0
    target_profit_pct: float = 10.0

class ExtendedAnalysisResult(BaseModel):
    prop_firm_check: PropFirmCheckResult = Field(default_factory=PropFirmCheckResult)
    monthly_heatmap: List[MonthlyHeatmapCell] = Field(default_factory=list)
    drawdown_recovery: DrawdownRecoveryStats = Field(default_factory=DrawdownRecoveryStats)
    loss_clusters: List[LossCluster] = Field(default_factory=list)
    lot_escalation: List[LotEscalationPoint] = Field(default_factory=list)
    session_breakdown: List[SessionStats] = Field(default_factory=list)
    symbol_spread: SymbolSpreadInsight = Field(default_factory=SymbolSpreadInsight)
    deposit_scenarios: List[DepositScenario] = Field(default_factory=list)
    verdict_evidence: List[VerdictEvidence] = Field(default_factory=list)
    data_quality: DataQualityAssessment = Field(default_factory=DataQualityAssessment)
    action_checklist: List[ActionItem] = Field(default_factory=list)
    what_if_defaults: WhatIfDefaults = Field(default_factory=WhatIfDefaults)

class AnalysisResponse(BaseModel):
    metrics: BacktestMetrics
    behavior: BehaviorAnalysis
    ai_analysis: AIAnalysisResult
    detailed_analysis: DetailedAnalysisResult
    forensic_analysis: ForensicAnalysis
    extended_analysis: ExtendedAnalysisResult = Field(default_factory=ExtendedAnalysisResult)
    equity_curve: List[float]
    trades_count: int
    report_type: str
