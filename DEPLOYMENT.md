# Cloud Hosting & Deployment Guide

This step-by-step guide explains how an end user or reviewer can host the **NSE India Market Monitor & Analytics Dashboard** on **Render** (or **Railway**) for 24/7 online access.

---

## Method 1: Deploy on Render.com (Recommended Free Hosting)

Render provides free hosting for Python web applications connected directly to GitHub.

### Step 1: Fork or Access the GitHub Repository
Ensure you have access to the repository:
[https://github.com/AdG1382/nse-market-monitor](https://github.com/AdG1382/nse-market-monitor)

*(If you are deploying from your own GitHub account, fork the repository to your account first).*

---

### Step 2: Sign Up / Log In to Render
1. Go to [Render.com](https://render.com/).
2. Click **Sign Up** or **Log In**.
3. Choose **Continue with GitHub** to authorize Render to access your repositories.

---

### Step 3: Create a New Web Service
1. On the Render Dashboard, click the **New +** button in the top right corner.
2. Select **Web Service**.
3. Under **Connect a repository**, find `nse-market-monitor` (or your forked repository) and click **Connect**.

---

### Step 4: Configure Deployment Settings
Fill out the configuration fields with the following exact settings:

| Setting | Value | Notes |
| :--- | :--- | :--- |
| **Name** | `nse-market-monitor` | Choose any unique name for your URL |
| **Region** | Singapore / Frankfurt / Oregon | Choose the region closest to India (e.g., Singapore) |
| **Branch** | `main` | Primary deployment branch |
| **Root Directory** | *(Leave blank)* | Uses project root |
| **Runtime** | `Python 3` | Built for Python 3.10+ |
| **Build Command** | `pip install -r requirements.txt` | Installs FastHTML, Pandas, OpenPyXL, etc. |
| **Start Command** | `python app.py` | Launches FastHTML server on port 5001 |
| **Instance Type** | **Free** | $0.00 / month |

---

### Step 5: Deploy the Application
1. Scroll down and click **Create Web Service**.
2. Render will automatically clone your repository, install dependencies, and start the app.
3. You can watch the real-time build logs in the deployment window.
4. Once completed, Render will display a green **Live** badge alongside your public URL:
   `https://nse-market-monitor.onrender.com`

---

## Method 2: Deploy on Railway.app (Alternative 1-Click Cloud Hosting)

Railway is an alternative zero-config cloud host.

1. Sign up at [Railway.app](https://railway.app/).
2. Click **New Project** $\rightarrow$ **Deploy from GitHub repo**.
3. Select `AdG1382/nse-market-monitor`.
4. Railway will automatically detect the Python application, execute `pip install -r requirements.txt`, and generate a public domain link.

---

## Frequently Asked Questions & Tips

### 1. Free Tier Spin-Down / Delay on First Request
On Render's free tier, the web service spins down after 15 minutes of inactivity. When a reviewer visits the URL after a period of idle time, the first request may take 30–50 seconds while the instance boots up. Subsequent requests will be instantaneous.

### 2. Market Snapshot Data Persistence
The app uses a lightweight SQLite database (`market_monitor.db`) running in Write-Ahead Logging (WAL) mode to record stock price snapshots and user preferences locally. On ephemeral free cloud tiers, SQLite data resets if the instance restarts. For production persistent storage, attach a free Render Persistent Disk to `/home/aditya/nsepython/market_monitor.db` or use a managed database service.

### 3. Background Scheduler
The background scheduler (`scheduler.py`) automatically runs inside the application container at **9:00 AM, 12:00 PM, 3:00 PM, and 9:00 PM IST** to record market sessions without requiring external cron setup.

---

## Verification Checklist for Reviewer

Once deployed, verify the following core features on your live URL:

- [ ] **Home Dashboard**: Loads live NSE market index rates and stock return tables cleanly without horizontal scrollbars on desktop or tablet.
- [ ] **Highlighted Benchmark**: Pin row #1 (e.g. NIFTY 50) and toggle between **Absolute %**, **Relative vs Benchmark %**, or **Both**.
- [ ] **Sector Grouping**: Navigate to sector modal `/modal/stocks` to view Top 200 NSE stocks grouped across 10 sector buckets.
- [ ] **Data Export**: Click **Export CSV** or **Export Excel** to confirm that downloaded files accurately omit unselected metric columns.
