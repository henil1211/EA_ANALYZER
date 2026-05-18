"use client";

import { useEffect, useState } from "react";
import { History, Link2, Trash2, RotateCcw, ChevronLeft } from "lucide-react";
import {
  loadHistory,
  deleteHistoryEntry,
  createShareLink,
  saveToHistory,
  type HistoryEntry,
} from "@/lib/analysisStorage";

type Props = {
  data: Record<string, unknown>;
  fileName?: string;
  onRestore: (snapshot: Record<string, unknown>) => void;
  onBack?: () => void;
};

export default function HistoryShareBar({ data, fileName, onRestore, onBack }: Props) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [shareUrl, setShareUrl] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setHistory(loadHistory());
  }, [data]);

  const handleSave = () => {
    saveToHistory(data, fileName);
    setHistory(loadHistory());
  };

  const handleShare = () => {
    const url = createShareLink(data);
    setShareUrl(url);
    navigator.clipboard?.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="glass rounded-2xl p-4 border border-white/5 space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <button
          type="button"
          onClick={() => onBack && onBack()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/10 text-xs font-bold hover:bg-muted/20"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>

        <button
          type="button"
          onClick={handleSave}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-muted text-xs font-bold hover:bg-muted/80"
        >
          <History className="w-3.5 h-3.5" />
          Save to history
        </button>
        <button
          type="button"
          onClick={handleShare}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/20 text-primary text-xs font-bold hover:bg-primary/30"
        >
          <Link2 className="w-3.5 h-3.5" />
          {copied ? "Link copied!" : "Copy share link"}
        </button>
      </div>
      {shareUrl && (
        <p className="text-[10px] text-zinc-500 break-all">Share summary stored locally: {shareUrl}</p>
      )}
      {history.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">Recent analyses</p>
          {history.map((entry) => {
            const snap: any = entry.snapshot as any;
            const displayName = snap?.metrics?.ea_name || entry.name;
            return (
              <div
                key={entry.id}
                className="flex items-center justify-between gap-2 p-2 rounded-lg bg-black/30 text-xs"
              >
                <div className="min-w-0">
                  <p className="font-bold truncate">{displayName}</p>
                  <p className="text-zinc-500">{entry.verdict} · {entry.overallScore}/100</p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => onRestore(entry.snapshot)}
                    className="p-1.5 rounded hover:bg-muted"
                    title="Restore"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      deleteHistoryEntry(entry.id);
                      setHistory(loadHistory());
                    }}
                    className="p-1.5 rounded hover:bg-rose-500/20 text-rose-400"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
