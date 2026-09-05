"""Builds structured report data. Rendering (FastHTML, etc.) is separate."""

from config import BENCHMARK_CATALOG
from analysis import returns_for_symbol, stock_comparison, rank_by_return
from db import save_report, utc_now_iso, get_user_stocks, get_user_benchmarks


def build_report(report_type: str) -> dict:
    stocks = get_user_stocks()
    benchmarks = get_user_benchmarks()

    global_benchmarks = [b for b in benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "global"]
    india_benchmarks = [b for b in benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "india" or b not in BENCHMARK_CATALOG]

    global_section = [
        {"key": key, **returns_for_symbol(key)} for key in global_benchmarks
    ]
    india_section = [
        {"key": key, **returns_for_symbol(key)} for key in india_benchmarks
    ]
    stocks_section = [stock_comparison(sym) for sym in stocks]

    top_movers = rank_by_return(stocks, window="1D")
    highlights = _build_highlights(stocks_section, top_movers)

    report = {
        "type": report_type,
        "timestamp": utc_now_iso(),
        "global": global_section,
        "india": india_section,
        "stocks": stocks_section,
        "highlights": highlights,
    }

    save_report(report_type, report)
    return report



def _build_highlights(stocks_section: list[dict], top_movers: list[dict]) -> list[str]:
    highlights = []
    if top_movers:
        best = top_movers[0]
        worst = top_movers[-1]
        if best.get("1D_abs") is not None:
            highlights.append(
                f"Best 1D mover: {best['symbol']} "
                f"({best['1D_from']:,.2f} to {best['price']:,.2f}, {best['1D_abs']:+,.2f})"
            )
        if worst.get("1D_abs") is not None and worst["symbol"] != best.get("symbol"):
            highlights.append(
                f"Worst 1D mover: {worst['symbol']} "
                f"({worst['1D_from']:,.2f} to {worst['price']:,.2f}, {worst['1D_abs']:+,.2f})"
            )

    for s in stocks_section:
        # Thresholded on percent so the bar means the same thing for a
        # 700-rupee stock and a 2,300-rupee one; reported as rupees.
        vs_pct = s.get("vs_nifty50_pct", {}).get("1M")
        vs_abs = s.get("vs_nifty50", {}).get("1M")
        if vs_pct is not None and vs_abs is not None and abs(vs_pct) >= 3:
            direction = "outperforming" if vs_abs > 0 else "underperforming"
            highlights.append(
                f"{s['symbol']} is {direction} NIFTY 50 by "
                f"{abs(vs_abs):,.2f} per share over 1M"
            )

    return highlights
