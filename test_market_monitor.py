"""Tests for the storage and analysis layers.

Everything here runs against a temporary SQLite file and hand-built bars, so
no test touches the network.
"""

import sqlite3

import pytest

import analysis
import charts
import db
from db import MarketSnapshot


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A fresh database, wired up so db.get_conn() points at it."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def bar(symbol, date, price, asset_type="stock"):
    return MarketSnapshot(
        symbol=symbol,
        asset_type=asset_type,
        market="NSE",
        price=price,
        source="test",
        timestamp=f"{date}T00:00:00",
    )


# --- pure functions -------------------------------------------------------

@pytest.mark.parametrize(
    "current, past, expected",
    [
        (110.0, 100.0, 10.0),
        (90.0, 100.0, -10.0),
        (100.0, 100.0, 0.0),
        (100.0, None, None),
        (None, 100.0, None),
        (100.0, 0.0, None),  # would divide by zero
    ],
)
def test_pct_return(current, past, expected):
    assert analysis.pct_return(current, past) == pytest.approx(expected)


def test_relative_returns_subtracts_benchmark_per_window():
    rel = analysis.relative_returns({"1D": 2.0, "1W": 1.0}, {"1D": 0.5, "1W": None})
    assert rel["1D"] == pytest.approx(1.5)
    assert rel["1W"] is None  # missing benchmark leaves the window undefined
    assert rel["1Y"] is None  # window absent from both inputs


# --- storage --------------------------------------------------------------

def test_saving_the_same_session_twice_keeps_one_row(store):
    store.save_snapshots([bar("TCS", "2026-09-04", 2304.0)])
    store.save_snapshots([bar("TCS", "2026-09-04", 2304.0)])
    assert store.snapshot_count("TCS") == 1


def test_snapshot_before_returns_most_recent_at_or_before_cutoff(store):
    store.save_snapshots([
        bar("TCS", "2026-09-01", 100.0),
        bar("TCS", "2026-09-03", 110.0),
        bar("TCS", "2026-09-04", 120.0),
    ])
    assert store.snapshot_before("TCS", "2026-09-03T00:00:00")["price"] == 110.0
    # No session on the 2nd, so the window falls back to the 1st.
    assert store.snapshot_before("TCS", "2026-09-02T00:00:00")["price"] == 100.0
    assert store.snapshot_before("TCS", "2024-01-01T00:00:00") is None


def test_migration_upgrades_legacy_index_and_drops_poll_rows(tmp_path, monkeypatch):
    """A pre-existing database keeps working, minus its per-poll rows."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL, asset_type TEXT NOT NULL, market TEXT NOT NULL,
            price REAL NOT NULL, open REAL, high REAL, low REAL,
            previous_close REAL, volume REAL, source TEXT NOT NULL);
        CREATE INDEX idx_snapshots_symbol_ts ON market_snapshots (symbol, timestamp);
        """
    )
    for ts in ("2026-09-04T00:00:00", "2026-09-05T08:02:19", "2026-09-05T12:31:07"):
        conn.execute(
            "INSERT INTO market_snapshots (timestamp, symbol, asset_type, market,"
            " price, source) VALUES (?, 'TCS', 'stock', 'NSE', 2304.0, 'yfinance')",
            (ts,),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()

    assert db.snapshot_count("TCS") == 1
    assert db.latest_snapshot("TCS")["timestamp"] == "2026-09-04T00:00:00"
    with db.get_conn() as conn:
        index = conn.execute(
            "SELECT [unique] FROM pragma_index_list('market_snapshots')"
            " WHERE name = 'idx_snapshots_symbol_ts'"
        ).fetchone()
    assert index["unique"] == 1


# --- analysis over stored history ----------------------------------------

def test_returns_for_symbol_resolves_every_window(store):
    """The bug this suite exists for: windows used to be permanently None
    because only same-day snapshots were ever stored."""
    store.save_snapshots([
        bar("TCS", "2025-09-04", 1000.0),  # 1Y
        bar("TCS", "2026-03-06", 1100.0),  # 6M
        bar("TCS", "2026-06-06", 1200.0),  # 3M
        bar("TCS", "2026-08-05", 1250.0),  # 1M
        bar("TCS", "2026-08-28", 1300.0),  # 1W
        bar("TCS", "2026-09-03", 1320.0),  # 1D
        bar("TCS", "2026-09-04", 1400.0),  # latest
    ])
    result = analysis.returns_for_symbol("TCS")

    assert result["price"] == 1400.0
    assert all(result[label] is not None for label, _ in analysis.RETURN_WINDOWS)
    assert result["1D"] == pytest.approx((1400 / 1320 - 1) * 100)
    assert result["1Y"] == pytest.approx(40.0)


def test_returns_for_symbol_is_empty_for_unknown_symbol(store):
    assert analysis.returns_for_symbol("NOPE") == {}


def test_stock_comparison_includes_sector_benchmark(store):
    for symbol in ("TCS", "nifty50", "niftyit"):
        store.save_snapshots([
            bar(symbol, "2026-09-03", 100.0),
            bar(symbol, "2026-09-04", 110.0 if symbol == "TCS" else 105.0),
        ])

    comp = analysis.stock_comparison("TCS")
    assert comp["vs_nifty50"]["1D"] == pytest.approx(5.0)
    assert comp["vs_niftyit"]["1D"] == pytest.approx(5.0)


def test_rank_by_return_orders_best_first(store):
    store.save_snapshots([
        bar("TCS", "2026-09-03", 100.0), bar("TCS", "2026-09-04", 105.0),
        bar("INFY", "2026-09-03", 100.0), bar("INFY", "2026-09-04", 95.0),
        bar("RELIANCE", "2026-09-03", 100.0), bar("RELIANCE", "2026-09-04", 110.0),
    ])
    ranked = analysis.rank_by_return(["TCS", "INFY", "RELIANCE"], window="1D")
    assert [r["symbol"] for r in ranked] == ["RELIANCE", "TCS", "INFY"]


# --- bar parsing ----------------------------------------------------------

def test_history_snapshots_keys_sessions_by_local_date_and_chains_prev_close(monkeypatch):
    import pandas as pd

    import market_data

    index = pd.to_datetime(
        ["2026-09-02", "2026-09-03", "2026-09-04"]
    ).tz_localize("Asia/Kolkata")
    frame = pd.DataFrame(
        {
            "Open": [10.0, 11.0, 12.0],
            "High": [10.5, 11.5, 12.5],
            "Low": [9.5, 10.5, 11.5],
            "Close": [10.0, 11.0, 12.0],
            "Volume": [100, 200, 300],
        },
        index=index,
    )

    class FakeTicker:
        def __init__(self, ticker):
            pass

        def history(self, period):
            return frame

    monkeypatch.setattr(market_data.yf, "Ticker", FakeTicker)
    snaps = market_data._history_snapshots("TCS", "TCS.NS", "stock", "NSE", "1mo")

    assert [s.timestamp for s in snaps] == [
        "2026-09-02T00:00:00",
        "2026-09-03T00:00:00",
        "2026-09-04T00:00:00",
    ]
    # previous_close chains off the preceding bar; the first bar has none.
    assert [s.previous_close for s in snaps] == [None, 10.0, 11.0]
    assert snaps[-1].price == 12.0


def test_history_snapshots_survives_a_provider_failure(monkeypatch):
    import market_data

    class ExplodingTicker:
        def __init__(self, ticker):
            pass

        def history(self, period):
            raise RuntimeError("upstream is down")

    monkeypatch.setattr(market_data.yf, "Ticker", ExplodingTicker)
    assert market_data._history_snapshots("TCS", "TCS.NS", "stock", "NSE", "1mo") == []


# --- absolute change ------------------------------------------------------

@pytest.mark.parametrize(
    "current, past, expected",
    [
        (110.0, 100.0, 10.0),
        (90.0, 100.0, -10.0),
        (100.0, None, None),
        (None, 100.0, None),
        (100.0, 0.0, 100.0),  # unlike percent, a zero base is still meaningful
    ],
)
def test_abs_change(current, past, expected):
    assert analysis.abs_change(current, past) == pytest.approx(expected)


def test_returns_for_symbol_reports_change_and_window_open(store):
    store.save_snapshots([
        bar("TCS", "2026-09-03", 2320.10),
        bar("TCS", "2026-09-04", 2304.00),
    ])
    result = analysis.returns_for_symbol("TCS")

    assert result["1D_from"] == pytest.approx(2320.10)
    assert result["1D_abs"] == pytest.approx(-16.10)
    assert result["1D"] == pytest.approx(-0.6939, abs=1e-3)  # percent still available


def test_relative_change_measures_the_gap_against_tracking_the_benchmark(store):
    # Stock 200 -> 220 (+10%); benchmark +5%. Tracking the benchmark would
    # have put the stock at 210, so it is 10 units per share ahead.
    store.save_snapshots([
        bar("TCS", "2026-09-03", 200.0), bar("TCS", "2026-09-04", 220.0),
        bar("nifty50", "2026-09-03", 100.0, asset_type="index"),
        bar("nifty50", "2026-09-04", 105.0, asset_type="index"),
    ])
    comp = analysis.stock_comparison("TCS")

    assert comp["vs_nifty50"]["1D"] == pytest.approx(10.0)
    assert comp["vs_nifty50_pct"]["1D"] == pytest.approx(5.0)


def test_relative_change_is_none_without_a_benchmark(store):
    store.save_snapshots([
        bar("TCS", "2026-09-03", 200.0), bar("TCS", "2026-09-04", 220.0),
    ])
    assert analysis.stock_comparison("TCS")["vs_nifty50"]["1D"] is None


def test_rank_by_return_ignores_price_magnitude(store):
    """The cheaper stock moved further in percent, so it ranks first even
    though the expensive one moved more in absolute terms."""
    store.save_snapshots([
        bar("TCS", "2026-09-03", 2000.0), bar("TCS", "2026-09-04", 2020.0),   # +1%, +20
        bar("INFY", "2026-09-03", 100.0), bar("INFY", "2026-09-04", 105.0),   # +5%, +5
    ])
    ranked = analysis.rank_by_return(["TCS", "INFY"], window="1D")
    assert [r["symbol"] for r in ranked] == ["INFY", "TCS"]
    assert ranked[0]["1D_abs"] == pytest.approx(5.0)


# --- charts ---------------------------------------------------------------

PNG_MAGIC = b"\x89PNG"


def test_price_chart_renders_a_png(store):
    store.save_snapshots([
        bar("TCS", f"2026-08-{day:02d}", 2300.0 + day) for day in range(1, 20)
    ])
    assert charts.price_chart("TCS", days=365).startswith(PNG_MAGIC)


def test_charts_render_a_placeholder_rather_than_crashing_on_thin_data(store):
    """A brand-new database has one session per symbol, or none at all."""
    store.save_snapshots([bar("TCS", "2026-09-04", 2304.0)])
    assert charts.price_chart("TCS").startswith(PNG_MAGIC)
    assert charts.price_chart("NEVER_SEEN").startswith(PNG_MAGIC)
    assert charts.vs_benchmark_chart("TCS").startswith(PNG_MAGIC)


def test_vs_benchmark_chart_needs_overlapping_sessions(store):
    # Stock and benchmark trade on disjoint dates — no comparison is possible,
    # but the route must still return an image.
    store.save_snapshots([
        bar("TCS", "2026-08-03", 2300.0), bar("TCS", "2026-08-04", 2310.0),
        bar("nifty50", "2026-07-06", 23000.0, asset_type="index"),
        bar("nifty50", "2026-07-07", 23100.0, asset_type="index"),
    ])
    assert charts.vs_benchmark_chart("RELIANCE").startswith(PNG_MAGIC)


def test_change_chart_skips_symbols_without_a_value():
    rows = [
        {"symbol": "TCS", "1D_abs": -16.10},
        {"symbol": "INFY", "1D_abs": None},
        {"symbol": "RELIANCE", "1D_abs": 19.50},
    ]
    assert charts.change_chart(rows, window="1D").startswith(PNG_MAGIC)
    assert charts.change_chart([{"symbol": "TCS", "1D_abs": None}]).startswith(PNG_MAGIC)


def test_rendering_closes_every_figure(store):
    """Leaked figures accumulate until the server runs out of memory."""
    import matplotlib.pyplot as plt

    store.save_snapshots([
        bar("TCS", f"2026-08-{day:02d}", 2300.0 + day) for day in range(1, 20)
    ])
    plt.close("all")
    for _ in range(5):
        charts.price_chart("TCS")
        charts.vs_benchmark_chart("TCS")
        charts.change_chart([{"symbol": "TCS", "1D_abs": 1.0}])
    assert plt.get_fignums() == []


# --- User Stocks & Benchmarks Management -----------------------------------

def test_user_stocks_crud(store):
    stocks = store.get_user_stocks()
    assert "TCS" in stocks

    store.save_user_stocks(["WIPRO", "TATAMOTORS"])
    assert store.get_user_stocks() == ["TATAMOTORS", "WIPRO"]

    store.add_user_stock("LT")
    assert "LT" in store.get_user_stocks()

    store.remove_user_stock("WIPRO")
    assert store.get_user_stocks() == ["LT", "TATAMOTORS"]


def test_user_benchmarks_crud(store):
    benchmarks = store.get_user_benchmarks()
    assert "nifty50" in benchmarks

    store.save_user_benchmarks(["nifty50", "sp500", "gold"])
    assert store.get_user_benchmarks() == ["gold", "nifty50", "sp500"]


def test_highlighted_benchmark_crud(store):
    assert store.get_highlighted_benchmark() == "nifty50"
    store.set_highlighted_benchmark("sp500")
    assert store.get_highlighted_benchmark() == "sp500"


# --- Exporters -------------------------------------------------------------

def test_export_to_csv_and_excel(store):
    import exporter

    store.save_snapshots([
        bar("TCS", "2026-09-03", 100.0), bar("TCS", "2026-09-04", 110.0),
    ])

    rows = [analysis.returns_for_symbol("TCS")]
    sections = {"Stocks": (rows, None)}

    csv_content = exporter.export_to_csv(sections)
    assert "=== STOCKS ===" in csv_content
    assert "TCS" in csv_content
    assert "10.00" in csv_content
    assert "1D From Price" in csv_content

    # Test filtering out % return and From Price columns
    filtered_csv = exporter.export_to_csv(sections, show_from=False, show_pct=False)
    assert "1D Change (±)" in filtered_csv
    assert "1D From Price" not in filtered_csv
    assert "1D % Return" not in filtered_csv

    excel_bytes = exporter.export_to_excel(sections, show_pct=False)
    assert len(excel_bytes) > 0
    assert excel_bytes.startswith(b"PK")  # xlsx is a zip file


def test_app_routes(store):
    from starlette.testclient import TestClient
    from app import app

    store.save_snapshots([
        bar("nifty50", "2026-09-04", 24000.0, asset_type="index"),
        bar("TCS", "2026-09-04", 3500.0),
    ])

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "highlighted-row" in resp.text

    b_resp = client.get("/modal/benchmarks")
    assert b_resp.status_code == 200
    assert "Highlighted Benchmark" in b_resp.text

    assert client.get("/modal/stocks").status_code == 200
    assert client.get("/export/csv").status_code == 200
    assert client.get("/export/excel").status_code == 200


