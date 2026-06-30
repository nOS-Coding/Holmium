"""Stock & finance tools using yfinance."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yfinance as yf

from tools.registry import register_tool, execute_tool

PORTFOLIO_PATH = Path("/var/holmium/finance/portfolio.json")
VLLM_SOCKET = "/run/holmium/vllm.sock"


def _load_portfolio() -> Dict[str, Any]:
    if not PORTFOLIO_PATH.is_file():
        return {"holdings": []}
    return json.loads(PORTFOLIO_PATH.read_text())


def _save_portfolio(data: Dict[str, Any]) -> None:
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_PATH.write_text(json.dumps(data, indent=2))


def _call_vllm(prompt: str) -> str:
    transport = httpx.HTTPTransport(uds=VLLM_SOCKET)
    payload = {
        "model": "Qwen3.6-35B-A3B-AWQ",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    with httpx.Client(transport=transport, timeout=120) as client:
        resp = client.post("http://localhost/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


@register_tool(
    "stock_price",
    "Get current stock price, change percentage, and volume for a ticker.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. AAPL, THYAO.IS)",
            },
        },
        "required": ["ticker"],
    },
)
def stock_price(ticker: str) -> Dict[str, Any]:
    """Get current price info for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)
        prev_close = info.get("previousClose", price)
        change = price - prev_close if price and prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        volume = info.get("volume") or info.get("regularMarketVolume", 0)
        return {
            "ticker": ticker.upper(),
            "price": round(price, 2) if price else 0,
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "volume": volume,
            "name": info.get("shortName", ticker.upper()),
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}


@register_tool(
    "stock_history",
    "Get historical OHLCV data for a ticker over a given period.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol",
            },
            "period": {
                "type": "string",
                "description": "Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)",
                "default": "1mo",
            },
        },
        "required": ["ticker"],
    },
)
def stock_history(ticker: str, period: str = "1mo") -> List[Dict[str, Any]]:
    """Get OHLCV history for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        records: List[Dict[str, Any]] = []
        for date, row in hist.iterrows():
            records.append({
                "date": str(date.date()),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        return records
    except Exception as e:
        return [{"error": str(e)}]


@register_tool(
    "stock_portfolio_summary",
    "Get the current portfolio summary with per-holding P&L.",
)
def stock_portfolio_summary() -> Dict[str, Any]:
    """Load portfolio.json and compute current value + gain/loss for each holding."""
    portfolio = _load_portfolio()
    holdings = portfolio.get("holdings", [])
    total_value = 0.0
    total_cost = 0.0
    enriched: List[Dict[str, Any]] = []

    for h in holdings:
        ticker = h.get("ticker", "")
        shares = h.get("shares", 0)
        avg_cost = h.get("avg_buy_price", 0)
        try:
            info = stock_price(ticker)
            if "error" in info:
                enriched.append({"ticker": ticker, "error": info["error"]})
                continue
            price = info["price"]
            cost_basis = shares * avg_cost
            current_value = shares * price
            gain_loss = current_value - cost_basis
            gain_loss_pct = ((price - avg_cost) / avg_cost * 100) if avg_cost else 0
            total_value += current_value
            total_cost += cost_basis
            enriched.append({
                "ticker": ticker.upper(),
                "shares": shares,
                "avg_buy_price": round(avg_cost, 2),
                "current_price": price,
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_value, 2),
                "gain_loss": round(gain_loss, 2),
                "gain_loss_pct": round(gain_loss_pct, 2),
            })
        except Exception as e:
            enriched.append({"ticker": ticker, "error": str(e)})

    return {
        "holdings": enriched,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_gain_loss": round(total_value - total_cost, 2),
        "total_gain_loss_pct": round(((total_value - total_cost) / total_cost * 100), 2) if total_cost else 0,
    }


@register_tool(
    "stock_add_holding",
    "Add a holding to the portfolio.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol"},
            "shares": {"type": "number", "description": "Number of shares"},
            "avg_buy_price": {"type": "number", "description": "Average buy price per share"},
        },
        "required": ["ticker", "shares", "avg_buy_price"],
    },
)
def stock_add_holding(ticker: str, shares: float, avg_buy_price: float) -> bool:
    """Add a holding to the portfolio JSON."""
    portfolio = _load_portfolio()
    holdings = portfolio.setdefault("holdings", [])

    for h in holdings:
        if h.get("ticker", "").upper() == ticker.upper():
            existing_shares = h["shares"]
            existing_cost = h["avg_buy_price"]
            total_shares = existing_shares + shares
            h["avg_buy_price"] = round(
                (existing_shares * existing_cost + shares * avg_buy_price) / total_shares, 2
            ) if total_shares else 0
            h["shares"] = total_shares
            _save_portfolio(portfolio)
            return True

    holdings.append({"ticker": ticker.upper(), "shares": shares, "avg_buy_price": avg_buy_price})
    _save_portfolio(portfolio)
    return True


@register_tool(
    "stock_remove_holding",
    "Remove a holding from the portfolio.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol to remove"},
        },
        "required": ["ticker"],
    },
)
def stock_remove_holding(ticker: str) -> bool:
    """Remove a holding from the portfolio by ticker."""
    portfolio = _load_portfolio()
    holdings = portfolio.get("holdings", [])
    portfolio["holdings"] = [h for h in holdings if h.get("ticker", "").upper() != ticker.upper()]
    _save_portfolio(portfolio)
    return True


@register_tool(
    "stock_analyze",
    "Analyze a ticker's recent performance and news via vLLM.",
    params_schema={
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock ticker symbol"},
        },
        "required": ["ticker"],
    },
)
def stock_analyze(ticker: str) -> str:
    """Get 3-month history + news and pass to vLLM for analysis."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        news = stock.news[:5] if hasattr(stock, "news") else []

        summary_lines = [f"=== {ticker.upper()} 3-Month History ==="]
        for date, row in hist.iterrows():
            summary_lines.append(f"{date.date()}: O={row['Open']:.2f} H={row['High']:.2f} L={row['Low']:.2f} C={row['Close']:.2f} V={int(row['Volume'])}")

        if news:
            summary_lines.append("\n=== Recent News ===")
            for item in news:
                summary_lines.append(f"- {item.get('title', '')}")

        prompt = (
            "You are a financial analyst. Analyze the following stock data and provide:\n"
            "1. Price trend and momentum\n"
            "2. Key support/resistance levels\n"
            "3. News sentiment\n"
            "4. Short-term outlook (1-2 weeks)\n"
            f"Keep it concise.\n\n{chr(10).join(summary_lines)}"
        )
        return _call_vllm(prompt)
    except Exception as e:
        return f"Error analyzing {ticker}: {e}"


@register_tool(
    "stock_suggest",
    "Suggest stocks based on risk level — uses top gainers + news.",
    params_schema={
        "type": "object",
        "properties": {
            "risk_level": {
                "type": "string",
                "description": "Risk tolerance: low, medium, or high",
                "enum": ["low", "medium", "high"],
            },
        },
        "required": ["risk_level"],
    },
)
def stock_suggest(risk_level: str) -> List[Dict[str, Any]]:
    """Get top market gainers and news, filter by risk level, return suggestions."""
    suggestions: List[Dict[str, Any]] = []
    try:
        sp500 = yf.Ticker("^GSPC")
        hist = sp500.history(period="5d")
        movers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ"]

        for sym in movers:
            try:
                info = stock_price(sym)
                if "error" not in info:
                    pct = abs(info["change_percent"])
                    if risk_level == "low" and pct < 3:
                        suggestions.append(info)
                    elif risk_level == "medium" and 2 <= pct <= 5:
                        suggestions.append(info)
                    elif risk_level == "high" and pct > 4:
                        suggestions.append(info)
            except Exception:
                continue

        suggestions.sort(key=lambda x: abs(x.get("change_percent", 0)), reverse=True)
        return suggestions[:5]
    except Exception as e:
        return [{"error": str(e)}]
