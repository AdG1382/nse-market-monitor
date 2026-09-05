"""PNG chart rendering from stored history.

Like analysis.py, this reads only what db.py has already stored — it never
talks to a data provider.

Two things matter for correctness here:

* The Agg backend is selected before pyplot is imported. Any interactive
  backend would try to find a display and fail under a web server.
* Rendering holds a lock. Starlette runs sync endpoints in a threadpool, so
  chart routes can overlap, and pyplot's figure manager is global mutable
  state that corrupts under concurrent use. Figures are closed explicitly;
  leaked ones accumulate until the process runs out of memory.

Charts stay in each instrument's own units — rupees for stocks, points for
indices — so they read the same way as the tables.
"""

import io
import threading
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from config import BENCHMARKS, STOCK_SECTOR  # noqa: E402
from db import price_history, utc_now_iso  # noqa: E402

_RENDER_LOCK = threading.Lock()

POS = "#1a7f37"
NEG = "#c0392b"
LINE = "#1f4e79"
BENCH = "#b07d2b"
GRID = "#dddddd"
TEXT = "#333333"


def _series(symbol: str, days: int):
    """(dates, prices) for a symbol over the trailing `days`."""
    since = (datetime.fromisoformat(utc_now_iso()) - timedelta(days=days)).strftime(
        "%Y-%m-%dT00:00:00"
    )
    rows = price_history(symbol, since)
    dates = [datetime.fromisoformat(r["timestamp"]) for r in rows]
    prices = [r["price"] for r in rows]
    return dates, prices


def _style(ax, title, ylabel):
    ax.set_title(title, fontsize=11, family="monospace", color=TEXT, loc="left")
    ax.set_ylabel(ylabel, fontsize=9, family="monospace", color=TEXT)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.tick_params(labelsize=8, colors=TEXT)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_family("monospace")


def _finish(fig):
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=110, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _empty(message: str):
    fig, ax = plt.subplots(figsize=(7.2, 1.4))
    ax.text(0.5, 0.5, message, ha="center", va="center",
            family="monospace", fontsize=10, color=TEXT)
    ax.axis("off")
    return _finish(fig)


def price_chart(symbol: str, days: int = 365) -> bytes:
    """Closing price over the trailing window."""
    with _RENDER_LOCK:
        dates, prices = _series(symbol, days)
        if len(prices) < 2:
            return _empty(f"Not enough history for {symbol}")

        fig, ax = plt.subplots(figsize=(7.2, 2.8))
        ax.plot(dates, prices, color=LINE, linewidth=1.4)
        # Shade against the window's opening level, so the fill shows
        # ground gained or lost rather than distance from zero.
        ax.fill_between(dates, prices, prices[0], where=[p >= prices[0] for p in prices],
                        color=POS, alpha=0.12, interpolate=True)
        ax.fill_between(dates, prices, prices[0], where=[p < prices[0] for p in prices],
                        color=NEG, alpha=0.12, interpolate=True)
        ax.axhline(prices[0], color=GRID, linewidth=0.9, linestyle="--")

        change = prices[-1] - prices[0]
        _style(ax, f"{symbol}  {prices[-1]:,.2f}  ({change:+,.2f})", "")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        return _finish(fig)


def vs_benchmark_chart(symbol: str, days: int = 365) -> bytes:
    """Actual price against where the benchmark's move would have put it.

    Both lines are in rupees and start from the same point, so the gap
    between them at any date is literally rupees per share of out- or
    under-performance — the same quantity the vs-benchmark tables report.
    """
    with _RENDER_LOCK:
        sector = STOCK_SECTOR.get(symbol)
        bench_key = sector or "nifty50"
        bench_name = BENCHMARKS.get(bench_key, bench_key)

        dates, prices = _series(symbol, days)
        bench_dates, bench_prices = _series(bench_key, days)
        if len(prices) < 2 or len(bench_prices) < 2:
            return _empty(f"Not enough history to compare {symbol}")

        # Align on shared session dates: exchanges keep different holidays.
        bench_by_date = dict(zip(bench_dates, bench_prices))
        pairs = [(d, p, bench_by_date[d]) for d, p in zip(dates, prices) if d in bench_by_date]
        if len(pairs) < 2:
            return _empty(f"No overlapping sessions for {symbol}")

        dates = [d for d, _, _ in pairs]
        prices = [p for _, p, _ in pairs]
        base_price, base_bench = prices[0], pairs[0][2]
        implied = [base_price * (b / base_bench) for _, _, b in pairs]

        fig, ax = plt.subplots(figsize=(7.2, 2.8))
        ax.plot(dates, prices, color=LINE, linewidth=1.4, label=symbol)
        ax.plot(dates, implied, color=BENCH, linewidth=1.2, linestyle="--",
                label=f"tracking {bench_name}")
        ahead = [p >= i for p, i in zip(prices, implied)]
        ax.fill_between(dates, prices, implied, where=ahead, color=POS, alpha=0.12, interpolate=True)
        ax.fill_between(dates, prices, implied, where=[not a for a in ahead],
                        color=NEG, alpha=0.12, interpolate=True)

        gap = prices[-1] - implied[-1]
        _style(ax, f"{symbol} vs {bench_name}  ({gap:+,.2f} per share)", "")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.legend(fontsize=8, frameon=False, prop={"family": "monospace"})
        return _finish(fig)


def change_chart(rows: list[dict], window: str = "1D", unit: str = "") -> bytes:
    """Horizontal bars of each symbol's change for one window.

    Only sound for instruments sharing a unit — the caller passes a single
    group (the rupee-denominated stocks), never stocks mixed with indices.
    """
    with _RENDER_LOCK:
        data = [(r["symbol"], r.get(f"{window}_abs")) for r in rows]
        data = [(s, v) for s, v in data if v is not None]
        if not data:
            return _empty("No data yet")

        data.reverse()  # barh draws bottom-up; keep the table's order.
        symbols = [s for s, _ in data]
        values = [v for _, v in data]

        fig, ax = plt.subplots(figsize=(7.2, 0.45 * len(data) + 1.2))
        ax.barh(symbols, values, color=[POS if v >= 0 else NEG for v in values], height=0.6)
        ax.axvline(0, color=TEXT, linewidth=0.9)

        span = max(abs(v) for v in values) or 1
        for y, v in enumerate(values):
            offset = span * 0.02
            ax.text(v + (offset if v >= 0 else -offset), y, f"{v:+,.2f}",
                    va="center", ha="left" if v >= 0 else "right",
                    fontsize=8, family="monospace", color=TEXT)
        ax.set_xlim(min(0, min(values)) - span * 0.25, max(0, max(values)) + span * 0.25)

        _style(ax, f"{window} change{unit}", "")
        ax.grid(axis="y", visible=False)
        return _finish(fig)
