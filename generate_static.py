"""
Generate a static HTML snapshot of the ASX200 Valuation Report.
Used by GitHub Actions to publish to GitHub Pages (docs/index.html).

Usage:
    python generate_static.py
"""

import json
import os
import sys
import time
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asx50_analysis import get_asx200_tickers, fetch_company_data, generate_html
from news_analysis import fetch_sector_news, fetch_company_news, reassess_stock
from quant_analysis import fetch_quant_data

DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(DIR, "asx200_cache.json")
DOCS_DIR = os.path.join(DIR, "docs")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    # 1. Fetch company data
    log("Fetching ASX200 ticker list...")
    tickers, names, sectors = get_asx200_tickers()
    log(f"Got {len(tickers)} tickers — fetching financials...")

    companies = []
    for i, (tick, name, sector) in enumerate(zip(tickers, names, sectors)):
        if (i + 1) % 20 == 0 or i == 0:
            log(f"  {tick} ({i+1}/{len(tickers)})")
        companies.append(fetch_company_data(tick, name, sector))

    ts = time.time()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"companies": companies, "timestamp": ts}, f)
    log(f"Fetched {len(companies)} companies")

    # 2. Sector news
    log("Fetching sector news...")
    try:
        sector_news = fetch_sector_news(force_refresh=True)
    except Exception as e:
        log(f"  Sector news error: {e}")
        sector_news = {}

    # 3. Company news + reassessments
    log("Fetching company news...")
    try:
        company_news = fetch_company_news(companies, force_refresh=True)
        reassessments = {}
        for c in companies:
            ticker = c.get("ticker", "")
            if ticker in company_news and c.get("signal") in ("Cheap", "Fair"):
                sect = c.get("sector", "")
                sect_sent = sector_news.get(sect, {}).get("sentiment", "Neutral")
                reassessments[ticker] = reassess_stock(c, company_news[ticker], sect_sent)
        log(f"  {len(reassessments)} reassessments")
    except Exception as e:
        log(f"  Company news error: {e}")
        company_news, reassessments = {}, {}

    # 4. Quant analysis
    log("Computing quant analysis...")
    try:
        quant_data = fetch_quant_data(companies, force_refresh=True,
                                       progress_cb=lambda m: None)
    except Exception as e:
        log(f"  Quant error: {e}")
        quant_data = {}

    # 5. Generate HTML
    lu = datetime.fromtimestamp(ts).strftime("%d %b %Y %H:%M")
    html = generate_html(companies, last_updated=lu,
                         sector_news=sector_news,
                         company_news=company_news,
                         reassessments=reassessments,
                         quant_data=quant_data)

    # 6. Patch the refresh button for static hosting
    html = html.replace(
        '<button id="refresh-btn" onclick="triggerRefresh()">&#x21bb; Refresh Data</button>',
        '<button id="refresh-btn" disabled style="opacity:.5;cursor:default">'
        '&#x1f4f8; Static Snapshot &mdash; updates daily at 4:30 PM AEST</button>'
    )
    # Remove the triggerRefresh / pollRefreshStatus JS
    html = re.sub(
        r'// ── Auto-refresh.*?(?=// ──|\Z)',
        '// Refresh disabled in static build\n',
        html, count=1, flags=re.DOTALL
    )

    out = os.path.join(DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"Static report written to {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
