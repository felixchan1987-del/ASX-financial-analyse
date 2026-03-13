"""
ASX200 Local Report Server
Run this instead of opening the HTML file directly.
Serves the report at http://localhost:8765 with auto-refresh capability.

Usage:
    python server.py
Or double-click launch_report.bat
"""

import json
import os
import sys
import time
import threading
from datetime import datetime

from flask import Flask, jsonify, Response, request

# Allow imports from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asx50_analysis import get_asx200_tickers, fetch_company_data, generate_html
from portfolio import PortfolioManager
from manual_portfolio import ManualPortfolio
from news_analysis import fetch_sector_news, fetch_company_news, reassess_stock
from quant_analysis import fetch_quant_data

_portfolio = PortfolioManager()
_manual    = ManualPortfolio()

PORT = 8765
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asx200_cache.json")
CACHE_MAX_AGE = 3600  # seconds — auto-serve cached data if fresher than this

app = Flask(__name__)

_state = {
    "companies":        None,
    "sector_news":      None,
    "company_news":     None,
    "reassessments":    None,
    "quant_data":       None,
    "last_updated":     None,      # unix timestamp
    "refresh_running":  False,
    "refresh_progress": 0,
    "refresh_total":    0,
    "refresh_message":  "",
}
_lock = threading.Lock()


# ── Cache helpers ─────────────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("companies"), data.get("timestamp")
        except Exception:
            pass
    return None, None


def save_cache(companies):
    ts = time.time()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"companies": companies, "timestamp": ts}, f)
    return ts


# ── Background refresh ────────────────────────────────────────────────────────

def do_refresh():
    with _lock:
        if _state["refresh_running"]:
            return
        _state["refresh_running"]  = True
        _state["refresh_progress"] = 0
        _state["refresh_message"]  = "Fetching ASX200 list..."

    try:
        tickers, names, sectors = get_asx200_tickers()
        _state["refresh_total"] = len(tickers)
        companies = []
        for i, (tick, name, sector) in enumerate(zip(tickers, names, sectors)):
            _state["refresh_progress"] = i + 1
            _state["refresh_message"]  = f"Fetching {tick} ({i+1}/{len(tickers)})..."
            companies.append(fetch_company_data(tick, name, sector))

        ts = save_cache(companies)
        _state["companies"]    = companies
        _state["last_updated"] = ts
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Refresh complete — {len(companies)} companies")

        # Fetch sector news
        _state["refresh_message"] = "Fetching sector news..."
        try:
            sn = fetch_sector_news(force_refresh=True)
            _state["sector_news"] = sn
            print(f"[{datetime.now().strftime('%H:%M:%S')}] News refresh complete")
        except Exception as ne:
            print(f"News fetch error: {ne}")

        # Fetch company-specific news for Cheap/Fair reassessment
        _state["refresh_message"] = "Analysing company news..."
        try:
            cn = fetch_company_news(companies, force_refresh=True)
            _state["company_news"] = cn
            # Build reassessments
            reassessments = {}
            sn = _state.get("sector_news") or {}
            for c in companies:
                ticker = c.get("ticker", "")
                if ticker in cn and c.get("signal") in ("Cheap", "Fair"):
                    sector = c.get("sector", "")
                    sector_sent = sn.get(sector, {}).get("sentiment", "Neutral")
                    reassessments[ticker] = reassess_stock(c, cn[ticker], sector_sent)
            _state["reassessments"] = reassessments
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Reassessment complete — {len(reassessments)} stocks")
        except Exception as ce:
            print(f"Company news error: {ce}")

        # Compute quant analysis (technical indicators + risk metrics)
        _state["refresh_message"] = "Computing quant analysis..."
        try:
            def _qprog(msg):
                _state["refresh_message"] = msg
            qd = fetch_quant_data(companies, force_refresh=True, progress_cb=_qprog)
            _state["quant_data"] = qd
            n_bull = sum(1 for k, v in qd.items()
                         if not k.startswith("_") and isinstance(v, dict)
                         and v.get("quant_label") in ("Bullish", "Lean Bullish"))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Quant analysis complete — {n_bull} bullish signals")
        except Exception as qe:
            print(f"Quant analysis error: {qe}")

        # Update mock portfolio after every data refresh
        try:
            _portfolio.update(companies)
        except Exception as pe:
            print(f"Portfolio update error: {pe}")

        # Reprice manual portfolio
        try:
            if _manual.state:
                _manual.reprice(companies)
        except Exception as me:
            print(f"Manual portfolio reprice error: {me}")
    except Exception as e:
        _state["refresh_message"] = f"Error: {e}"
        print(f"Refresh error: {e}")
    finally:
        _state["refresh_running"] = False


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    companies = _state["companies"]

    # Try loading from cache if nothing in memory
    if companies is None:
        cached, ts = load_cache()
        if cached:
            _state["companies"]    = cached
            _state["last_updated"] = ts
            companies = cached
            print(f"Loaded cache from disk ({len(cached)} companies)")

    # Still nothing — trigger a background fetch and show loading page
    if companies is None:
        if not _state["refresh_running"]:
            t = threading.Thread(target=do_refresh, daemon=True)
            t.start()
        return Response(LOADING_HTML, mimetype="text/html")

    ts  = _state.get("last_updated")
    lu  = datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M") if ts else None
    pf  = _portfolio.get_summary()
    # Reprice manual holdings with latest market data before rendering
    if _manual.state and companies:
        try:
            _manual.reprice(companies)
        except Exception:
            pass
    mp  = _manual.get_summary()
    sn  = _state.get("sector_news")
    cn  = _state.get("company_news")
    ra  = _state.get("reassessments")
    qd  = _state.get("quant_data")
    html = generate_html(companies, last_updated=lu, portfolio_summary=pf,
                         sector_news=sn, company_news=cn, reassessments=ra,
                         manual_summary=mp, quant_data=qd)
    return Response(html, mimetype="text/html")


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if not _state["refresh_running"]:
        t = threading.Thread(target=do_refresh, daemon=True)
        t.start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def api_status():
    ts  = _state.get("last_updated")
    age = int((time.time() - ts) / 60) if ts else None
    lu  = datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M") if ts else None
    return jsonify({
        "refresh_running":  _state["refresh_running"],
        "refresh_progress": _state["refresh_progress"],
        "refresh_total":    _state["refresh_total"],
        "refresh_message":  _state["refresh_message"],
        "last_updated":     lu,
        "age_minutes":      age,
    })


# ── Manual trading API ────────────────────────────────────────────────────────

@app.route("/api/manual/buy", methods=["POST"])
def api_manual_buy():
    if not _manual.state:
        _manual.initialize()
    companies = _state.get("companies")
    if not companies:
        return jsonify({"ok": False, "msg": "Market data not loaded yet. Wait for first refresh."}), 400
    data = request.get_json(silent=True) or {}
    ticker = data.get("ticker", "").strip().upper()
    amount = data.get("amount", 0)
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "Invalid amount"}), 400

    # Find the company — company dicts store ticker without .AX suffix
    by_ticker = {c["ticker"]: c for c in companies}
    raw_ticker = ticker.replace(".AX", "")
    c = by_ticker.get(raw_ticker)
    if not c:
        return jsonify({"ok": False, "msg": "Ticker {} not found in ASX200".format(ticker)}), 400
    price = c.get("price")
    if not price:
        return jsonify({"ok": False, "msg": "No price data for {}".format(ticker)}), 400

    # Store with .AX suffix in manual portfolio for consistency
    store_ticker = raw_ticker + ".AX"
    ok, msg = _manual.buy(store_ticker, amount, price, c.get("name", ""))
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/manual/sell", methods=["POST"])
def api_manual_sell():
    if not _manual.state:
        return jsonify({"ok": False, "msg": "Portfolio not initialized"}), 400
    companies = _state.get("companies")
    if not companies:
        return jsonify({"ok": False, "msg": "Market data not loaded yet."}), 400
    data = request.get_json(silent=True) or {}
    ticker = data.get("ticker", "").strip().upper()
    shares = data.get("shares", "all")

    # Company dicts store ticker without .AX; manual portfolio uses .AX
    raw_ticker = ticker.replace(".AX", "")
    store_ticker = raw_ticker + ".AX"

    by_ticker = {c["ticker"]: c for c in companies}
    c = by_ticker.get(raw_ticker)
    price = c.get("price") if c else None
    if not price:
        # Fall back to holding's last known price
        h = _manual.state.get("holdings", {}).get(store_ticker)
        if h:
            price = h.get("current_price")
    if not price:
        return jsonify({"ok": False, "msg": "No price for {}".format(ticker)}), 400

    ok, msg = _manual.sell(store_ticker, shares, price)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/manual/holdings")
def api_manual_holdings():
    if not _manual.state:
        _manual.initialize()
    return jsonify(_manual.get_summary())


# ── Loading page (shown before first fetch completes) ─────────────────────────

LOADING_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>ASX200 — Loading...</title>
<style>
  body { font-family: -apple-system, sans-serif; background: #f4f6f9;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; margin: 0; }
  .box { background: #fff; border-radius: 12px; padding: 40px 48px;
         box-shadow: 0 4px 20px rgba(0,0,0,.1); text-align: center; max-width: 480px; }
  h2 { color: #1a3a5c; margin-bottom: 10px; }
  p  { color: #666; font-size: 14px; }
  .bar-wrap { background: #e0e6ed; border-radius: 8px; height: 8px; margin: 20px 0; overflow: hidden; }
  .bar { background: #2980b9; height: 8px; border-radius: 8px; transition: width .5s; }
  #msg { font-size: 13px; color: #555; min-height: 20px; }
</style>
</head>
<body>
<div class="box">
  <h2>Fetching ASX200 data&hellip;</h2>
  <p>Pulling live financials from Yahoo Finance for ~200 companies.<br>This takes about 8 minutes on first run.</p>
  <div class="bar-wrap"><div class="bar" id="bar" style="width:0%"></div></div>
  <div id="msg">Starting&hellip;</div>
</div>
<script>
function poll() {
  fetch('/api/status').then(r => r.json()).then(d => {
    var pct = d.refresh_total > 0 ? Math.round(d.refresh_progress / d.refresh_total * 100) : 5;
    document.getElementById('bar').style.width = pct + '%';
    document.getElementById('msg').textContent = d.refresh_message || 'Working...';
    if (!d.refresh_running && d.last_updated) {
      location.reload();
    } else {
      setTimeout(poll, 1500);
    }
  }).catch(() => setTimeout(poll, 3000));
}
setTimeout(poll, 1000);
</script>
</body></html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  ASX200 Valuation Report Server")
    print(f"  http://localhost:{PORT}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)

    # Pre-load market data cache if fresh enough
    cached, ts = load_cache()
    age = (time.time() - ts) if ts else None
    if cached and age is not None and age < CACHE_MAX_AGE:
        _state["companies"]    = cached
        _state["last_updated"] = ts
        lu = datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")
        print(f"  Loaded market data from {lu} ({int(age/60)} min old)")
    else:
        print("  No fresh cache — market data will be fetched when browser opens")

    # Pre-load news cache if available
    try:
        sn = fetch_sector_news()  # loads from cache if < 6hr old
        _state["sector_news"] = sn
        macro_sent = sn.get("_macro", {}).get("sentiment", "N/A")
        print(f"  News loaded: macro sentiment = {macro_sent}")
    except Exception as ne:
        print(f"  News cache not available: {ne}")

    # Pre-load company news + reassessments from cache if available
    if cached:
        try:
            cn = fetch_company_news(cached)  # loads from cache if < 6hr old
            _state["company_news"] = cn
            sn = _state.get("sector_news") or {}
            reassessments = {}
            for c in cached:
                ticker = c.get("ticker", "")
                if ticker in cn and c.get("signal") in ("Cheap", "Fair"):
                    sector = c.get("sector", "")
                    sector_sent = sn.get(sector, {}).get("sentiment", "Neutral")
                    reassessments[ticker] = reassess_stock(c, cn[ticker], sector_sent)
            _state["reassessments"] = reassessments
            print(f"  Company news loaded: {len(reassessments)} reassessments")
        except Exception as ce:
            print(f"  Company news cache not available: {ce}")

    # Pre-load quant analysis from cache if available
    if cached:
        try:
            qd = fetch_quant_data(cached)  # loads from cache if < 4hr old
            _state["quant_data"] = qd
            n_bull = sum(1 for k, v in qd.items()
                         if not k.startswith("_") and isinstance(v, dict)
                         and v.get("quant_label") in ("Bullish", "Lean Bullish"))
            print(f"  Quant data loaded: {n_bull} bullish signals")
        except Exception as qe:
            print(f"  Quant cache not available: {qe}")

    # Load or initialise portfolio
    if _portfolio.load():
        ps = _portfolio.get_summary()
        print(f"  Portfolio loaded: value A${ps['total_value']:,.2f} "
              f"({'+' if ps['cum_pnl']>=0 else ''}A${ps['cum_pnl']:,.2f}), "
              f"{ps['n_holdings']} holdings")
        # If market data is ready but portfolio hasn't been updated today, update it now
        if cached and _portfolio.state:
            today = datetime.now().strftime("%Y-%m-%d")
            last_hist = (_portfolio.state.get("daily_history") or [{}])[-1].get("date", "")
            if last_hist != today:
                print("  Updating portfolio with today's prices...")
                _portfolio.update(cached)
    elif cached:
        print("  No portfolio found — initialising with current market data...")
        _portfolio.initialize(cached)
    else:
        print("  Portfolio will be initialised on first data fetch")

    # Load or initialise manual portfolio
    if _manual.load():
        ms = _manual.get_summary()
        print(f"  Manual portfolio loaded: value A${ms['total_value']:,.2f}, "
              f"{ms['n_holdings']} holdings")
        if cached and _manual.state:
            _manual.reprice(cached)
    else:
        _manual.initialize()
        print("  Manual portfolio initialised (A$10,000 cash)")

    # Open browser after a short delay
    import webbrowser
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
