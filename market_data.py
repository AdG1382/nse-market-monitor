"""Data collector: pulls daily bars from yfinance and normalizes them into
MarketSnapshot objects. Nothing outside this module should ever touch a
raw yfinance object.

NSE's own site (and nsepython, which scrapes it) blocks most cloud /
datacenter IPs at the edge (Akamai WAF), which makes it unreliable for a
server-hosted app. yfinance covers NSE stocks (".NS" suffix) and indices
("^NSEI" etc.) as well as global instruments, so it's used as the single
unified provider for V1.

Each stored row is one *trading session*, not one poll. A session is keyed
by its local exchange date at midnight (e.g. "2026-09-04T00:00:00"), which
means collecting four times a day writes the same row four times over
rather than four near-identical rows an hour apart. analysis.py depends on
that: its return windows step back N calendar days and look for the session
on or before the cutoff, which only resolves if the table holds real daily
history rather than however long the app happens to have been running.
"""

from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import yfinance as yf

from config import (
    BENCHMARK_CATALOG,
    HISTORY_PERIOD,
)
from db import MarketSnapshot, get_user_stocks, get_user_benchmarks, get_highlighted_benchmark

import nsepython
import requests
from typing import Optional

# Enough sessions to cover a routine top-up (including a long weekend or a
# stretch of holidays) without refetching years of history every run.
RECENT_PERIOD = "1mo"


def _session_ts(bar_index) -> str:
    """Canonical timestamp for a daily bar: its local exchange date at
    midnight, as a naive ISO string.
    """
    return bar_index.strftime("%Y-%m-%dT00:00:00")


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _fetch_from_nsepython(symbol: str, asset_type: str, market: str) -> Optional[MarketSnapshot]:
    """Attempt live fetch using open-source nsepython library."""
    if market != "NSE":
        return None
    try:
        if asset_type == "index":
            quote = nsepython.nse_get_index_quote(symbol)
            if isinstance(quote, dict) and "lastPrice" in quote:
                price = float(quote["lastPrice"])
                prev = float(quote.get("previousClose", price))
                return MarketSnapshot(
                    symbol=symbol,
                    asset_type=asset_type,
                    market=market,
                    price=price,
                    previous_close=prev,
                    source="nsepython",
                )
        else:
            ltp = nsepython.nse_quote_ltp(symbol)
            if isinstance(ltp, (int, float)) and ltp > 0:
                return MarketSnapshot(
                    symbol=symbol,
                    asset_type=asset_type,
                    market=market,
                    price=float(ltp),
                    source="nsepython",
                )
    except Exception as exc:
        pass
    return None


def _fetch_from_nse_public(symbol: str, asset_type: str, market: str) -> Optional[MarketSnapshot]:
    """Attempt live fetch via direct public exchange endpoint."""
    if market != "NSE":
        return None
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        session.get("https://www.nseindia.com", timeout=3)
        if asset_type == "index":
            resp = session.get("https://www.nseindia.com/api/allIndices", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                for idx in data.get("data", []):
                    idx_name = idx.get("indexSymbol") or idx.get("index")
                    if idx_name and idx_name.upper() in (symbol.upper(), symbol.replace(" ", "").upper()):
                        price = float(idx["last"])
                        prev = float(idx.get("previousClose", price))
                        return MarketSnapshot(
                            symbol=symbol,
                            asset_type=asset_type,
                            market=market,
                            price=price,
                            previous_close=prev,
                            source="nse_public",
                        )
        else:
            resp = session.get(f"https://www.nseindia.com/api/quote-equity?symbol={symbol}", timeout=3)
            if resp.status_code == 200:
                pinfo = resp.json().get("priceInfo", {})
                price = float(pinfo.get("lastPrice", 0))
                if price > 0:
                    return MarketSnapshot(
                        symbol=symbol,
                        asset_type=asset_type,
                        market=market,
                        price=price,
                        open=_to_float(pinfo.get("open")),
                        high=_to_float(pinfo.get("intraDayHighLow", {}).get("max")),
                        low=_to_float(pinfo.get("intraDayHighLow", {}).get("min")),
                        previous_close=_to_float(pinfo.get("previousClose")),
                        source="nse_public",
                    )
    except Exception as exc:
        pass
    return None


def _history_snapshots(
    symbol: str, ticker: str, asset_type: str, market: str, period: str
) -> list[MarketSnapshot]:
    """Fetches daily history with multi-provider strategy (nsepython -> nse_public -> yfinance)."""
    snaps = []

    # Attempt live fetch via open-source nsepython first
    live_snap = _fetch_from_nsepython(symbol, asset_type, market)
    if not live_snap:
        # Fallback to direct NSE public provider
        live_snap = _fetch_from_nse_public(symbol, asset_type, market)

    # Fetch daily history series via yfinance provider
    yf_snaps = []
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if not hist.empty:
            hist.columns = [str(c).capitalize() for c in hist.columns]
            prev_close = None
            for bar_index, row in hist.iterrows():
                close = _to_float(row.get("Close"))
                if close is None:
                    continue
                yf_snaps.append(
                    MarketSnapshot(
                        symbol=symbol,
                        asset_type=asset_type,
                        market=market,
                        price=close,
                        open=_to_float(row.get("Open")),
                        high=_to_float(row.get("High")),
                        low=_to_float(row.get("Low")),
                        previous_close=prev_close,
                        volume=_to_float(row.get("Volume")) or 0.0,
                        source="yfinance",
                        timestamp=_session_ts(bar_index),
                    )
                )
                prev_close = close
    except Exception as exc:
        print(f"[market_data] yfinance fetch failed for {symbol} ({ticker}): {exc}")

    if yf_snaps:
        snaps.extend(yf_snaps)

    # If live_snap obtained from nsepython or nse_public, append or overwrite the latest bar with provider info
    if live_snap:
        if snaps and snaps[-1].timestamp == live_snap.timestamp:
            snaps[-1] = live_snap
        elif not snaps or snaps[-1].timestamp < live_snap.timestamp:
            snaps.append(live_snap)

    return snaps


def _instruments() -> list[tuple[str, str, str, str]]:
    """(symbol, ticker, asset_type, market) for active stocks & benchmarks."""
    instruments = []

    # User stocks
    for s in get_user_stocks():
        # NSE stocks use .NS ticker suffix unless ticker specified
        ticker = f"{s}.NS" if not s.endswith(".NS") and not s.startswith("^") else s
        instruments.append((s, ticker, "stock", "NSE"))

    # Active benchmarks (including highlighted benchmark)
    active_b = list(get_user_benchmarks())
    hb = get_highlighted_benchmark()
    if hb and hb not in active_b:
        active_b.append(hb)

    for b_key in active_b:
        if b_key in BENCHMARK_CATALOG:
            b_info = BENCHMARK_CATALOG[b_key]
            instruments.append((b_key, b_info["ticker"], b_info["category"], b_info["market"]))
        else:
            # Fallback for custom benchmark key
            instruments.append((b_key, b_key, "index", "GLOBAL"))

    return instruments


def fetch_all_snapshots(period: str = RECENT_PERIOD) -> list[MarketSnapshot]:
    """Daily bars for every tracked instrument in parallel.

    Defaults to a short window; pass HISTORY_PERIOD to backfill.
    """
    instruments = _instruments()
    if not instruments:
        return []

    snaps = []

    def _fetch_one(item):
        symbol, ticker, asset_type, market = item
        return _history_snapshots(symbol, ticker, asset_type, market, period)

    with ThreadPoolExecutor(max_workers=min(len(instruments), 8)) as executor:
        results = executor.map(_fetch_one, instruments)
        for res in results:
            snaps.extend(res)

    return snaps


def fetch_full_history() -> list[MarketSnapshot]:
    """Backfill: enough history for the longest return window to resolve."""
    return fetch_all_snapshots(period=HISTORY_PERIOD)

