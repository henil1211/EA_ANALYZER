from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ..models.schemas import BacktestMetrics, TradeRecord


class MT5Parser:
    @staticmethod
    def parse(html_content) -> Tuple[BacktestMetrics, List[TradeRecord]]:
        if isinstance(html_content, bytes):
            html_content = MT5Parser._decode_html(html_content)

        soup = BeautifulSoup(html_content, "html.parser")
        rows = MT5Parser._rows(soup)
        text = soup.get_text("\n", strip=True)
        metric_cells = MT5Parser._metric_pairs(rows)

        total_trades = int(MT5Parser._metric_number(metric_cells, text, ["Total Trades", "Trades Total"]))
        short_won_pct = MT5Parser._metric_percent(metric_cells, text, ["Short Trades (won %)", "Short Positions (won %)"])
        long_won_pct = MT5Parser._metric_percent(metric_cells, text, ["Long Trades (won %)", "Long Positions (won %)"])
        profit_trades_pct = MT5Parser._metric_percent(metric_cells, text, ["Profit Trades (% of total)", "Profit Trades"])

        maximal_drawdown = MT5Parser._metric_money(
            metric_cells,
            text,
            ["Balance Drawdown Maximal", "Equity Drawdown Maximal", "Maximal Drawdown"],
        )
        maximal_drawdown_pct = MT5Parser._metric_percent(
            metric_cells,
            text,
            ["Balance Drawdown Relative", "Equity Drawdown Relative", "Relative Drawdown", "Maximal Drawdown"],
        )

        balance_drawdown_absolute = MT5Parser._metric_text(metric_cells, text, ["Balance Drawdown Absolute"])
        balance_drawdown_maximal = MT5Parser._metric_text(metric_cells, text, ["Balance Drawdown Maximal"])
        balance_drawdown_relative = MT5Parser._metric_text(metric_cells, text, ["Balance Drawdown Relative"])
        equity_drawdown_absolute = MT5Parser._metric_text(metric_cells, text, ["Equity Drawdown Absolute"])
        equity_drawdown_maximal = MT5Parser._metric_text(metric_cells, text, ["Equity Drawdown Maximal"])
        equity_drawdown_relative = MT5Parser._metric_text(metric_cells, text, ["Equity Drawdown Relative"])
        backtest_spread = MT5Parser._metric_text(metric_cells, text, ["Spread"])

        metrics = BacktestMetrics(
            ea_name=MT5Parser._metric_text(metric_cells, text, ["Expert", "Expert Advisor"]),
            symbol=MT5Parser._metric_text(metric_cells, text, ["Symbol"]) or "MT5 EA",
            period=MT5Parser._metric_text(metric_cells, text, ["Period"]) or "Historical",
            deposit=MT5Parser._metric_number(metric_cells, text, ["Initial Deposit", "Deposit"]),
            net_profit=MT5Parser._metric_number(metric_cells, text, ["Total Net Profit", "Net Profit"]),
            gross_profit=MT5Parser._metric_number(metric_cells, text, ["Gross Profit"]),
            gross_loss=abs(MT5Parser._metric_number(metric_cells, text, ["Gross Loss"])),
            profit_factor=MT5Parser._metric_number(metric_cells, text, ["Profit Factor"]),
            expected_payoff=MT5Parser._metric_number(metric_cells, text, ["Expected Payoff"]),
            maximal_drawdown=maximal_drawdown,
            maximal_drawdown_pct=maximal_drawdown_pct,
            recovery_factor=MT5Parser._metric_number(metric_cells, text, ["Recovery Factor"]),
            sharpe_ratio=MT5Parser._metric_number(metric_cells, text, ["Sharpe Ratio"]),
            total_trades=total_trades,
            short_positions_win_pct=short_won_pct,
            long_positions_win_pct=long_won_pct,
            win_rate=profit_trades_pct or MT5Parser._combined_win_rate(short_won_pct, long_won_pct),
            average_profit=MT5Parser._metric_number(metric_cells, text, ["Average profit trade", "Average Profit Trade"]),
            average_loss=abs(MT5Parser._metric_number(metric_cells, text, ["Average loss trade", "Average Loss Trade"])),
            consecutive_wins_max=int(MT5Parser._metric_number(metric_cells, text, ["Maximal consecutive wins"])),
            consecutive_losses_max=int(MT5Parser._metric_number(metric_cells, text, ["Maximal consecutive losses"])),
            balance_drawdown_absolute=balance_drawdown_absolute,
            balance_drawdown_maximal=balance_drawdown_maximal,
            balance_drawdown_relative=balance_drawdown_relative,
            equity_drawdown_absolute=equity_drawdown_absolute,
            equity_drawdown_maximal=equity_drawdown_maximal,
            equity_drawdown_relative=equity_drawdown_relative,
            backtest_spread=backtest_spread,
        )
        if metrics.risk_reward_ratio == 0 and metrics.average_loss:
            metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)

        trades = MT5Parser._parse_deals(rows)
        if not trades:
            trades = MT5Parser._parse_deals_from_text(text)
        MT5Parser._complete_metrics(metrics, trades)
        return metrics, trades

    @staticmethod
    def _decode_html(content: bytes) -> str:
        if content.startswith(b"\xff\xfe") or content[:200].count(b"\x00") > 20:
            return content.decode("utf-16", errors="ignore")
        if content.startswith(b"\xef\xbb\xbf"):
            return content.decode("utf-8-sig", errors="ignore")
        for encoding in ("utf-8", "cp1252", "latin1"):
            try:
                decoded = content.decode(encoding)
                if decoded.count("<tr") or decoded.count("<td") or "Strategy Tester" in decoded:
                    return decoded
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
        for row in rows:
            cells = [cell for cell in row if cell]
            if MT5Parser._looks_like_deal_header(cells) or MT5Parser._looks_like_trade_table_row(cells):
                continue

            for index in range(0, len(cells) - 1, 2):
                label = MT5Parser._label(cells[index])
                value = cells[index + 1]
                if MT5Parser._looks_like_metric_label(label):
                    pairs[label] = value

            for index in range(len(cells) - 1):
                label = MT5Parser._label(cells[index])
                value = cells[index + 1]
                if MT5Parser._looks_like_metric_label(label):
                    pairs.setdefault(label, value)
        return pairs

    @staticmethod
    def _parse_deals(rows: List[List[str]]) -> List[TradeRecord]:
        trades: List[TradeRecord] = []
        grouped_exits: Dict[str, List[TradeRecord]] = {}
        headers: Optional[List[str]] = None
        open_deals: Dict[str, Dict[str, str]] = {}
        open_by_symbol: Dict[str, List[Dict[str, str]]] = {}

        for row in rows:
            labels = [MT5Parser._label(cell) for cell in row]
            if MT5Parser._looks_like_deal_header(row):
                headers = labels
                continue
            if headers is None:
                continue

            row_map = MT5Parser._row_map(headers, row)
            trade_key = MT5Parser._trade_key(row_map)
            direction = (MT5Parser._first(row_map, ["direction"]) or "").lower()
            trade_type = (MT5Parser._first(row_map, ["type"]) or "").lower()
            symbol = MT5Parser._first(row_map, ["symbol", "item"]) or "Unknown"
            if trade_key and direction == "in" and ("buy" in trade_type or "sell" in trade_type):
                open_deals[trade_key] = row_map
                open_by_symbol.setdefault(symbol, []).append(row_map)
                continue

            opening_row = open_deals.get(trade_key or "") or MT5Parser._pop_matching_open(open_by_symbol, row_map)
            trade = MT5Parser._deal_to_trade(row_map, opening_row)
            if trade:
                if trade_key:
                    grouped_exits.setdefault(trade_key, []).append(trade)
                else:
                    trades.append(trade)

        for group in grouped_exits.values():
            trades.append(MT5Parser._combine_trade_group(group))
        trades.sort(key=lambda t: t.close_time or t.open_time or datetime.min)
        return trades

    @staticmethod
    def _deal_to_trade(row: Dict[str, str], opening_row: Optional[Dict[str, str]] = None) -> Optional[TradeRecord]:
        trade_type = (MT5Parser._first(row, ["type"]) or "").lower()
        direction = (MT5Parser._first(row, ["direction"]) or "").lower()

        if "buy" not in trade_type and "sell" not in trade_type:
            return None
        if direction and direction not in {"out", "out by", "in/out", "inout"}:
            return None

        profit = MT5Parser._number(MT5Parser._first(row, ["profit", "p/l", "result"]))
        balance = MT5Parser._number(MT5Parser._first(row, ["balance"]))
        if profit == 0 and balance == 0:
            return None

        open_time = MT5Parser._date(MT5Parser._first(opening_row or {}, ["time", "open time"]))
        close_time = MT5Parser._date(MT5Parser._first(row, ["time", "close time"]))
        duration = None
        if open_time and close_time and close_time >= open_time:
            duration = round((close_time - open_time).total_seconds() / 60, 2)

        return TradeRecord(
            ticket=MT5Parser._first(row, ["deal", "ticket", "order", "#"]),
            open_time=open_time,
            close_time=close_time,
            type="sell" if "sell" in trade_type else "buy",
            size=MT5Parser._number(MT5Parser._first(row, ["volume", "size", "lots"]))
            or MT5Parser._number(MT5Parser._first(opening_row or {}, ["volume", "size", "lots"])),
            item=MT5Parser._first(row, ["symbol", "item"])
            or MT5Parser._first(opening_row or {}, ["symbol", "item"])
            or "Unknown",
            price=MT5Parser._number(MT5Parser._first(opening_row or {}, ["price", "open price"]))
            or MT5Parser._number(MT5Parser._first(row, ["price", "open price"])),
            close_price=MT5Parser._number(MT5Parser._first(row, ["price", "close price"])) or None,
            commission=MT5Parser._number(MT5Parser._first(row, ["commission", "comm"])),
            swap=MT5Parser._number(MT5Parser._first(row, ["swap"])),
            profit=profit,
            balance=balance or None,
            comment=MT5Parser._first(row, ["comment"]),
            duration_minutes=duration,
        )

    @staticmethod
    def _parse_deals_from_text(text: str) -> List[TradeRecord]:
        trades: List[TradeRecord] = []
        open_deals: Dict[str, Dict[str, str]] = {}

        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not re.match(r"^\d{4}[.\-/]\d{2}[.\-/]\d{2}\s+\d{2}:\d{2}", line):
                continue
            if not re.search(r"\b(buy|sell)\b", line, re.I):
                continue

            parsed = MT5Parser._parse_text_deal_line(line)
            if not parsed:
                continue

            direction = (parsed.get("direction") or "").lower()
            trade_key = parsed.get("order")
            trade_type = (parsed.get("type") or "").lower()
            if trade_key and direction == "in" and ("buy" in trade_type or "sell" in trade_type):
                open_deals[trade_key] = parsed
                continue

            trade = MT5Parser._deal_to_trade(parsed, open_deals.get(trade_key or ""))
            if trade:
                trades.append(trade)

        trades.sort(key=lambda t: t.close_time or t.open_time or datetime.min)
        return trades

    @staticmethod
    def _parse_text_deal_line(line: str) -> Optional[Dict[str, str]]:
        parts = line.split()
        if len(parts) < 10:
            return None

        time_value = f"{parts[0]} {parts[1]}"
        type_index = next((i for i, part in enumerate(parts) if part.lower() in {"buy", "sell"}), None)
        if type_index is None or type_index + 4 >= len(parts):
            return None

        direction_index = type_index + 1
        direction = parts[direction_index].lower()
        if direction == "out" and direction_index + 1 < len(parts) and parts[direction_index + 1].lower() == "by":
            direction = "out by"
            after_direction = direction_index + 2
        else:
            after_direction = direction_index + 1

        numeric_tail = parts[after_direction:]
        if len(numeric_tail) < 5:
            return None

        return {
            "time": time_value,
            "deal": parts[2] if len(parts) > 2 else "",
            "symbol": parts[type_index - 1] if type_index >= 1 else "Unknown",
            "type": parts[type_index],
            "direction": direction,
            "volume": numeric_tail[0],
            "price": numeric_tail[1],
            "order": numeric_tail[2] if len(numeric_tail) >= 3 else "",
            "commission": numeric_tail[-4] if len(numeric_tail) >= 4 else "0",
            "swap": numeric_tail[-3] if len(numeric_tail) >= 3 else "0",
            "profit": numeric_tail[-2] if len(numeric_tail) >= 2 else "0",
            "balance": numeric_tail[-1] if numeric_tail else "0",
        }

    @staticmethod
    def _combine_trade_group(group: List[TradeRecord]) -> TradeRecord:
        group = sorted(group, key=lambda t: t.close_time or t.open_time or datetime.min)
        first = group[0]
        last = group[-1]
        profit = round(sum(t.profit for t in group), 2)
        commission = round(sum(t.commission for t in group), 2)
        swap = round(sum(t.swap for t in group), 2)
        volume = sum(t.size for t in group if t.size)
        open_time = first.open_time
        close_time = last.close_time or first.close_time
        duration = None
        if open_time and close_time and close_time >= open_time:
            duration = round((close_time - open_time).total_seconds() / 60, 2)

        return TradeRecord(
            ticket=first.ticket,
            open_time=open_time,
            close_time=close_time,
            type=first.type,
            size=round(volume, 4) if volume else first.size,
            item=first.item,
            price=first.price,
            close_price=last.close_price,
            commission=commission,
            swap=swap,
            profit=profit,
            balance=last.balance,
            comment=last.comment or first.comment,
            duration_minutes=duration,
        )

    @staticmethod
    def _complete_metrics(metrics: BacktestMetrics, trades: List[TradeRecord]) -> None:
        if not trades:
            if metrics.win_rate == 0:
                metrics.win_rate = MT5Parser._combined_win_rate(
                    metrics.short_positions_win_pct,
                    metrics.long_positions_win_pct,
                )
            if metrics.risk_reward_ratio == 0:
                if metrics.average_loss:
                    metrics.risk_reward_ratio = round(metrics.average_profit / metrics.average_loss, 2)
            return

        profits = [trade.profit for trade in trades if trade.profit > 0]
        losses = [abs(trade.profit) for trade in trades if trade.profit < 0]
        balances = [trade.balance for trade in trades if trade.balance is not None]
        durations = [trade.duration_minutes for trade in trades if trade.duration_minutes is not None]

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
        if metrics.deposit == 0 and balances:
            metrics.deposit = max(0.0, balances[0] - trades[0].profit)
        if not metrics.symbol or metrics.symbol == "MT5 EA":
            symbols = [trade.item for trade in trades if trade.item and trade.item != "Unknown"]
            metrics.symbol = max(set(symbols), key=symbols.count) if symbols else metrics.symbol

        MT5Parser._apply_streaks_and_drawdown(metrics, trades)
        if metrics.total_trades and len(trades) > metrics.total_trades:
            compressed = MT5Parser._compress_to_trade_count(trades, metrics.total_trades)
            trades[:] = compressed
            durations = [trade.duration_minutes for trade in trades if trade.duration_minutes is not None]
            if metrics.average_trade_duration == 0 and durations:
                metrics.average_trade_duration = round(sum(durations) / len(durations), 2)
            MT5Parser._apply_streaks_and_drawdown(metrics, trades)

    @staticmethod
    def _compress_to_trade_count(trades: List[TradeRecord], target_count: int) -> List[TradeRecord]:
        if target_count <= 0 or len(trades) <= target_count:
            return trades

        compressed: List[TradeRecord] = []
        total = len(trades)
        for index in range(target_count):
            start = round(index * total / target_count)
            end = round((index + 1) * total / target_count)
            chunk = trades[start:end] or [trades[min(start, total - 1)]]
            compressed.append(MT5Parser._combine_trade_group(chunk))
        return compressed

    @staticmethod
    def _apply_streaks_and_drawdown(metrics: BacktestMetrics, trades: List[TradeRecord]) -> None:
        peak = None
        max_drawdown = 0.0
        wins = losses = max_wins = max_losses = 0
        running = metrics.deposit

        for trade in trades:
            equity = trade.balance if trade.balance is not None else running + trade.profit
            running = equity
            peak = equity if peak is None else max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)

            if trade.profit > 0:
                wins += 1
                losses = 0
            elif trade.profit < 0:
                losses += 1
                wins = 0
            max_wins = max(max_wins, wins)
            max_losses = max(max_losses, losses)

        if metrics.maximal_drawdown == 0:
            metrics.maximal_drawdown = round(max_drawdown, 2)
        if metrics.maximal_drawdown_pct == 0 and metrics.deposit:
            metrics.maximal_drawdown_pct = round((metrics.maximal_drawdown / metrics.deposit) * 100, 2)
        metrics.consecutive_wins_max = metrics.consecutive_wins_max or max_wins
        metrics.consecutive_losses_max = metrics.consecutive_losses_max or max_losses

    @staticmethod
    def _metric_text(metric_cells: Dict[str, str], text: str, labels: List[str]) -> Optional[str]:
        for label in labels:
            normalised = MT5Parser._label(label)
            if normalised in metric_cells and MT5Parser._valid_metric_value(label, metric_cells[normalised]):
                return metric_cells[normalised]

        stop = "|".join(re.escape(label) for label in MT5Parser._known_labels())
        for label in labels:
            match = re.search(rf"{re.escape(label)}\s*:?\s*(.+?)(?=\n|(?:\s+(?:{stop})\s*:)|$)", text, re.I)
            if match:
                value = match.group(1).strip()
                if MT5Parser._valid_metric_value(label, value):
                    return value
        return None

    @staticmethod
    def _metric_number(metric_cells: Dict[str, str], text: str, labels: List[str]) -> float:
        return MT5Parser._number(MT5Parser._metric_text(metric_cells, text, labels))

    @staticmethod
    def _metric_money(metric_cells: Dict[str, str], text: str, labels: List[str]) -> float:
        value = MT5Parser._metric_text(metric_cells, text, labels)
        if not value:
            return 0.0
        return abs(MT5Parser._number(value.split("(")[0]))

    @staticmethod
    def _metric_percent(metric_cells: Dict[str, str], text: str, labels: List[str]) -> float:
        value = MT5Parser._metric_text(metric_cells, text, labels)
        if not value:
            return 0.0
        paren_percent = re.search(r"\(\s*(-?[\d\s,.]+)\s*%\s*\)", value)
        if paren_percent:
            return abs(MT5Parser._number(paren_percent.group(1)))
        any_percent = re.search(r"(-?[\d\s,.]+)\s*%", value)
        if any_percent:
            return abs(MT5Parser._number(any_percent.group(1)))
        number = abs(MT5Parser._number(value))
        return number if number <= 100 else 0.0

    @staticmethod
    @staticmethod
    def _combined_win_rate(short_pct: float, long_pct: float) -> float:
        values = [value for value in [short_pct, long_pct] if 0 < value <= 100]
        return round(sum(values) / len(values), 2) if values else 0.0

    @staticmethod
    def _row_map(headers: List[str], row: List[str]) -> Dict[str, str]:
        mapped: Dict[str, str] = {}
        for index, header in enumerate(headers):
            if index < len(row) and header:
                mapped[header] = row[index]
        return mapped

    @staticmethod
    def _first(row: Dict[str, str], labels: List[str]) -> Optional[str]:
        for label in labels:
            if label in row and row[label]:
                return row[label]
        return None

    @staticmethod
    def _trade_key(row: Dict[str, str]) -> Optional[str]:
        return MT5Parser._first(row, ["position", "position id", "order"])

    @staticmethod
    def _pop_matching_open(open_by_symbol: Dict[str, List[Dict[str, str]]], closing_row: Dict[str, str]) -> Optional[Dict[str, str]]:
        symbol = MT5Parser._first(closing_row, ["symbol", "item"]) or "Unknown"
        candidates = open_by_symbol.get(symbol) or []
        if not candidates:
            return None

        closing_type = (MT5Parser._first(closing_row, ["type"]) or "").lower()
        opposite = "sell" if closing_type == "buy" else "buy"
        for index, candidate in enumerate(candidates):
            candidate_type = (MT5Parser._first(candidate, ["type"]) or "").lower()
            if candidate_type == opposite:
                return candidates.pop(index)
        return candidates.pop(0)

    @staticmethod
    def _date(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ["%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _number(value: Optional[str]) -> float:
        if value is None:
            return 0.0
        raw = str(value).replace("\xa0", " ").strip()
        if not raw:
            return 0.0
        negative = raw.startswith("(") and raw.endswith(")")
        match = re.search(r"-?\d[\d\s,]*(?:\.\d+)?", raw.replace("%", ""))
        if not match:
            return 0.0
        try:
            parsed = float(match.group(0).replace(" ", "").replace(",", ""))
            return -abs(parsed) if negative else parsed
        except ValueError:
            return 0.0

    @staticmethod
    def _label(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace(":", " ").strip().lower())

    @staticmethod
    def _looks_like_deal_header(cells: List[str]) -> bool:
        labels = {MT5Parser._label(cell) for cell in cells}
        return "deal" in labels and "type" in labels and "direction" in labels and "profit" in labels

    @staticmethod
    def _looks_like_trade_table_row(cells: List[str]) -> bool:
        labels = {MT5Parser._label(cell) for cell in cells}
        return (
            "symbol" in labels
            and "type" in labels
            and ("profit" in labels or "balance" in labels)
            and ("volume" in labels or "size" in labels or "lots" in labels)
        )

    @staticmethod
    def _valid_metric_value(label: str, value: str) -> bool:
        normalised_value = MT5Parser._label(str(value))
        if not normalised_value:
            return False
        table_words = {
            "time",
            "deal",
            "order",
            "symbol",
            "type",
            "direction",
            "volume",
            "price",
            "commission",
            "fee",
            "swap",
            "profit",
            "balance",
            "comment",
        }
        if normalised_value in table_words:
            return False
        if MT5Parser._label(label) in {"symbol", "period"} and re.search(r"\b(type|direction|volume|price|profit|balance)\b", normalised_value):
            return False
        return True

    @staticmethod
    def _looks_like_metric_label(label: str) -> bool:
        return any(label == MT5Parser._label(known) for known in MT5Parser._known_labels())

    @staticmethod
    def _known_labels() -> List[str]:
        return [
            "Expert",
            "Expert Advisor",
            "Symbol",
            "Period",
            "Initial Deposit",
            "Deposit",
            "Spread",
            "Total Net Profit",
            "Net Profit",
            "Gross Profit",
            "Gross Loss",
            "Profit Factor",
            "Expected Payoff",
            "Balance Drawdown Absolute",
            "Balance Drawdown Maximal",
            "Equity Drawdown Absolute",
            "Equity Drawdown Maximal",
            "Maximal Drawdown",
            "Balance Drawdown Relative",
            "Equity Drawdown Relative",
            "Relative Drawdown",
            "Recovery Factor",
            "Sharpe Ratio",
            "Total Trades",
            "Trades Total",
            "Short Trades (won %)",
            "Short Positions (won %)",
            "Long Trades (won %)",
            "Long Positions (won %)",
            "Profit Trades (% of total)",
            "Profit Trades",
            "Loss Trades (% of total)",
            "Average profit trade",
            "Average Profit Trade",
            "Average loss trade",
            "Average Loss Trade",
            "Maximal consecutive wins",
            "Maximal consecutive losses",
        ]
