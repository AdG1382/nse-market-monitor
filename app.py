"""FastHTML dashboard for Market Monitor."""

import os
import threading

from fasthtml.common import *

from config import STOCK_CATALOG, STOCK_SECTORS, BENCHMARK_CATALOG, RETURN_WINDOWS, REPORT_SCHEDULE
from db import (
    init_db,
    save_snapshots,
    snapshot_count,
    latest_report,
    get_user_stocks,
    save_user_stocks,
    add_user_stock,
    remove_user_stock,
    get_user_benchmarks,
    save_user_benchmarks,
    get_highlighted_benchmark,
    set_highlighted_benchmark,
)
from market_data import fetch_all_snapshots, fetch_full_history
from analysis import returns_for_symbol, stock_comparison
from charts import price_chart, vs_benchmark_chart, change_chart
from scheduler import start_scheduler
from exporter import export_to_csv, export_to_excel

app, rt = fast_app()

init_db()


def _backfill_if_empty():
    """Populate history on boot if database is empty."""
    stocks = get_user_stocks()
    check_sym = stocks[0] if stocks else "nifty50"
    if snapshot_count(check_sym) > 0:
        return

    def run():
        print("[app] empty database, backfilling history")
        snaps = fetch_full_history()
        save_snapshots(snaps)
        print(f"[app] backfill complete ({len(snaps)} sessions)")

    threading.Thread(target=run, daemon=True).start()


_backfill_if_empty()
scheduler = start_scheduler()


def fmt_change(value):
    """A window's change in absolute units (rupees, index points)."""
    if value is None:
        return "-"
    cls = "pos" if value >= 0 else "neg"
    return Span(f"{value:+,.2f}", cls=cls)


def fmt_price(value):
    return f"{value:,.2f}" if isinstance(value, (int, float)) else "-"


def fmt_window_cell(r: dict, label: str):
    """Renders Historical Start Price, Absolute Change (±), and Percent Return (%) for a window."""
    from_p = r.get(f"{label}_from")
    abs_v = r.get(f"{label}_abs")
    pct_v = r.get(label)

    if from_p is None and abs_v is None and pct_v is None:
        return "-"

    children = []
    if from_p is not None:
        children.append(Div(f"₹{from_p:,.2f}", cls="val-from"))

    metrics = []
    if abs_v is not None:
        cls = "pos" if abs_v >= 0 else "neg"
        metrics.append(Span(f"{abs_v:+,.2f}", cls=f"val-abs {cls}"))

    if pct_v is not None:
        cls = "pos" if pct_v >= 0 else "neg"
        metrics.append(Span(f" ({pct_v:+.2f}%)", cls=f"val-pct {cls}"))

    if metrics:
        children.append(Div(*metrics, cls="val-metrics"))

    return Div(*children, cls="cell-container")


def png(data: bytes):
    return Response(
        data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


def chart_img(src, alt):
    return Img(src=src, alt=alt, cls="chart")


def section_title(text, action_button=None, source_badge=None):
    title_children = [H2(text, cls="section-title-text")]
    if source_badge:
        title_children.append(Span(source_badge, cls="source-badge"))
    left_side = Div(*title_children, cls="section-title-wrapper")
    if action_button:
        return Div(left_side, action_button, cls="section-header")
    return Div(left_side, cls="section-header")


def page(title, *content):
    font_links = (
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    )
    toggle_script = Script("""
    function updateExportUrls() {
        const showFrom = document.getElementById('chk-from')?.checked !== false;
        const showAbs = document.getElementById('chk-abs')?.checked !== false;
        const showPct = document.getElementById('chk-pct')?.checked !== false;
        const params = `show_from=${showFrom}&show_abs=${showAbs}&show_pct=${showPct}`;
        const csvBtn = document.getElementById('btn-export-csv');
        const xlsBtn = document.getElementById('btn-export-excel');
        if (csvBtn) csvBtn.href = `/export/csv?${params}`;
        if (xlsBtn) xlsBtn.href = `/export/excel?${params}`;
    }
    function toggleMetric(cls, show) {
        const elements = document.getElementsByClassName(cls);
        for (let i = 0; i < elements.length; i++) {
            elements[i].style.display = show ? '' : 'none';
        }
        updateExportUrls();
    }
    """)
    return Titled(title, *font_links, Style(CSS), toggle_script, *content)


def _as_of(rows):
    """Session date the displayed numbers belong to."""
    stamps = [r["timestamp"] for r in rows if r and r.get("timestamp")]
    return max(stamps)[:10] if stamps else None


@rt("/")
def index():
    user_stocks = get_user_stocks()
    user_benchmarks = get_user_benchmarks()
    hb_key = get_highlighted_benchmark()

    global_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "global"]
    india_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "india" or b not in BENCHMARK_CATALOG]

    global_rows = [r for r in (returns_for_symbol(k) for k in global_keys) if r]
    india_rows = [r for r in (returns_for_symbol(k) for k in india_keys) if r]

    # Prepend highlighted benchmark (Row #1) to Selected Stocks table
    stock_rows = []
    hb_row = returns_for_symbol(hb_key) if hb_key else None
    if hb_row:
        hb_name = BENCHMARK_CATALOG.get(hb_key, {}).get("name", hb_key.upper())
        hb_row_copy = dict(hb_row)
        hb_row_copy["display_name"] = hb_name
        hb_row_copy["is_highlighted"] = True
        stock_rows.append(hb_row_copy)

    stock_rows.extend([r for r in (returns_for_symbol(s) for s in user_stocks) if r])

    name_map = {k: v["name"] for k, v in BENCHMARK_CATALOG.items()}

    def simple_table(rows):
        return Div(
            Table(
                Thead(Tr(Th("Symbol / Benchmark"), Th("Level"), *[Th(label, cls="col-win") for label, _ in RETURN_WINDOWS])),
                Tbody(*[
                    Tr(
                        Td(name_map.get(r["symbol"], r["symbol"]), cls="font-medium sticky-col"),
                        Td(fmt_price(r.get("price")), cls="num-cell"),
                        *[Td(fmt_window_cell(r, label)) for label, _ in RETURN_WINDOWS],
                    )
                    for r in rows
                ]),
                cls="data-table"
            ),
            cls="table-container"
        )

    def stock_table(rows):
        return Div(
            Table(
                Thead(Tr(Th("Stock Symbol / Benchmark"), Th("Price (₹)"), *[Th(label, cls="col-win") for label, _ in RETURN_WINDOWS])),
                Tbody(*[
                    Tr(
                        Td(
                            Span(r.get("display_name", r["symbol"]), cls="font-semibold") if r.get("is_highlighted") else A(r["symbol"], href=f"/stock/{r['symbol']}", cls="stock-link"),
                            cls="sticky-col"
                        ),
                        Td(fmt_price(r.get("price")), cls="num-cell"),
                        *[Td(fmt_window_cell(r, label)) for label, _ in RETURN_WINDOWS],
                        cls="highlighted-row" if r.get("is_highlighted") else None
                    )
                    for r in rows
                ]),
                cls="data-table"
            ),
            cls="table-container"
        )


    as_of = _as_of(global_rows + india_rows + stock_rows)
    header_info = Div(
        Div(
            H1("National Stock Monitor & Benchmarks", cls="dashboard-header-title"),
            Div(
                Span(cls="status-dot"),
                Span(f"Session As Of: {as_of}" if as_of else "No data collected yet", cls="status-text"),
                Span(" • Runs at 9 AM, 12 PM, 3 PM, 9 PM IST", cls="schedule-text"),
                cls="status-banner"
            ),
            cls="header-title-group"
        ),
        P("Source Providers: Yahoo Finance API (yfinance), Stooq, Public Exchange Feeds • Markets: NSE India (.NS), BSE India (.BO), US (S&P 500, NASDAQ), Japan (Nikkei 225), Singapore (STI), Commodities (Gold, Crude Oil), Treasury Bonds (US 10Y Yield), Crypto (Bitcoin)", cls="muted-source"),
        cls="header-card"
    )

    action_bar = Div(
        Form(Button("🔄 Collect Data Now", cls="btn btn-primary"), hx_post="/collect", hx_target="body"),
        A("⚙️ Select Stocks", href="/modal/stocks", cls="btn btn-secondary"),
        A("📊 Select Benchmarks", href="/modal/benchmarks", cls="btn btn-secondary"),
        A("📥 Export CSV", href="/export/csv?show_from=true&show_abs=true&show_pct=true", id="btn-export-csv", cls="btn btn-outline"),
        A("📥 Export Excel", href="/export/excel?show_from=true&show_abs=true&show_pct=true", id="btn-export-excel", cls="btn btn-outline"),
        cls="action-bar",
    )

    view_toggle_bar = Div(
        Span("VIEW METRICS:", cls="toggle-title"),
        Label(Input(type="checkbox", id="chk-from", checked=True, onclick="toggleMetric('val-from', this.checked)", cls="toggle-input"), Span(" Historical Base Price"), cls="toggle-pill"),
        Label(Input(type="checkbox", id="chk-abs", checked=True, onclick="toggleMetric('val-abs', this.checked)", cls="toggle-input"), Span(" Absolute Change (±)"), cls="toggle-pill"),
        Label(Input(type="checkbox", id="chk-pct", checked=True, onclick="toggleMetric('val-pct', this.checked)", cls="toggle-input"), Span(" Percent Return (%)"), cls="toggle-pill"),
        cls="view-toggle-bar"
    )

    return page(
        "National Stock Monitor & Benchmarks",
        header_info,
        action_bar,
        view_toggle_bar,
        Div(
            section_title("Selected Stocks", A("+ Add / Edit Stocks", href="/modal/stocks", cls="btn-sm"), source_badge="NSE India via yfinance (.NS)"),
            stock_table(stock_rows) if stock_rows else P("No stocks selected. Click 'Select Stocks' above.", cls="muted-box"),
            cls="card"
        ),
        Div(
            section_title("India Benchmarks", A("Edit Benchmarks", href="/modal/benchmarks", cls="btn-sm"), source_badge="NSE & BSE Indices (^NSEI, ^BSESN, ^NSEBANK, ^CNXIT)"),
            simple_table(india_rows) if india_rows else P("No India benchmarks selected.", cls="muted-box"),
            cls="card"
        ),
        Div(
            section_title("Global & Commodity Benchmarks", A("Edit Benchmarks", href="/modal/benchmarks", cls="btn-sm"), source_badge="S&P 500, NASDAQ, Nikkei, STI, Gold, Oil, Bonds, Crypto"),
            simple_table(global_rows) if global_rows else P("No Global benchmarks selected.", cls="muted-box"),
            cls="card"
        ),
        P(A("View Generated Scheduled Reports →", href="/reports"), cls="nav-link"),
    )


@rt("/collect", methods=["POST"])
def collect():
    snaps = fetch_all_snapshots()
    save_snapshots(snaps)
    return index()


# --- Modals / Settings Routes ---

@rt("/modal/stocks")
def stocks_modal():
    user_stocks = get_user_stocks()
    catalog_symbols = [item["symbol"] for item in STOCK_CATALOG]

    sector_sections = []
    for sector_name, items in STOCK_SECTORS.items():
        checkboxes = []
        for item in items:
            sym = item["symbol"]
            is_checked = sym in user_stocks
            checkboxes.append(
                Label(
                    Input(type="checkbox", name="stocks", value=sym, checked=is_checked),
                    Span(f" {sym} - {item['name']}"),
                    cls="checkbox-label"
                )
            )
        sector_sections.extend([
            H4(sector_name),
            Div(*checkboxes, cls="checkbox-grid"),
            Hr(),
        ])

    custom_stocks = [s for s in user_stocks if s not in catalog_symbols]
    custom_list = ", ".join(custom_stocks) if custom_stocks else "None"

    form = Form(
        H3("Stock Addition & Selection Modal (Top 200 NSE Stocks)"),
        P("Select Top 200 NSE equities grouped by sector categories, or add custom tickers below:", cls="muted"),
        *sector_sections,
        H4("Add Custom NSE Symbol"),
        P("Enter ticker symbol (e.g. WIPRO, TATAMOTORS, LT):", cls="muted"),
        Input(type="text", name="custom_symbol", placeholder="e.g. WIPRO", cls="input-text"),
        P(f"Current custom stocks: {custom_list}", cls="muted-sub"),
        Hr(),
        Div(
            Button("Save Stock List", type="submit", cls="btn btn-primary"),
            A("Cancel", href="/", cls="btn btn-secondary"),
            cls="action-bar"
        ),
        action="/modal/stocks/save",
        method="POST",
    )

    return page("Select Stocks", Div(form, cls="card modal-card"))


@rt("/modal/stocks/save", methods=["POST"])
def save_stocks_route(stocks: list[str] = None, custom_symbol: str = ""):
    selected = stocks if stocks is not None else []
    if isinstance(selected, str):
        selected = [selected]

    if custom_symbol and custom_symbol.strip():
        new_sym = custom_symbol.strip().upper()
        if new_sym not in selected:
            selected.append(new_sym)

    save_user_stocks(selected)
    
    snaps = fetch_all_snapshots()
    save_snapshots(snaps)
    return index()


@rt("/modal/benchmarks")
def benchmarks_modal():
    user_benchmarks = get_user_benchmarks()
    hb_key = get_highlighted_benchmark()

    india_items = []
    global_items = []
    hb_items = []

    for key, info in BENCHMARK_CATALOG.items():
        is_checked = key in user_benchmarks
        cb = Label(
            Input(type="checkbox", name="benchmarks", value=key, checked=is_checked),
            Span(f" {info['name']} ({info['market']})"),
            cls="checkbox-label"
        )
        if info["category"] == "india":
            india_items.append(cb)
        else:
            global_items.append(cb)

        is_hb = (key == hb_key)
        rb = Label(
            Input(type="radio", name="highlighted_benchmark", value=key, checked=is_hb),
            Span(f" {info['name']} ({info['market']})"),
            cls="radio-label"
        )
        hb_items.append(rb)

    form = Form(
        H3("Benchmark Selection Modal"),
        P("Configure active benchmarks and set the highlighted benchmark featured at Row #1 of Selected Stocks:", cls="muted"),
        H4("Highlighted Benchmark (Row #1 in Selected Stocks Table)"),
        P("Select which benchmark is featured at the very top of the Selected Stocks table (e.g. NIFTY 50 / NSE Index):", cls="muted-sub"),
        Div(*hb_items, cls="checkbox-grid"),
        Hr(),
        H4("India Benchmarks"),
        Div(*india_items, cls="checkbox-grid"),
        Hr(),
        H4("Global & Commodity Benchmarks"),
        Div(*global_items, cls="checkbox-grid"),
        Hr(),
        Div(
            Button("Save Benchmarks", type="submit", cls="btn btn-primary"),
            A("Cancel", href="/", cls="btn btn-secondary"),
            cls="action-bar"
        ),
        action="/modal/benchmarks/save",
        method="POST",
    )

    return page("Select Benchmarks", Div(form, cls="card modal-card"))


@rt("/modal/benchmarks/save", methods=["POST"])
def save_benchmarks_route(benchmarks: list[str] = None, highlighted_benchmark: str = "nifty50"):
    selected = benchmarks if benchmarks is not None else []
    if isinstance(selected, str):
        selected = [selected]

    save_user_benchmarks(selected)
    set_highlighted_benchmark(highlighted_benchmark)
    
    snaps = fetch_all_snapshots()
    save_snapshots(snaps)
    return index()


# --- Export Routes ---

@rt("/export/csv")
def export_csv_route(show_from: str = "true", show_abs: str = "true", show_pct: str = "true"):
    s_from = show_from.lower() in ("true", "1", "yes")
    s_abs = show_abs.lower() in ("true", "1", "yes")
    s_pct = show_pct.lower() in ("true", "1", "yes")

    user_stocks = get_user_stocks()
    user_benchmarks = get_user_benchmarks()
    hb_key = get_highlighted_benchmark()

    global_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "global"]
    india_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "india" or b not in BENCHMARK_CATALOG]

    name_map = {k: v["name"] for k, v in BENCHMARK_CATALOG.items()}

    export_stock_rows = []
    hb_row = returns_for_symbol(hb_key) if hb_key else None
    if hb_row:
        hb_name = BENCHMARK_CATALOG.get(hb_key, {}).get("name", hb_key.upper())
        hb_row_copy = dict(hb_row)
        hb_row_copy["display_name"] = hb_name
        hb_row_copy["is_highlighted"] = True
        export_stock_rows.append(hb_row_copy)
    export_stock_rows.extend([r for r in (returns_for_symbol(s) for s in user_stocks) if r])

    sections = {
        "Selected Stocks": (export_stock_rows, None),
        "India Benchmarks": ([returns_for_symbol(k) for k in india_keys if returns_for_symbol(k)], name_map),
        "Global & Commodities": ([returns_for_symbol(k) for k in global_keys if returns_for_symbol(k)], name_map),
    }

    csv_data = export_to_csv(sections, show_from=s_from, show_abs=s_abs, show_pct=s_pct)
    return Response(
        csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=market_monitor_export.csv"}
    )


@rt("/export/excel")
def export_excel_route(show_from: str = "true", show_abs: str = "true", show_pct: str = "true"):
    s_from = show_from.lower() in ("true", "1", "yes")
    s_abs = show_abs.lower() in ("true", "1", "yes")
    s_pct = show_pct.lower() in ("true", "1", "yes")

    user_stocks = get_user_stocks()
    user_benchmarks = get_user_benchmarks()
    hb_key = get_highlighted_benchmark()

    global_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "global"]
    india_keys = [b for b in user_benchmarks if BENCHMARK_CATALOG.get(b, {}).get("category") == "india" or b not in BENCHMARK_CATALOG]

    name_map = {k: v["name"] for k, v in BENCHMARK_CATALOG.items()}

    export_stock_rows = []
    hb_row = returns_for_symbol(hb_key) if hb_key else None
    if hb_row:
        hb_name = BENCHMARK_CATALOG.get(hb_key, {}).get("name", hb_key.upper())
        hb_row_copy = dict(hb_row)
        hb_row_copy["display_name"] = hb_name
        hb_row_copy["is_highlighted"] = True
        export_stock_rows.append(hb_row_copy)
    export_stock_rows.extend([r for r in (returns_for_symbol(s) for s in user_stocks) if r])

    sections = {
        "Stocks": (export_stock_rows, None),
        "India Benchmarks": ([returns_for_symbol(k) for k in india_keys if returns_for_symbol(k)], name_map),
        "Global Benchmarks": ([returns_for_symbol(k) for k in global_keys if returns_for_symbol(k)], name_map),
    }

    excel_data = export_to_excel(sections, show_from=s_from, show_abs=s_abs, show_pct=s_pct)
    return Response(
        excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=market_monitor_export.xlsx"}
    )


# --- Detail & Chart Routes ---

@rt("/stock/{symbol}")
def stock_detail(symbol: str):
    user_stocks = get_user_stocks()
    if symbol not in user_stocks:
        return Response(
            to_xml(page("Unknown symbol", P(f"{symbol} is not currently tracked."), A("← Back", href="/"))),
            status_code=404,
            media_type="text/html",
        )

    comp = stock_comparison(symbol)
    ret = comp["returns"]

    def return_table(title, data, suffix="", note=None):
        return Div(
            H3(title),
            P(note, cls="muted") if note else "",
            Table(
                Tbody(*[
                    Tr(Td(label), Td(fmt_change(data.get(f"{label}{suffix}"))))
                    for label, _ in RETURN_WINDOWS
                ])
            ),
            cls="card"
        )

    excess = "Rupees per share ahead of / behind benchmark target."
    sections = [
        chart_img(f"/chart/price/{symbol}", f"{symbol} closing price, past year"),
        return_table(f"{symbol} change (₹)", ret, suffix="_abs"),
        chart_img(f"/chart/vs/{symbol}", f"{symbol} against benchmark"),
        return_table("vs NIFTY 50", comp.get("vs_nifty50", {}), note=excess),
    ]

    for key, value in comp.items():
        if key.startswith("vs_") and key not in ("vs_nifty50",) and not key.endswith("_pct"):
            b_info = BENCHMARK_CATALOG.get(key[3:], {})
            name = b_info.get("name", key[3:].upper())
            sections.append(return_table(f"vs {name}", value, note=excess))

    return page(
        f"Stock Details: {symbol}",
        Div(
            H2(symbol, cls="stock-title"),
            P(f"Price: ₹{fmt_price(ret.get('price'))}", cls="stock-price"),
            P(f"Session As Of: {ret['timestamp'][:10]}", cls="muted") if ret.get("timestamp") else "",
            cls="header-card"
        ),
        *sections,
        A("← Back to Dashboard", href="/", cls="btn btn-secondary"),
    )


@rt("/chart/movers")
def movers_chart():
    user_stocks = get_user_stocks()
    rows = [r for r in (returns_for_symbol(s) for s in user_stocks) if r]
    return png(change_chart(rows, window="1D", unit=" (₹)"))


@rt("/chart/price/{symbol}")
def price_chart_route(symbol: str):
    return png(price_chart(symbol))


@rt("/chart/vs/{symbol}")
def vs_chart_route(symbol: str):
    return png(vs_benchmark_chart(symbol))


@rt("/reports")
def reports_index():
    cards = []
    for report_type, sched_time in REPORT_SCHEDULE.items():
        report = latest_report(report_type)
        title = f"{report_type.replace('_', ' ').title()} Report ({sched_time})"
        if not report:
            cards.append(Div(H3(title), P("Not generated yet.", cls="muted"), cls="card"))
            continue
        highlights = report.get("highlights") or ["No notable moves."]
        cards.append(Div(
            H3(title),
            P(f"Generated {report['timestamp'][:16].replace('T', ' ')} UTC", cls="muted"),
            Ul(*[Li(h) for h in highlights]),
            cls="card"
        ))

    return page("Scheduled Reports (9 AM | 12 PM | 3 PM | 9 PM IST)", *cards, A("← Back to Dashboard", href="/", cls="btn btn-secondary"))


# --- Executive Minimal CSS Styling ---

CSS = """
:root {
    --bg-canvas: #f8fafc;
    --bg-card: #ffffff;
    --text-main: #0f172a;
    --text-muted: #64748b;
    --border-color: #e2e8f0;
    --pos-text: #047857;
    --pos-bg: #ecfdf5;
    --neg-text: #be123c;
    --neg-bg: #fff1f2;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 1240px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    color: var(--text-main);
    background-color: var(--bg-canvas);
    line-height: 1.5;
}

h1, h2, h3, h4 {
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.02em;
    color: var(--text-main);
}

.dashboard-header-title {
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0 0 0.5rem 0;
}

.header-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}

.status-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-muted);
}

.status-dot {
    width: 8px;
    height: 8px;
    background-color: #10b981;
    border-radius: 50%;
    display: inline-block;
}

.muted-source {
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px dashed var(--border-color);
}

/* Card System */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}

.modal-card {
    max-width: 760px;
    margin: 0 auto;
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.section-title-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.section-title-text {
    font-size: 1.15rem;
    font-weight: 600;
    margin: 0;
}

.source-badge {
    font-size: 0.75rem;
    background: #f1f5f9;
    color: #475569;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 500;
    border: 1px solid #cbd5e1;
}

.ml-2 {
    margin-left: 0.5rem;
}

.hb-cell-content {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
}

.radio-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.88rem;
    cursor: pointer;
    background: #f8fafc;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    transition: all 0.15s ease;
}

.radio-label:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
}

/* Highlighted Row (Row #1 Benchmark) */
.highlighted-row {
    background-color: #f0f9ff !important;
}

.highlighted-row td {
    background-color: #f0f9ff !important;
}

.highlighted-row td.sticky-col {
    background-color: #f0f9ff !important;
    font-weight: 600;
    color: #0369a1;
}

.data-table tr.highlighted-row:hover td {
    background-color: #e0f2fe !important;
}

/* Data Tables */
.data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-bottom: 0.5rem;
}

.data-table th {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    font-weight: 600;
    background: #f8fafc;
    padding: 12px 16px;
    border-bottom: 2px solid var(--border-color);
    text-align: right;
}

.data-table th:first-child {
    text-align: left;
    border-top-left-radius: 6px;
}

.data-table th:last-child {
    border-top-right-radius: 6px;
}

.data-table td {
    padding: 12px 16px;
    text-align: right;
    border-bottom: 1px solid var(--border-color);
    font-family: 'JetBrains Mono', 'Roboto Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.92rem;
    vertical-align: middle;
}

.data-table td:first-child {
    text-align: left;
    font-family: 'Inter', sans-serif;
}

.data-table tr:last-child td {
    border-bottom: none;
}

.data-table tr:hover td {
    background-color: #f8fafc;
}

.col-win {
    min-width: 130px;
}

.num-cell {
    font-weight: 600;
}

.font-medium {
    font-weight: 500;
}

.stock-link {
    color: #0284c7;
    text-decoration: none;
    font-weight: 600;
}

.stock-link:hover {
    text-decoration: underline;
}

/* Cell Multi-Metric Formatting */
.cell-container {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 3px;
}

.val-from {
    font-size: 0.76rem;
    color: #64748b;
    font-family: 'JetBrains Mono', monospace;
    font-weight: normal;
}

.val-metrics {
    display: flex;
    align-items: center;
    gap: 4px;
}

.val-abs {
    font-size: 0.88rem;
}

.val-pct {
    font-size: 0.82rem;
}

.pos {
    color: var(--pos-text);
    font-weight: 600;
}

.neg {
    color: var(--neg-text);
    font-weight: 600;
}

.pos-badge {
    background-color: var(--pos-bg);
    color: var(--pos-text);
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
}

.neg-badge {
    background-color: var(--neg-bg);
    color: var(--neg-text);
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 600;
}

/* View Toggle Bar */
.view-toggle-bar {
    display: flex;
    gap: 1rem;
    align-items: center;
    background: var(--bg-card);
    padding: 10px 16px;
    border: 1px solid var(--border-color);
    border-radius: 10px;
    margin-bottom: 1.5rem;
    font-size: 0.84rem;
    flex-wrap: wrap;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}

.toggle-title {
    font-weight: 700;
    font-size: 0.75rem;
    letter-spacing: 0.05em;
    color: #475569;
}

.toggle-pill {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    cursor: pointer;
    font-weight: 500;
    color: var(--text-main);
}

.toggle-input {
    accent-color: #0f172a;
    width: 15px;
    height: 15px;
    cursor: pointer;
}

/* Action Buttons & Navigation */
.action-bar {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin: 1.25rem 0;
    align-items: center;
}

.btn {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 1rem;
    text-decoration: none;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.88rem;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
}

.btn-primary {
    background-color: #0f172a;
    color: #ffffff;
}

.btn-primary:hover {
    background-color: #1e293b;
    transform: translateY(-1px);
}

.btn-secondary {
    background-color: #f1f5f9;
    color: #334155;
    border-color: #cbd5e1;
}

.btn-secondary:hover {
    background-color: #e2e8f0;
    transform: translateY(-1px);
}

.btn-outline {
    background-color: #ffffff;
    color: #0f172a;
    border-color: #cbd5e1;
}

.btn-outline:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
    transform: translateY(-1px);
}

.btn-sm {
    font-size: 0.8rem;
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    text-decoration: none;
    background: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
    font-weight: 500;
}

.btn-sm:hover {
    background: #e2e8f0;
}

/* Checkbox Grid in Modals */
.checkbox-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.75rem;
    margin: 1rem 0;
    background: #f8fafc;
    padding: 1rem;
    border: 1px solid var(--border-color);
    border-radius: 8px;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    cursor: pointer;
}

.input-text {
    padding: 0.6rem;
    width: 100%;
    max-width: 320px;
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 0.5rem;
}

.muted-box {
    color: var(--text-muted);
    font-size: 0.9rem;
    padding: 1rem 0;
}

.nav-link {
    margin-top: 1.5rem;
    font-weight: 600;
}

.chart {
    width: 100%;
    height: auto;
    margin: 0.5rem 0 1rem;
    border-radius: 6px;
}

/* Touch-Scrollable Table Container & Sticky Column (Mobile default) */
.table-container {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-bottom: 0.5rem;
}

.sticky-col {
    position: sticky;
    left: 0;
    background-color: var(--bg-card) !important;
    z-index: 5;
}

.data-table th:first-child {
    position: sticky;
    left: 0;
    background-color: #f8fafc !important;
    z-index: 6;
}

/* Responsive Media Queries */
@media (max-width: 640px) {
    body {
        padding: 0 0.75rem;
        margin: 1rem auto;
    }

    .dashboard-header-title {
        font-size: 1.3rem;
    }

    .header-card, .card {
        padding: 1rem;
        border-radius: 10px;
    }

    .action-bar {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.5rem;
    }

    .action-bar form {
        grid-column: span 2;
    }

    .action-bar .btn {
        width: 100%;
        justify-content: center;
        box-sizing: border-box;
        padding: 0.65rem 0.5rem;
        font-size: 0.82rem;
    }

    .view-toggle-bar {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
        padding: 10px 12px;
    }

    .checkbox-grid {
        grid-template-columns: 1fr;
        padding: 0.75rem;
    }

    .data-table td, .data-table th {
        padding: 10px 8px;
        font-size: 0.82rem;
    }

    .section-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .col-win {
        min-width: 105px;
    }

    .sticky-col, .data-table th:first-child {
        box-shadow: 2px 0 5px -2px rgba(0,0,0,0.08);
    }
}

/* Laptops, Tablets & Wide Screens: No Horizontal Scrollbar */
@media (min-width: 641px) {
    body {
        padding: 0 1.25rem;
    }

    .table-container {
        overflow-x: visible;
    }

    .data-table {
        table-layout: auto;
        width: 100%;
    }

    .col-win {
        min-width: 0;
    }

    .data-table td, .data-table th {
        padding: 10px 12px;
        font-size: 0.88rem;
    }

    .sticky-col, .data-table th:first-child {
        position: static;
        box-shadow: none;
    }

    .action-bar .btn {
        font-size: 0.85rem;
        padding: 0.45rem 0.85rem;
    }
}
"""

if __name__ == "__main__":
    serve(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5001)),
    )



