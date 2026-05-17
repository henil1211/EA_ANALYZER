import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from ..models.schemas import BacktestMetrics, TradeRecord
from .csv_parser import CSVParser


# ──────────────────────────────────────────────────────────────────────
# Excel epoch used for serial-date conversion.
# Excel incorrectly considers 1900-02-29 a valid date (the "1900 bug").
# ──────────────────────────────────────────────────────────────────────
_EXCEL_EPOCH = datetime(1899, 12, 30)


class XLSXParser:
    HEADER_ALIASES = {
        "ticket", "order", "deal", "id", "symbol", "asset", "item",
        "type", "direction", "side", "lot", "lots", "lot_size", "volume",
        "size", "open_time", "entry_time", "close_time", "exit_time",
        "time", "open_price", "entry_price", "close_price", "exit_price",
        "price", "profit", "p_l", "pl", "profit_loss", "net_profit",
        "swap", "commission", "balance", "sl", "stop_loss", "tp",
        "take_profit", "magic", "magic_number", "spread", "slippage",
        "mfe", "mae", "result", "net_p_l", "gross_p_l", "equity",
        "equity_at_exit", "equity_exit", "equity_at_entry", "equity_entry",
        "comment", "strategy_tag", "setup",
    }
    PROFIT_HEADERS = {
        "profit", "p_l", "pl", "profit_loss", "net_profit",
        "net_p_l", "gross_p_l", "result",
    }

    # ──────── Metric labels we try to extract from header/summary rows ────────
    _METRIC_LABELS = {
        "initial deposit":  "deposit",
        "deposit":          "deposit",
        "total net profit":  "net_profit",
        "net profit":       "net_profit",
        "gross profit":     "gross_profit",
        "gross loss":       "gross_loss",
        "profit factor":    "profit_factor",
        "expected payoff":  "expected_payoff",
        "total trades":     "total_trades",
        "balance drawdown absolute": "balance_drawdown_absolute",
        "balance drawdown maximal": "balance_drawdown_maximal",
        "balance drawdown relative": "balance_drawdown_relative",
        "equity drawdown absolute": "equity_drawdown_absolute",
        "equity drawdown maximal": "equity_drawdown_maximal",
        "equity drawdown relative": "equity_drawdown_relative",
        "maximal drawdown": "maximal_drawdown",
        "max drawdown":     "maximal_drawdown",
        "relative drawdown":   "maximal_drawdown_pct",
        "recovery factor":  "recovery_factor",
        "sharpe ratio":     "sharpe_ratio",
        "symbol":           "symbol",
        "period":           "period",
        "expert":           "ea_name",
        "expert advisor":   "ea_name",
        "spread":           "backtest_spread",
        "short positions (won %)": "short_positions_win_pct",
        "short trades (won %)":    "short_positions_win_pct",
        "long positions (won %)":  "long_positions_win_pct",
        "long trades (won %)":     "long_positions_win_pct",
        "profit trades (% of total)": "win_rate",
        "profit trades":    "win_rate",
        "average profit trade": "average_profit",
        "average loss trade":   "average_loss",
        "maximal consecutive wins":  "consecutive_wins_max",
        "maximal consecutive losses": "consecutive_losses_max",
        "consecutive wins (profit in money)":  "consecutive_wins_max",
        "consecutive losses (loss in money)":  "consecutive_losses_max",
    }

    def parse(self, xlsx_content: bytes) -> Tuple[BacktestMetrics, List[TradeRecord]]:
        all_sheets = self._read_all_sheets(xlsx_content)
        best_rows = self._best_trade_table(all_sheets)
        if not best_rows:
            return BacktestMetrics(), []

        # ── Extract summary metrics from ALL sheets (before trade table) ──
        pre_metrics = self._extract_summary_metrics(all_sheets)

        header_index = self._detect_header_index(best_rows)
        if header_index is None:
            return BacktestMetrics(), []

        seen_headers = {}
        headers = []
        for value in best_rows[header_index]:
            cleaned = self._clean_header(value)
            if not cleaned:
                headers.append("")
                continue
            if cleaned in seen_headers:
                seen_headers[cleaned] += 1
                headers.append(f"{cleaned}_{seen_headers[cleaned]}")
            else:
                seen_headers[cleaned] = 0
                headers.append(cleaned)

        records = []
        for raw_row in best_rows[header_index + 1:]:
            if not any(str(value).strip() for value in raw_row if value is not None):
                continue
            padded = raw_row + [""] * max(0, len(headers) - len(raw_row))
            record = {}
            for idx, key in enumerate(headers):
                if key:
                    record[key] = padded[idx]
            records.append(record)

        if not records:
            return BacktestMetrics(), []

        csv_buffer = io.StringIO()
        df = pd.DataFrame(records)
        df.to_csv(csv_buffer, index=False)
        metrics, trades = CSVParser().parse(csv_buffer.getvalue().encode("utf-8"))

        # ── Merge pre-extracted summary metrics into parsed metrics ──
        self._apply_summary_metrics(metrics, pre_metrics)

        return metrics, trades

    # ──────────────────────── Summary metric extraction ────────────────────────

    def _extract_summary_metrics(self, all_sheets: List[List[List[str]]]) -> dict:
        """Scan every sheet for label→value pairs above/outside the trade table."""
        found: dict = {}
        for rows in all_sheets:
            for row in rows:
                cells = [cell for cell in row if str(cell).strip()]
                idx = 0
                while idx < len(cells) - 1:
                    label = self._normalize_label(cells[idx])
                    value_text = str(cells[idx + 1]).strip()
                    mapped = self._METRIC_LABELS.get(label)
                    if mapped and value_text and mapped not in found:
                        found[mapped] = value_text
                    idx += 2
        return found

    def _normalize_label(self, text) -> str:
        t = str(text).strip().lower()
        t = re.sub(r"\([^)]*\)", "", t)
        t = re.sub(r"[:]+", "", t)
        return re.sub(r"\s+", " ", t).strip()

    def _apply_summary_metrics(self, metrics: BacktestMetrics, pre: dict):
        """Overlay summary-metric values when the parser didn't already fill them."""
        drawdown_fields = (
            "balance_drawdown_absolute",
            "balance_drawdown_maximal",
            "balance_drawdown_relative",
            "equity_drawdown_absolute",
            "equity_drawdown_maximal",
            "equity_drawdown_relative",
        )
        for field in drawdown_fields:
            if field in pre and not getattr(metrics, field, None):
                setattr(metrics, field, str(pre[field]).strip())

        if not metrics.maximal_drawdown:
            for f in ("equity_drawdown_maximal", "balance_drawdown_maximal"):
                if getattr(metrics, f, None):
                    money = self._extract_money(getattr(metrics, f))
                    if money is not None:
                        metrics.maximal_drawdown = abs(money)
                        break
        if not metrics.maximal_drawdown_pct:
            for f in ("equity_drawdown_relative", "balance_drawdown_relative"):
                if getattr(metrics, f, None):
                    pct = self._extract_pct(getattr(metrics, f))
                    if pct is not None:
                        metrics.maximal_drawdown_pct = pct
                        break

        for field, raw in pre.items():
            current = getattr(metrics, field, None)
            if field in ("symbol", "period", "ea_name", "backtest_spread") or field in drawdown_fields:
                if not current:
                    setattr(metrics, field, raw)
                continue
            # Numeric fields
            num = self._parse_money_or_pct(raw)
            if num is None:
                continue
            if field == "total_trades":
                if not metrics.total_trades:
                    metrics.total_trades = int(num)
            elif field == "consecutive_wins_max":
                if not metrics.consecutive_wins_max:
                    metrics.consecutive_wins_max = int(self._first_int_from(raw))
            elif field == "consecutive_losses_max":
                if not metrics.consecutive_losses_max:
                    metrics.consecutive_losses_max = int(self._first_int_from(raw))
            elif field == "maximal_drawdown_pct":
                if not getattr(metrics, field, 0):
                    pct = self._extract_pct(raw)
                    if pct is not None:
                        setattr(metrics, field, pct)
            elif field in ("short_positions_win_pct", "long_positions_win_pct", "win_rate"):
                if not getattr(metrics, field, 0):
                    pct = self._extract_pct(raw)
                    if pct is not None:
                        setattr(metrics, field, pct)
            elif field == "maximal_drawdown":
                if not metrics.maximal_drawdown:
                    money = self._extract_money(raw)
                    if money is not None:
                        metrics.maximal_drawdown = abs(money)
            elif field == "average_loss":
                if not metrics.average_loss:
                    metrics.average_loss = abs(num)
            else:
                if not getattr(metrics, field, 0):
                    setattr(metrics, field, num)

    def _parse_money_or_pct(self, raw: str) -> Optional[float]:
        cleaned = re.sub(r"[%$€£¥]", "", str(raw))
        cleaned = cleaned.replace("\xa0", " ").strip()
        match = re.search(r"-?\d[\d\s,]*(?:\.\d+)?", cleaned)
        if not match:
            return None
        try:
            return float(match.group(0).replace(" ", "").replace(",", ""))
        except ValueError:
            return None

    def _extract_pct(self, raw: str) -> Optional[float]:
        m = re.search(r"\(?\s*(-?[\d\s,.]+)\s*%\s*\)?", raw)
        if m:
            try:
                return abs(float(m.group(1).replace(" ", "").replace(",", "")))
            except ValueError:
                return None
        num = self._parse_money_or_pct(raw)
        if num is not None and abs(num) <= 100:
            return abs(num)
        return None

    def _extract_money(self, raw: str) -> Optional[float]:
        # Take the number before any parenthesised percentage
        part = raw.split("(")[0]
        return self._parse_money_or_pct(part)

    def _first_int_from(self, raw: str) -> int:
        m = re.search(r"\d+", str(raw))
        return int(m.group(0)) if m else 0

    # ──────────────────────── Sheet / table helpers ────────────────────────

    def _best_trade_table(self, all_sheets: List[List[List[str]]]) -> List[List[str]]:
        best_rows: List[List[str]] = []
        best_score = -1
        for rows in all_sheets:
            header_index = self._detect_header_index(rows)
            if header_index is None:
                continue
            score = self._header_score(rows[header_index]) + min(25, max(0, len(rows) - header_index - 1))
            if score > best_score:
                best_score = score
                best_rows = rows
        return best_rows

    def _read_all_sheets(self, content: bytes) -> List[List[List[str]]]:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared_strings = self._shared_strings(archive)
            date_style_ids = self._detect_date_styles(archive)
            sheet_paths = self._sheet_paths(archive)
            sheets = []
            for sheet_path in sheet_paths:
                if sheet_path not in archive.namelist():
                    continue
                root = ET.fromstring(archive.read(sheet_path))
                sheets.append(self._sheet_rows(root, shared_strings, date_style_ids))
            return sheets

    def _sheet_rows(self, root: ET.Element, shared_strings: List[str], date_style_ids: set) -> List[List[str]]:
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rows: List[List[str]] = []
        for row in root.findall(".//main:sheetData/main:row", ns):
            values = []
            current_col = 0
            for cell in row.findall("main:c", ns):
                ref = cell.attrib.get("r", "")
                col_index = self._column_index(ref)
                while current_col < col_index:
                    values.append("")
                    current_col += 1
                style_id = cell.attrib.get("s", "")
                is_date_style = style_id in date_style_ids
                values.append(self._cell_value(cell, shared_strings, ns, is_date_style))
                current_col += 1
            rows.append(values)
        return rows

    def _sheet_paths(self, archive: zipfile.ZipFile) -> List[str]:
        workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_xml = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
        relationships = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_xml.findall("rel:Relationship", rel_ns)
        }
        main_ns = {
            "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        paths = []
        for sheet in workbook_xml.findall(".//main:sheets/main:sheet", main_ns):
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = relationships.get(rel_id or "")
            if not target:
                continue
            paths.append("xl/" + target.lstrip("/") if not target.startswith("xl/") else target)
        return paths

    def _shared_strings(self, archive: zipfile.ZipFile) -> List[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        values = []
        for item in root.findall("main:si", ns):
            texts = [node.text or "" for node in item.findall(".//main:t", ns)]
            values.append("".join(texts))
        return values

    def _detect_date_styles(self, archive: zipfile.ZipFile) -> set:
        """Detect which cell style IDs correspond to date/time formats."""
        if "xl/styles.xml" not in archive.namelist():
            return set()
        try:
            root = ET.fromstring(archive.read("xl/styles.xml"))
        except Exception:
            return set()
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

        # Built-in date format IDs in Excel
        builtin_date_ids = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | {36}

        # Scan custom numFmts for date-like patterns
        custom_date_ids: set = set()
        for fmt in root.findall(".//main:numFmts/main:numFmt", ns):
            fmt_id = fmt.attrib.get("numFmtId", "")
            code = (fmt.attrib.get("formatCode", "") or "").lower()
            if any(tok in code for tok in ("yyyy", "yy", "mm", "dd", "hh", "ss", "am/pm")):
                try:
                    custom_date_ids.add(int(fmt_id))
                except ValueError:
                    pass

        all_date_fmt_ids = builtin_date_ids | custom_date_ids

        # Map cellXfs style index → set of style-index strings that use date numFmtId
        date_style_ids: set = set()
        xfs = root.findall(".//main:cellXfs/main:xf", ns)
        for idx, xf in enumerate(xfs):
            fmt_id_str = xf.attrib.get("numFmtId", "0")
            try:
                if int(fmt_id_str) in all_date_fmt_ids:
                    date_style_ids.add(str(idx))
            except ValueError:
                pass
        return date_style_ids

    def _cell_value(self, cell: ET.Element, shared_strings: List[str], ns, is_date_style: bool = False) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            texts = [node.text or "" for node in cell.findall(".//main:t", ns)]
            return "".join(texts)

        value_node = cell.find("main:v", ns)
        if value_node is None or value_node.text is None:
            return ""
        value = value_node.text
        if cell_type == "s":
            try:
                return shared_strings[int(value)]
            except Exception:
                return value
        if cell_type == "b":
            return "TRUE" if value == "1" else "FALSE"
        # For numeric cells, convert Excel serial dates to readable strings
        return self._maybe_convert_date(value, is_date_style)

    def _maybe_convert_date(self, value: str, is_date_style: bool) -> str:
        """Convert Excel serial-date numbers to YYYY.MM.DD HH:MM:SS strings."""
        try:
            numeric = float(value)
        except ValueError:
            return value

        # Only convert if style indicates a date format, or the number looks like a
        # plausible date serial (roughly 1900-01-01 through 2200-12-31).
        if is_date_style or (25569 < numeric < 109574 and "." not in value):
            # Heuristic: only convert integers or numbers with time fraction > 0
            # that look like valid Excel dates
            if is_date_style or (numeric > 25569):
                try:
                    dt = _EXCEL_EPOCH + timedelta(days=numeric)
                    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                        return dt.strftime("%Y.%m.%d 00:00")
                    return dt.strftime("%Y.%m.%d %H:%M:%S")
                except (OverflowError, ValueError, OSError):
                    pass
        return value

    def _column_index(self, ref: str) -> int:
        letters = re.sub(r"[^A-Z]", "", ref.upper())
        index = 0
        for letter in letters:
            index = index * 26 + (ord(letter) - ord("A") + 1)
        return max(0, index - 1)

    def _clean_header(self, value) -> str:
        text = str(value).strip().lower()
        text = re.sub(r"\([^)]*\)", "", text)
        text = re.sub(r"[^a-z0-9]+", "_", text)
        return text.strip("_")

    def _detect_header_index(self, rows: List[List[str]]) -> Optional[int]:
        best_index = None
        best_score = 0
        for index, row in enumerate(rows):
            score = self._header_score(row)
            if score > best_score:
                best_score = score
                best_index = index
        return best_index if best_score >= 3 else None

    def _header_score(self, row: List[str]) -> int:
        cleaned = {self._clean_header(value) for value in row if str(value).strip()}
        score = len(cleaned & self.HEADER_ALIASES)
        if self.PROFIT_HEADERS & cleaned:
            score += 20
        if {"balance", "equity", "equity_exit", "equity_at_exit"} & cleaned:
            score += 6
        if {"open_time", "entry_time", "time"} & cleaned:
            score += 2
        if {"symbol", "asset", "item"} & cleaned:
            score += 2
        if {"close_time", "exit_time", "close_price", "exit_price"} & cleaned:
            score += 2
        return score
