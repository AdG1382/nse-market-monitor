"""Central configuration: watchlist, benchmarks, global instruments."""

import os

# NSE stock symbols to track (display symbols; see STOCK_TICKERS for the
# actual data-provider ticker for each).
STOCKS = [
    "TCS",
    "INFY",
    "RELIANCE",
    "HDFCBANK",
]

# yfinance ticker for each stock. NSE-listed equities use the ".NS" suffix.
STOCK_TICKERS = {symbol: f"{symbol}.NS" for symbol in STOCKS}

# Maps a stock to the sector index it should be compared against, in
# addition to NIFTY 50. Value must be a key in BENCHMARKS.
STOCK_SECTOR = {
    "TCS": "niftyit",
    "INFY": "niftyit",
    "RELIANCE": None,
    "HDFCBANK": "niftybank",
}

# NSE index display names, keyed the same as BENCHMARK_TICKERS.
BENCHMARKS = {
    "nifty50": "NIFTY 50",
    "niftybank": "NIFTY BANK",
    "niftyit": "NIFTY IT",
}

# yfinance ticker for each index in BENCHMARKS.
BENCHMARK_TICKERS = {
    "nifty50": "^NSEI",
    "niftybank": "^NSEBANK",
    "niftyit": "^CNXIT",
}

# Global instruments, fetched via yfinance. Values are Yahoo Finance tickers.
GLOBAL = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "nikkei": "^N225",
    "singapore": "^STI",
    "gold": "GC=F",
}

# Master catalog of Top 200 NSE stocks grouped by sector categories.
STOCK_SECTORS = {
    "NSE Banking & Financial Services": [
        {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd"},
        {"symbol": "SBIN", "name": "State Bank of India"},
        {"symbol": "AXISBANK", "name": "Axis Bank Ltd"},
        {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd"},
        {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd"},
        {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd"},
        {"symbol": "BANKBARODA", "name": "Bank of Baroda"},
        {"symbol": "PNB", "name": "Punjab National Bank"},
        {"symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd"},
        {"symbol": "CANBK", "name": "Canara Bank"},
        {"symbol": "IDFCFIRSTB", "name": "IDFC First Bank Ltd"},
        {"symbol": "AUBANK", "name": "AU Small Finance Bank Ltd"},
        {"symbol": "FEDERALBNK", "name": "Federal Bank Ltd"},
        {"symbol": "BANDHANBNK", "name": "Bandhan Bank Ltd"},
        {"symbol": "CHOLAFIN", "name": "Cholamandalam Investment"},
        {"symbol": "MUTHOOTFIN", "name": "Muthoot Finance Ltd"},
        {"symbol": "SHRIRAMFIN", "name": "Shriram Finance Ltd"},
        {"symbol": "REC", "name": "REC Ltd"},
        {"symbol": "PFC", "name": "Power Finance Corporation"},
        {"symbol": "JIOFIN", "name": "Jio Financial Services Ltd"},
        {"symbol": "LICHSGFIN", "name": "LIC Housing Finance Ltd"},
        {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance Co"},
        {"symbol": "SBILIFE", "name": "SBI Life Insurance Co"},
        {"symbol": "ICICIPRULI", "name": "ICICI Prudential Life"},
        {"symbol": "ICICIGI", "name": "ICICI Lombard General Ins"},
        {"symbol": "M&MFIN", "name": "Mahindra & Mahindra Fin"},
        {"symbol": "BSE", "name": "BSE Ltd"},
        {"symbol": "CDSL", "name": "Central Depository Services"},
        {"symbol": "MCX", "name": "Multi Commodity Exchange"},
        {"symbol": "CAMS", "name": "Computer Age Management"},
        {"symbol": "MAXHEALTH", "name": "Max Healthcare Institute"},
    ],
    "NSE IT & Technology Services": [
        {"symbol": "TCS", "name": "Tata Consultancy Services"},
        {"symbol": "INFY", "name": "Infosys Ltd"},
        {"symbol": "HCLTECH", "name": "HCL Technologies Ltd"},
        {"symbol": "WIPRO", "name": "Wipro Ltd"},
        {"symbol": "LTIM", "name": "LTIMindtree Ltd"},
        {"symbol": "TECHM", "name": "Tech Mahindra Ltd"},
        {"symbol": "PERSISTENT", "name": "Persistent Systems Ltd"},
        {"symbol": "COFORGE", "name": "Coforge Ltd"},
        {"symbol": "LTTS", "name": "L&T Technology Services"},
        {"symbol": "MPHASIS", "name": "Mphasis Ltd"},
        {"symbol": "TATAELXSI", "name": "Tata Elxsi Ltd"},
        {"symbol": "OFSS", "name": "Oracle Financial Services"},
        {"symbol": "BIRLASOFT", "name": "Birlasoft Ltd"},
        {"symbol": "KPITTECH", "name": "KPIT Technologies Ltd"},
        {"symbol": "HAPPSTMNDS", "name": "Happiest Minds Tech"},
        {"symbol": "TATACOMM", "name": "Tata Communications Ltd"},
        {"symbol": "CYIENT", "name": "Cyient Ltd"},
        {"symbol": "ZENSARTECH", "name": "Zensar Technologies Ltd"},
        {"symbol": "NEWGEN", "name": "Newgen Software Tech"},
        {"symbol": "INTELLECT", "name": "Intellect Design Arena"},
    ],
    "NSE Oil, Gas & Energy": [
        {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"},
        {"symbol": "ONGC", "name": "Oil & Natural Gas Corp"},
        {"symbol": "NTPC", "name": "NTPC Ltd"},
        {"symbol": "POWERGRID", "name": "Power Grid Corporation"},
        {"symbol": "BPCL", "name": "Bharat Petroleum Corp"},
        {"symbol": "IOC", "name": "Indian Oil Corporation"},
        {"symbol": "GAIL", "name": "GAIL (India) Ltd"},
        {"symbol": "OIL", "name": "Oil India Ltd"},
        {"symbol": "COALINDIA", "name": "Coal India Ltd"},
        {"symbol": "ADANIGREEN", "name": "Adani Green Energy Ltd"},
        {"symbol": "ADANIPOWER", "name": "Adani Power Ltd"},
        {"symbol": "ATGL", "name": "Adani Total Gas Ltd"},
        {"symbol": "TATAPOWER", "name": "Tata Power Co Ltd"},
        {"symbol": "NHPC", "name": "NHPC Ltd"},
        {"symbol": "SJVN", "name": "SJVN Ltd"},
        {"symbol": "SUZLON", "name": "Suzlon Energy Ltd"},
        {"symbol": "IREDA", "name": "Indian Renewable Energy"},
        {"symbol": "TORNTPOWER", "name": "Torrent Power Ltd"},
        {"symbol": "IEX", "name": "Indian Energy Exchange"},
        {"symbol": "HINDPETRO", "name": "Hindustan Petroleum Corp"},
        {"symbol": "PETRONET", "name": "Petronet LNG Ltd"},
        {"symbol": "IGL", "name": "Indraprastha Gas Ltd"},
        {"symbol": "MGL", "name": "Mahanagar Gas Ltd"},
    ],
    "NSE Automobiles & Auto Components": [
        {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd"},
        {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd"},
        {"symbol": "M&M", "name": "Mahindra & Mahindra Ltd"},
        {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd"},
        {"symbol": "EICHERMOT", "name": "Eicher Motors Ltd"},
        {"symbol": "TVSMOTOR", "name": "TVS Motor Co Ltd"},
        {"symbol": "ASHOKLEY", "name": "Ashok Leyland Ltd"},
        {"symbol": "BALKRISIND", "name": "Balkrishna Industries"},
        {"symbol": "BHARATFORG", "name": "Bharat Forge Ltd"},
        {"symbol": "MOTHERSON", "name": "Samvardhana Motherson"},
        {"symbol": "TIINDIA", "name": "Tube Investments India"},
        {"symbol": "BOSCHLTD", "name": "Bosch Ltd"},
        {"symbol": "SONACOMS", "name": "Sona BLW Precision"},
        {"symbol": "EXIDEIND", "name": "Exide Industries Ltd"},
        {"symbol": "AMARAJABAT", "name": "Amara Raja Energy & Mobility"},
        {"symbol": "MRF", "name": "MRF Ltd"},
        {"symbol": "APOLLOTYRE", "name": "Apollo Tyres Ltd"},
        {"symbol": "CEATLTD", "name": "CEAT Ltd"},
        {"symbol": "ESCORT", "name": "Escorts Kubota Ltd"},
        {"symbol": "FORCE", "name": "Force Motors Ltd"},
    ],
    "NSE Pharmaceuticals & Healthcare": [
        {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Ind"},
        {"symbol": "DIVISLAB", "name": "Divi's Laboratories Ltd"},
        {"symbol": "CIPLA", "name": "Cipla Ltd"},
        {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories"},
        {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise"},
        {"symbol": "ZYDUSLIFE", "name": "Zydus Lifesciences Ltd"},
        {"symbol": "MANKIND", "name": "Mankind Pharma Ltd"},
        {"symbol": "TORNTPHARM", "name": "Torrent Pharmaceuticals"},
        {"symbol": "LUPIN", "name": "Lupin Ltd"},
        {"symbol": "AUROPHARMA", "name": "Aurobindo Pharma Ltd"},
        {"symbol": "ALKEM", "name": "Alkem Laboratories Ltd"},
        {"symbol": "BIOCON", "name": "Biocon Ltd"},
        {"symbol": "GLENMARK", "name": "Glenmark Pharmaceuticals"},
        {"symbol": "SYNGENE", "name": "Syngene International"},
        {"symbol": "METROPOLIS", "name": "Metropolis Healthcare"},
        {"symbol": "LALPATHLAB", "name": "Dr. Lal PathLabs Ltd"},
        {"symbol": "IPCALAB", "name": "IPCA Laboratories Ltd"},
        {"symbol": "GRANULES", "name": "Granules India Ltd"},
        {"symbol": "JBCHEPHARM", "name": "JB Chemicals & Pharma"},
        {"symbol": "LAURUSLABS", "name": "Laurus Labs Ltd"},
        {"symbol": "FORTIS", "name": "Fortis Healthcare Ltd"},
        {"symbol": "ASTERDM", "name": "Aster DM Healthcare"},
    ],
    "NSE FMCG & Consumer Goods": [
        {"symbol": "ITC", "name": "ITC Ltd"},
        {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd"},
        {"symbol": "NESTLEIND", "name": "Nestle India Ltd"},
        {"symbol": "BRITANNIA", "name": "Britannia Industries Ltd"},
        {"symbol": "TATACONSUM", "name": "Tata Consumer Products"},
        {"symbol": "VBL", "name": "Varun Beverages Ltd"},
        {"symbol": "DABUR", "name": "Dabur India Ltd"},
        {"symbol": "MARICO", "name": "Marico Ltd"},
        {"symbol": "GODREJCP", "name": "Godrej Consumer Products"},
        {"symbol": "COLPAL", "name": "Colgate-Palmolive India"},
        {"symbol": "UBL", "name": "United Breweries Ltd"},
        {"symbol": "MCDOWELL-N", "name": "United Spirits Ltd"},
        {"symbol": "EMAMILTD", "name": "Emami Ltd"},
        {"symbol": "RADICO", "name": "Radico Khaitan Ltd"},
        {"symbol": "JYOTHYLAB", "name": "Jyothy Labs Ltd"},
        {"symbol": "PATANJALI", "name": "Patanjali Foods Ltd"},
        {"symbol": "AWL", "name": "Adani Wilmar Ltd"},
        {"symbol": "BIKAJI", "name": "Bikaji Foods International"},
    ],
    "NSE Metals, Mining & Commodities": [
        {"symbol": "TATASTEEL", "name": "Tata Steel Ltd"},
        {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd"},
        {"symbol": "HINDALCO", "name": "Hindalco Industries Ltd"},
        {"symbol": "VEDL", "name": "Vedanta Ltd"},
        {"symbol": "NMDC", "name": "NMDC Ltd"},
        {"symbol": "JINDALSTEL", "name": "Jindal Steel & Power"},
        {"symbol": "NATIONALUM", "name": "National Aluminium Co"},
        {"symbol": "SAIL", "name": "Steel Authority of India"},
        {"symbol": "APLAPOLLO", "name": "APL Apollo Tubes Ltd"},
        {"symbol": "HINDZINC", "name": "Hindustan Zinc Ltd"},
        {"symbol": "RATNAMANI", "name": "Ratnamani Metals & Tubes"},
        {"symbol": "JSL", "name": "Jindal Stainless Ltd"},
        {"symbol": "HINDCOPPER", "name": "Hindustan Copper Ltd"},
        {"symbol": "MOIL", "name": "MOIL Ltd"},
    ],
    "NSE Infrastructure, Construction & Capital Goods": [
        {"symbol": "LT", "name": "Larsen & Toubro Ltd"},
        {"symbol": "BEL", "name": "Bharat Electronics Ltd"},
        {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"},
        {"symbol": "SIEMENS", "name": "Siemens Ltd"},
        {"symbol": "ABB", "name": "ABB India Ltd"},
        {"symbol": "CGPOWER", "name": "CG Power & Industrial Solution"},
        {"symbol": "BHEL", "name": "Bharat Heavy Electricals"},
        {"symbol": "DLF", "name": "DLF Ltd"},
        {"symbol": "LODHA", "name": "Macrotech Developers Ltd"},
        {"symbol": "GODREJPROP", "name": "Godrej Properties Ltd"},
        {"symbol": "PRESTIGE", "name": "Prestige Estates Projects"},
        {"symbol": "PHOENIXLTD", "name": "Phoenix Mills Ltd"},
        {"symbol": "TITAN", "name": "Titan Co Ltd"},
        {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd"},
        {"symbol": "BERGEPAINT", "name": "Berger Paints India Ltd"},
        {"symbol": "POLYCAB", "name": "Polycab India Ltd"},
        {"symbol": "KEI", "name": "KEI Industries Ltd"},
        {"symbol": "HAVELLS", "name": "Havells India Ltd"},
        {"symbol": "CROMPTON", "name": "Crompton Greaves Consumer"},
        {"symbol": "VOLTAS", "name": "Voltas Ltd"},
        {"symbol": "DIXON", "name": "Dixon Technologies Ltd"},
        {"symbol": "TRENT", "name": "Trent Ltd"},
        {"symbol": "ABFRL", "name": "Aditya Birla Fashion & Retail"},
        {"symbol": "KALYANKJIL", "name": "Kalyan Jewellers India"},
        {"symbol": "PIDILITIND", "name": "Pidilite Industries Ltd"},
    ],
    "NSE Telecom, Media & Internet": [
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd"},
        {"symbol": "IDEA", "name": "Vodafone Idea Ltd"},
        {"symbol": "NAUKRI", "name": "Info Edge (India) Ltd"},
        {"symbol": "ZOMATO", "name": "Zomato Ltd"},
        {"symbol": "PAYTM", "name": "One97 Communications Ltd"},
        {"symbol": "POLICYBZR", "name": "PB Fintech Ltd"},
        {"symbol": "NYKAA", "name": "FSN E-Commerce Ventures"},
        {"symbol": "DELHIVERY", "name": "Delhivery Ltd"},
        {"symbol": "MAPMYINDIA", "name": "C.E. Info Systems Ltd"},
        {"symbol": "SAREGAMA", "name": "Saregama India Ltd"},
        {"symbol": "SUNTV", "name": "Sun TV Network Ltd"},
        {"symbol": "ZEEL", "name": "Zee Entertainment Enterprise"},
        {"symbol": "AFFLE", "name": "Affle (India) Ltd"},
        {"symbol": "INDIAMART", "name": "IndiaMART InterMESH Ltd"},
    ],
    "NSE Chemicals, Fertilizers & Agriculture": [
        {"symbol": "SRF", "name": "SRF Ltd"},
        {"symbol": "UPL", "name": "UPL Ltd"},
        {"symbol": "AARTIIND", "name": "Aarti Industries Ltd"},
        {"symbol": "DEEPAKNTR", "name": "Deepak Nitrite Ltd"},
        {"symbol": "LINDEINDIA", "name": "Linde India Ltd"},
        {"symbol": "SOLARINDS", "name": "Solar Industries India"},
        {"symbol": "TATACHEM", "name": "Tata Chemicals Ltd"},
        {"symbol": "PIIND", "name": "PI Industries Ltd"},
        {"symbol": "CHAMBLFERT", "name": "Chambal Fertilisers & Chem"},
        {"symbol": "COROMANDEL", "name": "Coromandel International"},
        {"symbol": "SUMICHEM", "name": "Sumitomo Chemical India"},
        {"symbol": "ATUL", "name": "Atul Ltd"},
        {"symbol": "CLEAN", "name": "Clean Science & Technology"},
        {"symbol": "FINEORG", "name": "Fine Organic Industries"},
        {"symbol": "NAVINFLUOR", "name": "Navin Fluorine International"},
    ],
}

DEFAULT_STOCKS = ["TCS", "INFY", "RELIANCE", "HDFCBANK"]

# Flattened catalog containing all stocks across sectors
STOCK_CATALOG = [item for sector_list in STOCK_SECTORS.values() for item in sector_list]

BENCHMARK_CATALOG = {
    # Domestic (India)
    "nifty50": {"name": "NIFTY 50", "ticker": "^NSEI", "category": "india", "market": "NSE"},
    "niftybank": {"name": "NIFTY BANK", "ticker": "^NSEBANK", "category": "india", "market": "NSE"},
    "niftyit": {"name": "NIFTY IT", "ticker": "^CNXIT", "category": "india", "market": "NSE"},
    "sensex": {"name": "BSE SENSEX", "ticker": "^BSESN", "category": "india", "market": "BSE"},
    "niftymidcap": {"name": "NIFTY MIDCAP 100", "ticker": "^NSEMDCP50", "category": "india", "market": "NSE"},
    # Global, Commodities, Bonds & Crypto
    "sp500": {"name": "S&P 500", "ticker": "^GSPC", "category": "global", "market": "US"},
    "nasdaq": {"name": "NASDAQ Composite", "ticker": "^IXIC", "category": "global", "market": "US"},
    "nikkei": {"name": "Nikkei 225", "ticker": "^N225", "category": "global", "market": "JP"},
    "singapore": {"name": "STI Singapore", "ticker": "^STI", "category": "global", "market": "SG"},
    "gold": {"name": "Gold Futures", "ticker": "GC=F", "category": "global", "market": "COMMODITY"},
    "crudeoil": {"name": "Crude Oil (WTI)", "ticker": "CL=F", "category": "global", "market": "COMMODITY"},
    "us10y": {"name": "US 10Y Bond Yield", "ticker": "^TNX", "category": "global", "market": "US_BOND"},
    "bitcoin": {"name": "Bitcoin (USD)", "ticker": "BTC-USD", "category": "global", "market": "CRYPTO"},
}

DEFAULT_BENCHMARKS = ["nifty50", "niftybank", "niftyit", "sp500", "nasdaq", "nikkei", "singapore", "gold"]
DEFAULT_HIGHLIGHTED_BENCHMARK = "nifty50"

# Return windows used throughout analysis, as (label, calendar_days) pairs.
# Calendar days are converted to trading-day lookback when querying history.
RETURN_WINDOWS = [
    ("1D", 1),
    ("1W", 7),
    ("1M", 30),
    ("3M", 91),
    ("6M", 182),
    ("1Y", 365),
]

# Overridable so tests (and alternate deployments) can point at another file.
DB_PATH = os.environ.get("MARKET_MONITOR_DB", "market_monitor.db")

# How much daily history to backfill on first run, as a yfinance period string.
# Needs to exceed the longest RETURN_WINDOWS entry so 1Y returns resolve.
HISTORY_PERIOD = "2y"

TIMEZONE = "Asia/Kolkata"

# Scheduled report generation times (24h, local TIMEZONE)
# 9:00 AM, 12:00 PM, 3:00 PM, 9:00 PM
REPORT_SCHEDULE = {
    "morning": "09:00",
    "midday": "12:00",
    "pre_close": "15:00",
    "evening": "21:00",
}

