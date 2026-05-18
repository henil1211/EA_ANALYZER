"use client";

import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import {
  Building2,
  Calendar,
  TrendingDown,
  Layers,
  Globe,
  DollarSign,
  ListChecks,
  Sliders,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import AuditPdfExport from "./AuditPdfExport";

type Props = { data: Record<string, any> };

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export default function ExtendedInsightsPanel({ data }: Props) {
  const ext = data.extended_analysis || {};
  const whatIf = ext.what_if_defaults || { deposit: 10000, max_drawdown_pct: 5, daily_loss_pct: 5, target_profit_pct: 10 };
  const [ddLimit, setDdLimit] = useState(whatIf.max_drawdown_pct);
  const [dailyLimit, setDailyLimit] = useState(whatIf.daily_loss_pct);
  const [deposit, setDeposit] = useState(whatIf.deposit);

  const whatIfResult = useMemo(() => {
    const equityDd = ext.prop_firm_check?.max_equity_drawdown_pct ?? ddLimit;
    const passDd = equityDd <= ddLimit;
    const passDaily = (ext.prop_firm_check?.worst_day_loss_pct ?? 0) <= dailyLimit;
    const buffer = deposit * (1 - ddLimit / 100);
    return { passDd, passDaily, pass: passDd && passDaily, buffer: Math.round(buffer) };
  }, [ext, ddLimit, dailyLimit, deposit]);

  const heatmapChart = useMemo(() => {
    return (ext.monthly_heatmap || []).map((c: any) => ({
      label: `${MONTHS[c.month - 1]} ${c.year}`,
      profit: c.profit,
      trades: c.trades,
    }));
  }, [ext.monthly_heatmap]);

  const impactColor = (impact: string) =>
    impact === "pass" ? "text-emerald-400" : impact === "warn" ? "text-amber-400" : "text-rose-400";

  return (
    <motion.div className="space-y-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <motion.div className="flex flex-wrap gap-3 justify-end">
        <AuditPdfExport data={data} />
      </motion.div>

      {/* Prop firm rules */}
      <Section title="Prop Firm Rule Checker" icon={<Building2 className="w-5 h-5 text-purple-400" />}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <Stat label="Worst day loss" value={`${ext.prop_firm_check?.worst_day_loss_pct ?? 0}%`} />
          <Stat label="Max equity DD" value={`${ext.prop_firm_check?.max_equity_drawdown_pct ?? 0}%`} />
        </div>
        <motion.div className="space-y-3">
          {(ext.prop_firm_check?.rules || []).map((rule: any) => (
            <div
              key={rule.firm_id}
              className={`p-4 rounded-xl border ${rule.passed ? "border-emerald-500/30 bg-emerald-500/5" : "border-rose-500/30 bg-rose-500/5"}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-sm">{rule.firm_name}</span>
                {rule.passed ? (
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> PASS
                  </span>
                ) : (
                  <span className="text-xs font-bold text-rose-400 flex items-center gap-1">
                    <XCircle className="w-4 h-4" /> FAIL
                  </span>
                )}
              </div>
              {rule.violations?.map((v: string, i: number) => (
                <p key={i} className="text-xs text-rose-300">
                  • {v}
                </p>
              ))}
              {rule.details?.map((d: string, i: number) => (
                <p key={i} className="text-xs text-zinc-400">
                  ✓ {d}
                </p>
              ))}
            </div>
          ))}
        </motion.div>
      </Section>

      {/* Monthly heatmap */}
      {heatmapChart.length > 0 && (
        <Section title="Monthly P/L Heatmap" icon={<Calendar className="w-5 h-5 text-cyan-400" />}>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={heatmapChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#888", fontSize: 10 }} />
                <YAxis tick={{ fill: "#888", fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#333" }} />
                <Bar dataKey="profit" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      {/* Drawdown recovery */}
      <Section title="Drawdown Duration & Recovery" icon={<TrendingDown className="w-5 h-5 text-rose-400" />}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Longest underwater" value={`${ext.drawdown_recovery?.longest_underwater_trades ?? 0} trades`} />
          <Stat label="Avg recovery" value={`${ext.drawdown_recovery?.average_recovery_trades ?? 0} trades`} />
          <Stat label="DD periods" value={String(ext.drawdown_recovery?.underwater_periods ?? 0)} />
          <Stat label="Time underwater" value={`${ext.drawdown_recovery?.time_underwater_pct ?? 0}%`} />
        </div>
      </Section>

      {/* Loss clusters */}
      {(ext.loss_clusters || []).length > 0 && (
        <Section title="Loss Clustering" icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}>
          <div className="space-y-2 max-h-[240px] overflow-y-auto">
            {ext.loss_clusters.map((c: any, i: number) => (
              <motion.div key={i} className="p-3 rounded-lg bg-black/30 border border-white/5 text-xs">
                <span className="font-bold text-rose-400">{c.loss_count} losses</span> · ${c.total_loss} ·{" "}
                {c.duration_minutes} min
                <p className="text-zinc-500 mt-1">
                  {c.start_time?.slice(0, 16)} → {c.end_time?.slice(0, 16)}
                </p>
              </motion.div>
            ))}
          </div>
        </Section>
      )}

      {/* Lot escalation */}
      {(ext.lot_escalation || []).length > 0 && (
        <Section title="Lot Escalation Timeline" icon={<Layers className="w-5 h-5 text-orange-400" />}>
          <motion.div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={ext.lot_escalation}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="index" tick={{ fill: "#666", fontSize: 9 }} />
                <YAxis yAxisId="lot" tick={{ fill: "#666", fontSize: 9 }} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", borderColor: "#333" }} />
                <Line yAxisId="lot" type="monotone" dataKey="lot" stroke="#f97316" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>
        </Section>
      )}

      {/* Session breakdown */}
      <Section title="Session / Market Hours" icon={<Globe className="w-5 h-5 text-blue-400" />}>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {(ext.session_breakdown || []).map((s: any) => (
            <div key={s.session} className="p-4 rounded-xl bg-black/30 border border-white/5">
              <p className="text-xs font-bold uppercase text-muted-foreground">{s.session}</p>
              <p className={`text-lg font-black ${s.profit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                ${s.profit.toLocaleString()}
              </p>
              <p className="text-[10px] text-zinc-500">
                {s.trades} trades · {s.win_rate}% win
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Symbol & spread */}
      <Section title="Symbol & Spread Sensitivity" icon={<DollarSign className="w-5 h-5 text-emerald-400" />}>
        <p className="text-sm text-zinc-400 mb-3">
          Primary: <strong className="text-white">{ext.symbol_spread?.primary_symbol}</strong> · Spread:{" "}
          {ext.symbol_spread?.backtest_spread} · Sensitivity:{" "}
          <span className="text-amber-400">{ext.symbol_spread?.spread_sensitivity}</span>
        </p>
        {Object.entries(ext.symbol_spread?.symbol_profit_breakdown || {}).map(([sym, profit]) => (
          <div key={sym} className="flex justify-between text-xs py-1 border-b border-white/5">
            <span>{sym}</span>
            <span className={(profit as number) >= 0 ? "text-emerald-400" : "text-rose-400"}>
              ${(profit as number).toLocaleString()}
            </span>
          </div>
        ))}
      </Section>

      {/* Deposit scenarios */}
      <Section title="Multi-Deposit Scenarios" icon={<DollarSign className="w-5 h-5 text-violet-400" />}>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted-foreground uppercase tracking-widest">
                <th className="text-left py-2">Account</th>
                <th className="text-right py-2">Scaled profit</th>
                <th className="text-right py-2">Equity DD</th>
                <th className="text-right py-2">Prop viable</th>
              </tr>
            </thead>
            <tbody>
              {(ext.deposit_scenarios || []).map((row: any) => (
                <tr key={row.label} className="border-t border-white/5">
                  <td className="py-2 font-bold">{row.label}</td>
                  <td className="text-right text-emerald-400">${row.scaled_net_profit?.toLocaleString()}</td>
                  <td className="text-right">{row.scaled_max_dd_pct}%</td>
                  <td className="text-right">{row.prop_viable ? "✓" : "✗"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Explainable verdict */}
      <Section title="Explainable Verdict" icon={<ListChecks className="w-5 h-5 text-primary" />}>
        <div className="space-y-2">
          {(ext.verdict_evidence || []).map((e: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-black/30 border border-white/5">
              <div>
                <p className="text-sm font-semibold">{e.rule}</p>
                <p className="text-xs text-zinc-500">{e.value}</p>
              </div>
              <span className={`text-xs font-bold uppercase ${impactColor(e.impact)}`}>{e.impact}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* What-if sliders */}
      <Section title="What-If Scenarios" icon={<Sliders className="w-5 h-5 text-yellow-400" />}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Slider label="Account size ($)" value={deposit} min={1000} max={200000} step={1000} onChange={setDeposit} />
          <Slider label="Max drawdown cap (%)" value={ddLimit} min={1} max={20} step={0.5} onChange={setDdLimit} />
          <Slider label="Daily loss cap (%)" value={dailyLimit} min={1} max={10} step={0.5} onChange={setDailyLimit} />
        </div>
        <div
          className={`mt-4 p-4 rounded-xl border ${whatIfResult.pass ? "border-emerald-500/30 bg-emerald-500/10" : "border-rose-500/30 bg-rose-500/10"}`}
        >
          <p className="font-bold text-sm">
            {whatIfResult.pass ? "Would pass your custom prop rules" : "Would fail your custom prop rules"}
          </p>
          <p className="text-xs text-zinc-400 mt-1">
            Balance buffer at max DD: ${whatIfResult.buffer.toLocaleString()} · DD check:{" "}
            {whatIfResult.passDd ? "OK" : "Fail"} · Daily check: {whatIfResult.passDaily ? "OK" : "Fail"}
          </p>
        </div>
      </Section>

      {/* Action checklist */}
      <Section title="Action Checklist" icon={<ListChecks className="w-5 h-5 text-emerald-400" />}>
        <ActionChecklist items={ext.action_checklist || []} />
      </Section>
    </motion.div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass-strong rounded-3xl p-8 border border-white/5">
      <h3 className="text-lg font-bold mb-6 flex items-center gap-3">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-xl bg-black/30 border border-white/5">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">{label}</p>
      <p className="text-lg font-black">{value}</p>
    </div>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
        {label}: {value.toLocaleString()}
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full mt-2 accent-primary"
      />
    </div>
  );
}

function ActionChecklist({ items }: { items: any[] }) {
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <label
          key={item.id}
          className="flex items-start gap-3 p-3 rounded-lg bg-black/30 border border-white/5 cursor-pointer hover:border-primary/30"
        >
          <input
            type="checkbox"
            checked={!!checked[item.id]}
            onChange={() => setChecked((c) => ({ ...c, [item.id]: !c[item.id] }))}
            className="mt-1"
          />
          <motion.div>
            <span
              className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                item.priority === "high"
                  ? "bg-rose-500/20 text-rose-400"
                  : item.priority === "medium"
                    ? "bg-amber-500/20 text-amber-400"
                    : "bg-zinc-500/20 text-zinc-400"
              }`}
            >
              {item.priority}
            </span>
            <p className={`text-sm mt-1 ${checked[item.id] ? "line-through text-zinc-500" : ""}`}>{item.text}</p>
          </motion.div>
        </label>
      ))}
    </div>
  );
}
