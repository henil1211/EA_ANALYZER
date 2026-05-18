"use client";

import { motion } from "framer-motion";
import {
  Shield,
  TrendingUp,
  Activity,
  HeartPulse,
  Building2,
} from "lucide-react";

interface ScoreData {
  category: string;
  score: number;
  grade: string;
  summary: string;
  details: string[];
}

interface ScoreCardsProps {
  profitability?: ScoreData;
  risk?: ScoreData;
  stability?: ScoreData;
  survivability?: ScoreData;
  propFirm?: ScoreData;
  overall: number;
}

const icons: Record<string, React.ReactNode> = {
  Profitability: <TrendingUp className="w-5 h-5" />,
  "Risk Management": <Shield className="w-5 h-5" />,
  Stability: <Activity className="w-5 h-5" />,
  Survivability: <HeartPulse className="w-5 h-5" />,
  "Prop Firm Compatibility": <Building2 className="w-5 h-5" />,
};

function getScoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;
  const color = getScoreColor(score);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(39,39,42,0.5)"
          strokeWidth="4"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-bold" style={{ color }}>
          {score}
        </span>
      </div>
    </div>
  );
}

function ScoreCard({
  data,
  index,
}: {
  data: ScoreData;
  index: number;
}) {
  const color = getScoreColor(data.score);
  const icon = icons[data.category] || <Activity className="w-5 h-5" />;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className="glass rounded-xl p-5 hover:glow transition-all duration-300 group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div
            className="p-2 rounded-lg"
            style={{ backgroundColor: `${color}15` }}
          >
            <div style={{ color }}>{icon}</div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {data.category}
            </h3>
            <p className="text-xs text-muted-foreground">{data.summary}</p>
          </div>
        </div>
        <div
          className="text-xs font-bold px-2 py-1 rounded-md"
          style={{ backgroundColor: `${color}15`, color }}
        >
          {data.grade}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <ScoreRing score={data.score} size={64} />
        <div className="flex-1 space-y-1.5">
          {data.details.slice(0, 3).map((detail, i) => (
            <p key={i} className="text-xs text-muted-foreground leading-relaxed">
              • {detail}
            </p>
          ))}
        </div>
      </div>

      <div className="mt-3">
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <motion.div
            className="h-full rounded-full"
            style={{ backgroundColor: color }}
            initial={{ width: 0 }}
            animate={{ width: `${data.score}%` }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.5 + index * 0.1 }}
          />
        </div>
      </div>
    </motion.div>
  );
}

export default function ScoreCards({
  profitability,
  risk,
  stability,
  survivability,
  propFirm,
  overall,
}: ScoreCardsProps) {
  const scores = [profitability, risk, stability, survivability, propFirm].filter(
    Boolean
  ) as ScoreData[];

  return (
    <div className="space-y-6">
      {/* Overall Score */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6 }}
        className="glass-strong rounded-2xl p-8 text-center glow"
      >
        <p className="text-sm text-muted-foreground mb-4 uppercase tracking-wider font-medium">
          Overall Score
        </p>
        <div className="flex justify-center mb-4">
          <ScoreRing score={Math.round(overall)} size={120} />
        </div>
        <p
          className="text-lg font-bold"
          style={{ color: getScoreColor(overall) }}
        >
          {overall >= 80
            ? "Institutional Grade"
            : overall >= 60
            ? "Acceptable Quality"
            : overall >= 40
            ? "Significant Concerns"
            : "Critical Issues"}
        </p>
      </motion.div>

      {/* Individual Scores */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {scores.map((score, i) => (
          <ScoreCard key={score.category} data={score} index={i} />
        ))}
      </div>
    </div>
  );
}
