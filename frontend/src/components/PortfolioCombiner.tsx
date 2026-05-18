"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Upload,
  Layers,
  Plus,
  Trash2,
  TrendingUp,
  Activity,
  AlertTriangle,
  CheckCircle,
  FileText,
  DollarSign,
  TrendingDown,
  Info,
} from "lucide-react";
import { analyzeReport } from "@/lib/api";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

const parseBrokerDate = (dateStr: string | null | undefined): Date | null => {
  if (!dateStr) return null;
  
  // Standardize delimiters: replace periods with hyphens, and spaces with T
  let cleanStr = dateStr.replace(/\./g, "-").replace(" ", "T").trim();
  
  // Extract only the core date-time part: "YYYY-MM-DDTHH:MM:SS" (first 19 characters)
  if (cleanStr.length > 19) {
    cleanStr = cleanStr.substring(0, 19);
  }
  
  const tempDate = new Date(cleanStr);
  if (isNaN(tempDate.getTime())) return null;
  
  // Standard MetaQuotes broker servers are GMT+3 in Summer (DST), GMT+2 in Winter
  // Summer runs from last Sunday of March to last Sunday of October
  const month = tempDate.getMonth(); // 0-indexed (0=Jan, 11=Dec)
  const isSummer = month > 2 && month < 10;
  const brokerOffset = isSummer ? "+03:00" : "+02:00";
  
  // Create standard W3C ISO 8601 offset: "YYYY-MM-DDTHH:MM:SS+HH:MM"
  const parsed = new Date(`${cleanStr}${brokerOffset}`);
  return isNaN(parsed.getTime()) ? tempDate : parsed;
};

interface CombinedReport {
  fileName: string;
  eaName: string;
  metrics: Record<string, any>;
  tradeRows: Record<string, any>[];
  equityCurve: number[];
}

export default function PortfolioCombiner() {
  const [files, setFiles] = useState<File[]>([]);
  const [reports, setReports] = useState<CombinedReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [portfolioStartBalance, setPortfolioStartBalance] = useState<number>(0);
  const [customEANames, setCustomEANames] = useState<Record<string, string>>({});

  // 1. Handle drag over & drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const newFiles = Array.from(e.dataTransfer.files).filter(
        (file) => file.name.endsWith(".xlsx") || file.name.endsWith(".html") || file.name.endsWith(".htm")
      );
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files).filter(
        (file) => file.name.endsWith(".xlsx") || file.name.endsWith(".html") || file.name.endsWith(".htm")
      );
      setFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const clearAll = () => {
    setFiles([]);
    setReports([]);
    setError("");
  };

  // 2. Process & Combine Reports
  const combineReports = async () => {
    if (files.length < 2) {
      setError("Please select at least 2 reports to combine.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const promises = files.map(async (file, idx) => {
        const res = await analyzeReport(file);
        const metrics = res.metrics || {};
        const tradeRows = res.detailed_analysis?.trade_rows || [];
        const equityCurve = res.equity_curve || [];
        
        // Try to generate a smart default EA name from symbol or filename (suffix index for uniqueness)
        const cleanSymbol = metrics.symbol 
          ? `${metrics.symbol} (#${idx + 1})`
          : `${file.name.replace(/\.[^/.]+$/, "")} (#${idx + 1})`;
        
        return {
          fileName: file.name,
          eaName: cleanSymbol,
          metrics,
          tradeRows,
          equityCurve,
        };
      });

      const parsedReports = await Promise.all(promises);
      setReports(parsedReports);

      // Set initial combined deposit
      const totalInitialDeposit = parsedReports.reduce(
        (sum, r) => sum + Number(r.metrics.deposit || 10000),
        0
      );
      setPortfolioStartBalance(totalInitialDeposit);
    } catch (e: any) {
      setError(e.message || "Failed to analyze and combine reports.");
    } finally {
      setLoading(false);
    }
  };

  // 3. Mathematical Merging & Alignments (Memoized)
  const portfolioData = useMemo(() => {
    if (reports.length === 0) return null;

    const startCap = portfolioStartBalance || 20000;

    // A. Gather and label all trades
    const allTrades: { eaIdx: number; eaName: string; time: number; profit: number; lot: number }[] = [];
    
    reports.forEach((rep, eaIdx) => {
      const eaName = customEANames[rep.fileName] || rep.eaName;
      rep.tradeRows.forEach((t) => {
        const tTimeStr = t.close_time || t.open_time;
        const parsedDt = parseBrokerDate(tTimeStr);
        const timeMs = parsedDt ? parsedDt.getTime() : 0;
        const profit = Number(t.profit_loss || 0);
        const lot = Number(t.lot_size || 0.1);
        
        if (timeMs > 0) {
          allTrades.push({
            eaIdx,
            eaName,
            time: timeMs,
            profit,
            lot,
          });
        }
      });
    });

    // Sort chronologically
    allTrades.sort((a, b) => a.time - b.time);

    // B. Reconstruct Combined Equity Curve
    let balance = startCap;
    let peak = startCap;
    let maxDD = 0;
    let winsCount = 0;
    
    // Tracks balance per individual EA starting from its original backtest share
    const eaBalances = reports.map(r => Number(r.metrics.deposit || 10000));
    
    const combinedCurve = allTrades.map((t, idx) => {
      balance += t.profit;
      peak = Math.max(peak, balance);
      maxDD = Math.max(maxDD, peak - balance);
      
      if (t.profit > 0) winsCount++;

      // Update specific EA balance
      eaBalances[t.eaIdx] += t.profit;

      // Pack object for Recharts
      const point: Record<string, any> = {
        trade: idx + 1,
        Combined: Math.round(balance),
      };

      // Add individual EA curves
      reports.forEach((rep, eaIdx) => {
        const label = customEANames[rep.fileName] || rep.eaName;
        point[label] = Math.round(eaBalances[eaIdx]);
      });

      return point;
    });

    const totalProfit = balance - startCap;
    const maxDDPct = peak > 0 ? (maxDD / peak) * 100 : 0;
    const winRate = allTrades.length ? (winsCount / allTrades.length) * 100 : 0;

    // C. Weekly Returns Correlation Matrix
    // Group profits by week (arbitrary anchor of first trade time)
    const minTradeTime = allTrades.length ? allTrades[0].time : Date.now();
    const msInWeek = 7 * 24 * 60 * 60 * 1000;
    
    const weeklyReturnsMap: Record<number, number[]> = {}; // weekIndex -> [ea0Return, ea1Return, ...]
    
    allTrades.forEach((t) => {
      const weekIdx = Math.floor((t.time - minTradeTime) / msInWeek);
      if (!weeklyReturnsMap[weekIdx]) {
        weeklyReturnsMap[weekIdx] = reports.map(() => 0);
      }
      weeklyReturnsMap[weekIdx][t.eaIdx] += t.profit;
    });

    const weeks = Object.keys(weeklyReturnsMap).map(Number).sort((a, b) => a - b);
    const weeklyReturnVectors = reports.map((_, eaIdx) => {
      return weeks.map(w => weeklyReturnsMap[w][eaIdx]);
    });

    // Pearson Correlation Function
    const getPearsonCorrelation = (x: number[], y: number[]) => {
      const n = x.length;
      if (n === 0) return 0;
      
      const meanX = x.reduce((a, b) => a + b, 0) / n;
      const meanY = y.reduce((a, b) => a + b, 0) / n;
      
      let num = 0;
      let denX = 0;
      let denY = 0;
      
      for (let i = 0; i < n; i++) {
        const diffX = x[i] - meanX;
        const diffY = y[i] - meanY;
        num += diffX * diffY;
        denX += diffX * diffX;
        denY += diffY * diffY;
      }
      
      if (denX === 0 || denY === 0) return 0;
      return num / Math.sqrt(denX * denY);
    };

    // Build the Matrix
    const correlationMatrix: number[][] = [];
    reports.forEach((_, r1Idx) => {
      correlationMatrix[r1Idx] = [];
      reports.forEach((_, r2Idx) => {
        if (r1Idx === r2Idx) {
          correlationMatrix[r1Idx][r2Idx] = 1.0;
        } else {
          correlationMatrix[r1Idx][r2Idx] = getPearsonCorrelation(
            weeklyReturnVectors[r1Idx],
            weeklyReturnVectors[r2Idx]
          );
        }
      });
    });

    // Consolidate global stats
    const totalGrossProfit = allTrades.reduce((sum, t) => t.profit > 0 ? sum + t.profit : sum, 0);
    const totalGrossLoss = allTrades.reduce((sum, t) => t.profit < 0 ? sum + Math.abs(t.profit) : sum, 0);
    const combinedProfitFactor = totalGrossLoss > 0 ? totalGrossProfit / totalGrossLoss : totalGrossProfit > 0 ? 99.9 : 0;

    return {
      allTrades,
      combinedCurve,
      totalProfit,
      maxDD,
      maxDDPct,
      winRate,
      combinedProfitFactor,
      correlationMatrix,
      finalBalance: balance,
    };
  }, [reports, portfolioStartBalance, customEANames]);

  // Diversification Rating Assessment
  const diversificationReview = useMemo(() => {
    if (!portfolioData || reports.length < 2) return null;

    let totalCorrelation = 0;
    let count = 0;
    
    portfolioData.correlationMatrix.forEach((row, rIdx) => {
      row.forEach((val, cIdx) => {
        if (rIdx < cIdx) {
          totalCorrelation += val;
          count++;
        }
      });
    });

    const avgCorr = count > 0 ? totalCorrelation / count : 0;
    
    let grade = "EXCELLENT";
    let color = "text-green-400";
    let advice = "Your EAs are trading highly independent, non-correlated strategies. When one experiences a drawdown, the others offset the loss. This is a top-tier hedge-fund style portfolio setup.";
    
    if (avgCorr > 0.7) {
      grade = "HIGH RISK (CORRELATED)";
      color = "text-red-400";
      advice = "Your EAs are highly correlated! They are taking risks at the same time in the same direction. Running these together will compound drawdowns and double your account exposure during trend spikes. Consider adding a non-correlated metal/crypto EA to diversify.";
    } else if (avgCorr > 0.3) {
      grade = "MODERATE DIVERSIFICATION";
      color = "text-amber-400";
      advice = "Moderate correlation detected. The strategies share some joint exposure (likely due to USD directionality). It is reasonably stable but caution is recommended during major news spikes.";
    }

    return {
      avgCorr,
      grade,
      color,
      advice,
    };
  }, [portfolioData, reports]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-border pb-6">
        <h2 className="text-2xl font-black tracking-tight flex items-center gap-3">
          <Layers className="w-6 h-6 text-primary" />
          Multi-Report Portfolio Combiner
        </h2>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
          Chronologically aligns trade entries from multiple EA backtest reports to calculate portfolio drawdown, profit factors, and Pearson correlation coefficients.
        </p>
      </div>

      {reports.length === 0 ? (
        /* Workspace Setup Mode */
        <div className="max-w-3xl mx-auto space-y-6">
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className="border-2 border-dashed border-border/80 hover:border-primary/50 transition-all rounded-3xl p-10 text-center space-y-4 bg-muted/10 relative overflow-hidden group cursor-pointer"
          >
            <input
              type="file"
              multiple
              onChange={handleFileSelect}
              className="absolute inset-0 opacity-0 cursor-pointer"
              accept=".xlsx,.html,.htm"
            />
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
              <Upload className="w-7 h-7 text-primary" />
            </div>
            <div>
              <p className="text-sm font-bold text-foreground">Drag & Drop Multiple Backtest Reports Here</p>
              <p className="text-xs text-muted-foreground mt-1">Supports MT5 MT4 HTML Reports and XLSX sheets</p>
            </div>
            <button className="px-4 py-2 text-xs font-bold bg-primary text-foreground rounded-xl shadow-lg shadow-primary/10">
              Browse Files
            </button>
          </div>

          {/* Queued Files List */}
          {files.length > 0 && (
            <div className="glass-strong rounded-3xl p-6 border border-white/5 space-y-4">
              <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground">Queued Reports ({files.length})</h3>
              <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                {files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3.5 rounded-2xl bg-muted/20 border border-border">
                    <div className="flex items-center gap-3">
                      <FileText className="w-4 h-4 text-primary" />
                      <span className="text-xs font-bold text-foreground/90">{file.name}</span>
                    </div>
                    <button
                      onClick={() => removeFile(idx)}
                      className="p-1 text-muted-foreground hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-border/60">
                <button
                  onClick={clearAll}
                  className="px-4 py-2.5 text-xs font-bold hover:text-foreground text-muted-foreground transition-colors"
                >
                  Clear All
                </button>
                <button
                  onClick={combineReports}
                  disabled={files.length < 2 || loading}
                  className="px-5 py-2.5 text-xs font-bold bg-primary text-foreground rounded-xl flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <>Combining & Merging...</>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Combine Portfolio
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
          {error && <p className="text-xs font-bold text-red-400 text-center">{error}</p>}
        </div>
      ) : (
        /* Consolidated Dashboard View */
        portfolioData && (
          <div className="space-y-8">
            <div className="flex justify-between items-center">
              <button
                onClick={clearAll}
                className="px-4 py-2 text-xs font-bold bg-muted hover:bg-muted/70 text-foreground border border-border rounded-xl transition-all"
              >
                ← Back to Upload Screen
              </button>

              {/* Start capital modifier */}
              <div className="flex items-center gap-3 bg-muted/30 p-2 rounded-xl border border-border">
                <span className="text-[10px] font-bold text-muted-foreground uppercase pl-1">Starting Balance:</span>
                <input
                  type="number"
                  value={portfolioStartBalance}
                  onChange={(e) => setPortfolioStartBalance(Number(e.target.value))}
                  className="w-24 bg-muted p-1 text-xs font-bold text-primary rounded-lg border border-border text-center"
                />
              </div>
            </div>

            {/* Combined KPI Scorecard */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1.5">Consolidated Net Profit</p>
                <p className={`text-2xl font-black ${portfolioData.totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  ${portfolioData.totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
                <span className="text-[10px] text-muted-foreground mt-0.5 block">
                  Final Equity: <span className="font-bold text-foreground">${portfolioData.finalBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </span>
              </div>

              <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1.5">Consolidated Profit Factor</p>
                <p className="text-2xl font-black text-foreground">
                  {portfolioData.combinedProfitFactor.toFixed(2)}
                </p>
                <span className="text-[10px] text-muted-foreground mt-0.5 block">
                  Consolidated risk metric
                </span>
              </div>

              <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1.5">Consolidated Win Rate</p>
                <p className="text-2xl font-black text-foreground">
                  {portfolioData.winRate.toFixed(1)}%
                </p>
                <span className="text-[10px] text-muted-foreground mt-0.5 block">
                  Total trades aligned: <span className="font-bold text-foreground">{portfolioData.allTrades.length}</span>
                </span>
              </div>

              <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                <p className="text-[10px] font-bold text-red-400 uppercase tracking-widest mb-1.5">Max Equity Drawdown</p>
                <p className="text-2xl font-black text-red-500">
                  {portfolioData.maxDDPct.toFixed(1)}%
                </p>
                <span className="text-[10px] text-muted-foreground mt-0.5 block">
                  Cash drop: <span className="font-bold text-foreground">${portfolioData.maxDD.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </span>
              </div>
            </div>

            {/* Custom Label Customizer */}
            <div className="p-5 rounded-2xl bg-muted/10 border border-border">
              <span className="font-black uppercase tracking-widest text-[9px] text-muted-foreground block mb-3">Rename EAs for Chart Keys</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {reports.map((rep, idx) => (
                  <div key={idx} className="flex flex-col gap-1.5">
                    <label className="text-[9px] font-bold text-muted-foreground truncate">{rep.fileName}</label>
                    <input
                      type="text"
                      placeholder={rep.eaName}
                      value={customEANames[rep.fileName] || ""}
                      onChange={(e) => setCustomEANames(prev => ({ ...prev, [rep.fileName]: e.target.value }))}
                      className="bg-muted px-2.5 py-1.5 text-xs font-bold text-foreground rounded-lg border border-border"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Grid Layout: Combined Equity Chart + Correlation Matrix */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Portfolio Curve Graph */}
              <div className="lg:col-span-2 p-6 rounded-2xl bg-muted/20 border border-border space-y-4">
                <div className="flex justify-between items-center text-xs font-bold text-muted-foreground">
                  <span>Consolidated Timeline Equity Curve</span>
                  <span className="text-primary font-black uppercase">Consolidated Output</span>
                </div>
                <div className="h-[300px] w-full mt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={portfolioData.combinedCurve} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="combCol" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                      <XAxis dataKey="trade" stroke="#52525b" fontSize={9} tickLine={false} />
                      <YAxis stroke="#52525b" fontSize={9} tickLine={false} domain={["auto", "auto"]} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #27272a",
                          borderRadius: "12px",
                          fontSize: "11px",
                          color: "#fafafa",
                        }}
                      />
                      <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px', fontWeight: 'bold' }} />
                      
                      {/* Individual EA curves */}
                      {reports.map((rep, idx) => {
                        const name = customEANames[rep.fileName] || rep.eaName;
                        const colors = ["#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];
                        return (
                          <Area
                            key={name}
                            type="monotone"
                            dataKey={name}
                            stroke={colors[idx % colors.length]}
                            strokeWidth={1}
                            fill="transparent"
                          />
                        );
                      })}
                      
                      {/* Thick Combined Portfolio Curve */}
                      <Area
                        type="monotone"
                        dataKey="Combined"
                        stroke="#3b82f6"
                        strokeWidth={3}
                        fill="url(#combCol)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Correlation Matrix and Diversification Audit */}
              <div className="p-6 rounded-2xl bg-muted/20 border border-border flex flex-col justify-between space-y-6">
                <div>
                  <div className="flex items-center gap-1.5 mb-3">
                    <h3 className="text-sm font-black uppercase tracking-widest text-muted-foreground">Pearson Correlation Matrix</h3>
                    <Info className="w-3.5 h-3.5 text-muted-foreground" />
                  </div>
                  
                  {/* The Matrix Table */}
                  <div className="overflow-x-auto border border-border rounded-xl">
                    <table className="w-full text-center text-xs font-bold">
                      <thead className="bg-muted text-[10px] text-muted-foreground uppercase tracking-widest border-b border-border">
                        <tr>
                          <th className="p-2.5 text-left truncate max-w-[80px]">EA</th>
                          {reports.map((rep, idx) => (
                            <th key={idx} className="p-2.5 truncate max-w-[60px]">
                              {customEANames[rep.fileName] || rep.eaName}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {reports.map((r1, r1Idx) => (
                          <tr key={r1Idx} className="hover:bg-muted/10">
                            <td className="p-2.5 text-left text-muted-foreground text-[10px] truncate max-w-[80px] font-sans">
                              {customEANames[r1.fileName] || r1.eaName}
                            </td>
                            {reports.map((_, r2Idx) => {
                              const value = portfolioData.correlationMatrix[r1Idx][r2Idx];
                              let cellColor = "text-foreground";
                              let cellBg = "";
                              
                              if (r1Idx === r2Idx) {
                                cellColor = "text-muted-foreground opacity-55";
                              } else if (value > 0.7) {
                                cellColor = "text-red-400 font-black";
                                cellBg = "bg-red-500/5";
                              } else if (value < 0.3) {
                                cellColor = "text-green-400 font-black";
                                cellBg = "bg-green-500/5";
                              } else {
                                cellColor = "text-amber-400 font-bold";
                              }
                              
                              return (
                                <td key={r2Idx} className={`p-2.5 font-mono ${cellColor} ${cellBg}`}>
                                  {value.toFixed(2)}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Audit Verdict */}
                {diversificationReview && (
                  <div className="pt-4 border-t border-border/80 space-y-3">
                    <span className="font-black uppercase tracking-widest text-[9px] text-muted-foreground block">Portfolio Audit</span>
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-bold text-foreground">Avg Weekly Correlation:</span>
                      <span className="font-mono text-xs font-extrabold text-primary">
                        {diversificationReview.avgCorr.toFixed(2)}
                      </span>
                    </div>
                    <div className={`px-3 py-1.5 rounded-lg border text-[10px] font-black uppercase text-center border-border/80 ${diversificationReview.color}`}>
                      {diversificationReview.grade}
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      {diversificationReview.advice}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      )}
    </div>
  );
}
