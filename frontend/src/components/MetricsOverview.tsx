"use client";

import { motion } from "framer-motion";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  Percent,
  ArrowUpDown,
  Layers,
  Clock,
  Award,
} from "lucide-react";

interface MetricsOverviewProps {
  metrics: Record<string, any>;
}

interface MetricItem {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}

export default function MetricsOverview({ metrics }: MetricsOverviewProps) {
  const m = metrics;

  const items: MetricItem[] = [
    {
      label: "Net Profit",
      value: `$${Number(m.net_profit || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      icon: <DollarSign className="w-4 h-4" />,
      color: Number(m.net_profit || 0) >= 0 ? "#22c55e" : "#ef4444",
    },
    {
      label: "Profit Factor",
      value: String(m.profit_factor || "N/A"),
      icon: <TrendingUp className="w-4 h-4" />,
      color: Number(m.profit_factor || 0) > 1.5 ? "#22c55e" : Number(m.profit_factor || 0) > 1 ? "#f59e0b" : "#ef4444",
    },
    {
      label: "Win Rate",
      value: m.win_rate ? `${m.win_rate}%` : "N/A",
      icon: <Target className="w-4 h-4" />,
      color: Number(m.win_rate || 0) > 60 ? "#22c55e" : Number(m.win_rate || 0) > 45 ? "#f59e0b" : "#ef4444",
    },
    {
      label: "Max Equity Drawdown",
      value: m.equity_drawdown_maximal
        ? String(m.equity_drawdown_maximal)
        : (m.maximal_drawdown_pct ? `${m.maximal_drawdown_pct}%` : (m.maximal_drawdown ? `$${Number(m.maximal_drawdown).toLocaleString()}` : "N/A")),
      icon: <TrendingDown className="w-4 h-4" />,
      color: "#ef4444",
    },
    {
      label: "Total Trades",
      value: String(m.total_trades || 0),
      icon: <BarChart3 className="w-4 h-4" />,
      color: "#6d5cff",
    },
    {
      label: "Sharpe Ratio",
      value: m.sharpe_ratio ? String(m.sharpe_ratio) : "N/A",
      icon: <Award className="w-4 h-4" />,
      color: Number(m.sharpe_ratio || 0) > 1.5 ? "#22c55e" : Number(m.sharpe_ratio || 0) > 0.5 ? "#f59e0b" : "#ef4444",
    },
    {
      label: "Recovery Factor",
      value: m.recovery_factor ? String(m.recovery_factor) : "N/A",
      icon: <ArrowUpDown className="w-4 h-4" />,
      color: Number(m.recovery_factor || 0) > 3 ? "#22c55e" : Number(m.recovery_factor || 0) > 1 ? "#f59e0b" : "#ef4444",
    },
    {
      label: "Risk/Reward",
      value: m.risk_reward_ratio ? `1:${m.risk_reward_ratio}` : "N/A",
      icon: <Percent className="w-4 h-4" />,
      color: Number(m.risk_reward_ratio || 0) > 1.5 ? "#22c55e" : "#f59e0b",
    },
    {
      label: "Expected Payoff",
      value: m.expected_payoff ? `$${Number(m.expected_payoff).toFixed(2)}` : "N/A",
      icon: <Layers className="w-4 h-4" />,
      color: Number(m.expected_payoff || 0) > 0 ? "#22c55e" : "#ef4444",
    },
    {
      label: "Avg Trade Duration",
      value: m.average_trade_duration ? `${Math.round(Number(m.average_trade_duration))} min` : "N/A",
      icon: <Clock className="w-4 h-4" />,
      color: "#6d5cff",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      <div className="flex items-center gap-3 mb-4">
        <h3 className="text-lg font-semibold text-foreground">
          Key Metrics
        </h3>
        {m.ea_name && (
          <span className="px-2.5 py-1 text-xs font-medium rounded-lg bg-primary/10 text-primary">
            {String(m.ea_name)}
          </span>
        )}
        {m.symbol && (
          <span className="px-2.5 py-1 text-xs font-medium rounded-lg bg-muted text-muted-foreground">
            {String(m.symbol)} {m.period ? `• ${m.period}` : ""}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {items.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: i * 0.05 }}
            className="glass rounded-xl p-4 hover:glow transition-all duration-300"
          >
            <div className="flex items-center gap-2 mb-2">
              <div style={{ color: item.color }}>{item.icon}</div>
              <span className="text-xs text-muted-foreground">{item.label}</span>
            </div>
            <p
              className="text-lg font-bold tracking-tight"
              style={{ color: item.color }}
            >
              {item.value}
            </p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
