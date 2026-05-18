"use client";

import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";

interface EquityChartProps {
  data: number[];
  analysis?: string;
}

export default function EquityChart({ data, analysis }: EquityChartProps) {
  const chartData = data.map((val, index) => ({
    trade: index,
    equity: val,
  }));

  const startEquity = data[0] || 0;
  const endEquity = data[data.length - 1] || 0;
  const isProfit = endEquity >= startEquity;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6 }}
      className="glass-strong rounded-3xl p-8 border border-white/5 shadow-2xl"
    >
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold tracking-tight">Equity Curve Analysis</h3>
          <p className="text-sm text-muted-foreground">Historical growth and drawdown visualization</p>
        </div>
        <div className={`flex items-center gap-2 px-4 py-2 rounded-2xl ${isProfit ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'} border border-current/20`}>
          {isProfit ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          <span className="text-sm font-black uppercase tracking-widest">
            {isProfit ? "Growth" : "Decline"}
          </span>
        </div>
      </div>

      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={isProfit ? "#6d5cff" : "#ef4444"} stopOpacity={0.3} />
                <stop offset="95%" stopColor={isProfit ? "#6d5cff" : "#ef4444"} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis 
              dataKey="trade" 
              stroke="#52525b" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false}
              tick={{ fill: '#71717a' }}
            />
            <YAxis 
              stroke="#52525b" 
              fontSize={10} 
              tickLine={false} 
              axisLine={false}
              tickFormatter={(val) => `$${val.toLocaleString()}`}
              tick={{ fill: '#71717a' }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #27272a",
                borderRadius: "16px",
                fontSize: "12px",
                color: "#fafafa",
                boxShadow: "0 20px 40px rgba(0,0,0,0.4)"
              }}
              formatter={(value: any) => [`$${Number(value).toLocaleString()}`, "Equity"]}
              labelFormatter={(label) => `Trade #${label}`}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={isProfit ? "#6d5cff" : "#ef4444"}
              strokeWidth={4}
              fillOpacity={1}
              fill="url(#colorEquity)"
              animationDuration={2000}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {analysis && (
        <div className="mt-8 p-6 rounded-2xl bg-muted/40 border border-border">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-3">AI Curve Verdict</h4>
          <p className="text-sm text-foreground/80 leading-relaxed font-medium">
            {analysis}
          </p>
        </div>
      )}
    </motion.div>
  );
}
