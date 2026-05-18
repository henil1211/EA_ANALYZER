const HISTORY_KEY = "ea-analyzer-history";
const SHARE_PREFIX = "ea-analyzer-share-";

export type HistoryEntry = {
  id: string;
  name: string;
  savedAt: string;
  verdict?: string;
  overallScore?: number;
  snapshot: Record<string, unknown>;
};

export function saveToHistory(data: Record<string, unknown>, fileName?: string) {
  if (typeof window === "undefined") return;
  const entry: HistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: fileName || (data.metrics as { ea_name?: string })?.ea_name || "Unnamed report",
    savedAt: new Date().toISOString(),
    verdict: (data.ai_analysis as { verdict?: string })?.verdict,
    overallScore: (data.ai_analysis as { overall_score?: number })?.overall_score,
    snapshot: data,
  };
  const list = loadHistory();
  list.unshift(entry);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 20)));
  return entry.id;
}

export function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

export function loadHistoryEntry(id: string): Record<string, unknown> | null {
  const entry = loadHistory().find((e) => e.id === id);
  return entry?.snapshot ?? null;
}

export function deleteHistoryEntry(id: string) {
  const list = loadHistory().filter((e) => e.id !== id);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}

export function createShareLink(data: Record<string, unknown>): string {
  if (typeof window === "undefined") return "";
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const slim = {
    metrics: data.metrics,
    ai_analysis: {
      verdict: (data.ai_analysis as { verdict?: string })?.verdict,
      overall_score: (data.ai_analysis as { overall_score?: number })?.overall_score,
      executive_summary: (data.ai_analysis as { executive_summary?: string })?.executive_summary,
      prop_firm_score: (data.ai_analysis as { prop_firm_score?: unknown })?.prop_firm_score,
    },
    extended_analysis: data.extended_analysis,
    trades_count: data.trades_count,
    report_type: data.report_type,
  };
  localStorage.setItem(SHARE_PREFIX + id, JSON.stringify(slim));
  return `${window.location.origin}${window.location.pathname}?share=${id}`;
}

export function loadShareFromUrl(): Record<string, unknown> | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const id = params.get("share");
  if (!id) return null;
  try {
    return JSON.parse(localStorage.getItem(SHARE_PREFIX + id) || "null");
  } catch {
    return null;
  }
}
