from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..models.schemas import BacktestMetrics, TradeRecord


class MT4Parser:
    @staticmethod
    def parse(html_content) -> Tuple[BacktestMetrics, List[TradeRecord]]:
        if isinstance(html_content, bytes):
            html_content = MT4Parser._decode_html(html_content)

        soup = BeautifulSoup(html_content, "html.parser")
        rows = MT4Parser._rows(soup)
        pairs = MT4Parser._metric_pairs(rows)

        maximal_drawdown = MT4Parser._money(pairs, ["maximal drawdown"])
        maximal_drawdown_pct = MT4Parser._percent(pairs, ["relative drawdown", "maximal drawdown"])
        avg_profit = MT4Parser._number_from_pair(pairs, ["average profit trade", "profit trade"])
        avg_loss = abs(MT4Parser._number_from_pair(pairs, ["average loss trade", "loss trade"]))

        metrics = BacktestMetrics(
            ea_name=MT4Parser._title_text(soup),
            symbol=MT4Parser._text_from_pair(pairs, ["symbol"]),
            period=MT4Parser._text_from_pair(pairs, ["period"]),
            deposit=MT4Parser._number_from_pair(pairs, ["initial deposit", "deposit"]),
            net_profit=MT4Parser._number_from_pair(pairs, ["total net profit", "net profit"]),
            gross_profit=MT4Parser._number_from_pair(pairs, ["gross profit"]),
            gross_loss=abs(MT4Parser._number_from_pair(pairs, ["gross loss"])),
            profit_factor=MT4Parser._number_from_pair(pairs, ["profit factor"]),
            expected_payoff=MT4Parser._number_from_pair(pairs, ["expected payoff"]),
            maximal_drawdown=maximal_drawdown,
            maximal_drawdown_pct=maximal_drawdown_pct,
            total_trades=int(MT4Parser._number_from_pair(pairs, ["total trades"])),
            short_positions_win_pct=MT4Parser._percent(pairs, ["short positions (won %)"]),
            long_positions_win_pct=MT4Parser._percent(pairs, ["long positions (won %)"]),
            win_rate=MT4Parser._percent(pairs, ["profit trades (% of total)"]),
            average_profit=avg_profit,
            average_loss=avg_loss,
            consecutive_wins_max=int(MT4Parser._first_int(pairs, ["consecutive wins (profit in money)"])),
            consecutive_losses_max=int(MT4Parser._first_int(pairs, ["consecutive losses (loss in money)"])),
            risk_reward_ratio=round(avg_profit / avg_loss, 2) if avg_loss else 0.0,
        )

        trades = MT4Parser._parse_history(rows)
        MT4Parser._complete_metrics(metrics, trades)
        return metrics, trades

    @staticmethod
    def _decode_html(content: bytes) -> str:
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

    @staticmethod
    def _rows(soup: BeautifulSoup) -> List[List[str]]:
        parsed_rows: List[List[str]] = []
        for tr in soup.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
            cells = [re.sub(r"\s+", " ", cell).strip() for cell in cells]
            if any(cells):
                parsed_rows.append(cells)
        return parsed_rows

    @staticmethod
    def _metric_pairs(rows: List[List[str]]) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        prefix = ""

        for row in rows:
            cells = [cell for cell in row if cell]
            if MT4Parser._is_history_header(cells):
                break

            if cells and cells[0].lower() in {"largest", "average", "maximum", "maximal"}:
                prefix = cells[0].lower()
                cells = cells[1:]

            index = 0
            while index < len(cells) - 1:
                label = MT4Parser._label(cells[index])
                value = cells[index + 1]
                if label and not MT4Parser._looks_like_number(label):
                    full_label = f"{prefix} {label}".strip() if prefix and label in {"profit trade", "loss trade"} else label
                    if MT4Parser._valid_metric_value(value):
                        pairs[full_label] = value
                index += 2

        return pairs

    @staticmethod
    def _parse_history(rows: List[List[str]]) -> List[TradeRecord]:
        trades: List[TradeRecord] = []
        in_history = False
        open_orders: Dict[str, Dict[str, str]] = {}

        for row in rows:
            if MT4Parser._is_history_header(row):
                in_history = True
                continue
            if not in_history or len(row) < 8:
                continue

            row_type = row[2].lower() if len(row) > 2 else ""
            order_id = row[3] if len(row) > 3 else ""
            if not order_id or not row_type:
                continue

            if row_type in {"buy", "sell"}:
                open_orders[order_id] = {
                    "time": row[1],
                    "type": row_type,
                    "size": row[4],
                    "price": row[5],
                    "s_l": row[6] if len(row) > 6 else "",
                    "t_p": row[7] if len(row) > 7 else "",
                }
                continue

            if row_type not in {"s/l", "t/p", "close", "close at stop", "close at profit"}:
                continue
            if len(row) < 10:
                continue

            profit = MT4Parser._number(row[8])
            balance = MT4Parser._number(row[9])
            if profit == 0 and balance == 0:
                continue

            opening = open_orders.get(order_id, {})
            open_time = MT4Parser._date(opening.get("time"))
            close_time = MT4Parser._date(row[1])
            duration = None
            if open_time and close_time and close_time >= open_time:
                duration = round((close_time - open_time).total_seconds() / 60, 2)

            trades.append(
                TradeRecord(
                    ticket=order_id,
                    open_time=open_time,
                    close_time=close_time,
                    type=opening.get("type", "buy"),
                    size=MT4Parser._volume(opening.get("size") or row[4]),
                    item="Unknown",
                    price=MT4Parser._number(opening.get("price")),
                    s_l=MT4Parser._optional_number(opening.get("s_l")),
                    t_p=MT4Parser._optional_number(opening.get("t_p")),
                    close_price=MT4Parser._number(row[5]),
                    profit=profit,
                    balance=balance,
                    comment=row_type,
                    duration_minutes=duration,
                )
            )

        trades.sort(key=lambda trade: trade.close_time or trade.open_time or datetime.min)
        return trades

    @staticmethod
    def _complete_metrics(metrics: BacktestMetrics, trades: List[TradeRecord]) -> None:
        if not trades:
            if metrics.win_rate == 0:
                rates = [metrics.short_positions_win_pct, metrics.long_positions_win_pct]
                rates = [rate for rate in rates if rate > 0]
                metrics.win_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
            if metrics.recovery_factor == 0 and metrics.maximal_drawdown:
                metrics.recovery_factor = round(metrics.net_profit / metrics.maximal_drawdown, 2)
            return

        profits = [trade.profit for trade in trades if trade.profit > 0]
        losses = [abs(trade.profit) for trade in trades if trade.profit < 0]
        durations = [trade.duration_minutes for trade in trades if trade.duration_minutes is not None]
        returns = [trade.profit / max(abs((trade.balance or 0) - trade.profit), 1.0) for trade in trades]

        metrics.total_trades = metrics.total_trades or len(trades)
        metrics.net_profit = metrics.net_profit or round(sum(trade.profit for trade in trades), 2)
        metrics.gross_profit = metrics.gross_profit or round(sum(profits), 2)
        metrics.gross_loss = metrics.gross_loss or round(sum(losses), 2)
        if metrics.profit_factor == 0 and metrics.gross_loss:
            metrics.profit_factor = round(metrics.gross_profit / metrics.gross_loss, 2)
        if metrics.expected_payoff == 0 and trades:
            metrics.expected_payoff = round(metrics.net_profit / len(trades), 2)
        if metrics.win_rate == 0 and trades:
            metrics.win_rate = round((len(profits) / len(trades)) * 100, 2)
        if metrics.average_profit == 0 and profits:
            metrics.average_profit = round(sum(profits) / len(profits), 2)
        if metrics.average_loss == 0 and losses:
            metrics.average_loss = round(sum(losses) / len(losses), 2)
        if metrics.risk_reward_ratio == 0 and metrics.average_loss:
            metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)
        if metrics.average_trade_duration == 0 and durations:
            metrics.average_trade_duration = round(sum(durations) / len(durations), 2)
        if metrics.recovery_factor == 0 and metrics.maximal_drawdown:
            metrics.recovery_factor = round(metrics.net_profit / metrics.maximal_drawdown, 2)
        if metrics.sharpe_ratio == 0 and len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            variance = sum((value - avg_return) ** 2 for value in returns) / (len(returns) - 1)
            stdev = math.sqrt(variance)
            if stdev:
                metrics.sharpe_ratio = round((avg_return / stdev) * math.sqrt(len(returns)), 2)
        if not metrics.symbol:
            metrics.symbol = "MT4 Report"

    @staticmethod
    def _title_text(soup: BeautifulSoup) -> Optional[str]:
        title = soup.find("title")
        if title:
            text = title.get_text(" ", strip=True)
            return text.replace("Strategy Tester:", "").strip() or None
        return None

    @staticmethod
    def _text_from_pair(pairs: Dict[str, str], labels: List[str]) -> Optional[str]:
        for label in labels:
            value = pairs.get(MT4Parser._label(label))
            if value:
                return value
        return None

    @staticmethod
    def _number_from_pair(pairs: Dict[str, str], labels: List[str]) -> float:
        value = MT4Parser._text_from_pair(pairs, labels)
        return MT4Parser._number(value)

    @staticmethod
    def _money(pairs: Dict[str, str], labels: List[str]) -> float:
        value = MT4Parser._text_from_pair(pairs, labels)
        if not value:
            return 0.0
        return abs(MT4Parser._number(value.split("(")[0]))

    @staticmethod
    def _percent(pairs: Dict[str, str], labels: List[str]) -> float:
        value = MT4Parser._text_from_pair(pairs, labels)
        if not value:
            return 0.0
        paren = re.search(r"\(([-\d\s,.]+)%\)", value)
        if paren:
            return abs(MT4Parser._number(paren.group(1)))
        percent = re.search(r"([-\d\s,.]+)%", value)
        if percent:
            return abs(MT4Parser._number(percent.group(1)))
        number = abs(MT4Parser._number(value))
        return number if number <= 100 else 0.0

    @staticmethod
    def _first_int(pairs: Dict[str, str], labels: List[str]) -> int:
        value = MT4Parser._text_from_pair(pairs, labels)
        if not value:
            return 0
        match = re.search(r"\d+", value)
        return int(match.group(0)) if match else 0

    @staticmethod
    def _number(value: Optional[str]) -> float:
        if not value:
            return 0.0
        raw = str(value).replace("\xa0", " ").strip()
        negative = raw.startswith("(") and raw.endswith(")")
        match = re.search(r"-?\d[\d\s,]*(?:\.\d+)?", raw)
        if not match:
            return 0.0
        try:
            parsed = float(match.group(0).replace(" ", "").replace(",", ""))
            return -abs(parsed) if negative else parsed
        except ValueError:
            return 0.0

    @staticmethod
    def _volume(value: Optional[str]) -> float:
        if not value:
            return 0.0
        return MT4Parser._number(str(value).split("/")[0])

    @staticmethod
    def _optional_number(value: Optional[str]) -> Optional[float]:
        number = MT4Parser._number(value)
        return number if number else None

    @staticmethod
    def _date(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y.%m.%d %H:%M", "%Y.%m.%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _label(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace(":", " ").strip().lower())

    @staticmethod
    def _looks_like_number(value: str) -> bool:
        return bool(re.fullmatch(r"[-\d\s,.()%]+", value or ""))

    @staticmethod
    def _valid_metric_value(value: str) -> bool:
        if not value:
            return False
        return MT4Parser._label(value) not in {"type", "profit", "balance", "price", "time", "order", "size"}

    @staticmethod
    def _is_history_header(cells: List[str]) -> bool:
        labels = {MT4Parser._label(cell) for cell in cells}
        return {"#", "time", "type", "order", "size", "price", "profit", "balance"}.issubset(labels)
