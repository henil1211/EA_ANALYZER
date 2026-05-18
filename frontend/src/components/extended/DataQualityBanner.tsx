"use client";

import { motion } from "framer-motion";
import { Shield, AlertTriangle, CheckCircle2 } from "lucide-react";

export default function DataQualityBanner({ quality }: { quality?: any }) {
  if (!quality) return null;

  const level = quality.level || "medium";
  const styles =
    level === "high"
      ? "border-emerald-500/30 bg-emerald-500/10"
      : level === "low"
        ? "border-rose-500/30 bg-rose-500/10"
        : "border-amber-500/30 bg-amber-500/10";

  const Icon = level === "high" ? CheckCircle2 : level === "low" ? AlertTriangle : Shield;

  return (
    <div className={`rounded-2xl border p-5 ${styles}`}>
      <motion.div className="flex items-start gap-4" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Icon className="w-6 h-6 shrink-0 opacity-80" />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <h3 className="font-bold text-sm uppercase tracking-widest">Data Quality · {quality.label}</h3>
            <span className="text-xs font-black px-2 py-1 rounded-full bg-black/30">{quality.score}/100</span>
          </div>
          {quality.signals?.length > 0 && (
            <p className="text-xs text-zinc-400 mb-2">{quality.signals.join(" · ")}</p>
          )}
          {quality.limitations?.length > 0 && (
            <ul className="text-xs text-amber-200/80 space-y-1">
              {quality.limitations.map((l: string, i: number) => (
                <li key={i}>⚠ {l}</li>
              ))}
            </ul>
          )}
        </div>
      </motion.div>
    </div>
  );
}
