"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sliders,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Shield,
  Activity,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  Building,
  RefreshCw,
  Compass,
  Shuffle,
  Calendar,
} from "lucide-react";
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

interface LiveSimulatorProps {
  metrics: Record<string, any>;
  behavior: Record<string, any>;
  tradeRows: Record<string, any>[];
  equityCurve: number[];
}

export default function LiveSimulator({
  metrics,
  behavior,
  tradeRows,
  equityCurve,
}: LiveSimulatorProps) {
  const [activeTab, setActiveTab] = useState<"broker" | "montecarlo" | "news" | "risk" | "strategy" | "propfirm">("broker");

  // Auto-detect Asset Class from uploaded Symbol
  const symbolUpper = String(metrics.symbol || "EURUSD").toUpperCase();
  const getInitialAssetClass = () => {
    if (symbolUpper.includes("XAU") || symbolUpper.includes("GOLD")) return "gold";
    if (symbolUpper.includes("JPY")) return "jpy";
    if (symbolUpper.includes("BTC") || symbolUpper.includes("ETH") || symbolUpper.includes("CRYPTO")) return "crypto";
    if (symbolUpper.includes("US30") || symbolUpper.includes("GER30") || symbolUpper.includes("DE30") || symbolUpper.includes("NAS") || symbolUpper.includes("SPX") || symbolUpper.includes("IND")) return "indices";
    return "forex";
  };

  const [assetClass, setAssetClass] = useState<"forex" | "gold" | "jpy" | "indices" | "crypto">(getInitialAssetClass);

  // Set multipliers dynamically (USD cost per lot per pip)
  let costMultiplier = 10; 
  let pipWord = "Pips";
  let unitExplanation = "1 Pip = 10 Points";

  if (assetClass === "jpy") {
    costMultiplier = 9.3; 
    pipWord = "Pips";
    unitExplanation = "1 Pip = 10 Points";
  } else if (assetClass === "crypto") {
    costMultiplier = 1.0; 
    pipWord = "Points";
    unitExplanation = "1 Point = $1.00 move";
  } else if (assetClass === "indices") {
    costMultiplier = 1.0; 
    pipWord = "Points";
    unitExplanation = "1 Index Point = $1.00 move";
  } else if (assetClass === "gold") {
    costMultiplier = 10.0; 
    pipWord = "Pips / Points";
    unitExplanation = "1 Point (0.10 move) = 1 Pip = $10 per lot";
  }

  // --- Feature 1: Live Broker Simulator State ---
  const [slippagePips, setSlippagePips] = useState(1.0);
  const [spreadMarkupPips, setSpreadMarkupPips] = useState(0.5);

  // --- Feature 2: Account Blowout Calculator State ---
  const [startingCapital, setStartingCapital] = useState(metrics.deposit || 10000);
  const [riskMultiplier, setRiskMultiplier] = useState(1.0);

  // --- Option 1 & 4: Monte Carlo & News Impact States ---
  const [mcDrawdownLimit, setMcDrawdownLimit] = useState(25); // cap in %
  const [newsAvoidFilter, setNewsAvoidFilter] = useState(false);
  const [spreadSpikePips, setSpreadSpikePips] = useState(1.5); // spread spike during news (in pips/points)

  // Parse total trades
  const totalTrades = tradeRows.length || metrics.total_trades || 100;

  // ──────────────────────────────────────────────────────────────────────────
  // 1. Calculations for Live Broker Simulator
  // ──────────────────────────────────────────────────────────────────────────
  const costPerLot = (slippagePips + spreadMarkupPips) * costMultiplier;
  
  let simulatedNetProfit = 0;
  let simulatedGrossProfit = 0;
  let simulatedGrossLoss = 0;
  
  const simulatedEquityCurve: number[] = [startingCapital];
  let currentBalance = startingCapital;

  const adjustedTradeRows = tradeRows.map((trade) => {
    const lotSize = Number(trade.lot_size || 0.1);
    const originalProfit = Number(trade.profit_loss || 0);
    const executionCost = lotSize * costPerLot;
    const adjustedProfit = originalProfit - executionCost;

    simulatedNetProfit += adjustedProfit;
    if (adjustedProfit > 0) {
      simulatedGrossProfit += adjustedProfit;
    } else {
      simulatedGrossLoss += Math.abs(adjustedProfit);
    }

    currentBalance += adjustedProfit;
    simulatedEquityCurve.push(roundTo(currentBalance, 2));

    return {
      ...trade,
      adjustedProfit: roundTo(adjustedProfit, 2),
    } as Record<string, any>;
  });

  const simulatedProfitFactor = simulatedGrossLoss > 0 
    ? roundTo(simulatedGrossProfit / simulatedGrossLoss, 2) 
    : simulatedGrossProfit > 0 ? 99.9 : 0;

  // Re-generate chart data comparison
  const originalStart = equityCurve[0] || startingCapital;
  const chartData = adjustedTradeRows.map((trade, idx) => {
    // scale original equity curve if startingCapital is adjusted
    const scaleFactor = startingCapital / originalStart;
    const originalVal = (equityCurve[idx] || originalStart) * scaleFactor;
    return {
      trade: idx + 1,
      Original: roundTo(originalVal, 2),
      Adjusted: simulatedEquityCurve[idx + 1] || startingCapital,
    };
  });

  const profitLossDiffPct = metrics.net_profit 
    ? ((simulatedNetProfit - metrics.net_profit) / Math.abs(metrics.net_profit)) * 100 
    : 0;

  const isHighlySensitive = costPerLot > 0 && Math.abs(profitLossDiffPct) > 30;

  // ──────────────────────────────────────────────────────────────────────────
  // 1.5. News Event Generator & Matching Logic (Option 4)
  // ──────────────────────────────────────────────────────────────────────────
  const tradesWithTime = useMemo(() => {
    console.log("DEBUG: tradeRows count =", tradeRows?.length);
    if (tradeRows && tradeRows.length > 0) {
      console.log("DEBUG: First trade row =", tradeRows[0]);
    }
    const parsed = tradeRows.map((t: any) => {
      const parsedDt = t.close_time ? parseBrokerDate(t.close_time) : (t.open_time ? parseBrokerDate(t.open_time) : null);
      return {
        ...t,
        parsedDate: parsedDt
      };
    });
    const filtered = parsed.filter((t: any) => t.parsedDate instanceof Date && !isNaN(t.parsedDate.getTime()));
    console.log("DEBUG: Filtered trades count =", filtered.length);
    if (filtered.length > 0) {
      console.log("DEBUG: First filtered trade parsedDate =", filtered[0].parsedDate);
    }
    return filtered;
  }, [tradeRows]);

  // Reproducible news events inside the backtest range (using real-world calendar frequency rules)
  const newsEvents = useMemo(() => {
    const list: { id: string; name: string; impact: "HIGH"; time: Date; description: string }[] = [];
    if (tradesWithTime.length > 2) {
      const times = tradesWithTime.map((t: any) => t.parsedDate!.getTime());
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      
      const startDate = new Date(minTime);
      const endDate = new Date(maxTime);
      
      let currentYear = startDate.getFullYear();
      let currentMonth = startDate.getMonth();
      
      const endYear = endDate.getFullYear();
      const endMonth = endDate.getMonth();
      
      while (currentYear < endYear || (currentYear === endYear && currentMonth <= endMonth)) {
        const isSummer = currentMonth > 1 && currentMonth < 10; // US DST is March to November roughly (using Apr-Oct as core)
        const usOffset = isSummer ? "-04:00" : "-05:00";
        
        // 1. NFP - First Friday of the month (8:30 AM US Eastern Time)
        let firstFriday = 1;
        for (let d = 1; d <= 7; d++) {
          const date = new Date(currentYear, currentMonth, d);
          if (date.getDay() === 5) {
            firstFriday = d;
            break;
          }
        }
        const nfpDate = new Date(`${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(firstFriday).padStart(2, '0')}T08:30:00${usOffset}`);
        if (nfpDate.getTime() >= minTime && nfpDate.getTime() <= maxTime) {
          list.push({
            id: `news_nfp_${nfpDate.getTime()}`,
            name: "NFP - Non-Farm Payrolls",
            impact: "HIGH",
            time: nfpDate,
            description: "US employment report showing new jobs added. Extreme market-wide volatility expected."
          });
        }
        
        // 2. CPI Inflation Data - Second Tuesday of the month (8:30 AM US Eastern Time)
        let tuesdayCount = 0;
        let secondTuesday = 8;
        for (let d = 1; d <= 31; d++) {
          const date = new Date(currentYear, currentMonth, d);
          if (date.getDay() === 2) {
            tuesdayCount++;
            if (tuesdayCount === 2) {
              secondTuesday = d;
              break;
            }
          }
        }
        const cpiDate = new Date(`${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(secondTuesday).padStart(2, '0')}T08:30:00${usOffset}`);
        if (cpiDate.getTime() >= minTime && cpiDate.getTime() <= maxTime) {
          list.push({
            id: `news_cpi_${cpiDate.getTime()}`,
            name: "CPI Inflation Data Release",
            impact: "HIGH",
            time: cpiDate,
            description: "US Consumer Price Index inflation report. Massive gold and USD volatility expected."
          });
        }

        // 3. FOMC Rate Decision - Third Wednesday of the month (2:00 PM US Eastern Time)
        let wednesdayCount = 0;
        let thirdWednesday = 15;
        for (let d = 1; d <= 31; d++) {
          const date = new Date(currentYear, currentMonth, d);
          if (date.getDay() === 3) {
            wednesdayCount++;
            if (wednesdayCount === 3) {
              thirdWednesday = d;
              break;
            }
          }
        }
        const fomcDate = new Date(`${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(thirdWednesday).padStart(2, '0')}T14:00:00${usOffset}`);
        if (fomcDate.getTime() >= minTime && fomcDate.getTime() <= maxTime) {
          list.push({
            id: `news_fomc_${fomcDate.getTime()}`,
            name: "FOMC Interest Rate Decision",
            impact: "HIGH",
            time: fomcDate,
            description: "Federal Reserve interest rate announcement and press conference. High probability of broker slippage."
          });
        }

        // 4. ECB Press Conference - Second Thursday of the month (1:45 PM Central European Time)
        let thursdayCount = 0;
        let secondThursday = 10;
        for (let d = 1; d <= 31; d++) {
          const date = new Date(currentYear, currentMonth, d);
          if (date.getDay() === 4) {
            thursdayCount++;
            if (thursdayCount === 2) {
              secondThursday = d;
              break;
            }
          }
        }
        const euOffset = isSummer ? "+02:00" : "+01:00";
        const ecbDate = new Date(`${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(secondThursday).padStart(2, '0')}T13:45:00${euOffset}`);
        if (ecbDate.getTime() >= minTime && ecbDate.getTime() <= maxTime) {
          list.push({
            id: `news_ecb_${ecbDate.getTime()}`,
            name: "ECB Press Conference",
            impact: "HIGH",
            time: ecbDate,
            description: "European Central Bank monetary policy meeting and rate decisions."
          });
        }

        currentMonth++;
        if (currentMonth > 11) {
          currentMonth = 0;
          currentYear++;
        }
      }
    }
    return list.sort((a, b) => a.time.getTime() - b.time.getTime());
  }, [tradesWithTime]);

  // Map news info to adjustedTradeRows
  const tradesWithNewsInfo = useMemo(() => {
    return adjustedTradeRows.map((trade: any) => {
      const parsedDt = trade.close_time ? parseBrokerDate(trade.close_time) : (trade.open_time ? parseBrokerDate(trade.open_time) : null);
      const tTime = parsedDt ? parsedDt.getTime() : null;
      if (!tTime) return { ...trade, isNewsAffected: false, matchedNews: null } as Record<string, any>;
      
      const matchedNews = newsEvents.find(n => Math.abs(n.time.getTime() - tTime) <= 60 * 60 * 1000);
      return {
        ...trade,
        isNewsAffected: !!matchedNews,
        matchedNews: matchedNews || null
      } as Record<string, any>;
    });
  }, [adjustedTradeRows, newsEvents]);

  // Compute news-filtered outcomes
  let newsFilteredNetProfit = 0;
  let newsFilteredGrossProfit = 0;
  let newsFilteredGrossLoss = 0;
  let newsFilteredBalance = startingCapital;
  const newsFilteredEquityCurve: number[] = [startingCapital];
  let newsAffectedTradesCount = 0;

  const newsSimulatedTrades = tradesWithNewsInfo.map((trade: any) => {
    let finalProfit = Number(trade.adjustedProfit || 0);
    
    if (trade.isNewsAffected) {
      newsAffectedTradesCount++;
      if (newsAvoidFilter) {
        finalProfit = 0;
      } else {
        const lotSize = Number(trade.lot_size || 0.1);
        const spikeCost = lotSize * spreadSpikePips * costMultiplier;
        finalProfit -= spikeCost;
      }
    }
    
    newsFilteredNetProfit += finalProfit;
    if (finalProfit > 0) {
      newsFilteredGrossProfit += finalProfit;
    } else {
      newsFilteredGrossLoss += Math.abs(finalProfit);
    }
    
    newsFilteredBalance += finalProfit;
    newsFilteredEquityCurve.push(roundTo(newsFilteredBalance, 2));
    
    return {
      ...trade,
      newsSimulatedProfit: roundTo(finalProfit, 2)
    };
  });

  const newsSimulatedProfitFactor = newsFilteredGrossLoss > 0
    ? roundTo(newsFilteredGrossProfit / newsFilteredGrossLoss, 2)
    : newsFilteredGrossProfit > 0 ? 99.9 : 0;

  const newsChartData = newsSimulatedTrades.map((trade, idx) => {
    return {
      trade: idx + 1,
      Original: chartData[idx]?.Original || startingCapital,
      Adjusted: chartData[idx]?.Adjusted || startingCapital,
      NewsSimulated: newsFilteredEquityCurve[idx + 1] || startingCapital
    };
  });

  // ──────────────────────────────────────────────────────────────────────────
  // 1.6. Monte Carlo Shuffling Computations (Option 1)
  // ──────────────────────────────────────────────────────────────────────────
  const monteCarloRuns = useMemo(() => {
    if (adjustedTradeRows.length === 0) return [];
    
    const runsCount = 200;
    const list: { finalProfit: number; maxDD: number; curve: number[] }[] = [];
    
    for (let s = 0; s < runsCount; s++) {
      const shuffled = [...adjustedTradeRows];
      for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
      }
      
      let balance = startingCapital;
      let peak = startingCapital;
      let maxDD = 0;
      const curve: number[] = [startingCapital];
      
      shuffled.forEach(t => {
        const profit = Number(t.adjustedProfit || 0);
        balance += profit;
        curve.push(roundTo(balance, 2));
        peak = Math.max(peak, balance);
        maxDD = Math.max(maxDD, ((peak - balance) / peak) * 100);
      });
      
      list.push({
        finalProfit: balance - startingCapital,
        maxDD,
        curve
      });
    }
    
    return list;
  }, [adjustedTradeRows, startingCapital]);

  const mcWorst = monteCarloRuns.length ? [...monteCarloRuns].sort((a, b) => b.maxDD - a.maxDD)[0] : { finalProfit: 0, maxDD: 0, curve: [] };
  const mcBest = monteCarloRuns.length ? [...monteCarloRuns].sort((a, b) => b.finalProfit - a.finalProfit)[0] : { finalProfit: 0, maxDD: 0, curve: [] };
  const mcMedian = monteCarloRuns.length ? [...monteCarloRuns].sort((a, b) => a.finalProfit - b.finalProfit)[Math.floor(monteCarloRuns.length / 2)] : { finalProfit: 0, maxDD: 0, curve: [] };
  
  const mcBlowouts = monteCarloRuns.filter(r => r.maxDD >= mcDrawdownLimit).length;
  const mcBlowoutRiskPct = monteCarloRuns.length ? roundTo((mcBlowouts / monteCarloRuns.length) * 100, 1) : 0;

  // Build Monte Carlo Chart Data
  const mcChartData = useMemo(() => {
    if (adjustedTradeRows.length === 0) return [];
    return adjustedTradeRows.map((_, idx) => {
      return {
        trade: idx + 1,
        Original: chartData[idx]?.Original || startingCapital,
        Adjusted: chartData[idx]?.Adjusted || startingCapital,
        Best: mcBest.curve[idx + 1] || startingCapital,
        Worst: mcWorst.curve[idx + 1] || startingCapital,
        Median: mcMedian.curve[idx + 1] || startingCapital
      };
    });
  }, [adjustedTradeRows, mcBest, mcWorst, mcMedian, chartData, startingCapital]);

  // ──────────────────────────────────────────────────────────────────────────
  // 2. Calculations for Account Blowout & Survival
  // ──────────────────────────────────────────────────────────────────────────
  const originalDrawdownPct = metrics.maximal_drawdown_pct || 5.0;
  const simulatedDrawdownPct = roundTo(originalDrawdownPct * riskMultiplier, 2);

  // Mathematical Gambler's Ruin / Drawdown probability over time
  // Risk of Ruin = ((1 - W) / W) ^ consecutive_losses_max
  const winRateFraction = (metrics.win_rate || 50) / 100;
  const maxConsecLosses = metrics.consecutive_losses_max || 5;
  const rawRuinProb = winRateFraction > 0 && winRateFraction < 1
    ? Math.pow((1 - winRateFraction) / winRateFraction, maxConsecLosses)
    : 0.1;

  // Scale ruin probability cleanly based on simulated drawdown and risk multiplier
  const blowout30d = Math.min(100, Math.max(1, Math.round(100 * (1 - Math.exp(-0.012 * simulatedDrawdownPct * (1 + rawRuinProb))))));
  const blowout90d = Math.min(100, Math.max(2, Math.round(100 * (1 - Math.exp(-0.038 * simulatedDrawdownPct * (1 + rawRuinProb))))));
  const blowout365d = Math.min(100, Math.max(5, Math.round(100 * (1 - Math.exp(-0.16 * simulatedDrawdownPct * (1 + rawRuinProb))))));

  const blowoutColor = simulatedDrawdownPct > 45 ? "text-red-400" : simulatedDrawdownPct > 20 ? "text-orange-400" : "text-green-400";
  const blowoutBg = simulatedDrawdownPct > 45 ? "bg-red-500/10 border-red-500/20" : simulatedDrawdownPct > 20 ? "bg-orange-500/10 border-orange-500/20" : "bg-green-500/10 border-green-500/20";

  // ──────────────────────────────────────────────────────────────────────────
  // 3. Strategy Decoder logic
  // ──────────────────────────────────────────────────────────────────────────
  const isMartingale = behavior.is_martingale || behavior.martingale_confidence > 0.25;
  const isGrid = behavior.is_grid || behavior.grid_confidence > 0.25;
  const isScalping = behavior.is_scalping || behavior.scalping_confidence > 0.25;
  const isAveraging = behavior.is_averaging_down || behavior.averaging_confidence > 0.25;

  let strategyType = "Standard Trend Following / Swing";
  let strategyRiskRating = "Low to Medium";
  let strategyDescription = "This strategy enters trades based on standard technical parameters with uniform or variable lot sizes that align with typical trend-following or range-bound strategies. It exhibits no structural warning signs of dangerous recovery models.";

  if (isMartingale && isGrid) {
    strategyType = "Martingale-Grid Hybrid Recovery";
    strategyRiskRating = "EXTREME RISK";
    strategyDescription = "This is the most dangerous EA style. It builds a grid of orders as the market goes against it and doubles the lot size of subsequent orders (Martingale) to force a quick break-even exit. While this creates a beautiful, straight equity curve in backtests, it is structurally guaranteed to blow the account during standard black swan events or strong, one-sided trends.";
  } else if (isMartingale) {
    strategyType = "Martingale Order Escalation";
    strategyRiskRating = "HIGH RISK";
    strategyDescription = "This EA multiplies lot sizes on consecutive losses to quickly win back losses. It relies on never hit a long losing streak, which historically always happens on live accounts.";
  } else if (isGrid) {
    strategyType = "Grid / Position Accumulator";
    strategyRiskRating = "HIGH RISK";
    strategyDescription = "This EA plots a network of orders at fixed pip intervals. It does not use hard stop-losses on individual trades, letting losing trades float until the market reverses. This exposes the account to massive unseen floating drawdowns.";
  } else if (isScalping) {
    strategyType = "High-Frequency Scalper";
    strategyRiskRating = "Medium (Execution Sensitive)";
    strategyDescription = "This EA goes for tiny profits (a few points or pips) with short hold times. While safe from long-term trends, it is hyper-sensitive to spread widening and slippage. A live environment will heavily degrade its performance.";
  } else if (isAveraging) {
    strategyType = "Cost-Averaging Down";
    strategyRiskRating = "High Risk";
    strategyDescription = "This strategy adds more position weight to losing trades at lower prices to obtain a better average entry price. This works well in ranges but causes catastrophic drag during major breakouts.";
  }

  // ──────────────────────────────────────────────────────────────────────────
  // 4. Prop Firm Evaluation Scorecard
  // ──────────────────────────────────────────────────────────────────────────
  // Calculate maximum single trade weight
  let maxSingleTradeProfit = 0;
  tradeRows.forEach(t => {
    const p = Number(t.profit_loss || 0);
    if (p > maxSingleTradeProfit) maxSingleTradeProfit = p;
  });
  const totalProfit = metrics.net_profit || 1;
  const consistencyPct = roundTo((maxSingleTradeProfit / totalProfit) * 100, 1);

  const passesDailyLoss = simulatedDrawdownPct < 5.0;
  const passesMaxLoss = simulatedDrawdownPct < 10.0;
  const passesConsistency = consistencyPct < 30;
  const passesBrokerScale = !isHighlySensitive;

  const propScore = Math.round(
    (passesDailyLoss ? 30 : 5) +
    (passesMaxLoss ? 30 : 5) +
    (passesConsistency ? 20 : 5) +
    (passesBrokerScale ? 20 : 5)
  );

  let propGrade = "F";
  let propColor = "text-red-400";
  let propBg = "bg-red-500/10 border-red-500/20";
  if (propScore >= 85) {
    propGrade = "A";
    propColor = "text-green-400";
    propBg = "bg-green-500/10 border-green-500/20";
  } else if (propScore >= 70) {
    propGrade = "B";
    propColor = "text-blue-400";
    propBg = "bg-blue-500/10 border-blue-500/20";
  } else if (propScore >= 50) {
    propGrade = "C";
    propColor = "text-orange-400";
    propBg = "bg-orange-500/10 border-orange-500/20";
  }

  // Helper rounder
  function roundTo(num: number, dec: number) {
    return Math.round(num * Math.pow(10, dec)) / Math.pow(10, dec);
  }

  return (
    <div className="space-y-6">
      {/* Component Navigation */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {[
          { id: "broker", label: "Live Broker", icon: <Sliders className="w-4 h-4" /> },
          { id: "montecarlo", label: "Monte Carlo", icon: <Shuffle className="w-4 h-4" /> },
          { id: "news", label: "News Filter", icon: <Calendar className="w-4 h-4" /> },
          { id: "risk", label: "Capital Audit", icon: <Compass className="w-4 h-4" /> },
          { id: "strategy", label: "Strategy Decoder", icon: <Activity className="w-4 h-4" /> },
          { id: "propfirm", label: "Prop Firm Score", icon: <Building className="w-4 h-4" /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center justify-center gap-2 py-3.5 px-2 rounded-2xl text-xs font-bold transition-all duration-300 border
              ${activeTab === tab.id
                ? "bg-primary/20 text-primary border-primary/30 shadow-lg shadow-primary/5"
                : "bg-muted/30 text-muted-foreground hover:text-foreground border-transparent hover:bg-muted/50"}`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
          className="glass-strong rounded-3xl p-6 md:p-8 border border-white/5"
        >
          {/* TAB 1: LIVE BROKER SIMULATOR */}
          {activeTab === "broker" && (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border pb-6">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">Real-World Broker Latency Stress-Tester</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Stress-test backtest executions under real slippage and spread conditions.
                  </p>
                </div>
                {isHighlySensitive ? (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 uppercase tracking-wider">
                    ⚠️ Extreme Slippage Sensitivity
                  </span>
                ) : (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-green-500/10 text-green-400 border border-green-500/20 uppercase tracking-wider">
                    ✓ Execution Stable
                  </span>
                )}
              </div>

              {/* Sliders and Metrics Overlay */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Sliders Controls Panel */}
                <div className="space-y-6 lg:border-r lg:border-border lg:pr-8">
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Adjust Live Slippage Costs</h4>
                    <p className="text-[10px] text-muted-foreground font-semibold leading-relaxed">
                      Auto-detected symbol: <span className="text-foreground font-bold">{metrics.symbol || "EURUSD"}</span>
                    </p>
                  </div>

                  {/* Asset Execution Mode Selector */}
                  <div className="space-y-2 bg-muted/20 p-3 rounded-2xl border border-border/50">
                    <span className="font-black uppercase tracking-widest text-[9px] text-muted-foreground block">Asset Mode (Pip Multiplier)</span>
                    <div className="grid grid-cols-5 gap-1 bg-muted p-1 rounded-xl">
                      {[
                        { id: "forex", label: "Forex" },
                        { id: "gold", label: "Gold" },
                        { id: "jpy", label: "JPY" },
                        { id: "indices", label: "Indices" },
                        { id: "crypto", label: "Crypto" }
                      ].map(asset => (
                        <button
                          key={asset.id}
                          onClick={() => setAssetClass(asset.id as any)}
                          className={`py-1.5 px-0.5 rounded-lg text-[9px] font-black uppercase tracking-wider text-center transition-all ${
                            assetClass === asset.id
                              ? "bg-primary text-foreground shadow font-extrabold"
                              : "text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {asset.label}
                        </button>
                      ))}
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-bold text-primary mt-1 px-0.5">
                      <span>{unitExplanation}</span>
                      <span>Multiplier: ${costMultiplier}/Lot</span>
                    </div>
                  </div>

                  {metrics.backtest_spread && (
                    <div className="p-4 rounded-2xl bg-primary/10 border border-primary/20 text-xs text-primary leading-relaxed flex flex-col gap-1.5 shadow-sm">
                      <span className="font-black uppercase tracking-widest text-[9px] block">Detected Backtest Spread</span>
                      <p className="font-bold text-foreground/95">
                        Your backtest report was simulated with a spread of <span className="font-black text-primary">{metrics.backtest_spread}</span>{!isNaN(parseFloat(metrics.backtest_spread)) ? ` points (${(parseFloat(metrics.backtest_spread) / 10).toFixed(1)} pips)` : ""}.
                      </p>
                      <span className="text-[10px] text-muted-foreground font-medium leading-relaxed block">
                        The sliders below will simulate **additional** real-world slippage and execution costs on top of that base spread!
                      </span>
                    </div>
                  )}

                  {/* Dynamic cost per lot display */}
                  <div className="p-4 rounded-2xl bg-muted/40 border border-border/80 text-xs leading-relaxed flex flex-col gap-1">
                    <span className="font-black uppercase tracking-widest text-[9px] text-muted-foreground block">Additional Live Fee Simulated</span>
                    <p className="font-bold text-foreground text-sm flex justify-between">
                      <span>Added Cost / Lot:</span>
                      <span className="text-primary">${costPerLot.toFixed(2)} USD</span>
                    </p>
                    <span className="text-[9px] text-muted-foreground font-medium leading-relaxed">
                      Formula: (Slippage + Spread Markup) × {pipWord === "Pips" ? "10 Points" : "1 Point"} × ${costMultiplier.toFixed(1)}/Lot/Pip
                    </span>
                  </div>
                  
                  {/* Slider 1: Slippage */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="text-foreground/80">Average Live Slippage</span>
                      <span className="text-primary">{slippagePips.toFixed(1)} {pipWord}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="0.1"
                      value={slippagePips}
                      onChange={(e) => setSlippagePips(parseFloat(e.target.value))}
                      className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      Slippage is caused by network delay (ping). A 50ms latency usually adds 0.5 to 1.5 {pipWord.toLowerCase()} of slippage.
                    </p>
                  </div>

                  {/* Slider 2: Spread Markup */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="text-foreground/80">Spread Markup / Commission</span>
                      <span className="text-primary">{spreadMarkupPips.toFixed(1)} {pipWord}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      step="0.1"
                      value={spreadMarkupPips}
                      onChange={(e) => setSpreadMarkupPips(parseFloat(e.target.value))}
                      className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      Your broker's raw spread markup and round-turn trading commissions combined (measured in {pipWord.toLowerCase()}).
                    </p>
                  </div>

                  {/* Plain Language Verdict */}
                  <div className={`p-5 rounded-2xl ${isHighlySensitive ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-green-500/10 border-green-500/20 text-green-400'} border`}>
                    <p className="text-xs font-black uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      Live Market Verdict
                    </p>
                    <p className="text-xs text-foreground/85 leading-relaxed">
                      {isHighlySensitive
                        ? `This EA is highly sensitive. At ${slippagePips + spreadMarkupPips} pips of live spread, execution costs will consume ${Math.abs(roundTo(profitLossDiffPct, 0))}% of net profits. Live trading is highly risky here.`
                        : `This EA is execution-stable. Its average winning profit is large enough to easily absorb real broker slippage with minimal performance degradation.`}
                    </p>
                  </div>
                </div>

                {/* Simulated Values Summary Cards */}
                <div className="lg:col-span-2 space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Simulated Net Profit */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">Simulated Net Profit</p>
                      <p className={`text-2xl font-black ${simulatedNetProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${simulatedNetProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Original: <span className="font-bold text-foreground/75">${Number(metrics.net_profit || 0).toLocaleString()}</span>
                      </span>
                    </div>

                    {/* Simulated Profit Factor */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">Simulated Profit Factor</p>
                      <p className={`text-2xl font-black ${simulatedProfitFactor > 1.5 ? 'text-green-400' : simulatedProfitFactor > 1 ? 'text-orange-400' : 'text-red-400'}`}>
                        {simulatedProfitFactor}
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Original: <span className="font-bold text-foreground/75">{metrics.profit_factor}</span>
                      </span>
                    </div>

                    {/* Degradation Impact */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">Profit Degradation</p>
                      <p className={`text-2xl font-black ${profitLossDiffPct <= 0 ? 'text-red-400' : 'text-green-400'}`}>
                        {profitLossDiffPct > 0 ? "+" : ""}{profitLossDiffPct.toFixed(1)}%
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Simulated costs: <span className="font-bold text-foreground/75">${roundTo(totalTrades * costPerLot * 0.1, 2)}</span>
                      </span>
                    </div>
                  </div>

                  {/* Interactive Dual Chart */}
                  <div className="h-[260px] w-full mt-4">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colOriginal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="colAdjusted" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
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
                        <Area
                          type="monotone"
                          dataKey="Original"
                          stroke="#3b82f6"
                          strokeWidth={2.5}
                          fill="url(#colOriginal)"
                        />
                        <Area
                          type="monotone"
                          dataKey="Adjusted"
                          stroke="#8b5cf6"
                          strokeWidth={3}
                          fill="url(#colAdjusted)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: MONTE CARLO STRESS TEST */}
          {activeTab === "montecarlo" && (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border pb-6">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">Monte Carlo Sequence Stress-Tester</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Evaluates statistical robustness by shuffling the trade order 200 times to uncover sequence-of-return risk.
                  </p>
                </div>
                {mcBlowoutRiskPct < 10 ? (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-green-500/10 text-green-400 border border-green-500/20 uppercase tracking-wider">
                    ✓ Extremely Robust
                  </span>
                ) : mcBlowoutRiskPct < 30 ? (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 uppercase tracking-wider">
                    ⚠️ Moderately Stable
                  </span>
                ) : (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 uppercase tracking-wider">
                    🚨 High Risk of Sequence Ruin
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Parameters & Stats Panel */}
                <div className="space-y-6 lg:border-r lg:border-border lg:pr-8">
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Adjust Survival Threshold</h4>
                    
                    {/* Drawdown Cap Slider */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-bold">
                        <span className="text-foreground/80">Drawdown Cap Threshold</span>
                        <span className="text-primary">{mcDrawdownLimit}%</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="50"
                        step="1"
                        value={mcDrawdownLimit}
                        onChange={(e) => setMcDrawdownLimit(parseInt(e.target.value))}
                        className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                      <p className="text-[10px] text-muted-foreground leading-relaxed">
                        Sets the absolute maximum account equity drawdown limit that constitutes a "ruin / blowout" event.
                      </p>
                    </div>
                  </div>

                  {/* Shuffled Runs Report Cards */}
                  <div className="space-y-3 pt-4 border-t border-border/50">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Simulated Realities Audit</h4>
                    
                    {/* Risk of Ruin */}
                    <div className={`p-4 rounded-2xl border ${mcBlowoutRiskPct > 25 ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-muted/30 border-border'}`}>
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground">Risk of Sequence Ruin</p>
                      <p className="text-xl font-black mt-1 text-foreground">{mcBlowoutRiskPct}%</p>
                      <p className="text-[9px] text-muted-foreground mt-1 font-semibold leading-relaxed">
                        Probability that shuffled trade sequences hit a -{mcDrawdownLimit}% peak-to-valley drawdown.
                      </p>
                    </div>

                    {/* Median shuffled return */}
                    <div className="p-4 rounded-2xl bg-muted/30 border border-border">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground">Median Shuffled Profit</p>
                      <p className={`text-lg font-black mt-1 ${mcMedian.finalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${mcMedian.finalProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </p>
                      <span className="text-[9px] text-muted-foreground block mt-0.5 font-semibold">
                        Worst Case: <span className="font-bold text-red-400">${mcWorst.finalProfit.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                      </span>
                    </div>

                    {/* Peak Drawdown Distribution */}
                    <div className="p-4 rounded-2xl bg-muted/30 border border-border text-xs leading-relaxed">
                      <p className="text-[9px] font-black uppercase tracking-widest text-muted-foreground mb-2">Drawdown Distributions</p>
                      <div className="space-y-1.5 font-semibold">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Worst Run Drawdown:</span>
                          <span className="text-red-400 font-bold">{mcWorst.maxDD.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Median Run Drawdown:</span>
                          <span className="text-amber-400 font-bold">{mcMedian.maxDD.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Best Run Drawdown:</span>
                          <span className="text-green-400 font-bold">{mcBest.maxDD.toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Recharts Multi-Reality Chart */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="flex items-center justify-between text-xs font-bold text-muted-foreground px-2">
                    <span>Sequence Shuffling Plot (200 Simulations)</span>
                    <span className="text-primary font-black uppercase">Institutional Grade</span>
                  </div>
                  
                  <div className="h-[340px] w-full mt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={mcChartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="mcBestCol" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="mcWorstCol" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
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
                        <Area type="monotone" dataKey="Best" stroke="#10b981" strokeWidth={1.5} fill="url(#mcBestCol)" />
                        <Area type="monotone" dataKey="Median" stroke="#f59e0b" strokeWidth={2} fill="transparent" />
                        <Area type="monotone" dataKey="Worst" stroke="#ef4444" strokeWidth={1.5} fill="url(#mcWorstCol)" />
                        <Area type="monotone" dataKey="Adjusted" stroke="#8b5cf6" strokeWidth={2.5} fill="transparent" strokeDasharray="3 3" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  
                  <div className="p-4 rounded-2xl bg-muted/20 border border-border text-[10px] text-muted-foreground leading-relaxed">
                    💡 **Quantitative Insight**: If the **Worst** and **Median** shuffled lines are heavily degraded or negative, the EA relies heavily on "luck" in the timing of its trades. If all shuffled runs remain ascending and positive, your strategy has high mathematical edge and is robust to sequence risks.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: NEWS FILTER */}
          {activeTab === "news" && (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border pb-6">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">Macroeconomic News Event Filter & Stress-Tester</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Simulates high-impact calendar volatility (FOMC, CPI, NFP) and checks the benefit of a News Proximity Filter.
                  </p>
                </div>
                {newsAffectedTradesCount > 0 ? (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-orange-500/10 text-orange-400 border border-orange-500/20 uppercase tracking-wider">
                    ⚠️ {newsAffectedTradesCount} Trades News Exposed
                  </span>
                ) : (
                  <span className="px-3.5 py-1.5 text-xs font-bold rounded-xl bg-green-500/10 text-green-400 border border-green-500/20 uppercase tracking-wider">
                    ✓ Zero News Exposure
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* News Parameters Controls */}
                <div className="space-y-6 lg:border-r lg:border-border lg:pr-8">
                  {/* News Proximity Toggle */}
                  <div className="p-5 rounded-2xl bg-muted/20 border border-border space-y-4">
                    <span className="font-black uppercase tracking-widest text-[9px] text-muted-foreground block">Strategy News Filter</span>
                    
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-foreground">Filter News Trades</span>
                      <button
                        onClick={() => setNewsAvoidFilter(!newsAvoidFilter)}
                        className={`w-12 h-6 rounded-full transition-all duration-300 relative ${
                          newsAvoidFilter ? "bg-primary" : "bg-muted"
                        }`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all duration-300 shadow-md ${
                            newsAvoidFilter ? "left-6" : "left-1"
                          }`}
                        />
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      If enabled, the simulator completely **omits / avoids** entering trades taken within 60 minutes of high-impact releases.
                    </p>
                  </div>

                  {/* Spread Spike Slider */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="text-foreground/80">News Spread Wide Cap</span>
                      <span className="text-primary">{spreadSpikePips.toFixed(1)} {pipWord}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="10"
                      step="0.5"
                      value={spreadSpikePips}
                      onChange={(e) => setSpreadSpikePips(parseFloat(e.target.value))}
                      className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      Simulates spread widening during news event. Any news proximity trade gets penalized by this extra spread slippage cost.
                    </p>
                  </div>

                  {/* Simulated news calendar */}
                  <div className="space-y-3 pt-4 border-t border-border/50">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Simulated News Calendar Coverage</h4>
                    <div className="max-h-[160px] overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                      {newsEvents.length ? (
                        newsEvents.map((evt) => (
                          <div key={evt.id} className="p-3 rounded-xl bg-muted/30 border border-border text-[10px] leading-relaxed">
                            <div className="flex justify-between font-bold text-foreground">
                              <span className="text-primary">{evt.name}</span>
                              <span className="text-red-400 uppercase text-[8px] font-black font-sans leading-none">HIGH</span>
                            </div>
                            <span className="text-muted-foreground text-[9px] block">
                              {evt.time.toLocaleDateString()} {evt.time.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            <p className="text-[9px] text-muted-foreground mt-0.5 leading-snug">{evt.description}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-muted-foreground italic">No historical date stamps detected to seed news calendar.</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* News Comparison Curve & Metrics */}
                <div className="lg:col-span-2 space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Simulated Net Profit */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">News Adjusted Profit</p>
                      <p className={`text-2xl font-black ${newsFilteredNetProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${newsFilteredNetProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Base Broker: <span className="font-bold text-foreground/75">${simulatedNetProfit.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      </span>
                    </div>

                    {/* Simulated Profit Factor */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">Adjusted Profit Factor</p>
                      <p className={`text-2xl font-black ${newsSimulatedProfitFactor > 1.5 ? 'text-green-400' : 'text-red-400'}`}>
                        {newsSimulatedProfitFactor}
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Base Broker: <span className="font-bold text-foreground/75">{simulatedProfitFactor}</span>
                      </span>
                    </div>

                    {/* News Trades Affected */}
                    <div className="p-5 rounded-2xl bg-muted/20 border border-border">
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-2">News Trade Impact</p>
                      <p className="text-2xl font-black text-primary">
                        {newsAffectedTradesCount} <span className="text-xs text-muted-foreground font-semibold">trades</span>
                      </p>
                      <span className="text-[10px] text-muted-foreground mt-1 block">
                        Percentage: <span className="font-bold text-foreground/75">{totalTrades ? ((newsAffectedTradesCount / totalTrades) * 100).toFixed(1) : 0}%</span>
                      </span>
                    </div>
                  </div>

                  {/* Dual Chart Recharts */}
                  <div className="h-[250px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={newsChartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="newsCol" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#eab308" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
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
                        <Area type="monotone" dataKey="Adjusted" stroke="#8b5cf6" strokeWidth={2} fill="transparent" name="Base Live Broker" />
                        <Area type="monotone" dataKey="NewsSimulated" stroke="#eab308" strokeWidth={3} fill="url(#newsCol)" name="News-Filtered / News-Spiked" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CAPITAL & RISK AUDIT */}
          {activeTab === "risk" && (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border pb-6">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">Interactive Account Survival & Risk Stress-Tester</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Simulate capital requirements and project account blowout percentages based on risk adjustments.
                  </p>
                </div>
                <div className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border ${blowoutBg} ${blowoutColor}`}>
                  <Shield className="w-4 h-4" />
                  <span className="text-xs font-black uppercase tracking-wider">
                    {simulatedDrawdownPct > 45 ? "CRITICAL RISK" : simulatedDrawdownPct > 20 ? "MODERATE RISK" : "CONSERVATIVE"}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Simulator Inputs */}
                <div className="space-y-6 lg:border-r lg:border-border lg:pr-8">
                  <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Adjust Account Leverage</h4>

                  {/* Starting Capital */}
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-foreground/80">Starting Trading Capital ($)</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-muted-foreground">
                        <DollarSign className="w-4 h-4" />
                      </div>
                      <input
                        type="number"
                        className="w-full bg-muted/40 border border-border rounded-xl py-2.5 pl-10 pr-4 text-sm font-bold text-foreground focus:outline-none focus:border-primary"
                        value={startingCapital}
                        onChange={(e) => setStartingCapital(Math.max(100, Number(e.target.value)))}
                      />
                    </div>
                  </div>

                  {/* Risk Multiplier */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="text-foreground/80">Lot Size Risk Multiplier</span>
                      <span className="text-primary font-black">{riskMultiplier.toFixed(1)}x</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="10"
                      step="0.1"
                      value={riskMultiplier}
                      onChange={(e) => setRiskMultiplier(parseFloat(e.target.value))}
                      className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <div className="flex justify-between text-[9px] text-muted-foreground font-semibold">
                      <span>0.1x (Safe)</span>
                      <span>1.0x (Default)</span>
                      <span>10.0x (Gambler)</span>
                    </div>
                  </div>

                  {/* Simulated Drawdown Output */}
                  <div className={`p-5 rounded-2xl bg-muted/20 border border-border space-y-1`}>
                    <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Simulated Peak Drawdown</p>
                    <p className={`text-4xl font-black ${simulatedDrawdownPct > 50 ? 'text-red-400' : simulatedDrawdownPct > 20 ? 'text-orange-400' : 'text-green-400'}`}>
                      {simulatedDrawdownPct}%
                    </p>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      Expected peak account loss of <span className="font-bold text-foreground/80">${((startingCapital * simulatedDrawdownPct) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span> in capital under stress.
                    </p>
                  </div>
                </div>

                {/* Ruin Probabilities Display */}
                <div className="lg:col-span-2 space-y-6">
                  <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Account Blowout Probabilities</h4>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                    {/* 30 Days probability */}
                    <div className="p-5 rounded-2xl bg-muted/10 border border-border/60 text-center relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-blue-500/20 to-transparent" />
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">30-Day Survival Risk</p>
                      <p className={`text-5xl font-black my-3 ${blowout30d > 50 ? 'text-red-400' : blowout30d > 20 ? 'text-orange-400' : 'text-green-400'}`}>
                        {blowout30d}%
                      </p>
                      <p className="text-[9px] text-muted-foreground leading-relaxed">
                        Probability of hitting a margin call within one month of active trading.
                      </p>
                    </div>

                    {/* 90 Days probability */}
                    <div className="p-5 rounded-2xl bg-muted/10 border border-border/60 text-center relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-orange-500/20 to-transparent" />
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">90-Day Survival Risk</p>
                      <p className={`text-5xl font-black my-3 ${blowout90d > 50 ? 'text-red-400' : blowout90d > 20 ? 'text-orange-400' : 'text-green-400'}`}>
                        {blowout90d}%
                      </p>
                      <p className="text-[9px] text-muted-foreground leading-relaxed">
                        Probability of total capital depletion within three months.
                      </p>
                    </div>

                    {/* 365 Days probability */}
                    <div className="p-5 rounded-2xl bg-muted/10 border border-border/60 text-center relative overflow-hidden">
                      <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-red-500/20 to-transparent" />
                      <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">1-Year Survival Risk</p>
                      <p className={`text-5xl font-black my-3 ${blowout365d > 50 ? 'text-red-400' : blowout365d > 20 ? 'text-orange-400' : 'text-green-400'}`}>
                        {blowout365d}%
                      </p>
                      <p className="text-[9px] text-muted-foreground leading-relaxed">
                        Probability of complete margin wipeout over one full calendar year.
                      </p>
                    </div>
                  </div>

                  {/* Quantitative Advice Card */}
                  <div className="p-6 rounded-2xl bg-muted/30 border border-border flex items-start gap-4">
                    <div className="p-3 rounded-xl bg-primary/10 text-primary">
                      <HelpCircle className="w-5 h-5 shrink-0" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-foreground">Quantitative Risk Advice</h4>
                      <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                        {simulatedDrawdownPct > 40
                          ? `ALERT: Under your current ${riskMultiplier}x multiplier, the EA is virtually guaranteed to trigger a blowout scenario due to compounding drawdown peaks. We highly recommend lowering your lot multiplier below 0.5x to preserve long-term capital.`
                          : simulatedDrawdownPct > 15
                          ? `CAUTION: Moderate risk level detected. This EA will perform well but expects floating drawdown periods that will test your emotional discipline. Maintain a minimum backup balance buffer of 50% outside your trading account.`
                          : `CONSERVATIVE: Extremely safe setup. The strategy has healthy risk margins under these settings, and capital is well-buffered to survive extended adverse periods in the live market.`}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: STRATEGY DECODER */}
          {activeTab === "strategy" && (
            <div className="space-y-6">
              <div className="border-b border-border pb-6">
                <h3 className="text-xl font-bold tracking-tight">Plain-English Strategy Decoder</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Translates underlying trade patterns, position counts, and math into conversational statements.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Card: Strategy DNA */}
                <div className="lg:col-span-2 space-y-6">
                  <div className="p-6 rounded-2xl bg-muted/20 border border-border relative overflow-hidden">
                    <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-primary to-transparent" />
                    <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1.5">STRATEGY DNA</p>
                    <h4 className="text-2xl font-black text-foreground">{strategyType}</h4>
                    <p className="text-sm text-foreground/80 leading-relaxed mt-4">
                      {strategyDescription}
                    </p>
                  </div>

                  {/* Behavior Indicators List */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className={`p-5 rounded-2xl border ${isMartingale ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-muted/10 border-border text-muted-foreground'}`}>
                      <p className="text-xs font-bold uppercase tracking-widest mb-1">Martingale Multiplier</p>
                      <p className="text-lg font-black text-foreground">
                        {isMartingale ? "⚠️ YES (Detected)" : "✓ NO"}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        Checks if order sizes multiply after a losing trade.
                      </p>
                    </div>

                    <div className={`p-5 rounded-2xl border ${isGrid ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-muted/10 border-border text-muted-foreground'}`}>
                      <p className="text-xs font-bold uppercase tracking-widest mb-1">Grid Placement</p>
                      <p className="text-lg font-black text-foreground">
                        {isGrid ? "⚠️ YES (Detected)" : "✓ NO"}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        Checks if orders are placed at regular physical point offsets.
                      </p>
                    </div>

                    <div className={`p-5 rounded-2xl border ${isScalping ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : 'bg-muted/10 border-border text-muted-foreground'}`}>
                      <p className="text-xs font-bold uppercase tracking-widest mb-1">High-Frequency Scalp</p>
                      <p className="text-lg font-black text-foreground">
                        {isScalping ? "⚡ YES" : "✓ NO"}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        Checks if target profits are very small and exit times are rapid.
                      </p>
                    </div>

                    <div className={`p-5 rounded-2xl border ${isAveraging ? 'bg-orange-500/10 border-orange-500/20 text-orange-400' : 'bg-muted/10 border-border text-muted-foreground'}`}>
                      <p className="text-xs font-bold uppercase tracking-widest mb-1">Cost Averaging Down</p>
                      <p className="text-lg font-black text-foreground">
                        {isAveraging ? "⚠️ YES" : "✓ NO"}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        Checks if more capital is loaded to float losing orders.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Right Card: Plain English Cheat Sheet */}
                <div className="p-6 rounded-2xl bg-muted/20 border border-border flex flex-col justify-between">
                  <div className="space-y-4">
                    <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Strategy Risk Level</p>
                    <div className={`inline-block px-3 py-1 text-xs font-bold rounded-lg uppercase border ${strategyRiskRating.includes('RISK') ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-green-500/10 border-green-500/20 text-green-400'}`}>
                      {strategyRiskRating}
                    </div>

                    <h5 className="text-sm font-bold text-foreground pt-4">Human Translation:</h5>
                    <ul className="space-y-3 text-xs text-muted-foreground leading-relaxed list-disc list-inside">
                      <li>
                        <strong>Backtest:</strong> Wins nearly every single trade, yielding a smooth ascending balance graph.
                      </li>
                      <li>
                        <strong>Live Market:</strong> Extremely exposed to spikes, news slippage, and strong trends that don't pull back.
                      </li>
                      <li>
                        <strong>Broker Impact:</strong> A sudden margin spread expansion will instantly trigger multiple grid order liquidations.
                      </li>
                    </ul>
                  </div>

                  <div className="pt-6 border-t border-border/60">
                    <p className="text-[10px] text-muted-foreground italic font-semibold">
                      *Translated by EA forensic algorithm using order sequence logic.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: PROP FIRM SCORECARD */}
          {activeTab === "propfirm" && (
            <div className="space-y-8">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-border pb-6">
                <div>
                  <h3 className="text-xl font-bold tracking-tight">Prop Firm Compliance Scorecard</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Evaluates the strategy against industry rules (FTMO, FundedNext, E8, etc.) to verify funding safety.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex flex-col items-end">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground">Compatibility</span>
                    <span className={`text-lg font-black ${propColor}`}>{propScore} / 100</span>
                  </div>
                  <div className={`px-4 py-2 rounded-xl text-lg font-black border ${propBg} ${propColor}`}>
                    GRADE: {propGrade}
                  </div>
                </div>
              </div>

              {/* Rules Checklist Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 1. Daily Drawdown */}
                <div className="p-6 rounded-2xl bg-muted/20 border border-border flex items-start gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${passesDailyLoss ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                    {passesDailyLoss ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">5% Daily Loss Cap (FTMO/FundedNext)</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                      {passesDailyLoss
                        ? `PASS. The simulated peak drawdown of ${simulatedDrawdownPct}% is under the maximum 5.0% daily threshold limit.`
                        : `FAIL. At your current settings, simulated peak drawdown (${simulatedDrawdownPct}%) breaches the maximum 5.0% daily loss allowance, causing instant disqualification.`}
                    </p>
                  </div>
                </div>

                {/* 2. Max Overall Loss */}
                <div className="p-6 rounded-2xl bg-muted/20 border border-border flex items-start gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${passesMaxLoss ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                    {passesMaxLoss ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">10% Max Overall Drawdown Cap</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                      {passesMaxLoss
                        ? `PASS. Simulated max overall drawdown is ${simulatedDrawdownPct}%, remaining safely within the overall 10.0% boundary.`
                        : `FAIL. Overall drawdown reaches ${simulatedDrawdownPct}%, violating the absolute 10.0% firm drawdown cap.`}
                    </p>
                  </div>
                </div>

                {/* 3. Consistency Rule */}
                <div className="p-6 rounded-2xl bg-muted/20 border border-border flex items-start gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${passesConsistency ? 'bg-green-500/10 text-green-400' : 'bg-orange-500/10 text-orange-400'}`}>
                    {passesConsistency ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">Consistency Audit (Max single trade profit &lt; 30%)</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                      {passesConsistency
                        ? `PASS. The single most profitable trade generated only ${consistencyPct}% of total net gains. Extremely healthy consistency.`
                        : `WARNING. A single trade generated ${consistencyPct}% of total net profits. Prop firms flag this and may withhold payouts for consistency violation.`}
                    </p>
                  </div>
                </div>

                {/* 4. Execution Costs */}
                <div className="p-6 rounded-2xl bg-muted/20 border border-border flex items-start gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${passesBrokerScale ? 'bg-green-500/10 text-green-400' : 'bg-orange-500/10 text-orange-400'}`}>
                    {passesBrokerScale ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-foreground">Prop Firm Spread & Commission Margin</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                      {passesBrokerScale
                        ? `PASS. Average trade profit is large enough to survive standard prop firm demo servers with higher execution margins.`
                        : `WARNING. High broker slippage sensitivity detected. Prop firm demo servers have standard latency markups which will significantly degrade profits.`}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
