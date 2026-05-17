import io
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import pdfplumber

from ..models.schemas import BacktestMetrics, TradeRecord


class PDFParser:
    KEY_LABELS = {
        "ea_name": ["Expert", "Expert Advisor", "EA Name"],
        "symbol": ["Symbol"],
        "period": ["Period"],
        "deposit": ["Initial Deposit", "Deposit"],
        "net_profit": ["Total Net Profit", "Net Profit"],
        "gross_profit": ["Gross Profit"],
        "gross_loss": ["Gross Loss"],
        "profit_factor": ["Profit Factor"],
        "expected_payoff": ["Expected Payoff"],
        "maximal_drawdown": ["Maximal Drawdown", "Balance Drawdown Maximal", "Equity Drawdown Maximal"],
        "maximal_drawdown_pct": [
            "Maximal Drawdown %",
            "Relative Drawdown",
            "Balance Drawdown Relative",
            "Equity Drawdown Relative",
        ],
        "recovery_factor": ["Recovery Factor"],
        "sharpe_ratio": ["Sharpe Ratio"],
        "total_trades": ["Total Trades", "Trades"],
        "profit_trades_win_pct": ["Profit Trades (% of total)", "Profit Trades"],
        "short_positions_win_pct": ["Short Positions (won %)", "Short Positions"],
        "long_positions_win_pct": ["Long Positions (won %)", "Long Positions"],
        "average_profit": ["Average profit trade", "Average Profit Trade"],
        "average_loss": ["Average loss trade", "Average Loss Trade"],
        "consecutive_wins_max": ["Maximal consecutive wins", "Maximum consecutive wins"],
        "consecutive_losses_max": ["Maximal consecutive losses", "Maximum consecutive losses"],
    }

    @staticmethod
    def parse(content: bytes) -> Tuple[BacktestMetrics, List[TradeRecord]]:
        text, tables = PDFParser._extract_pdf(content)
        metric_cells = PDFParser._collect_metric_cells(tables)

        maximal_drawdown = PDFParser._find_money_from_drawdown("maximal_drawdown", text, metric_cells)
        maximal_drawdown_pct = (
            PDFParser._find_percent_from_drawdown("maximal_drawdown_pct", text, metric_cells)
            or PDFParser._find_percent_from_drawdown("maximal_drawdown", text, metric_cells)
        )

        profit_trades_win_pct = PDFParser._find_percent_from_drawdown("profit_trades_win_pct", text, metric_cells)

        metrics = BacktestMetrics(
            ea_name=PDFParser._find_text_value("ea_name", text, metric_cells),
            symbol=PDFParser._find_text_value("symbol", text, metric_cells),
            period=PDFParser._find_text_value("period", text, metric_cells),
            deposit=PDFParser._find_number("deposit", text, metric_cells),
            net_profit=PDFParser._find_number("net_profit", text, metric_cells),
            gross_profit=PDFParser._find_number("gross_profit", text, metric_cells),
            gross_loss=abs(PDFParser._find_number("gross_loss", text, metric_cells)),
            profit_factor=PDFParser._find_number("profit_factor", text, metric_cells),
            expected_payoff=PDFParser._find_number("expected_payoff", text, metric_cells),
            maximal_drawdown=maximal_drawdown,
            maximal_drawdown_pct=maximal_drawdown_pct,
            recovery_factor=PDFParser._find_number("recovery_factor", text, metric_cells),
            sharpe_ratio=PDFParser._find_number("sharpe_ratio", text, metric_cells),
            total_trades=int(PDFParser._find_number("total_trades", text, metric_cells)),
            short_positions_win_pct=PDFParser._find_percent_from_drawdown("short_positions_win_pct", text, metric_cells),
            long_positions_win_pct=PDFParser._find_percent_from_drawdown("long_positions_win_pct", text, metric_cells),
            win_rate=profit_trades_win_pct,
            average_profit=PDFParser._find_number("average_profit", text, metric_cells),
            average_loss=abs(PDFParser._find_number("average_loss", text, metric_cells)),
            consecutive_wins_max=int(PDFParser._find_number("consecutive_wins_max", text, metric_cells)),
            consecutive_losses_max=int(PDFParser._find_number("consecutive_losses_max", text, metric_cells)),
        )
        if metrics.risk_reward_ratio == 0 and metrics.average_loss > 0:
            metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)

        trades = PDFParser._parse_trades(tables)
        PDFParser._complete_metrics_from_trades(metrics, trades)
        return metrics, trades

    @staticmethod
    def _extract_pdf(content: bytes) -> Tuple[str, List[List[List[str]]]]:
        text_parts: List[str] = []
        tables: List[List[List[str]]] = []

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)
                for table in page.extract_tables() or []:
                    cleaned = []
                    for row in table or []:
                        cells = [PDFParser._clean_cell(cell) for cell in row]
                        if any(cells):
                            cleaned.append(cells)
                    if cleaned:
                        tables.append(cleaned)

        return "\n".join(text_parts), tables

    @staticmethod
    def _collect_metric_cells(tables: List[List[List[str]]]) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        for table in tables:
            for row in table:
                cells = [cell for cell in row if cell]
                for i in range(0, len(cells) - 1, 2):
                    label = PDFParser._normalise_label(cells[i])
                    value = cells[i + 1]
                    if label and value and not PDFParser._looks_like_trade_header(cells) and PDFParser._valid_metric_value(label, value):
                        pairs[label] = value
                for i in range(len(cells) - 1):
                    label = PDFParser._normalise_label(cells[i])
                    value = cells[i + 1]
                    if label and value and PDFParser._is_known_label(label) and PDFParser._valid_metric_value(label, value):
                        pairs.setdefault(label, value)
        return pairs

    @staticmethod
    def _parse_trades(tables: List[List[List[str]]]) -> List[TradeRecord]:
        trades: List[TradeRecord] = []

        for table in tables:
            header_idx = PDFParser._find_trade_header_index(table)
            if header_idx is None:
                continue

            headers = [PDFParser._normalise_label(cell) for cell in table[header_idx]]
            for row in table[header_idx + 1 :]:
                row_map = PDFParser._map_row(headers, row)
                trade = PDFParser._trade_from_row(row_map)
                if trade is not None:
                    trades.append(trade)

        trades.sort(key=lambda t: t.close_time or t.open_time or datetime.min)
        return trades

    @staticmethod
    def _trade_from_row(row: Dict[str, str]) -> Optional[TradeRecord]:
        type_value = PDFParser._first(row, ["type", "order type"])
        direction = PDFParser._first(row, ["direction", "entry"])
        trade_type = (type_value or "").lower()

        if "buy" not in trade_type and "sell" not in trade_type:
            return None
        if direction and direction.lower() == "in":
            return None

        profit = PDFParser._parse_number(PDFParser._first(row, ["profit", "p/l", "result"]))
        swap = PDFParser._parse_number(PDFParser._first(row, ["swap"]))
        commission = PDFParser._parse_number(PDFParser._first(row, ["commission", "comm"]))
        taxes = PDFParser._parse_number(PDFParser._first(row, ["taxes", "tax"]))
        balance = PDFParser._parse_number(PDFParser._first(row, ["balance"]))

        if profit == 0 and balance == 0 and not direction:
            return None

        open_time = PDFParser._parse_datetime(
            PDFParser._first(row, ["open time", "open date", "time"])
        )
        close_time = PDFParser._parse_datetime(
            PDFParser._first(row, ["close time", "close date", "time"])
        )
        duration = None
        if open_time and close_time and close_time >= open_time:
            duration = (close_time - open_time).total_seconds() / 60

        return TradeRecord(
            ticket=PDFParser._first(row, ["ticket", "order", "deal", "#"]),
            open_time=open_time,
            close_time=close_time,
            type="sell" if "sell" in trade_type else "buy",
            size=PDFParser._parse_number(PDFParser._first(row, ["size", "volume", "lots"])) or 0.0,
            item=PDFParser._first(row, ["item", "symbol"]) or "Unknown",
            price=PDFParser._parse_number(PDFParser._first(row, ["open price", "price"])) or 0.0,
            s_l=PDFParser._optional_number(PDFParser._first(row, ["s/l", "sl"])),
            t_p=PDFParser._optional_number(PDFParser._first(row, ["t/p", "tp"])),
            close_price=PDFParser._optional_number(PDFParser._first(row, ["close price", "price"])),
            commission=commission,
            taxes=taxes,
            swap=swap,
            profit=profit,
            balance=balance or None,
            comment=PDFParser._first(row, ["comment"]),
            duration_minutes=duration,
        )

    @staticmethod
    def _complete_metrics_from_trades(metrics: BacktestMetrics, trades: List[TradeRecord]) -> None:
        if not trades:
            if metrics.total_trades == 0:
                metrics.total_trades = 0
            if metrics.win_rate == 0:
                wins = [metrics.short_positions_win_pct, metrics.long_positions_win_pct]
                wins = [w for w in wins if w > 0]
                metrics.win_rate = round(sum(wins) / len(wins), 2) if wins else 0.0
            return

        profits = [t.profit for t in trades if t.profit > 0]
        losses = [abs(t.profit) for t in trades if t.profit < 0]
        durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]

        metrics.total_trades = metrics.total_trades or len(trades)
        metrics.net_profit = metrics.net_profit or round(sum(t.profit for t in trades), 2)
        metrics.gross_profit = metrics.gross_profit or round(sum(profits), 2)
        metrics.gross_loss = metrics.gross_loss or round(sum(losses), 2)
        if metrics.profit_factor == 0 and metrics.gross_loss > 0:
            metrics.profit_factor = round(metrics.gross_profit / metrics.gross_loss, 2)
        if metrics.expected_payoff == 0:
            metrics.expected_payoff = round(metrics.net_profit / len(trades), 2)
        if metrics.win_rate == 0:
            metrics.win_rate = round((len(profits) / len(trades)) * 100, 2)
        if metrics.average_profit == 0 and profits:
            metrics.average_profit = round(sum(profits) / len(profits), 2)
        if metrics.average_loss == 0 and losses:
            metrics.average_loss = round(sum(losses) / len(losses), 2)
        if metrics.risk_reward_ratio == 0 and metrics.average_loss > 0:
            metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)
        if metrics.average_trade_duration == 0 and durations:
            metrics.average_trade_duration = round(sum(durations) / len(durations), 2)
        if not metrics.symbol or metrics.symbol == "Unknown":
            symbols = [t.item for t in trades if t.item and t.item != "Unknown"]
            metrics.symbol = max(set(symbols), key=symbols.count) if symbols else metrics.symbol

    @staticmethod
    def _find_number(key: str, text: str, cells: Dict[str, str]) -> float:
        value = PDFParser._find_text_value(key, text, cells)
        return PDFParser._parse_number(value)

    @staticmethod
    def _find_money_from_drawdown(key: str, text: str, cells: Dict[str, str]) -> float:
        value = PDFParser._find_text_value(key, text, cells)
        if not value:
            return 0.0
        before_percent = value.split("(")[0]
        return abs(PDFParser._parse_number(before_percent))

    @staticmethod
    def _find_percent_from_drawdown(key: str, text: str, cells: Dict[str, str]) -> float:
        value = PDFParser._find_text_value(key, text, cells)
        if not value:
            return 0.0
        percent = re.search(r"\(?\s*(-?[\d\s,.]+)\s*%\s*\)?", value)
        if percent:
            return abs(PDFParser._parse_number(percent.group(1)))
        return abs(PDFParser._parse_number(value))

    @staticmethod
    def _find_text_value(key: str, text: str, cells: Dict[str, str]) -> Optional[str]:
        for label in PDFParser.KEY_LABELS[key]:
            normalised = PDFParser._normalise_label(label)
            if normalised in cells and PDFParser._valid_metric_value(normalised, cells[normalised]):
                return cells[normalised]

        all_labels = [re.escape(label) for labels in PDFParser.KEY_LABELS.values() for label in labels]
        stop = "|".join(all_labels)
        for label in PDFParser.KEY_LABELS[key]:
            pattern = re.compile(
                rf"{re.escape(label)}\s*:?\s*(.+?)(?=\s+(?:{stop})\s*:|\n|$)",
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                value = match.group(1).strip()
                if PDFParser._valid_metric_value(label, value):
                    return value

        lines = [PDFParser._clean_cell(line) for line in text.splitlines() if PDFParser._clean_cell(line)]
        for index, line in enumerate(lines):
            normalised_line = PDFParser._normalise_label(line)
            for label in PDFParser.KEY_LABELS[key]:
                normalised_label = PDFParser._normalise_label(label)
                if normalised_line == normalised_label and index + 1 < len(lines):
                    value = lines[index + 1]
                    if PDFParser._valid_metric_value(label, value):
                        return value
                if normalised_line.startswith(normalised_label + " "):
                    value = line[len(label):].strip(" :")
                    if PDFParser._valid_metric_value(label, value):
                        return value
        return None

    @staticmethod
    def _find_trade_header_index(table: List[List[str]]) -> Optional[int]:
        for index, row in enumerate(table):
            cells = [PDFParser._normalise_label(cell) for cell in row]
            joined = " ".join(cells)
            has_type = any(cell in {"type", "order type"} for cell in cells)
            has_trade_id = any(cell in {"ticket", "order", "deal", "#"} for cell in cells)
            has_profit = "profit" in cells or "p/l" in cells
            has_time = "time" in cells or "open time" in cells
            if has_type and has_profit and (has_trade_id or has_time or "symbol" in joined):
                return index
        return None

    @staticmethod
    def _map_row(headers: List[str], row: List[str]) -> Dict[str, str]:
        row_map: Dict[str, str] = {}
        for index, header in enumerate(headers):
            if not header or index >= len(row):
                continue
            value = PDFParser._clean_cell(row[index])
            if value:
                row_map[header] = value
        return row_map

    @staticmethod
    def _first(row: Dict[str, str], keys: Iterable[str]) -> Optional[str]:
        for key in keys:
            if key in row and row[key]:
                return row[key]
        return None

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        value = value.strip()
        formats = [
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _optional_number(value: Optional[str]) -> Optional[float]:
        number = PDFParser._parse_number(value)
        return number if number != 0 else None

    @staticmethod
    def _parse_number(value: Optional[str]) -> float:
        if value is None:
            return 0.0
        raw = str(value).strip()
        if not raw:
            return 0.0

        negative = raw.startswith("(") and raw.endswith(")")
        raw = raw.replace("\u00a0", " ").replace("%", "")
        match = re.search(r"-?\d[\d\s,]*(?:\.\d+)?", raw)
        if not match:
            return 0.0
        number = match.group(0).replace(" ", "").replace(",", "")
        try:
            parsed = float(number)
            return -abs(parsed) if negative else parsed
        except ValueError:
            return 0.0

    @staticmethod
    def _clean_cell(cell: Optional[str]) -> str:
        return re.sub(r"\s+", " ", str(cell or "")).strip()

    @staticmethod
    def _normalise_label(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace(":", " ").strip().lower())

    @staticmethod
    def _is_known_label(label: str) -> bool:
        return any(label == PDFParser._normalise_label(item) for labels in PDFParser.KEY_LABELS.values() for item in labels)

    @staticmethod
    def _looks_like_trade_header(cells: List[str]) -> bool:
        normalised = {PDFParser._normalise_label(cell) for cell in cells}
        return (
            ("profit" in normalised and ("type" in normalised or "deal" in normalised or "order" in normalised))
            or ("symbol" in normalised and "type" in normalised and ("volume" in normalised or "size" in normalised))
        )

    @staticmethod
    def _valid_metric_value(label: str, value: str) -> bool:
        raw = PDFParser._clean_cell(value)
        if not raw:
            return False
        normalised_value = PDFParser._normalise_label(raw)
        table_words = {
            "time",
            "deal",
            "order",
            "symbol",
            "type",
            "direction",
            "volume",
            "size",
            "price",
            "s/l",
            "t/p",
            "commission",
            "swap",
            "profit",
            "balance",
            "comment",
        }
        if normalised_value in table_words:
            return False
        if PDFParser._normalise_label(label) in {"symbol", "period"} and re.search(
            r"\b(type|direction|volume|size|price|profit|balance|commission|swap)\b",
            normalised_value,
        ):
            return False
        return True
