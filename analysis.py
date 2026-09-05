"""Return calculations and relative-performance comparisons.

Operates purely on data already stored in SQLite via db.py — never talks
to a data provider directly.

Each window is reported three ways, because they serve different jobs:

    "1M"        percent change
    "1M_abs"    change in the instrument's own units (rupees, index points)
    "1M_from"   the price the window started at

The dashboard displays the absolute change. Percent is kept because it is
the only sound basis for *comparing* instruments: ranking by absolute change
would just rank by price magnitude, putting the Nikkei at 65,000 permanently
above a 2,300-rupee stock no matter how either one actually moved.
"""

from datetime import datetime, timedelta
from typing import Optional

from config import RETURN_WINDOWS, STOCK_SECTOR
from db import latest_snapshot, snapshot_before


def pct_return(current: float, past: float) -> Optional[float]:
    if current is None or past is None or past == 0:
        return None
    return (current / past - 1) * 100


def abs_change(current: float, past: float) -> Optional[float]:
    """Change in the instrument's own units."""
    if current is None or past is None:
        return None
    return current - past


def returns_for_symbol(symbol: str) -> dict:
    """Compute per-window change for a symbol using stored history."""
    latest = latest_snapshot(symbol)
    if latest is None:
        return {}

    now = datetime.fromisoformat(latest["timestamp"])
    price = latest["price"]
    result = {"symbol": symbol, "price": price, "timestamp": latest["timestamp"]}

    for label, days in RETURN_WINDOWS:
        cutoff = (now - timedelta(days=days)).isoformat()
        past = snapshot_before(symbol, cutoff)
        past_price = past["price"] if past else None
        result[label] = pct_return(price, past_price)
        result[f"{label}_abs"] = abs_change(price, past_price)
        result[f"{label}_from"] = past_price

    return result


def relative_returns(stock_returns: dict, benchmark_returns: dict) -> dict:
    """Stock return minus benchmark return, in percentage points, per window."""
    rel = {}
    for label, _ in RETURN_WINDOWS:
        s = stock_returns.get(label)
        b = benchmark_returns.get(label)
        rel[label] = (s - b) if (s is not None and b is not None) else None
    return rel


def relative_change(stock_returns: dict, benchmark_returns: dict) -> dict:
    """Out/under-performance vs a benchmark, in the stock's own units.

    Percentage points can't be expressed as a plain number across two
    instruments — rupees minus index points is meaningless. What *is*
    meaningful is the gap against where the stock would have ended up had it
    tracked the benchmark: start from the window's opening price, apply the
    benchmark's percent move, and compare against the actual price. The
    result is "you are N rupees per share ahead of where the index would
    have put you".
    """
    rel = {}
    for label, _ in RETURN_WINDOWS:
        past = stock_returns.get(f"{label}_from")
        change = stock_returns.get(f"{label}_abs")
        bench_pct = benchmark_returns.get(label)
        if past is None or change is None or bench_pct is None:
            rel[label] = None
            continue
        rel[label] = change - past * bench_pct / 100
    return rel


def stock_comparison(symbol: str) -> dict:
    """Full comparison of a stock vs NIFTY 50 and (if configured) its sector index."""
    stock_ret = returns_for_symbol(symbol)
    nifty_ret = returns_for_symbol("nifty50")

    comparison = {
        "symbol": symbol,
        "returns": stock_ret,
        "vs_nifty50": relative_change(stock_ret, nifty_ret),
        "vs_nifty50_pct": relative_returns(stock_ret, nifty_ret),
    }

    sector_key = STOCK_SECTOR.get(symbol)
    if sector_key:
        sector_ret = returns_for_symbol(sector_key)
        comparison[f"vs_{sector_key}"] = relative_change(stock_ret, sector_ret)
        comparison[f"vs_{sector_key}_pct"] = relative_returns(stock_ret, sector_ret)

    return comparison


def rank_by_return(symbols: list[str], window: str = "1D") -> list[dict]:
    """Rank symbols by *percent* return over a window, descending.

    Percent, not absolute change: a ranking by absolute change would only
    reflect which instrument carries the bigger price tag.
    """
    rows = [returns_for_symbol(s) for s in symbols]
    rows = [r for r in rows if r.get(window) is not None]
    return sorted(rows, key=lambda r: r[window], reverse=True)
