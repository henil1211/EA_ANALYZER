"use client";

import { FileDown } from "lucide-react";
import { jsPDF } from "jspdf";

export default function AuditPdfExport({ data }: { data: Record<string, any> }) {
  const exportPdf = () => {
    const m = data.metrics || {};
    const ai = data.ai_analysis || {};
    const ext = data.extended_analysis || {};
    const doc = new jsPDF();
    let y = 16;

    const line = (text: string, size = 10, bold = false) => {
      doc.setFontSize(size);
      doc.setFont("helvetica", bold ? "bold" : "normal");
      const lines = doc.splitTextToSize(text, 180);
      doc.text(lines, 14, y);
      y += lines.length * (size * 0.45) + 4;
      if (y > 270) {
        doc.addPage();
        y = 16;
      }
    };

    line("EA Analyzer — Audit Report", 16, true);
    line(`Generated: ${new Date().toLocaleString()}`, 9);
    line(`Verdict: ${ai.verdict || "N/A"} · Score: ${ai.overall_score ?? "—"}/100`, 11, true);
    line(ai.executive_summary || "", 10);
    y += 4;
    line("Key metrics", 12, true);
    line(
      `Net profit: $${m.net_profit} · PF: ${m.profit_factor} · Trades: ${m.total_trades} · Win rate: ${m.win_rate}%`,
      10
    );
    line(
      `Balance DD: ${m.balance_drawdown_maximal || "—"} · Equity DD: ${m.equity_drawdown_maximal || "—"}`,
      10
    );
    line("Prop firm rules", 12, true);
    (ext.prop_firm_check?.rules || []).forEach((r: any) => {
      line(`${r.firm_name}: ${r.passed ? "PASS" : "FAIL"}`, 10);
      r.violations?.forEach((v: string) => line(`  - ${v}`, 9));
    });
    line("Action checklist", 12, true);
    (ext.action_checklist || []).slice(0, 8).forEach((a: any) => line(`[${a.priority}] ${a.text}`, 9));
    line(`Data quality: ${ext.data_quality?.label || "—"} (${ext.data_quality?.score ?? "—"}/100)`, 10);

    doc.save(`ea-audit-${m.symbol || "report"}-${Date.now()}.pdf`);
  };

  return (
    <button
      type="button"
      onClick={exportPdf}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary/20 border border-primary/30 text-primary text-xs font-bold hover:bg-primary/30 transition-colors"
    >
      <FileDown className="w-4 h-4" />
      Export PDF Audit
    </button>
  );
}
