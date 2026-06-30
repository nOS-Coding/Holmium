"""Portfolio history tracking, markdown reporting, and daily snapshots."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf

from tools.registry import register_tool

DB_PATH = Path("/var/holmium/memory/facts.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT,
            ticker TEXT,
            shares REAL,
            price REAL,
            value REAL,
            gain_loss REAL,
            gain_loss_pct REAL
        )
    """)
    conn.commit()
    return conn


def _take_snapshot() -> None:
    """Daily snapshot: record current holdings and prices."""
    portfolio_path = Path("/var/holmium/finance/portfolio.json")
    if not portfolio_path.is_file():
        return

    portfolio = json.loads(portfolio_path.read_text())
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return

    conn = _get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        for h in holdings:
            ticker = h.get("ticker", "")
            shares = h.get("shares", 0)
            avg_cost = h.get("avg_buy_price", 0)
            try:
                stock = yf.Ticker(ticker)
                price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice", 0)
            except Exception:
                price = avg_cost
            value = shares * price
            gain_loss = value - (shares * avg_cost)
            gain_loss_pct = ((price - avg_cost) / avg_cost * 100) if avg_cost else 0
            conn.execute(
                "INSERT INTO portfolio_snapshots (snapshot_date, ticker, shares, price, value, gain_loss, gain_loss_pct) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (today, ticker, shares, round(price, 2), round(value, 2), round(gain_loss, 2), round(gain_loss_pct, 2)),
            )
        conn.commit()
    finally:
        conn.close()


@register_tool(
    "portfolio_history",
    "Get historical snapshot data for a ticker's portfolio performance.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol",
            },
            "period": {
                "type": "string",
                "description": "Time period filter (1w, 1mo, 3mo, 6mo, 1y, all)",
                "default": "all",
            },
        },
        "required": ["ticker"],
    },
)
def portfolio_history(ticker: str, period: str = "all") -> List[Dict[str, Any]]:
    """Get historical snapshot data for a ticker."""
    conn = _get_connection()
    try:
        query = "SELECT * FROM portfolio_snapshots WHERE ticker = ?"
        params: List[Any] = [ticker.upper()]

        if period and period != "all":
            period_map = {"1w": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
            days = period_map.get(period, 0)
            if days:
                from datetime import timedelta
                cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                query += " AND snapshot_date >= ?"
                params.append(cutoff)

        query += " ORDER BY snapshot_date"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@register_tool(
    "portfolio_report",
    "Generate a markdown portfolio report with P&L and sparklines.",
)
def portfolio_report() -> str:
    """Generate a markdown report of portfolio performance."""
    try:
        _take_snapshot()

        portfolio_path = Path("/var/holmium/finance/portfolio.json")
        if not portfolio_path.is_file():
            return "No portfolio data found."

        portfolio = json.loads(portfolio_path.read_text())
        holdings = portfolio.get("holdings", [])
        if not holdings:
            return "Portfolio is empty."

        conn = _get_connection()
        lines: List[str] = []
        lines.append("# Portfolio Report")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        total_value = 0.0
        total_cost = 0.0

        for h in holdings:
            ticker = h["ticker"]
            shares = h["shares"]
            avg_cost = h["avg_buy_price"]

            try:
                stock = yf.Ticker(ticker)
                price = stock.info.get("currentPrice") or stock.info.get("regularMarketPrice", 0)
            except Exception:
                price = avg_cost

            cost_basis = shares * avg_cost
            current_value = shares * price
            gain_loss = current_value - cost_basis
            gain_loss_pct = ((price - avg_cost) / avg_cost * 100) if avg_cost else 0
            total_value += current_value
            total_cost += cost_basis

            rows = conn.execute(
                "SELECT * FROM portfolio_snapshots WHERE ticker = ? ORDER BY snapshot_date",
                (ticker,),
            ).fetchall()

            arrow = "📈" if gain_loss >= 0 else "📉"
            lines.append(f"## {ticker} {arrow}")
            lines.append(f"- Shares: {shares}")
            lines.append(f"- Avg Cost: ${avg_cost:.2f}")
            lines.append(f"- Current: ${price:.2f}")
            lines.append(f"- Value: ${current_value:.2f}")
            lines.append(f"- P&L: ${gain_loss:+.2f} ({gain_loss_pct:+.2f}%)")

            if rows:
                prices = [r["price"] for r in rows]
                mini = min(prices)
                maxi = max(prices)
            else:
                prices = [price]
                mini = maxi = price

            spark = "".join(
                "▁" if p <= mini else "▇" if p >= maxi else
                "▂" if p <= mini + (maxi - mini) * 0.25 else
                "▄" if p <= mini + (maxi - mini) * 0.5 else
                "▆"
                for p in prices
            )
            lines.append(f"- Trend: {spark}")
            lines.append("")

        total_gain = total_value - total_cost
        total_pct = ((total_value - total_cost) / total_cost * 100) if total_cost else 0
        lines.append("---")
        lines.append(f"**Total**: ${total_value:.2f}")
        lines.append(f"**Total P&L**: ${total_gain:+.2f} ({total_pct:+.2f}%)")

        conn.close()
        return "\n".join(lines)
    except Exception as e:
        return f"Error generating report: {e}"


def snapshot_daily() -> None:
    """Called by the daily scheduler at market close."""
    _take_snapshot()
