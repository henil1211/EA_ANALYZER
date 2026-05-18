"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { ArrowLeft, GitCompare, X } from "lucide-react";
import { analyzeReport } from "@/lib/api";
import { createShareLink } from "@/lib/analysisStorage";
import MetricsOverview from "@/components/MetricsOverview";
import AIVerdict from "@/components/AIVerdict";
import EquityChart from "@/components/EquityChart";
import ScoreCards from "@/components/ScoreCards";
import TradeBehavior from "@/components/TradeBehavior";
import RiskAnalysisPanel from "@/components/RiskAnalysisPanel";
import HiddenDetails from "@/components/HiddenDetails";
import DetailedAnalysis from "@/components/DetailedAnalysis";
import ForensicDeepDive from "@/components/ForensicDeepDive";
import LiveSimulator from "@/components/LiveSimulator";
import ExtendedInsightsPanel from "@/components/extended/ExtendedInsightsPanel";

type Row = {
  name: string;
  verdict: string;
  score: number;
  netProfit: number;
  pf: number;
  equityDd: number;
  trades: number;
  propPass: boolean;
};

const formatTwoDecimals = (value: unknown) => {
  const numericValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue.toFixed(2) : "N/A";
};

type CompareEAsProps = {
  onBack?: () => void;
};

const compareSections = [
  { key: 'overview', label: 'Overview' },
  { key: 'simulator', label: 'Live Simulator' },
  { key: 'verdict', label: 'AI Verdict' },
  { key: 'risk', label: 'Risk Analysis' },
  { key: 'behavior', label: 'Trade Behavior' },
  { key: 'equity', label: 'Equity Curve' },
  { key: 'hidden', label: 'Hidden Details' },
  { key: 'forensic', label: 'Forensic Deep Dive' },
  { key: 'insights', label: 'Insights Hub' },
  { key: 'detailed', label: 'Detailed Analysis' },
  { key: 'summary', label: 'Summary' },
];

export default function CompareEAs({ onBack }: CompareEAsProps) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("Upload 1 to 3 files, then start comparison when ready.");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [globalSection, setGlobalSection] = useState<string>("overview");

  const updateStatusMessage = (count: number) => {
    if (count <= 0) {
      setStatusMessage("Upload 1 to 3 files, then start comparison when ready.");
      return;
    }

    if (count === 1) {
      setStatusMessage("1 file uploaded. Add 1 more file to enable comparison.");
      return;
    }

    if (count === 2) {
      setStatusMessage("2 files ready. Add a 3rd file or click Start comparison.");
      return;
    }

    setStatusMessage("3 files ready. Click Start comparison.");
  };

  const startComparison = async () => {
    if (selectedFiles.length < 2) {
      setError("Please upload at least 2 files before starting comparison.");
      return;
    }

    setLoading(true);
    setError("");
    setStatusMessage("");

    try {
      const limited = selectedFiles.slice(0, 3);
      const results = await Promise.all(limited.map((f) => analyzeReport(f)));
      setResults(results);
      setSelectedFiles([]);
      const parsed: Row[] = results.map((data, i) => {
        const m = data.metrics || {};
        const ai = data.ai_analysis || {};
        const ext = data.extended_analysis || {};
        const equityDd =
          ext.prop_firm_check?.max_equity_drawdown_pct ?? m.maximal_drawdown_pct ?? 0;
        return {
          name: m.ea_name || m.symbol || limited[i].name,
          verdict: ai.verdict || "—",
          score: ai.overall_score ?? 0,
          netProfit: m.net_profit ?? 0,
          pf: m.profit_factor ?? 0,
          equityDd,
          trades: m.total_trades ?? 0,
          propPass: ext.prop_firm_check?.overall_pass ?? false,
        };
      });
      setRows(parsed);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  const onDrop = async (files: File[]) => {
    if (!files.length) return;
    const mergedFiles = [...selectedFiles, ...files].slice(0, 3);

    setSelectedFiles(mergedFiles);
    setError("");
    updateStatusMessage(mergedFiles.length);
  };

  const removeSelectedFile = (indexToRemove: number) => {
    const nextFiles = selectedFiles.filter((_, index) => index !== indexToRemove);
    setSelectedFiles(nextFiles);
    setError("");
    updateStatusMessage(nextFiles.length);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/html": [".html", ".htm"], "text/csv": [".csv"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    multiple: true,
    maxFiles: 3,
  });

  const best = rows.length ? rows.reduce((a, b) => (b.score > a.score ? b : a)) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.3em] text-primary/80">Comparison Mode</p>
          <h3 className="mt-2 text-2xl font-black tracking-tight">Compare 2 to 3 EAs</h3>
        </div>
        {onBack && (
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-muted/40 px-4 py-2 text-sm font-semibold text-foreground transition-all hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </button>
        )}
      </div>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-3xl p-12 text-center cursor-pointer transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
        }`}
      >
        <input {...getInputProps()} />
        <GitCompare className="w-10 h-10 mx-auto text-primary mb-4" />
        <p className="font-bold">Drop 1 to 3 backtest reports to compare</p>
        <p className="text-xs text-muted-foreground mt-2">HTML, CSV, or XLSX</p>
        {!loading && <p className="mt-4 text-sm text-amber-400">{statusMessage}</p>}
        {loading && <p className="text-sm text-primary mt-4">Analyzing…</p>}
      </div>

      {selectedFiles.length > 0 && !loading && (
        <div className="rounded-2xl border border-white/5 bg-white/5 p-4">
          <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Selected files ({selectedFiles.length}/3)</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedFiles.map((file, index) => (
              <span key={`${file.name}-${file.size}-${index}`} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 py-1 pl-3 pr-1 text-xs text-foreground">
                <span className="max-w-[220px] truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeSelectedFile(index)}
                  className="inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                  aria-label={`Remove ${file.name}`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              onClick={startComparison}
              disabled={selectedFiles.length < 2}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-bold text-white transition-all disabled:cursor-not-allowed disabled:opacity-40"
            >
              Start comparison
            </button>
            {selectedFiles.length < 3 ? (
              <span className="text-xs text-muted-foreground">
                {selectedFiles.length === 2
                  ? "You can still add one more file before starting."
                  : "Add one more file to enable comparison."}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">Maximum 3 files reached. Click Start comparison.</span>
            )}
          </div>
        </div>
      )}

      {error && <p className="text-sm text-rose-400">{error}</p>}

      {rows.length > 0 && (
        <div className="glass-strong rounded-3xl p-6 border border-white/5 overflow-x-auto">
          <table className="w-full min-w-[980px] table-fixed text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-widest text-muted-foreground">
                <th className="w-[24%] px-4 py-2">EA</th>
                <th className="w-[15%] px-4 py-2">Verdict</th>
                <th className="w-[8%] px-4 py-2 text-center">Score</th>
                <th className="w-[15%] px-4 py-2">Net $</th>
                <th className="w-[8%] px-4 py-2 text-center">PF</th>
                <th className="w-[12%] px-4 py-2 text-center">Equity DD</th>
                <th className="w-[8%] px-4 py-2 text-center">Trades</th>
                <th className="w-[10%] px-4 py-2 text-right">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={`${r.name}-${i}`}
                  className={`border-t border-white/5 ${best?.name === r.name ? "bg-primary/10" : ""}`}
                >
                  <td className="px-4 py-3 font-bold truncate" title={r.name}>{r.name}</td>
                  <td className="px-4 py-3 truncate" title={r.verdict}>{r.verdict}</td>
                  <td className="px-4 py-3 text-center">{r.score}</td>
                  <td className={`px-4 py-3 truncate ${r.netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    ${r.netProfit.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-center">{r.pf.toFixed(2)}</td>
                  <td className="px-4 py-3 text-center">{r.equityDd.toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">{r.trades}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setOpenIndex(openIndex === i ? null : i)}
                      className="text-xs font-medium text-primary underline"
                    >
                      {openIndex === i ? "Hide" : "View"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {best && (
            <p className="text-xs text-muted-foreground mt-4">
              Highest score: <strong className="text-primary">{best.name}</strong> ({best.score}/100)
            </p>
          )}
          {openIndex !== null && results[openIndex] && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="glass rounded-2xl p-6 border border-white/5">
                <h4 className="text-lg font-bold mb-2">AI Summary — {rows[openIndex].name}</h4>
                <p className="text-sm text-foreground/80 mb-3">{results[openIndex].ai_analysis?.executive_summary || "No executive summary available."}</p>
                {(results[openIndex].ai_analysis?.strengths || []).length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-bold text-muted-foreground uppercase mb-2">Strengths</p>
                    <ul className="list-disc ml-5 text-sm">
                      {results[openIndex].ai_analysis.strengths.map((s: string, idx: number) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(results[openIndex].ai_analysis?.weaknesses || []).length > 0 && (
                  <div>
                    <p className="text-xs font-bold text-muted-foreground uppercase mb-2">Weaknesses</p>
                    <ul className="list-disc ml-5 text-sm">
                      {results[openIndex].ai_analysis.weaknesses.map((w: string, idx: number) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="glass rounded-2xl p-6 border border-white/5">
                <h4 className="text-lg font-bold mb-2">Key Metrics</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="text-muted-foreground">Net Profit</div>
                  <div className={results[openIndex].metrics?.net_profit >= 0 ? "text-emerald-400" : "text-rose-400"}>${(results[openIndex].metrics?.net_profit ?? 0).toLocaleString()}</div>
                  <div className="text-muted-foreground">Profit Factor</div>
                  <div>{(results[openIndex].metrics?.profit_factor ?? 0).toFixed(2)}</div>
                  <div className="text-muted-foreground">Max Drawdown</div>
                  <div>{(results[openIndex].extended_analysis?.prop_firm_check?.max_equity_drawdown_pct ?? results[openIndex].metrics?.maximal_drawdown_pct ?? 0).toFixed(2)}%</div>
                  <div className="text-muted-foreground">Trades</div>
                  <div>{results[openIndex].metrics?.total_trades ?? 0}</div>
                </div>
              </div>
            </div>
          )}
          {/* Full side-by-side report view (simplified for compile) */}
          {results.length > 0 && (
            <div className="mt-8">
              <h3 className="text-lg font-bold mb-4">Full Report Comparison</h3>

              <div className="space-y-3 mb-4">
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
                  {compareSections.slice(0, 6).map((s) => (
                    <button
                      key={s.key}
                      onClick={() => setGlobalSection(s.key)}
                      className={`w-full rounded-2xl px-5 py-3 text-sm font-semibold transition-all ${globalSection === s.key ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground'}`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                  {compareSections.slice(6).map((s) => (
                    <button
                      key={s.key}
                      onClick={() => setGlobalSection(s.key)}
                      className={`w-full rounded-2xl px-5 py-3 text-sm font-semibold transition-all ${globalSection === s.key ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground'}`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-8">
                <div className="flex flex-col gap-8">
                  {results.map((data, idx) => {
                    const ai = data.ai_analysis || {};
                    const metrics = data.metrics || {};
                    const sec = globalSection;
                    const scoreValue = typeof ai.overall_score === 'number' ? ai.overall_score : 0;
                    const scorePct = Math.max(0, Math.min(100, scoreValue));
                    const finalBalance = Array.isArray(data.equity_curve) && data.equity_curve.length
                      ? Number(data.equity_curve[data.equity_curve.length - 1])
                      : null;
                    const equityDrawdown = data.extended_analysis?.prop_firm_check?.max_equity_drawdown_pct ?? metrics.max_equity_drawdown ?? metrics.maximal_drawdown_pct ?? null;
                    const topRisks = ((ai.hidden_risks && ai.hidden_risks.length ? ai.hidden_risks : ai.risks) || []).slice(0, 3).map((r: any) => (typeof r === 'string' ? r : (r.title || r.name || r)));
                    const topImprovements = (ai.improvement_opportunities || ai.recommendations || []).slice(0, 3).map((r: any) => (typeof r === 'string' ? r : (r.text || r)));
                    const liveLabel = typeof ai.overall_score === 'number' ? (ai.overall_score >= 75 ? 'Ready' : ai.overall_score >= 50 ? 'Caution' : 'Not Recommended') : (ai.verdict || 'Unknown');
                    const propFirmLabel = ai.prop_firm_safety || 'Unknown';
                    const liveReason = ai.executive_summary || ai.verdict || '';
                    const brokerLevel = (metrics.broker_dependency_level || ai.broker_dependency_level || 'unknown').toString().toLowerCase();
                    const brokerExplanation = brokerLevel === 'high'
                      ? 'High: EA is sensitive to broker conditions — requires low spreads, low slippage, reliable fills, and VPS near the broker server.'
                      : brokerLevel === 'medium'
                      ? 'Medium: EA benefits from moderate spreads and good execution; monitor slippage and latency.'
                      : brokerLevel === 'low'
                      ? 'Low: EA is robust across common broker conditions but still monitor execution.'
                      : 'Unknown broker sensitivity.';
                    const eaSpecificSummary = (() => {
                      const riskText = [
                        ...(ai.hidden_risks || []),
                        ...(ai.risks || []),
                        ...(ai.weaknesses || []),
                      ]
                        .map((item: any) => (typeof item === 'string' ? item : (item?.title || item?.name || item?.text || '')))
                        .join(' ')
                        .toLowerCase();

                      const behaviorText = [ai.trade_behavior_summary, ai.risk_summary, ai.executive_summary, ai.verdict]
                        .filter(Boolean)
                        .join(' ')
                        .toLowerCase();

                      if (/martingale|grid/.test(riskText) || /martingale|grid/.test(behaviorText)) {
                        return 'Grid / martingale behavior is present, so this EA is more fragile and less suitable for prop-firm style evaluation.';
                      }

                      if (brokerLevel === 'high') {
                        return 'This EA is highly broker-sensitive and needs tight spreads, low slippage, and stable execution to hold up well.';
                      }

                      if (typeof ai.overall_score === 'number' && ai.overall_score >= 75) {
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
                      <div key={idx} className={`space-y-4 w-full break-words ${idx > 0 ? 'pt-12 border-t-2 border-white/15 mt-12' : ''}`}>
                        <div className="rounded-2xl border border-white/10 bg-muted/20 px-5 py-3 shadow-inner shadow-black/20">
                          <div className="flex items-center gap-3">
                            <div className="h-px flex-1 bg-white/10" />
                            <span className="rounded-full bg-primary/15 px-3 py-1 text-[10px] font-black uppercase tracking-[0.35em] text-primary border border-primary/20">
                              {idx === 0 ? 'First EA Report' : `EA ${idx + 1} Begins Here`}
                            </span>
                            <div className="h-px flex-1 bg-white/10" />
                          </div>
                        </div>

                        <div className="glass-strong rounded-2xl p-4 border border-white/5 w-full shadow-[0_0_0_1px_rgba(255,255,255,0.03)]">
                          <div className="flex items-start justify-between">
                            <div>
                              <h4 className="text-md font-bold">{metrics.ea_name || metrics.symbol || `EA ${idx + 1}`}</h4>
                              <p className="text-xs text-muted-foreground">{metrics.period ? `${metrics.symbol || ''} • ${metrics.period}` : metrics.symbol}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-xs text-muted-foreground">Verdict</p>
                              <p className="font-bold text-primary">{ai.verdict || '—'}</p>
                            </div>
                          </div>
                        </div>

                        <div className="w-full">
                          {sec === 'overview' && (
                            <div className="space-y-8">
                              <MetricsOverview metrics={metrics} />
                              <ScoreCards
                                profitability={ai.profitability_score}
                                risk={ai.risk_score}
                                stability={ai.stability_score}
                                survivability={ai.survivability_score}
                                propFirm={ai.prop_firm_score}
                                overall={ai.overall_score || 0}
                              />
                              {data.equity_curve?.length > 0 && <EquityChart data={data.equity_curve} analysis={ai.equity_analysis} />}
                            </div>
                          )}

                          {sec === 'simulator' && (
                            <LiveSimulator
                              metrics={metrics}
                              behavior={data.behavior || {}}
                              tradeRows={data.detailed_analysis?.trade_rows || []}
                              equityCurve={data.equity_curve || []}
                            />
                          )}

                          {sec === 'verdict' && (
                            <AIVerdict
                              verdict={ai.verdict || 'N/A'}
                              verdictColor={ai.verdict_color || ''}
                              summary={ai.executive_summary || ''}
                              strengths={ai.strengths || []}
                              weaknesses={ai.weaknesses || []}
                              hiddenRisks={ai.hidden_risks || []}
                              recommendations={ai.recommendations || []}
                            />
                          )}

                          {sec === 'equity' && <EquityChart data={data.equity_curve || []} analysis={ai.equity_analysis} />}

                          {sec === 'behavior' && <TradeBehavior behavior={data.behavior || {}} summary={ai.trade_behavior_summary} />}

                          {sec === 'risk' && (
                            <RiskAnalysisPanel
                              riskAnalysis={ai.risk_analysis}
                              brokerRequirements={ai.broker_requirements}
                              propFirmSafety={ai.prop_firm_safety}
                              slippageSensitivity={ai.slippage_sensitivity}
                              brokerDependency={ai.broker_dependency_level}
                              survivability={ai.long_term_survivability}
                              accountLifetime={ai.estimated_account_lifetime}
                              overfittingProbability={ai.overfitting_probability}
                              overfittingIndicators={ai.overfitting_indicators || []}
                              riskSummary={ai.risk_summary}
                            />
                          )}

                          {sec === 'hidden' && <HiddenDetails details={ai.hidden_details} />}

                          {sec === 'detailed' && <DetailedAnalysis details={data.detailed_analysis} />}

                          {sec === 'forensic' && <ForensicDeepDive data={data} />}

                          {sec === 'insights' && <ExtendedInsightsPanel data={data} />}

                          {sec === 'summary' && (
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
                                        {metrics?.symbol || 'Symbol N/A'}
                                      </span>
                                    </div>

                                    <div className="mt-4">
                                      <h3 className="text-2xl font-black tracking-tight md:text-3xl">{metrics?.ea_name || rows[idx]?.name || `EA ${idx + 1}`}</h3>
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
                                      <p className="mt-1 text-xs text-muted-foreground">{metrics?.broker_dependency_level || ai?.broker_dependency_level || 'N/A'}</p>
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
                                          <p className="mt-2 text-2xl font-black">{metrics?.win_rate ?? metrics?.winrate ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Profit Factor</p>
                                          <p className="mt-2 text-2xl font-black">{metrics?.profit_factor ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Sharpe Ratio</p>
                                          <p className="mt-2 text-2xl font-black">{metrics?.sharpe_ratio ?? metrics?.sharpe ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Starting Balance</p>
                                          <p className="mt-2 text-2xl font-black">{metrics?.start_balance ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Total Net Profit</p>
                                          <p className="mt-2 text-2xl font-black">{typeof metrics?.net_profit !== 'undefined' ? formatTwoDecimals(metrics.net_profit) : (typeof metrics?.profit !== 'undefined' ? formatTwoDecimals(metrics.profit) : 'N/A')}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Final Equity</p>
                                          <p className="mt-2 text-2xl font-black">{finalBalance !== null ? finalBalance : 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Max Drawdown</p>
                                          <p className="mt-2 text-2xl font-black">{metrics?.maximal_drawdown_pct ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Max Equity DD</p>
                                          <p className="mt-2 text-2xl font-black">{equityDrawdown ?? 'N/A'}</p>
                                        </div>
                                        <div className="rounded-2xl bg-white/5 p-4">
                                          <p className="text-xs text-muted-foreground">Trades</p>
                                          <p className="mt-2 text-2xl font-black">{metrics?.trades_count ?? data?.detailed_analysis?.total_trade_rows ?? 'N/A'}</p>
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
                                        <p className="mt-3 text-sm leading-6 text-muted-foreground">{eaSpecificSummary}</p>
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
                                    {metrics?.ea_name || rows[idx]?.name || `EA ${idx + 1}`} • {new Date().toLocaleString()}
                                  </div>

                                  <div className="flex flex-wrap items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        const summaryText = `${metrics?.ea_name || rows[idx]?.name || `EA ${idx + 1}`} — Score: ${scoreValue || 'N/A'}; Live: ${propFirmLabel}; Risks: ${topRisks.join('; ') || 'none'}; Improvements: ${topImprovements.join('; ') || 'none'}`;
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
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
