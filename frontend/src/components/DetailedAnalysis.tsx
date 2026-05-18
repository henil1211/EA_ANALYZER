"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Database, FileSearch, Info, Table2, ChevronLeft, ChevronRight } from "lucide-react";

interface DetailedMetric {
  key: string;
  label: string;
  value: string | number | null;
  status: "available" | "derived" | "unavailable" | string;
  description?: string;
}

interface DetailedAnalysisResult {
  summary: string;
  summary_cards: DetailedMetric[];
  metric_groups: Record<string, DetailedMetric[]>;
  trade_rows: Record<string, any>[];
  total_trade_rows: number;
  unavailable_metrics: DetailedMetric[];
}

interface Props {
  details?: DetailedAnalysisResult;
}

const statusStyle: Record<string, { label?: string; color: string; bg: string; icon: React.ReactNode }> = {
  available: {
    color: "text-green-400",
    bg: "bg-green-500/10 border-green-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  derived: {
    color: "text-blue-400",
    bg: "bg-blue-500/10 border-blue-500/20",
    icon: <Info className="w-3.5 h-3.5" />,
  },
  unavailable: {
    label: "Needs Extra Data",
    color: "text-yellow-400",
    bg: "bg-yellow-500/10 border-yellow-500/20",
    icon: <AlertCircle className="w-3.5 h-3.5" />,
  },
};

const EXCLUDED_KEYS = new Set([
  "ticket",
  "magic_number",
  "entry_price",
  "exit_price",
  "open_time",
  "close_time",
  "mae",
  "maximum_losing_period_days",
  "commission",
  "swap",
  "round_turn_cost_efficiency",
  "spread_at_entry",
  "slippage_distribution",
  "fill_quality",
  "rejected_orders",
  "order_modification_count",
  "entry_efficiency",
  "exit_efficiency",
  "trailing_stop_efficiency",
  "partial_closes",
  "partial_close_efficiency",
  "volatility_at_entry",
  "news_proximity",
  "beta",
  "alpha"
]);

const columns = [
  ["symbol", "Symbol"],
  ["type", "Type"],
  ["lot_size", "Lot"],
  ["profit_loss", "P/L"],
  ["duration", "Duration"],
  ["session", "Session"],
  ["equity_at_entry", "Equity Entry"],
  ["equity_at_exit", "Equity Exit"],
  ["comment", "Comment"],
] as const;

function formatValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

export default function DetailedAnalysis({ details }: Props) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50;

  useEffect(() => {
    setCurrentPage(1);
  }, [details]);

  if (!details) {
    return (
      <div className="glass-strong rounded-2xl p-8 border border-yellow-500/20 bg-yellow-500/5">
        <div className="flex items-start gap-4">
          <AlertCircle className="w-6 h-6 text-yellow-400 shrink-0 mt-1" />
          <div>
            <h3 className="text-xl font-bold mb-2">Detailed Analysis Not Loaded</h3>
            <p className="text-sm text-foreground/70 leading-relaxed">
              This analysis result was created before the backend returned detailed-analysis data.
              Click New Analysis and upload the report again after restarting the backend.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const totalRows = details.trade_rows?.length || 0;
  const totalPages = Math.ceil(totalRows / itemsPerPage);

  const paginatedRows = (details.trade_rows || []).slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Filter out excluded keys
  const filteredSummaryCards = (details.summary_cards || []).filter(
    (card) => !EXCLUDED_KEYS.has(card.key)
  );

  const filteredMetricGroups = Object.entries(details.metric_groups || {}).reduce(
    (acc, [groupName, metrics]) => {
      const filtered = metrics.filter((m) => !EXCLUDED_KEYS.has(m.key));
      if (filtered.length > 0) {
        acc[groupName] = filtered;
      }
      return acc;
    },
    {} as Record<string, typeof details.summary_cards>
  );

  const filteredUnavailableMetrics = (details.unavailable_metrics || []).filter(
    (m) => !EXCLUDED_KEYS.has(m.key)
  );

  const getPageNumbers = () => {
    const pages: (number | "...")[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);
      if (currentPage <= 4) {
        pages.push(2, 3, 4, 5);
        pages.push("...");
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 3) {
        pages.push("...");
        for (let i = totalPages - 4; i < totalPages; i++) {
          pages.push(i);
        }
        pages.push(totalPages);
      } else {
        pages.push("...");
        pages.push(currentPage - 1, currentPage, currentPage + 1);
        pages.push("...");
        pages.push(totalPages);
      }
    }
    return pages;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      <div className="glass-strong rounded-2xl p-6 border border-white/5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <FileSearch className="w-5 h-5 text-primary" />
              <h3 className="text-xl font-bold">Detailed Analysis</h3>
            </div>
            <p className="text-sm text-foreground/70 leading-relaxed max-w-4xl">
              {details.summary}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="px-4 py-3 rounded-xl bg-primary/10 border border-primary/20">
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">Rows</p>
              <p className="text-2xl font-black text-primary">{details.total_trade_rows}</p>
            </div>
            <div className="px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20">
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">Needs Data</p>
              <p className="text-2xl font-black text-yellow-400">{filteredUnavailableMetrics.length}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {filteredSummaryCards.map((item) => (
          <div key={item.key} className="glass rounded-xl p-4 border border-white/5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
              {item.label}
            </p>
            <p className="text-sm font-black text-foreground leading-tight">
              {formatValue(item.value)}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {Object.entries(filteredMetricGroups).map(([groupName, metrics]) => (
          <div key={groupName} className="glass rounded-xl p-5 border border-white/5">
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-primary" />
              <h4 className="text-sm font-black">{groupName}</h4>
            </div>
            <div className="space-y-2">
              {metrics.map((metric) => {
                    // remove status symbol; center the value horizontally
                    return (
                      <div key={metric.key} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/20 p-3">
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-foreground">{metric.label}</p>
                          {metric.description && (
                            <p className="text-[11px] text-muted-foreground leading-relaxed mt-1">
                              {metric.description}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 max-w-44 flex items-center justify-center">
                          <p className="text-xs font-black text-foreground leading-tight text-center break-words">
                            {formatValue(metric.value)}
                          </p>
                        </div>
                      </div>
                    );
                  })}
            </div>
          </div>
        ))}
      </div>

      <div className="glass-strong rounded-2xl p-5 border border-white/5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Table2 className="w-5 h-5 text-primary" />
            <h4 className="text-sm font-black">Per-Trade Detail Rows</h4>
          </div>
          <p className="text-xs text-muted-foreground">
            Showing {totalRows > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} – {Math.min(currentPage * itemsPerPage, totalRows)} of {totalRows}
          </p>
        </div>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[1200px] text-xs">
            <thead className="bg-muted/50">
              <tr>
                {columns.map(([, label]) => (
                  <th key={label} className="px-3 py-3 text-left font-black text-muted-foreground uppercase tracking-wider">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedRows.map((row, index) => {
                const globalIndex = (currentPage - 1) * itemsPerPage + index;
                return (
                  <tr key={`${row.ticket || globalIndex}-${globalIndex}`} className="border-t border-border hover:bg-muted/20">
                    {columns.map(([key]) => (
                      <td key={key} className={`px-3 py-3 whitespace-nowrap ${key === "profit_loss" && Number(row[key]) < 0 ? "text-red-400" : key === "profit_loss" ? "text-green-400" : "text-foreground/75"}`}>
                        {formatValue(row[key])}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-5 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground">
              Page <span className="font-bold text-foreground">{currentPage}</span> of{" "}
              <span className="font-bold text-foreground">{totalPages}</span>
            </p>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="inline-flex items-center justify-center p-2 rounded-lg border border-border bg-muted/20 hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-foreground"
                title="Previous Page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              {getPageNumbers().map((pageNum, idx) => {
                if (pageNum === "...") {
                  return (
                    <span
                      key={`ellipsis-${idx}`}
                      className="px-2 text-xs text-muted-foreground font-bold select-none"
                    >
                      ...
                    </span>
                  );
                }
                return (
                  <button
                    key={`page-${pageNum}`}
                    onClick={() => setCurrentPage(Number(pageNum))}
                    className={`inline-flex items-center justify-center min-w-8 h-8 px-2.5 rounded-lg border text-xs font-bold transition-all ${
                      currentPage === pageNum
                        ? "bg-primary border-primary text-black font-black"
                        : "border-border bg-muted/10 hover:bg-muted/30 text-foreground"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}

              <button
                onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="inline-flex items-center justify-center p-2 rounded-lg border border-border bg-muted/20 hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-foreground"
                title="Next Page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        <p className="text-xs text-muted-foreground mt-3">
          Deep fields like news proximity, MFE/MAE, slippage, fill quality, and rejected orders require external tick/news/order-log data.
        </p>
      </div>
    </motion.div>
  );
}
