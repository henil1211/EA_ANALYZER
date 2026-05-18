"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Brain,
  Shield,
  Building2,
  TrendingUp,
  GitCompare,
  Lightbulb,
  FileText,
} from "lucide-react";
import FileUpload from "@/components/FileUpload";
import ScoreCards from "@/components/ScoreCards";
import AIVerdict from "@/components/AIVerdict";
import EquityChart from "@/components/EquityChart";
import MetricsOverview from "@/components/MetricsOverview";
import TradeBehavior from "@/components/TradeBehavior";
import RiskAnalysisPanel from "@/components/RiskAnalysisPanel";
import HiddenDetails from "@/components/HiddenDetails";
import DetailedAnalysis from "@/components/DetailedAnalysis";
import LiveSimulator from "@/components/LiveSimulator";
import ForensicDeepDive from "@/components/ForensicDeepDive";
import ExtendedInsightsPanel from "@/components/extended/ExtendedInsightsPanel";
import CompareEAs from "@/components/extended/CompareEAs";
import HistoryShareBar from "@/components/extended/HistoryShareBar";
import { analyzeReport } from "@/lib/api";
import { loadShareFromUrl, saveToHistory, createShareLink } from "@/lib/analysisStorage";

type TabKey =
  | "overview"
  | "simulator"
  | "verdict"
  | "risk"
  | "behavior"
  | "equity"
  | "hidden"
  | "forensic"
  | "insights"
  | "detailed"
  | "summary";

const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "overview", label: "Overview", icon: <TrendingUp className="w-4 h-4" /> },
  { key: "simulator", label: "Live Simulator", icon: <Lightbulb className="w-4 h-4" /> },
  { key: "verdict", label: "AI Verdict", icon: <Brain className="w-4 h-4" /> },
  { key: "risk", label: "Risk Analysis", icon: <Shield className="w-4 h-4" /> },
  { key: "behavior", label: "Trade Behavior", icon: <Activity className="w-4 h-4" /> },
  { key: "equity", label: "Equity Curve", icon: <TrendingUp className="w-4 h-4" /> },
  { key: "hidden", label: "Hidden Details", icon: <Shield className="w-4 h-4" /> },
  { key: "forensic", label: "Forensic Deep Dive", icon: <Activity className="w-4 h-4" /> },
  { key: "insights", label: "Insights Hub", icon: <Lightbulb className="w-4 h-4" /> },
  { key: "detailed", label: "Detailed Analysis", icon: <FileText className="w-4 h-4" /> },
  { key: "summary", label: "Summary", icon: <Building2 className="w-4 h-4" /> },
];

export default function Home() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [mainView, setMainView] = useState<"analyzer" | "history">("analyzer");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [lastFileName, setLastFileName] = useState("");

  useEffect(() => {
    const shared = loadShareFromUrl();
    if (shared) {
      setData(shared as Record<string, unknown>);
      setActiveTab("overview");
    }
  }, []);

  const handleAnalyze = async (file: File) => {
    setLoading(true);
    setError("");
    try {
      const result = await analyzeReport(file);
      setData(result);
      setLastFileName(file.name);
      saveToHistory(result, file.name);
      setMainView("analyzer");
      setActiveTab("overview");
    } catch (e: any) {
      setError(e.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const ai = data?.ai_analysis;
  const m = data?.metrics;

  // Derived summary labels
  const scoreValue = typeof ai?.overall_score === 'number' ? ai.overall_score : 0;
  const scorePct = Math.max(0, Math.min(100, scoreValue));
  const finalBalance = Array.isArray(data?.equity_curve) && data.equity_curve.length
    ? Number(data.equity_curve[data.equity_curve.length - 1])
    : null;
  const startBalance = typeof m?.start_balance === 'number' ? m.start_balance : null;
  const profitDeltaPct = finalBalance !== null && startBalance ? (((finalBalance - startBalance) / Math.max(1, startBalance)) * 100).toFixed(2) : null;
  const formatTwoDecimals = (value: unknown) => {
    const numericValue = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(numericValue) ? numericValue.toFixed(2) : 'N/A';
  };
  const equityDrawdown = m?.max_equity_drawdown ?? m?.equity_drawdown_maximal ?? m?.maximal_drawdown_pct ?? null;
  const topRisks = ((ai?.hidden_risks && ai.hidden_risks.length ? ai.hidden_risks : ai?.risks) || []).slice(0, 3).map((r: any) => (typeof r === 'string' ? r : (r.title || r.name || r)));
  const topImprovements = (ai?.improvement_opportunities || ai?.recommendations || []).slice(0, 3).map((r: any) => (typeof r === 'string' ? r : (r.text || r)));

  const overallScore = ai?.overall_score;
  const liveLabel = typeof overallScore === 'number' ? (overallScore >= 75 ? 'Ready' : overallScore >= 50 ? 'Caution' : 'Not Recommended') : (ai?.verdict || 'Unknown');
  const propFirmLabel = ai?.prop_firm_safety || 'Unknown';
  const liveReason = ai?.executive_summary || ai?.verdict || '';

  const brokerLevel = (m?.broker_dependency_level || ai?.broker_dependency_level || 'unknown').toString().toLowerCase();
  const brokerExplanation = brokerLevel === 'high'
    ? 'High: EA is sensitive to broker conditions — requires low spreads, low slippage, reliable fills, and VPS near the broker server.'
    : brokerLevel === 'medium'
    ? 'Medium: EA benefits from moderate spreads and good execution; monitor slippage and latency.'
    : brokerLevel === 'low'
    ? 'Low: EA is robust across common broker conditions but still monitor execution.'
    : 'Unknown broker sensitivity.';
  const eaSpecificSummary = (() => {
    const riskText = [
      ...(ai?.hidden_risks || []),
      ...(ai?.risks || []),
      ...(ai?.weaknesses || []),
    ]
      .map((item: any) => (typeof item === 'string' ? item : (item?.title || item?.name || item?.text || '')))
      .join(' ')
      .toLowerCase();

    const behaviorText = [ai?.trade_behavior_summary, ai?.risk_summary, ai?.executive_summary, ai?.verdict]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    if (/martingale|grid/.test(riskText) || /martingale|grid/.test(behaviorText)) {
      return 'Grid / martingale behavior is present, so this EA is more fragile and less suitable for prop-firm style evaluation.';
    }

    if (brokerLevel === 'high') {
      return 'This EA is highly broker-sensitive and needs tight spreads, low slippage, and stable execution to hold up well.';
    }

    if (typeof overallScore === 'number' && overallScore >= 75) {
      return 'This EA is comparatively stronger, with a cleaner profile for live-style use and fewer visible stability concerns.';
    }

    if ((propFirmLabel || '').toLowerCase().includes('danger') || (propFirmLabel || '').toLowerCase().includes('poor')) {
      return 'Prop-firm compatibility looks weak because the current risk profile does not look robust enough for funded-account rules.';
    }

    if (liveReason) {
      return liveReason;
    }

    return 'This EA summary is based on the current risk, execution, and behavior signals in the report.';
  })();

  return (
    <div className="min-h-screen bg-background text-foreground font-sans">
      <header className="sticky top-0 z-50 glass-strong border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl gradient-primary flex items-center justify-center shadow-lg shadow-primary/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">EA Analyzer</h1>
              <p className="text-[10px] text-muted-foreground -mt-0.5 uppercase tracking-widest font-semibold">AI Risk Audit</p>
            </div>
          </div>

          <p className="hidden md:block text-xs font-bold text-muted-foreground">Telegram Contact - @vivek_1840</p>

          {(data || isCompareMode) && (
            <div className="flex items-center gap-2">
              {data && !isCompareMode && (
                <button
                  onClick={() => setMainView("history")}
                  className={`text-xs font-semibold transition-all px-4 py-2 rounded-xl border ${mainView === "history" ? "bg-primary text-white border-primary shadow-lg shadow-primary/20" : "text-muted-foreground hover:text-foreground hover:bg-muted border-transparent hover:border-border"}`}
                >
                  History
                </button>
              )}
              <button
                onClick={() => { setData(null); setIsCompareMode(false); setMainView("analyzer"); setError(""); setActiveTab("overview"); }}
                className="text-xs font-medium text-muted-foreground hover:text-foreground transition-all px-4 py-2 rounded-xl hover:bg-muted border border-transparent hover:border-border"
              >
                New Analysis
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {isCompareMode && !data ? (
          <div className="space-y-6">
            <CompareEAs onBack={() => setIsCompareMode(false)} />
          </div>
        ) : !data ? (
          <div className="flex flex-col items-center justify-center min-h-[75vh]">
            <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: "easeOut" }} className="text-center mb-12">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-[10px] font-bold uppercase tracking-wider mb-6">
                <Brain className="w-3 h-3" /> Powered by GPT-4o
              </div>
              <h2 className="text-5xl md:text-6xl font-black gradient-text mb-6 tracking-tight">Institutional-Grade <br/>EA Auditing</h2>
              <p className="text-muted-foreground max-w-2xl mx-auto text-lg leading-relaxed font-medium">Professional quantitative risk analysis for MetaTrader backtest reports. Identify hidden Martingale, Grid, and Overfitting in seconds.</p>
            </motion.div>

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] w-full max-w-6xl">
              <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="glass-strong rounded-3xl border border-white/5 p-6 md:p-8 shadow-2xl shadow-black/20">
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.28em] text-primary/80">Single EA Test</p>
                    <h3 className="mt-2 text-2xl font-black tracking-tight">Upload one backtest report</h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">Run a full AI audit on one MT4 or MT5 report, then open the summary, risk, and trade breakdown tabs.</p>
                  </div>
                  <div className="hidden md:flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/15">
                    <FileText className="h-5 w-5" />
                  </div>
                </div>
                <div className="flex justify-center lg:justify-start">
                  <FileUpload onAnalyze={handleAnalyze} isLoading={loading} />
                </div>
                {error && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }} className="mt-6 flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-sm font-medium text-destructive">
                    <Shield className="w-4 h-4" />
                    <span>{error}</span>
                  </motion.div>
                )}
              </motion.section>

              <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.5 }} className="glass-strong rounded-3xl border border-white/5 p-6 md:p-8 shadow-2xl shadow-black/20">
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.28em] text-primary/80">Comparison Mode</p>
                    <h3 className="mt-2 text-2xl font-black tracking-tight">Compare up to 3 EAs</h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">Drop multiple reports to see which EA is stronger across profit, drawdown, and prop-firm safety.</p>
                  </div>
                  <div className="hidden md:flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/15">
                    <GitCompare className="h-5 w-5" />
                  </div>
                </div>

                <div className="rounded-3xl border border-dashed border-border bg-black/20 p-6 md:p-8 text-center transition-colors hover:border-primary/50 hover:bg-muted/20">
                  <GitCompare className="mx-auto h-10 w-10 text-primary" />
                  <p className="mt-4 text-lg font-bold">Stress-test multiple backtests together</p>
                  <p className="mt-2 text-sm text-muted-foreground">Best for side-by-side strategy selection and risk comparison before live deployment.</p>
                  <button onClick={() => setIsCompareMode(true)} className="mt-6 inline-flex items-center gap-2 rounded-xl border border-border bg-muted/40 px-6 py-3 text-sm font-bold text-foreground shadow-md transition-all duration-300 hover:bg-muted">
                    <GitCompare className="h-4 w-4 text-primary" />
                    Open Comparison
                  </button>
                </div>
              </motion.section>
            </div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6, duration: 0.8 }} className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-14 w-full max-w-4xl">
              {[
                { icon: <Shield className="w-5 h-5" />, title: "Risk Auditor", desc: "Institutional safety check" },
                { icon: <Brain className="w-5 h-5" />, title: "AI Intelligence", desc: "Deep pattern recognition" },
                { icon: <Building2 className="w-5 h-5" />, title: "Prop Firm Lab", desc: "Rule compliance audit" },
                { icon: <TrendingUp className="w-5 h-5" />, title: "Curve Analysis", desc: "Stability & drawdown test" },
              ].map((f, i) => (
                <div key={i} className="glass rounded-2xl p-6 text-center hover:glow transition-all duration-500 border border-white/5">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-inner">{f.icon}</div>
                  <p className="mb-1 text-sm font-bold text-foreground">{f.title}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{f.desc}</p>
                </div>
              ))}
            </motion.div>
          </div>
        ) : (
          <motion.div className="space-y-8">
            {mainView === "history" ? (
              <HistoryShareBar data={data} fileName={lastFileName} onRestore={(snapshot) => { setData(snapshot as Record<string, any>); setMainView("analyzer"); setActiveTab("overview"); }} onBack={() => setMainView("analyzer")} />
            ) : (
              <>
                <div className="space-y-3 pb-4 -mx-2 px-2">
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
                    {tabs.slice(0, 6).map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`flex min-h-12 items-center justify-center gap-2.5 rounded-2xl px-5 py-3 text-sm font-bold transition-all duration-300 ${activeTab === tab.key ? "bg-primary text-white shadow-xl shadow-primary/30 scale-[1.02]" : "text-muted-foreground hover:text-foreground hover:bg-muted border border-transparent hover:border-border"}`}
                      >
                        {tab.icon}{tab.label}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                    {tabs.slice(6).map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`flex min-h-12 items-center justify-center gap-2.5 rounded-2xl px-5 py-3 text-sm font-bold transition-all duration-300 ${activeTab === tab.key ? "bg-primary text-white shadow-xl shadow-primary/30 scale-[1.02]" : "text-muted-foreground hover:text-foreground hover:bg-muted border border-transparent hover:border-border"}`}
                      >
                        {tab.icon}{tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                <AnimatePresence mode="wait">
                  <motion.div key={activeTab} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -15 }} transition={{ duration: 0.4, ease: "easeOut" }}>
                    {activeTab === "overview" && (
                      <div className="space-y-8">
                        <MetricsOverview metrics={m || {}} />
                        {ai && <ScoreCards profitability={ai.profitability_score} risk={ai.risk_score} stability={ai.stability_score} survivability={ai.survivability_score} propFirm={ai.prop_firm_score} overall={ai.overall_score || 0} />}
                        {data?.equity_curve?.length > 0 && <EquityChart data={data.equity_curve} />}
                      </div>
                    )}

                    {activeTab === "simulator" && <LiveSimulator metrics={m || {}} behavior={data?.behavior || {}} tradeRows={data?.detailed_analysis?.trade_rows || []} equityCurve={data?.equity_curve || []} />}

                    {activeTab === "verdict" && ai && <AIVerdict verdict={ai.verdict} verdictColor={ai.verdict_color} summary={ai.executive_summary} strengths={ai.strengths || []} weaknesses={ai.weaknesses || []} hiddenRisks={ai.hidden_risks || []} recommendations={ai.recommendations || []} />}

                    {activeTab === "risk" && ai && <RiskAnalysisPanel riskAnalysis={ai.risk_analysis} brokerRequirements={ai.broker_requirements} propFirmSafety={ai.prop_firm_safety} slippageSensitivity={ai.slippage_sensitivity} brokerDependency={ai.broker_dependency_level} survivability={ai.long_term_survivability} riskSummary={ai.risk_summary} />}

                    {activeTab === "behavior" && <TradeBehavior behavior={data?.behavior || {}} summary={ai?.trade_behavior_summary} />}

                    {activeTab === "equity" && <EquityChart data={data?.equity_curve || []} analysis={ai?.equity_analysis} />}


                    {activeTab === "hidden" && ai && <HiddenDetails details={ai.hidden_details} />}

                    {activeTab === "forensic" && data?.forensic_analysis && <ForensicDeepDive data={data} />}

                    {activeTab === "insights" && <ExtendedInsightsPanel data={data as Record<string, any>} />}

                    {activeTab === "detailed" && data?.detailed_analysis && <DetailedAnalysis details={data.detailed_analysis} />}

                    {activeTab === "summary" && ai && (
                      <div className="space-y-6">
                        <div className="rounded-3xl border border-white/5 bg-gradient-to-b from-white/5 to-black/20 p-5 shadow-2xl shadow-black/20 lg:p-6">
                          <div className="flex flex-col gap-5 border-b border-white/5 pb-5 xl:flex-row xl:items-start xl:justify-between">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2.5">
                                <span className={`inline-flex items-center rounded-full px-3.5 py-1 text-sm font-bold ${scoreValue >= 75 ? 'bg-emerald-500 text-black' : scoreValue >= 50 ? 'bg-amber-400 text-black' : 'bg-rose-500 text-white'}`}>
                                  {liveLabel}
                                </span>
                                <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs font-semibold text-muted-foreground">
                                  {propFirmLabel}
                                </span>
                                <span className="inline-flex items-center rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs font-semibold text-muted-foreground">
                                  {m?.symbol || 'Symbol N/A'}
                                </span>
                              </div>

                              <div className="mt-4">
                                <h3 className="text-2xl font-black tracking-tight md:text-3xl">{m?.ea_name || lastFileName || 'Unnamed EA'}</h3>
                                <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                                  {liveReason || 'Managed summary view with performance, risk, and improvement context.'}
                                </p>
                              </div>
                            </div>

                            <div className="grid min-w-[260px] grid-cols-2 gap-3">
                              <div className="rounded-2xl border border-white/5 bg-black/25 p-4">
                                <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">Overall Score</p>
                                <div className="mt-3 flex items-center gap-4">
                                  <div
                                    className="flex h-16 w-16 items-center justify-center rounded-full"
                                    style={{ background: `conic-gradient(#f59e0b ${scorePct}%, rgba(255,255,255,0.08) 0)` }}
                                  >
                                    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-black/90 text-base font-black">
                                      {scoreValue || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    Decision score
                                  </div>
                                </div>
                              </div>
                              <div className="rounded-2xl border border-white/5 bg-black/25 p-4">
                                <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">Broker Sens.</p>
                                <p className="mt-3 text-2xl font-black capitalize">{brokerLevel}</p>
                                <p className="mt-1 text-xs text-muted-foreground">{m?.broker_dependency_level || ai?.broker_dependency_level || 'N/A'}</p>
                              </div>
                            </div>
                          </div>

                          <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]">
                            <div className="space-y-4">
                              <div className="rounded-3xl border border-white/5 bg-black/20 p-5">
                                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Performance & Core Metrics</p>
                                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Win Rate</p>
                                    <p className="mt-2 text-2xl font-black">{m?.win_rate ?? m?.winrate ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Profit Factor</p>
                                    <p className="mt-2 text-2xl font-black">{m?.profit_factor ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Sharpe Ratio</p>
                                    <p className="mt-2 text-2xl font-black">{m?.sharpe_ratio ?? m?.sharpe ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Starting Balance</p>
                                    <p className="mt-2 text-2xl font-black">{m?.start_balance ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Total Net Profit</p>
                                    <p className="mt-2 text-2xl font-black">{typeof m?.net_profit !== 'undefined' ? formatTwoDecimals(m.net_profit) : (typeof m?.profit !== 'undefined' ? formatTwoDecimals(m.profit) : 'N/A')}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Final Equity</p>
                                    <p className="mt-2 text-2xl font-black">{finalBalance !== null ? finalBalance : 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Max Drawdown</p>
                                    <p className="mt-2 text-2xl font-black">{m?.maximal_drawdown_pct ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Max Equity DD</p>
                                    <p className="mt-2 text-2xl font-black">{equityDrawdown ?? 'N/A'}</p>
                                  </div>
                                  <div className="rounded-2xl bg-white/5 p-4">
                                    <p className="text-xs text-muted-foreground">Trades</p>
                                    <p className="mt-2 text-2xl font-black">{m?.trades_count ?? data?.detailed_analysis?.total_trade_rows ?? 'N/A'}</p>
                                  </div>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                <div className="rounded-3xl border border-white/5 bg-black/20 p-5">
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-bold">Primary Risks</p>
                                    <span className="text-xs text-muted-foreground">Top 3</span>
                                  </div>
                                  <ul className="mt-4 space-y-3">
                                    {topRisks.length > 0 ? topRisks.map((risk: any, index: number) => (
                                      <li key={index} className="flex gap-3 rounded-2xl bg-white/5 px-4 py-3 text-sm text-muted-foreground">
                                        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-bold text-foreground">{index + 1}</span>
                                        <span className="leading-6">{risk}</span>
                                      </li>
                                    )) : (
                                      <li className="rounded-2xl bg-white/5 px-4 py-3 text-sm text-muted-foreground">No specific risks identified in summary.</li>
                                    )}
                                  </ul>
                                </div>

                                <div className="rounded-3xl border border-white/5 bg-black/20 p-5">
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="text-sm font-bold">Key Improvements</p>
                                    <span className="text-xs text-muted-foreground">Actionable</span>
                                  </div>
                                  <ul className="mt-4 space-y-3">
                                    {topImprovements.length > 0 ? topImprovements.map((item: any, index: number) => (
                                      <li key={index} className="flex gap-3 rounded-2xl bg-white/5 px-4 py-3 text-sm text-muted-foreground">
                                        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">{index + 1}</span>
                                        <span className="leading-6">{item}</span>
                                      </li>
                                    )) : (
                                      <li className="rounded-2xl bg-white/5 px-4 py-3 text-sm text-muted-foreground">No quick improvements detected.</li>
                                    )}
                                  </ul>
                                </div>
                              </div>
                            </div>

                            <div className="space-y-4">
                              <div className="rounded-3xl border border-white/5 bg-black/20 p-5">
                                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Performance & Risk</p>
                                <div className="mt-4 flex items-start justify-between gap-4 border-b border-white/5 pb-4">
                                  <div>
                                    <p className="text-sm text-muted-foreground">Overall score</p>
                                    <p className="text-3xl font-black">{scoreValue || 'N/A'}</p>
                                  </div>
                                  <div className="text-right">
                                    <p className="text-sm text-muted-foreground">Broker sensitivity</p>
                                    <p className="text-2xl font-black capitalize">{brokerLevel}</p>
                                  </div>
                                </div>

                                <div className="mt-4 rounded-2xl border border-white/5 bg-black/15 p-4">
                                  <p className="text-sm font-semibold">Prop Firm Risk Assessment</p>
                                  <p className="mt-3 text-2xl font-black leading-tight">Live readiness: {liveLabel}</p>
                                  <p className="mt-2 text-sm font-semibold text-muted-foreground">Broker sensitivity: {brokerLevel}</p>
                                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                                    {eaSpecificSummary}
                                  </p>
                                </div>
                              </div>

                              <div className="rounded-3xl border border-white/5 bg-black/20 p-5">
                                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Broker Sensitivity Profile</p>
                                <p className="mt-3 text-xl font-black capitalize">{brokerLevel}</p>
                                <p className="mt-2 text-sm leading-6 text-muted-foreground">{brokerExplanation}</p>
                              </div>
                            </div>
                          </div>

                          <div className="mt-6 flex flex-col gap-4 border-t border-white/5 pt-5 md:flex-row md:items-center md:justify-between">
                            <div className="text-sm text-muted-foreground">
                              {m?.ea_name || lastFileName || 'Unnamed EA'} • {new Date().toLocaleString()}
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => {
                                  const summaryText = `${m?.ea_name || lastFileName || 'EA'} — Score: ${scoreValue || 'N/A'}; Live: ${propFirmLabel}; Risks: ${topRisks.join('; ') || 'none'}; Improvements: ${topImprovements.join('; ') || 'none'}`;
                                  navigator.clipboard?.writeText(summaryText);
                                }}
                                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold transition-colors hover:bg-white/10"
                              >
                                Copy Summary
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  const url = createShareLink(data as Record<string, unknown>);
                                  navigator.clipboard?.writeText(url);
                                }}
                                className="rounded-full border border-primary/30 bg-primary/15 px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/25"
                              >
                                Copy Share Link
                              </button>
                              <button
                                type="button"
                                onClick={() => saveToHistory(data as Record<string, unknown>, lastFileName)}
                                className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold transition-colors hover:bg-white/10"
                              >
                                Save
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
              </>
            )}
          </motion.div>
        )}
      </main>

      <footer className="mt-auto border-t border-border py-10 bg-muted/20">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3 opacity-50">
            <Activity className="w-4 h-4" />
            <p className="text-xs font-bold uppercase tracking-widest">EA ANALYZER V1.0</p>
          </div>
          <p className="text-xs font-bold text-muted-foreground">Telegram Contact - @vivek_1840</p>
          <p className="text-xs font-bold text-primary/60">ADVANCED EA ANALYZER ENGINE ENABLED</p>
        </div>
      </footer>
    </div>
  );
}
