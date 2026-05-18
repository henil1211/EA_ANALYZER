"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  Grid3X3,
  Repeat,
  Zap,
  TrendingUp,
  Layers,
  Clock,
  Activity,
} from "lucide-react";

interface TradeBehaviorProps {
  behavior: Record<string, any>;
  summary?: string;
}

interface Detection {
  label: string;
  detected: boolean;
  confidence: number;
  icon: React.ReactNode;
  severity: "critical" | "warning" | "info";
  description: string;
}

export default function TradeBehavior({ behavior, summary }: TradeBehaviorProps) {
  const b = behavior;

  const detections: Detection[] = [
    {
      label: "Martingale",
      detected: Boolean(b.is_martingale),
      confidence: Number(b.martingale_confidence || 0),
      icon: <AlertTriangle className="w-5 h-5" />,
      severity: "critical",
      description: "Lot size increases after losses — catastrophic loss risk",
    },
    {
      label: "Grid Trading",
      detected: Boolean(b.is_grid),
      confidence: Number(b.grid_confidence || 0),
      icon: <Grid3X3 className="w-5 h-5" />,
      severity: "warning",
      description: "Evenly spaced entries — vulnerable to strong trends",
    },
    {
      label: "Hedging",
      detected: Boolean(b.is_hedging),
      confidence: Number(b.hedging_confidence || 0),
      icon: <Repeat className="w-5 h-5" />,
      severity: "info",
      description: "Simultaneous buy/sell positions detected",
    },
    {
      label: "Scalping",
      detected: Boolean(b.is_scalping),
      confidence: Number(b.scalping_confidence || 0),
      icon: <Zap className="w-5 h-5" />,
      severity: "info",
      description: "Short-duration trades — sensitive to spread and slippage",
    },
    {
      label: "Lot Escalation",
      detected: Boolean(b.lot_escalation_detected),
      confidence: b.lot_escalation_factor ? Number(b.lot_escalation_factor) * 10 : 0,
      icon: <TrendingUp className="w-5 h-5" />,
      severity: "critical",
      description: `Max/min lot ratio: ${b.lot_escalation_factor || "N/A"}x`,
    },
    {
      label: "Averaging Down",
      detected: Boolean(b.is_averaging_down),
      confidence: Number(b.averaging_confidence || 0),
      icon: <Layers className="w-5 h-5" />,
      severity: "critical",
      description: "Adding to losing positions — margin call risk",
    },
    {
      label: "Overtrading",
      detected: Boolean(b.overtrading_detected),
      confidence: b.overtrading_detected ? 80 : 0,
      icon: <Activity className="w-5 h-5" />,
      severity: "warning",
      description: "Excessive trade frequency detected",
    },
    {
      label: "Dangerous Recovery",
      detected: Boolean(b.dangerous_recovery_system),
      confidence: b.dangerous_recovery_system ? 90 : 0,
      icon: <AlertTriangle className="w-5 h-5" />,
      severity: "critical",
      description: "Aggressive position sizing during drawdown",
    },
  ];

  const severityColors = {
    critical: { bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-400", dot: "bg-red-400" },
    warning: { bg: "bg-yellow-500/10", border: "border-yellow-500/30", text: "text-yellow-400", dot: "bg-yellow-400" },
    info: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", dot: "bg-blue-400" },
  };

  const detected = detections.filter((d) => d.detected);
  const clean = detections.filter((d) => !d.detected);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="space-y-6"
    >
      <h3 className="text-lg font-semibold text-foreground">
        Trade Behavior Analysis
      </h3>

      {/* Detected Patterns */}
      {detected.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Detected Patterns ({detected.length})
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {detected.map((d, i) => {
              const colors = severityColors[d.severity];
              return (
                <motion.div
                  key={d.label}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className={`rounded-xl border ${colors.border} ${colors.bg} p-4`}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={colors.text}>{d.icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-semibold ${colors.text}`}>
                          {d.label}
                        </span>
                        <span className={`text-xs font-mono ${colors.text}`}>
                          {d.confidence.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-foreground/60">{d.description}</p>
                  <div className="mt-2 h-1 rounded-full bg-black/20 overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${colors.dot}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(d.confidence, 100)}%` }}
                      transition={{ duration: 0.8, delay: 0.3 }}
                    />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Clean Checks */}
      {clean.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm font-medium text-green-400">
            ✓ Clean Checks ({clean.length})
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {clean.map((d) => (
              <div
                key={d.label}
                className="glass rounded-lg p-3 flex items-center gap-2"
              >
                <div className="w-2 h-2 rounded-full bg-green-400" />
                <span className="text-xs text-foreground/70">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lot Analysis */}
      {(b.min_lot || b.max_lot || b.avg_lot) && (
        <div className="glass rounded-xl p-5">
          <h4 className="text-sm font-semibold text-foreground mb-3">
            Lot Size Analysis
          </h4>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Min Lot</p>
              <p className="text-sm font-bold text-foreground">{String(b.min_lot || "—")}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Max Lot</p>
              <p className="text-sm font-bold text-foreground">{String(b.max_lot || "—")}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Avg Lot</p>
              <p className="text-sm font-bold text-foreground">{String(b.avg_lot || "—")}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Std Dev</p>
              <p className="text-sm font-bold text-foreground">{String(b.lot_std_dev || "—")}</p>
            </div>
          </div>
        </div>
      )}

      {/* Session Distribution */}
      {b.session_distribution && (
        <div className="glass rounded-xl p-5">
          <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            Session Distribution
          </h4>
          <div className="grid grid-cols-4 gap-3">
            {Object.entries(b.session_distribution as Record<string, number>).map(([session, count]) => (
              <div key={session} className="text-center">
                <p className="text-xs text-muted-foreground mb-1">{session}</p>
                <p className="text-lg font-bold text-foreground">{count}</p>
                <p className="text-xs text-muted-foreground">trades</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary && (
        <div className="glass rounded-xl p-5">
          <h4 className="text-sm font-semibold text-foreground mb-2">
            AI Behavior Summary
          </h4>
          <p className="text-sm text-foreground/70 leading-relaxed">{summary}</p>
        </div>
      )}
    </motion.div>
  );
}
