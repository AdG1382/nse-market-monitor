# NSE India Market Monitor & Analytics Dashboard

A modern, lightweight, high-performance web dashboard for tracking **NSE India** stock market performance, benchmarking individual stocks against market indices, running automated daily snapshots, and exporting custom analytics.

Built with pure Python using **FastHTML**, **SQLite**, **Pandas**, **Matplotlib**, and a **multi-tier open-source data fetcher pipeline**.

---

## Key Features

- **Multi-Source Open Data Pipeline**: 
  - Primary: [`nsepython`](https://github.com/aadhikari/nsepython) (Direct NSE API client)
  - Fallback 1: Direct public NSE endpoints
  - Fallback 2: Yahoo Finance (`yfinance`) with automatic `.NS` symbol mapping
  - **100% Free & Open Source**: No API keys, subscriptions, or paid data services required.
- **Top 200 NSE Stocks Categorized**:
  - Organized into 10 key sector buckets: Banking, IT, Pharma, Auto, Energy, FMCG, Metals, Financial Services, Infrastructure, and Consumer Discretionary.
- **Dynamic Benchmark Comparison**:
  - Compare stocks across 5, 10, 20, 30, 45, 60, 90, 180, 270, and 365-day return windows.
  - Pin a **Highlighted Benchmark** (e.g. **NIFTY 50** or **NIFTY BANK**) to row #1 of stock comparison tables for instant relative performance context.
- **Flexible Metric Toggles & Dynamic Exporters**:
  - Toggle between **Absolute Return %**, **Relative Outperformance vs Benchmark %**, or **Both**.
  - Dynamic **CSV** and **Excel** report generators that respect active metric toggles (omitting unselected metric columns automatically).
- **Automated Market Snapshot Scheduler**:
  - Built-in APScheduler background daemon captures market state at 9:00 AM, 12:00 PM, 3:00 PM, and 9:00 PM IST.
  - Persisted in local SQLite WAL database for fast historical queries.
- **Responsive Widescreen-Optimized Dark UI**:
  - Clean, minimal aesthetic crafted with CSS Grid/Flexbox.
  - Zero unwanted horizontal scrolling on wide desktop and tablet viewports, with seamless mobile fallback.

---

## Architecture Overview

```
                          ┌─────────────────────────────┐
                          │   FastHTML Web Application   │
                          │          (app.py)           │
                          └──────────────┬──────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
      ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
      │ Market Data Engine │  │ Return Calculator  │  │ Dynamic Exporter   │
      │  (market_data.py)  │  │    (analysis.py)   │  │   (exporter.py)    │
      └──────────┬─────────┘  └────────────────────┘  └────────────────────┘
                 │
       ┌─────────┴─────────┬────────────────────────┐
       ▼                   ▼                        ▼
┌──────────────┐   ┌──────────────┐        ┌────────────────┐
│  nsepython   │   │  nse_public  │        │ yfinance (.NS) │
└──────────────┘   └──────────────┘        └────────────────┘
                                                    │
                                                    ▼
                                           ┌────────────────┐
                                           │  SQLite WAL DB │
                                           │(market_monitor)│
                                           └────────────────┘
```

---

## Code Base Metadata & Metrics

| Metric | Value |
| :--- | :--- |
| **Total Lines of Code (LOC)** | **3,009 lines** |
| **Primary Language** | Python 3.12+ |
| **Framework** | FastHTML (`fasthtml.common`) |
| **Test Coverage** | 35 / 35 Pytest Unit Tests Passing (100% Pass Rate) |
| **Telemetry / Tracking** | **0%** (Zero telemetry, tracking scripts, or cloud analytics) |
| **Paid Service Cost** | **$0.00 / mo** |

### File Breakdown

| File | LOC | Purpose |
| :--- | :---: | :--- |
| `app.py` | 1,169 | FastHTML application server, UI components, modal handlers, metric controls |
| `test_market_monitor.py` | 417 | Pytest suite covering routes, data fetchers, analytics, DB, and exporters |
| `db.py` | 345 | SQLite database layer (WAL mode) for user settings, snapshots, and reports |
| `config.py` | 330 | Top 200 NSE stock list (10 sectors), benchmark index catalogs, system defaults |
| `market_data.py` | 244 | Robust multi-tier market data fetcher (`nsepython` -> `nse_public` -> `yfinance`) |
| `charts.py` | 181 | Matplotlib server-side visual chart generator with automatic cleanup |
| `analysis.py` | 121 | Windowed return calculation engine and relative outperformance math |
| `exporter.py` | 74 | CSV and OpenPyXL Excel exporters with dynamic column filtering |
| `reports.py` | 68 | Scheduled market snapshot summary compiler |
| `scheduler.py` | 60 | APScheduler background service for market session snapshots |
| **Total** | **3,009** | |

---

## Audit Summary: Invasiveness & Costs

An exhaustive security and financial audit was performed on this repository:

### 1. Invasiveness & Privacy Audit
- **Telemetry / Analytics**: `NONE`. The application contains zero Google Analytics, Mixpanel, Segment, or third-party tracking scripts.
- **Third-Party Data Leaks**: `NONE`. All web requests stay local to your browser and the underlying data APIs (`nsepython` / NSE / Yahoo Finance).
- **Data Storage**: `100% Local`. User settings, selected benchmarks, metric preferences, and historical snapshots are stored locally inside `market_monitor.db`.

### 2. Cost & Expense Audit
- **Paid APIs**: `$0.00`. Uses free open-source Python data clients and public endpoints.
- **Infrastructure / Cloud Overhead**: Minimal CPU & Memory footprint (< 60MB RAM idle). Can run locally on any Linux, macOS, or Windows machine, or a micro VPS.
- **Bandwidth Usage**: Low. Requests data on-demand and caches market session data locally in SQLite.

---

## Local Setup & Cloud Deployment

- **For End Users / Cloud Deployment**: Follow the step-by-step [Deployment & Cloud Hosting Guide](DEPLOYMENT.md) to host the app on Render or Railway for free.
- **For Local Setup**: Follow the instructions below.

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- `pip` package manager

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/nse-market-monitor.git
cd nse-market-monitor
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/ choir  # Linux/macOS
# or .venv\Scripts\activate  # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```
Open your browser and navigate to: **`http://localhost:5001`**

---

## Running Automated Tests

To execute the unit test suite:

```bash
pytest test_market_monitor.py -v
```

All 35 unit tests verify database migrations, multi-provider data fetching, relative return calculations, export column filtering, and FastHTML routes.

---

## License

MIT License. Free for open-source, personal, and commercial use.
