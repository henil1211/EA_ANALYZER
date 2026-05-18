"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Info,
  ShieldAlert,
} from "lucide-react";

interface HiddenInsight {
  id: string;
  title: string;
  status: string;
  severity: "positive" | "info" | "warning" | "critical" | string;
  value: string;
  summary: string;
  evidence: string[];
  recommendation: string;
}

interface HiddenDetailsResult {
  hidden_risk_score: number;
  verdict: string;
  summary: string;
  confidence_score?: number;
  reliability_score?: number;
  reliability_label?: string;
  limitations?: string[];
  insights: HiddenInsight[];
}

interface HiddenDetailsProps {
  details?: HiddenDetailsResult;
}

const severityStyles: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  positive: {
    color: "text-green-400",
    bg: "bg-green-500/10",
    border: "border-green-500/25",
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
  info: {
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/25",
    icon: <Info className="w-4 h-4" />,
  },
  warning: {
    color: "text-yellow-400",
    bg: "bg-yellow-500/10",
    border: "border-yellow-500/25",
    icon: <AlertTriangle className="w-4 h-4" />,
  },
  critical: {
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/25",
    icon: <ShieldAlert className="w-4 h-4" />,
  },
};

function scoreColor(score: number) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

export default function HiddenDetails({ details }: HiddenDetailsProps) {
  if (!details) {
    return null;
  }

  const score = Number(details.hidden_risk_score || 0);
  const color = scoreColor(score);
  const insights = details.insights || [];
  const findInsight = (id: string) => insights.find((insight) => insight.id === id);
  const topSummary = [
    { label: "Safety", value: details.verdict, tone: color },
    { label: "Personality", value: findInsight("strategy-personality")?.status || "Unknown", tone: "#8b5cf6" },
    { label: "Reliability", value: `${details.reliability_label || "Unknown"} ${details.reliability_score ?? 0}/100`, tone: scoreColor(details.reliability_score ?? 0) },
    { label: "Verdict Confidence", value: `${details.confidence_score ?? 0}/100`, tone: scoreColor(details.confidence_score ?? 0) },
    { label: "Live Suitability", value: findInsight("live-survival")?.status || "Unknown", tone: "#22c55e" },
    { label: "Main Danger", value: findInsight("hidden-risk")?.status || "Unknown", tone: "#ef4444" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="space-y-6"
    >
      <div className="glass-strong rounded-2xl p-6 border border-white/5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Eye className="w-5 h-5 text-primary" />
              <h3 className="text-xl font-bold">AI Forensic Details</h3>
            </div>
            <p className="text-sm text-foreground/70 leading-relaxed">
              {details.summary}
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-4">
            <div className="text-right">
              <p className="text-xs text-muted-foreground uppercase tracking-widest font-bold">
                Forensic Safety Score
              </p>
              <p className="text-4xl font-black" style={{ color }}>
                {score}
              </p>
            </div>
            <div
              className="px-5 py-3 rounded-xl border text-lg font-black"
              style={{ color, borderColor: `${color}55`, backgroundColor: `${color}15` }}
            >
              {details.verdict}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {topSummary.map((item) => (
          <div key={item.label} className="glass rounded-xl p-4 border border-white/5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
              {item.label}
            </p>
            <p className="text-sm font-black leading-tight" style={{ color: item.tone }}>
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {!!details.limitations?.length && (
        <div className="glass rounded-xl p-4 border border-yellow-500/20 bg-yellow-500/5">
          <p className="text-xs font-bold uppercase tracking-widest text-yellow-400 mb-2">
            Assumptions & Confidence Limits
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {details.limitations.map((item, index) => (
              <p key={index} className="text-xs text-foreground/70 leading-relaxed">
                {item}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {insights.map((insight, index) => {
          const style = severityStyles[insight.severity] || severityStyles.info;
          return (
            <motion.div
              key={insight.id || insight.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: index * 0.025 }}
              className={`glass rounded-xl p-5 border ${style.border}`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className={`${style.bg} ${style.color} rounded-lg p-2 shrink-0`}>
                    {style.icon}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-sm font-bold text-foreground leading-snug">
                      {insight.title}
                    </h4>
                    <p className={`text-xs font-bold ${style.color}`}>
                      {insight.status}
                    </p>
                  </div>
                </div>
                <span className={`text-xs font-black px-2 py-1 rounded-md ${style.bg} ${style.color} shrink-0 max-w-36 text-right leading-tight whitespace-normal`}>
                  {insight.value}
                </span>
              </div>

              <p className="text-xs text-foreground/70 leading-relaxed mb-3">
                {insight.summary}
              </p>

              <div className="space-y-1.5 mb-4">
                {(insight.evidence || []).slice(0, 4).map((item, i) => (
                  <p key={i} className="text-xs text-muted-foreground leading-relaxed">
                    {item}
                  </p>
                ))}
              </div>

              <div className="rounded-lg bg-muted/30 border border-border p-3">
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">
                  Action
                </p>
                <p className="text-xs text-foreground/75 leading-relaxed">
                  {insight.recommendation}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
