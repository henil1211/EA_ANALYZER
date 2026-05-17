from fastapi import APIRouter, UploadFile, File, HTTPException
from ..parsers.mt4_parser import MT4Parser
from ..parsers.mt5_parser import MT5Parser
from ..parsers.csv_parser import CSVParser
from ..parsers.xlsx_parser import XLSXParser
from ..parsers.pdf_parser import PDFParser
from ..analysis.behavior_analyzer import BehaviorAnalyzer
from ..analysis.ai_analyzer import AIAnalyzer
from ..analysis.detailed_analyzer import DetailedAnalyzer
from ..analysis.extended_analyzer import ExtendedAnalyzer
from ..models.schemas import AnalysisResponse
import io
import os
import re

router = APIRouter(prefix="/api")

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_backtest(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename.lower()
    
    # Detect report type
    parser = None
    if filename.endswith(".html") or filename.endswith(".htm"):
        text_content = _decode_report_text(content)
        if _looks_like_mt4_report(text_content):
            parser = MT4Parser()
        else:
            parser = MT5Parser()
    elif filename.endswith(".csv"):
        parser = CSVParser()
    elif filename.endswith(".xlsx"):
        parser = XLSXParser()
    elif filename.endswith(".pdf"):
        parser = PDFParser()
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Please upload HTML, HTM, CSV, XLSX, or PDF.")

    try:
        # Parse trades and metrics
        metrics, trades = parser.parse(content)
        if not _has_extractable_report_data(metrics, trades):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract backtest metrics from this report. "
                    "Please upload the original MetaTrader HTML report or a text-based PDF export."
                ),
            )
        
        # Analyze behavior
        behavior_analyzer = BehaviorAnalyzer()
        behavior = behavior_analyzer.analyze(trades)
        
        equity_curve = _build_equity_curve(metrics, trades)
        
        # AI Analysis (Local Engine)
        ai_analyzer = AIAnalyzer()
        ai_result = await ai_analyzer.analyze(metrics, behavior, trades)
        detailed_analysis = DetailedAnalyzer().analyze(metrics, behavior, trades, equity_curve)
        
        # Forensic Analysis
        from ..analysis.forensic_analyzer import ForensicAnalyzer
        forensic_analysis = ForensicAnalyzer().analyze(metrics, trades, equity_curve)

        extended_analysis = ExtendedAnalyzer().analyze(
            metrics,
            behavior,
            trades,
            equity_curve,
            ai_result.verdict,
            parser.__class__.__name__,
        )
        
        return AnalysisResponse(
            metrics=metrics,
            behavior=behavior,
            ai_analysis=ai_result,
            detailed_analysis=detailed_analysis,
            forensic_analysis=forensic_analysis,
            extended_analysis=extended_analysis,
            equity_curve=equity_curve,
            trades_count=metrics.total_trades or len(trades),
            report_type=parser.__class__.__name__
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@router.get("/health")
async def health_check():
    return {"status": "healthy"}


def _build_equity_curve(metrics, trades):
    starting_balance = metrics.deposit or 0.0
    first_balance_trade = next((t for t in trades if t.balance is not None), None)
    if not starting_balance and first_balance_trade:
        starting_balance = max(0.0, first_balance_trade.balance - first_balance_trade.profit)

    expected_delta = metrics.net_profit
    tolerance = max(1.0, abs(expected_delta) * 0.02)

    balance_curve = _balance_curve(starting_balance, trades)
    if expected_delta and abs((balance_curve[-1] - starting_balance) - expected_delta) <= tolerance:
        return balance_curve

    profit_curve = _profit_curve(starting_balance, [t.profit for t in trades])
    if not expected_delta or abs((profit_curve[-1] - starting_balance) - expected_delta) <= tolerance:
        return profit_curve

    if trades:
        reconciled_profits = _reconcile_trade_profits([t.profit for t in trades], expected_delta)
        return _profit_curve(starting_balance, reconciled_profits)

    if expected_delta:
        return [round(starting_balance, 2), round(starting_balance + expected_delta, 2)]
    return [round(starting_balance, 2)]


def _balance_curve(starting_balance, trades):
    curve = [round(starting_balance, 2)]
    current = starting_balance
    for trade in trades:
        if trade.balance is not None:
            current = trade.balance
        else:
            current += trade.profit
        curve.append(round(current, 2))
    return curve


def _profit_curve(starting_balance, profits):
    curve = [round(starting_balance, 2)]
    current = starting_balance
    for profit in profits:
        current += profit
        curve.append(round(current, 2))
    return curve


def _reconcile_trade_profits(profits, expected_delta):
    if not profits:
        return []

    current_delta = sum(profits)
    if abs(current_delta) > 0 and (current_delta > 0) == (expected_delta > 0):
        scale = expected_delta / current_delta
        reconciled = [round(profit * scale, 2) for profit in profits]
    else:
        correction = (expected_delta - current_delta) / len(profits)
        reconciled = [round(profit + correction, 2) for profit in profits]

    rounding_gap = round(expected_delta - sum(reconciled), 2)
    reconciled[-1] = round(reconciled[-1] + rounding_gap, 2)
    return reconciled


def _has_extractable_report_data(metrics, trades):
    metric_values = [
        metrics.deposit,
        metrics.net_profit,
        metrics.gross_profit,
        metrics.gross_loss,
        metrics.profit_factor,
        metrics.expected_payoff,
        metrics.maximal_drawdown,
        metrics.maximal_drawdown_pct,
        metrics.total_trades,
        metrics.sharpe_ratio,
        metrics.recovery_factor,
    ]
    return bool(trades) or any(abs(float(value or 0)) > 0 for value in metric_values)


def _decode_report_text(content: bytes) -> str:
    if content.startswith(b"\xff\xfe") or content[:200].count(b"\x00") > 20:
        return content.decode("utf-16", errors="ignore")
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig", errors="ignore")
    for encoding in ("utf-8", "cp1252", "latin1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _looks_like_mt4_report(text: str) -> bool:
    lowered = text.lower()
    if "metatrader 4" in lowered:
        return True
    if "strategy tester report" not in lowered:
        return False
    return bool(
        re.search(r">\s*#\s*</td>.*?>\s*time\s*</td>.*?>\s*type\s*</td>.*?>\s*order\s*</td>.*?>\s*size\s*</td>.*?>\s*profit\s*</td>.*?>\s*balance\s*</td>", text, re.I | re.S)
        or ("total net profit" in lowered and "short positions (won %)" in lowered and "ticks modelled" in lowered)
    )
