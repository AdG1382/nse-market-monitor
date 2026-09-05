"""SQLite storage for market snapshots and generated reports."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH, DEFAULT_STOCKS, DEFAULT_BENCHMARKS, DEFAULT_HIGHLIGHTED_BENCHMARK

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,   -- 'stock' | 'index' | 'global'
    market TEXT NOT NULL,       -- 'NSE' | 'US' | 'JP' | 'SG' | 'COMMODITY'
    price REAL NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    previous_close REAL,
    volume REAL,
    source TEXT NOT NULL
);

-- One row per symbol per session timestamp. Collection re-fetches
-- overlapping history every run, so this is what makes it idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_symbol_ts
    ON market_snapshots (symbol, timestamp);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    report_type TEXT NOT NULL,
    content TEXT NOT NULL       -- JSON blob
);

CREATE TABLE IF NOT EXISTS user_stocks (
    symbol TEXT PRIMARY KEY,
    display_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_benchmarks (
    key TEXT PRIMARY KEY,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def utc_now_iso() -> str:
    """Naive-UTC ISO timestamp, matching the format stored in the DB."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def init_db():
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        _drop_non_session_rows(conn)
        _migrate_unique_session_index(conn)
        _seed_defaults_if_empty(conn)


def _seed_defaults_if_empty(conn):
    # Seed default user stocks if empty
    cur = conn.execute("SELECT COUNT(*) AS count FROM user_stocks")
    if cur.fetchone()["count"] == 0:
        now = utc_now_iso()
        conn.executemany(
            "INSERT OR IGNORE INTO user_stocks (symbol, display_name, created_at) VALUES (?, ?, ?)",
            [(s, s, now) for s in DEFAULT_STOCKS]
        )

    # Seed default user benchmarks if empty
    cur = conn.execute("SELECT COUNT(*) AS count FROM user_benchmarks")
    if cur.fetchone()["count"] == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO user_benchmarks (key, is_active) VALUES (?, 1)",
            [(k,) for k in DEFAULT_BENCHMARKS]
        )

    # Seed default highlighted benchmark if empty
    cur = conn.execute("SELECT COUNT(*) AS count FROM user_settings WHERE key = 'highlighted_benchmark'")
    if cur.fetchone()["count"] == 0:
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (key, value) VALUES ('highlighted_benchmark', ?)",
            (DEFAULT_HIGHLIGHTED_BENCHMARK,)
        )



def _drop_non_session_rows(conn):
    """Remove rows that predate session-keyed collection.

    Older versions wrote one row per poll, so a symbol collected four times a
    day left four near-identical rows carrying the same daily close. They now
    sort *after* the daily bar for that session and would win latest_snapshot,
    so the timestamped-poll rows go; collection rewrites the sessions they
    covered. Daily bars are always keyed at midnight, which is the tell.
    """
    conn.execute("DELETE FROM market_snapshots WHERE timestamp NOT LIKE '%T00:00:00'")


def _migrate_unique_session_index(conn):
    """Upgrade the pre-existing non-unique (symbol, timestamp) index.

    SCHEMA declares the index with IF NOT EXISTS, which matches on *name* and
    so silently keeps an older non-unique index of the same name. Databases
    created before sessions were deduplicated hold several intraday rows per
    session; those collapse to the daily bar that collection now writes, so
    the extras are dropped before the unique index goes on.
    """
    row = conn.execute(
        "SELECT [unique] FROM pragma_index_list('market_snapshots')"
        " WHERE name = 'idx_snapshots_symbol_ts'"
    ).fetchone()
    if row is None or row["unique"]:
        return

    conn.execute("DROP INDEX idx_snapshots_symbol_ts")
    conn.execute(
        """
        DELETE FROM market_snapshots WHERE id NOT IN (
            SELECT MIN(id) FROM market_snapshots GROUP BY symbol, timestamp
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX idx_snapshots_symbol_ts"
        " ON market_snapshots (symbol, timestamp)"
    )


@dataclass
class MarketSnapshot:
    symbol: str
    asset_type: str
    market: str
    price: float
    source: str
    timestamp: str = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = utc_now_iso()


def save_snapshot(snap: MarketSnapshot):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO market_snapshots
                (timestamp, symbol, asset_type, market, price, open, high, low,
                 previous_close, volume, source)
            VALUES (:timestamp, :symbol, :asset_type, :market, :price, :open,
                    :high, :low, :previous_close, :volume, :source)
            """,
            asdict(snap),
        )


def save_snapshots(snaps: list[MarketSnapshot]):
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO market_snapshots
                (timestamp, symbol, asset_type, market, price, open, high, low,
                 previous_close, volume, source)
            VALUES (:timestamp, :symbol, :asset_type, :market, :price, :open,
                    :high, :low, :previous_close, :volume, :source)
            """,
            [asdict(s) for s in snaps],
        )


def latest_snapshot(symbol: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM market_snapshots
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol,),
        )
        return cur.fetchone()


def snapshot_before(symbol: str, cutoff_iso: str) -> Optional[sqlite3.Row]:
    """Most recent snapshot for `symbol` at or before `cutoff_iso`."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM market_snapshots
            WHERE symbol = ? AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol, cutoff_iso),
        )
        return cur.fetchone()


def save_report(report_type: str, content: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (timestamp, report_type, content) VALUES (?, ?, ?)",
            (utc_now_iso(), report_type, json.dumps(content)),
        )


def latest_report(report_type: str) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT content FROM reports
            WHERE report_type = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (report_type,),
        )
        row = cur.fetchone()
        return json.loads(row["content"]) if row else None


def snapshot_count(symbol: str) -> int:
    """Number of stored sessions for `symbol`. Used to decide whether the
    initial history backfill still needs to run."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) AS n FROM market_snapshots WHERE symbol = ?", (symbol,)
        )
        return cur.fetchone()["n"]


def price_history(symbol: str, since_iso: str) -> list[sqlite3.Row]:
    """Every stored session for `symbol` at or after `since_iso`, oldest first."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT timestamp, price FROM market_snapshots
            WHERE symbol = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (symbol, since_iso),
        )
        return cur.fetchall()


def get_user_stocks() -> list[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT symbol FROM user_stocks ORDER BY symbol ASC")
        rows = cur.fetchall()
        if not rows:
            return DEFAULT_STOCKS
        return [r["symbol"] for r in rows]


def save_user_stocks(stocks: list[str]):
    now = utc_now_iso()
    clean_stocks = [s.strip().upper() for s in stocks if s and s.strip()]
    with get_conn() as conn:
        conn.execute("DELETE FROM user_stocks")
        conn.executemany(
            "INSERT INTO user_stocks (symbol, display_name, created_at) VALUES (?, ?, ?)",
            [(s, s, now) for s in clean_stocks]
        )


def add_user_stock(symbol: str):
    symbol = symbol.strip().upper()
    if not symbol:
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_stocks (symbol, display_name, created_at) VALUES (?, ?, ?)",
            (symbol, symbol, utc_now_iso())
        )


def remove_user_stock(symbol: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_stocks WHERE symbol = ?", (symbol.strip().upper(),))


def get_user_benchmarks() -> list[str]:
    with get_conn() as conn:
        cur = conn.execute("SELECT key FROM user_benchmarks WHERE is_active = 1 ORDER BY key ASC")
        rows = cur.fetchall()
        if not rows:
            return DEFAULT_BENCHMARKS
        return [r["key"] for r in rows]


def save_user_benchmarks(keys: list[str]):
    clean_keys = [k.strip().lower() for k in keys if k and k.strip()]
    with get_conn() as conn:
        conn.execute("DELETE FROM user_benchmarks")
        conn.executemany(
            "INSERT INTO user_benchmarks (key, is_active) VALUES (?, 1)",
            [(k,) for k in clean_keys]
        )


def get_highlighted_benchmark() -> str:
    with get_conn() as conn:
        cur = conn.execute("SELECT value FROM user_settings WHERE key = 'highlighted_benchmark'")
        row = cur.fetchone()
        return row["value"] if row else DEFAULT_HIGHLIGHTED_BENCHMARK


def set_highlighted_benchmark(benchmark_key: str):
    key = benchmark_key.strip().lower() if benchmark_key and benchmark_key.strip() else DEFAULT_HIGHLIGHTED_BENCHMARK
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_settings (key, value) VALUES ('highlighted_benchmark', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key,)
        )

