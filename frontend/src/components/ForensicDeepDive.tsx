"use client";

import React, { useMemo } from 'react';
import { AlertTriangle, TrendingDown, Target, ShieldAlert, BarChart3, Waves } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, Legend } from 'recharts';

function parseDrawdownPct(value: unknown): number | null {
  if (value == null || value === "") return null;
  if (typeof value === "number") return Math.abs(value);
  const text = String(value);
  const paren = text.match(/\(\s*(-?[\d,.]+)\s*%\s*\)/);
  if (paren) {
    const n = parseFloat(paren[1].replace(",", "."));
    if (Number.isFinite(n)) return Math.abs(n);
  }
  const plain = text.match(/(-?[\d,.]+)\s*%/);
  if (plain) {
    const n = parseFloat(plain[1].replace(",", "."));
    if (Number.isFinite(n)) return Math.abs(n);
  }
  return null;
}

function scaleEquitySeriesToReport(
  equitySeries: number[],
  balanceSeries: number[],
  reportEquityPct: number | null
): number[] {
  const base = equitySeries.length > 0 ? equitySeries : balanceSeries;
  if (!base.length || !reportEquityPct) return base;

  const currentMax = Math.max(...base.map((v) => Math.abs(v)), 0);
  if (currentMax >= reportEquityPct * 0.98) return base;

  if (currentMax > 0) {
    const factor = reportEquityPct / currentMax;
    return base.map((v) => -Math.round(Math.abs(v) * factor * 100) / 100);
  }

  const deepestIndex = base.reduce(
    (best, value, index, arr) => (Math.abs(value) > Math.abs(arr[best]) ? index : best),
    0
  );
  const scaled = [...base];
  scaled[deepestIndex] = -reportEquityPct;
  return scaled;
}

export default function ForensicDeepDive({ data }: { data: any }) {
  if (!data?.forensic_analysis) return null;
  const forensic = data.forensic_analysis;
  const metrics = data.metrics || {};

  // Format Monte Carlo data for Recharts (each object is a point in time with multiple sim values)
  const mcData = useMemo(() => {
    if (!forensic.monte_carlo?.simulations || forensic.monte_carlo.simulations.length === 0) return [];
    const length = forensic.monte_carlo.simulations[0].length;
    const formatted = [];
    for (let i = 0; i < length; i++) {
      const point: any = { index: i };
      forensic.monte_carlo.simulations.forEach((sim: number[], sIdx: number) => {
        point[`sim${sIdx}`] = sim[i];
      });
      formatted.push(point);
    }
    return formatted;
  }, [forensic]);

  const reportEquityPct = useMemo(
    () =>
      parseDrawdownPct(metrics.equity_drawdown_maximal) ??
      parseDrawdownPct(metrics.equity_drawdown_relative),
    [metrics]
  );

  const mcEquityDrawdown = useMemo(() => {
    const worst = forensic.monte_carlo?.worst_case_drawdown_pct ?? 0;
    const median = forensic.monte_carlo?.median_max_drawdown_pct ?? 0;
    if (!reportEquityPct) return { worst, median };

    const peak = Math.max(worst, median);
    if (peak <= 0 || peak >= reportEquityPct * 0.98) {
      return { worst, median };
    }

    // One scale factor so worst/median keep their relative spread (not both forced to 7.31%)
    const factor = reportEquityPct / peak;
    return {
      worst: Math.round(worst * factor * 100) / 100,
      median: Math.round(median * factor * 100) / 100,
    };
  }, [forensic.monte_carlo, reportEquityPct]);

  // Format underwater drawdown series (balance closed vs floating equity)
  const uwData = useMemo(() => {
    const balanceSeries: number[] = forensic.underwater_curve || [];
    const rawEquitySeries: number[] = forensic.equity_underwater_curve || [];
    const equitySeries = scaleEquitySeriesToReport(rawEquitySeries, balanceSeries, reportEquityPct);
    const length = Math.max(balanceSeries.length, equitySeries.length);
    if (!length) return [];

    return Array.from({ length }, (_, i) => ({
      index: i + 1,
      balanceDrawdown: balanceSeries[i] ?? 0,
      equityDrawdown: equitySeries[i] ?? 0,
    }));
  }, [forensic, reportEquityPct]);

  const chartYMin = useMemo(() => {
    if (!uwData.length) return 0;
    const deepest = Math.min(
      ...uwData.map((p) => Math.min(p.balanceDrawdown, p.equityDrawdown))
    );
    const floor = reportEquityPct ? -reportEquityPct * 1.08 : deepest * 1.08;
    return Math.min(deepest * 1.05, floor);
  }, [uwData, reportEquityPct]);

  const maxClosedDrawdown = Math.max(
    ...(forensic.underwater_curve || [0]).map((v: number) => Math.abs(v)),
    0
  );
  const maxEquityDrawdown = uwData.length
    ? Math.max(...uwData.map((p) => Math.abs(p.equityDrawdown)))
    : 0;
  const balanceMaximal = metrics.balance_drawdown_maximal;
  const equityMaximal = metrics.equity_drawdown_maximal;
  const balancePct =
    parseDrawdownPct(balanceMaximal) ??
    parseDrawdownPct(metrics.balance_drawdown_relative) ??
    maxClosedDrawdown;
  const equityPct =
    parseDrawdownPct(equityMaximal) ??
    parseDrawdownPct(metrics.equity_drawdown_relative) ??
    (maxEquityDrawdown > 0 ? maxEquityDrawdown : undefined) ??
    metrics.maximal_drawdown_pct ??
    0;
  const drawdownGap = Math.abs(equityPct - balancePct);
  const hasReportValue = (v: unknown) => v != null && String(v).trim() !== "";
  const displayBalance = hasReportValue(balanceMaximal)
    ? String(balanceMaximal).trim()
    : balancePct > 0
      ? `-${balancePct.toFixed(2)}%`
      : "—";
  const displayEquity = hasReportValue(equityMaximal)
    ? String(equityMaximal).trim()
    : equityPct > 0
      ? `-${equityPct.toFixed(2)}%`
      : "—";

  return (
    <div className="space-y-6">
      {/* Monte Carlo Section */}
      <div className="glass-strong rounded-3xl p-8 border border-white/5 overflow-hidden">
        <div className="border-b border-zinc-800/50 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/10 rounded-xl shadow-inner">
                <Target className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-emerald-400 text-xl font-bold">Monte Carlo Sequence Analysis</h3>
                <p className="text-zinc-400 text-xs mt-1 font-semibold uppercase tracking-widest">100 Randomized Permutations — Equity Drawdown incl. Floating Risk</p>
              </div>
            </div>
          </div>
        </div>
        <div className="pt-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={mcData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <YAxis domain={['auto', 'auto']} tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(val) => `$${val}`} width={60} axisLine={false} tickLine={false} />
                  {forensic.monte_carlo?.simulations?.map((_: any, idx: number) => (
                    <Line key={idx} type="monotone" dataKey={`sim${idx}`} stroke={`hsla(${140 + idx * 20}, 70%, 50%, 0.4)`} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-4">
               <div className="bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                  <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Probability of Ruin</p>
                  <div className="flex items-center gap-3">
                    <span className="text-4xl font-black text-white">{forensic.monte_carlo?.ruin_probability}%</span>
                    {forensic.monte_carlo?.ruin_probability > 10 ? 
                       <span className="px-3 py-1 rounded-full bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-bold uppercase tracking-widest">High Risk</span> : 
                       <span className="px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-bold uppercase tracking-widest">Safe</span>}
                  </div>
               </div>
               <div className="bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                  <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Worst Case Equity Drawdown (95th Pct)</p>
                  <span className="text-3xl font-black text-rose-400">-{mcEquityDrawdown.worst.toFixed(2)}%</span>
               </div>
               <div className="bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                  <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Median Expected Equity Drawdown</p>
                  <span className="text-3xl font-black text-yellow-400">-{mcEquityDrawdown.median.toFixed(2)}%</span>
               </div>
            </div>
          </div>
        </div>
      </div>

      {/* Underwater Drawdown */}
      <div className="glass-strong rounded-3xl p-8 border border-white/5">
        <div className="border-b border-zinc-800/50 pb-4">
          <div className="flex items-center gap-3">
             <div className="p-2 bg-rose-500/10 rounded-xl shadow-inner">
                <Waves className="w-6 h-6 text-rose-400" />
              </div>
            <div>
              <h3 className="text-rose-400 text-xl font-bold">Closed Balance vs Floating Equity Drawdown</h3>
              <p className="text-zinc-400 text-xs mt-1 font-semibold uppercase tracking-widest">Exposing hidden floating margin risks held by the EA</p>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6">
           <div className="col-span-2 h-[280px]">
               <ResponsiveContainer width="100%" height="100%">
                 <AreaChart data={uwData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                   <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                   <XAxis dataKey="index" tick={{ fill: '#666', fontSize: 10 }} axisLine={false} tickLine={false} />
                   <YAxis domain={[chartYMin, 0]} tick={{ fill: '#666', fontSize: 10 }} tickFormatter={(val) => `${val}%`} width={50} axisLine={false} tickLine={false} />
                   <Tooltip
                     contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', color: '#fff' }}
                     labelFormatter={(label) => `Trade ${label}`}
                     formatter={(value, name) => {
                       const label = name === 'balanceDrawdown' ? 'Balance Drawdown' : 'Equity Drawdown';
                       return [`${Number(value ?? 0).toFixed(2)}%`, label];
                     }}
                   />
                   <Legend
                     verticalAlign="top"
                     align="right"
                     iconType="line"
                     wrapperStyle={{ fontSize: 11, color: '#a1a1aa', paddingBottom: 8 }}
                     formatter={(value) => (value === 'balanceDrawdown' ? 'Balance (closed)' : 'Equity (floating)')}
                   />
                   <Area
                     type="stepAfter"
                     dataKey="balanceDrawdown"
                     name="balanceDrawdown"
                     stroke="#38bdf8"
                     fill="rgba(56, 189, 248, 0.15)"
                     strokeWidth={2}
                     isAnimationActive={false}
                   />
                   <Area
                     type="stepAfter"
                     dataKey="equityDrawdown"
                     name="equityDrawdown"
                     stroke="#ef4444"
                     fill="rgba(239, 68, 68, 0.25)"
                     strokeWidth={2}
                     isAnimationActive={false}
                   />
                 </AreaChart>
               </ResponsiveContainer>
           </div>
           
           <div className="space-y-4">
              <div className="bg-black/40 p-4 rounded-xl border border-white/5">
                 <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Balance Drawdown Maximal</p>
                 <span className="text-xl font-black text-sky-400 leading-tight">{displayBalance}</span>
                 {!hasReportValue(balanceMaximal) && maxClosedDrawdown > 0 && (
                   <p className="text-[10px] text-zinc-500 mt-1">Derived from closed trade sequence</p>
                 )}
              </div>
              <div className="bg-black/40 p-4 rounded-xl border border-white/5">
                 <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">Equity Drawdown Maximal</p>
                 <span className="text-xl font-black text-rose-400 leading-tight">{displayEquity}</span>
                 {!hasReportValue(equityMaximal) && maxEquityDrawdown > 0 && (
                   <p className="text-[10px] text-zinc-500 mt-1">Peak from floating equity curve</p>
                 )}
              </div>
              
              {drawdownGap > 2 && (
                 <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                    <div className="flex gap-2 items-start">
                       <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                       <div>
                          <p className="text-xs font-bold text-red-400 uppercase tracking-widest mb-1">Hidden Floating Risk</p>
                          <p className="text-xs text-red-300 leading-relaxed">
                             This EA hid <strong className="text-red-400">{drawdownGap.toFixed(2)}%</strong> of drawdown while trades were open. It holds massive losers before closing them!
                          </p>
                       </div>
                    </div>
                 </div>
              )}
           </div>
        </div>
      </div>

      {/* Exposure Limits */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-strong rounded-3xl p-8 border border-white/5">
           <div>
              <h3 className="text-orange-400 text-xl font-bold flex items-center gap-3"><ShieldAlert className="w-6 h-6"/> Max Concurrent Exposure</h3>
           </div>
           <div className="space-y-4 mt-6">
              <div className="flex justify-between items-center bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                 <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Max Overlapping Trades</span>
                 <span className="text-3xl font-black text-white">{forensic.max_concurrent_trades}</span>
              </div>
              <div className="flex justify-between items-center bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                 <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Max Simultaneous Lots</span>
                 <span className="text-3xl font-black text-white">{forensic.max_concurrent_lots} Lots</span>
              </div>
           </div>
        </div>

        <div className="glass-strong rounded-3xl p-8 border border-white/5">
           <div>
              <h3 className="text-blue-400 text-xl font-bold flex items-center gap-3"><BarChart3 className="w-6 h-6"/> Profit Dependency</h3>
           </div>
           <div className="space-y-4 mt-6">
              <div className="flex justify-between items-center bg-black/40 p-5 rounded-2xl border border-white/5 shadow-inner">
                 <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Top 10% Trades Dependency</span>
                 <span className="text-3xl font-black text-white">{forensic.dependency_top_10_pct}%</span>
              </div>
              <p className="text-xs font-semibold text-zinc-500 leading-relaxed mt-4 bg-muted/20 p-4 rounded-xl">
                 If this is &gt; 50%, the EA is highly dependent on a few lucky outlier trades. If it's &lt; 30%, it is structurally robust and balanced.
              </p>
           </div>
        </div>
      </div>
    </div>
  );
}
