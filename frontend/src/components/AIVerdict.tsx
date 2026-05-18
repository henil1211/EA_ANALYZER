"use client";

import { motion } from "framer-motion";
import {
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Eye,
  Lightbulb,
} from "lucide-react";

interface AIVerdictProps {
  verdict: string;
  verdictColor: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  hiddenRisks: string[];
  recommendations: string[];
}

const verdictConfig: Record<string, { icon: React.ReactNode; bg: string; border: string; text: string }> = {
  PASS: {
    icon: <ShieldCheck className="w-10 h-10" />,
    bg: "from-green-500/10 to-emerald-500/5",
    border: "border-green-500/30",
    text: "text-green-400",
  },
  CAUTION: {
    icon: <ShieldAlert className="w-10 h-10" />,
    bg: "from-yellow-500/10 to-amber-500/5",
    border: "border-yellow-500/30",
    text: "text-yellow-400",
  },
  FAIL: {
    icon: <AlertTriangle className="w-10 h-10" />,
    bg: "from-orange-500/10 to-red-500/5",
    border: "border-orange-500/30",
    text: "text-orange-400",
  },
  DANGEROUS: {
    icon: <ShieldX className="w-10 h-10" />,
    bg: "from-red-500/10 to-rose-500/5",
    border: "border-red-500/30",
    text: "text-red-400",
  },
};

export default function AIVerdict({
  verdict,
  verdictColor,
  summary,
  strengths,
  weaknesses,
  hiddenRisks,
  recommendations,
}: AIVerdictProps) {
  const config = verdictConfig[verdict] || verdictConfig.CAUTION;

  return (
    <div className="space-y-6">
      {/* Verdict Banner */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className={`rounded-2xl border ${config.border} bg-gradient-to-br ${config.bg} p-6`}
      >
        <div className="flex items-center gap-4 mb-4">
          <div className={config.text}>{config.icon}</div>
          <div>
            <h2 className={`text-2xl font-bold ${config.text}`}>
              Verdict: {verdict}
            </h2>
            <p className="text-sm text-muted-foreground">AI Analysis Complete</p>
          </div>
        </div>
        <p className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">
          {summary}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Strengths */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="glass rounded-xl p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            <h3 className="text-sm font-semibold text-green-400">Strengths</h3>
          </div>
          <ul className="space-y-2.5">
            {strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/70">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 mt-1.5 shrink-0" />
                {s}
              </li>
            ))}
            {strengths.length === 0 && (
              <li className="text-sm text-muted-foreground italic">No significant strengths identified</li>
            )}
          </ul>
        </motion.div>

        {/* Weaknesses */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="glass rounded-xl p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <XCircle className="w-5 h-5 text-red-400" />
            <h3 className="text-sm font-semibold text-red-400">Weaknesses</h3>
          </div>
          <ul className="space-y-2.5">
            {weaknesses.map((w, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/70">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 shrink-0" />
                {w}
              </li>
            ))}
            {weaknesses.length === 0 && (
              <li className="text-sm text-muted-foreground italic">No weaknesses identified</li>
            )}
          </ul>
        </motion.div>

        {/* Hidden Risks */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="glass rounded-xl p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Eye className="w-5 h-5 text-orange-400" />
            <h3 className="text-sm font-semibold text-orange-400">Hidden Risks</h3>
          </div>
          <ul className="space-y-2.5">
            {hiddenRisks.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/70">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-400 mt-1.5 shrink-0" />
                {r}
              </li>
            ))}
            {hiddenRisks.length === 0 && (
              <li className="text-sm text-muted-foreground italic">No hidden risks detected</li>
            )}
          </ul>
        </motion.div>

        {/* Recommendations */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="glass rounded-xl p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-5 h-5 text-blue-400" />
            <h3 className="text-sm font-semibold text-blue-400">Recommendations</h3>
          </div>
          <ul className="space-y-2.5">
            {recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground/70">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </motion.div>
      </div>
    </div>
  );
}
