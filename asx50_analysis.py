"""
ASX200 Valuation Analysis
Fetches financial data for ASX200 constituents and generates an HTML report.
"""

import json
import math
import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd

REPORT_DATE = datetime.date.today().strftime("%d %B %Y")
DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. Fetch ASX200 constituents from Wikipedia ──────────────────────────────

def get_asx200_tickers():
    """Scrape ASX200 list from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/S%26P/ASX_200"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ASX-Research/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table", {"class": "wikitable"})
        tickers = []
        names = []
        sectors = []
        # The ASX200 constituents table has columns: Code | Company | Sector | ...
        for table in tables:
            header_row = table.find("tr")
            if not header_row:
                continue
            hdrs = [h.get_text(strip=True).lower() for h in header_row.find_all(["th", "td"])]
            if "code" not in hdrs:
                continue
            code_idx = hdrs.index("code")
            comp_idx = hdrs.index("company") if "company" in hdrs else code_idx + 1
            sect_idx = hdrs.index("sector") if "sector" in hdrs else comp_idx + 1
            rows = table.find_all("tr")[1:]
            for row in rows:
                cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cols) > max(code_idx, comp_idx, sect_idx):
                    tick = cols[code_idx]
                    if tick and 1 <= len(tick) <= 5:
                        tickers.append(tick + ".AX")
                        # Strip Wikipedia citation refs like [17]
                        names.append(re.sub(r"\[\d+\]", "", cols[comp_idx]).strip())
                        sectors.append(re.sub(r"\[\d+\]", "", cols[sect_idx]).strip())
        if tickers:
            print(f"  Found {len(tickers)} tickers from Wikipedia")
            return tickers, names, sectors
    except Exception as e:
        print(f"  Wikipedia scrape failed: {e}")

    # Fallback: hardcoded ASX200 as of March 2026
    print("  Using hardcoded ASX200 list")
    data = [
        ("A2M", "a2 Milk Company", "Consumer Staples"),
        ("ABC", "Adbri", "Materials"),
        ("ABP", "Abacus Property Group", "Real Estate"),
        ("AGL", "AGL Energy", "Utilities"),
        ("AIA", "Auckland Airport", "Industrials"),
        ("AKE", "Allkem", "Materials"),
        ("ALD", "Ampol", "Energy"),
        ("ALL", "Aristocrat Leisure", "Consumer Discretionary"),
        ("ALQ", "ALS", "Industrials"),
        ("ALU", "Altium", "Information Technology"),
        ("ALX", "Atlas Arteria", "Industrials"),
        ("AMC", "Amcor", "Materials"),
        ("AMP", "AMP", "Financials"),
        ("ANN", "Ansell", "Healthcare"),
        ("ANZ", "ANZ Banking Group", "Financials"),
        ("APA", "APA Group", "Utilities"),
        ("APE", "Eagers Automotive", "Consumer Discretionary"),
        ("SQ2", "Block Inc. CDI", "Information Technology"),
        ("ARB", "ARB Corporation", "Consumer Discretionary"),
        ("ARF", "Arena REIT", "Real Estate"),
        ("ASX", "ASX", "Financials"),
        ("AUB", "AUB Group", "Financials"),
        ("AWC", "Alumina", "Materials"),
        ("AZJ", "Aurizon", "Industrials"),
        ("BAP", "Bapcor", "Consumer Discretionary"),
        ("BEN", "Bendigo & Adelaide Bank", "Financials"),
        ("BGA", "Bega Cheese", "Consumer Staples"),
        ("BHP", "BHP Group", "Materials"),
        ("BKL", "Blackmores", "Consumer Staples"),
        ("BKW", "Brickworks", "Materials"),
        ("BLD", "Boral", "Materials"),
        ("BOQ", "Bank of Queensland", "Financials"),
        ("BPT", "Beach Energy", "Energy"),
        ("BRG", "Breville Group", "Consumer Discretionary"),
        ("BSL", "BlueScope Steel", "Materials"),
        ("BWP", "BWP Trust", "Real Estate"),
        ("BXB", "Brambles", "Industrials"),
        ("CAR", "CAR Group", "Communication Services"),
        ("CBA", "Commonwealth Bank", "Financials"),
        ("CCP", "Credit Corp Group", "Financials"),
        ("CGC", "Costa Group", "Consumer Staples"),
        ("CGF", "Challenger", "Financials"),
        ("CHC", "Charter Hall", "Real Estate"),
        ("CHN", "Chalice Mining", "Materials"),
        ("CIA", "Champion Iron", "Materials"),
        ("CIP", "Centuria Industrial REIT", "Real Estate"),
        ("CKF", "Collins Foods", "Consumer Discretionary"),
        ("CLW", "Charter Hall Long WALE REIT", "Real Estate"),
        ("CMW", "Cromwell Property Group", "Real Estate"),
        ("CNI", "Centuria Capital", "Real Estate"),
        ("COH", "Cochlear", "Healthcare"),
        ("COL", "Coles Group", "Consumer Staples"),
        ("CPU", "Computershare", "Information Technology"),
        ("CRN", "Coronado Global Resources", "Materials"),
        ("CQR", "Charter Hall Retail REIT", "Real Estate"),
        ("CSL", "CSL", "Healthcare"),
        ("CTD", "Corporate Travel Management", "Consumer Discretionary"),
        ("CWY", "Cleanaway", "Industrials"),
        ("DEG", "De Grey Mining", "Materials"),
        ("DHG", "Domain Group", "Communication Services"),
        ("DMP", "Domino's Pizza Enterprises", "Consumer Discretionary"),
        ("DOW", "Downer Group", "Industrials"),
        ("DRR", "Deterra Royalties", "Materials"),
        ("DXS", "Dexus", "Real Estate"),
        ("EDV", "Endeavour Group", "Consumer Staples"),
        ("ELD", "Elders", "Consumer Staples"),
        ("EVN", "Evolution Mining", "Materials"),
        ("EVT", "Event Hospitality and Entertainment", "Communication Services"),
        ("FBU", "Fletcher Building", "Industrials"),
        ("FLT", "Flight Centre", "Consumer Discretionary"),
        ("FMG", "Fortescue", "Materials"),
        ("FPH", "Fisher & Paykel Healthcare", "Healthcare"),
        ("GMG", "Goodman Group", "Real Estate"),
        ("GNC", "GrainCorp", "Consumer Staples"),
        ("GOR", "Gold Road Resources", "Materials"),
        ("GOZ", "Growthpoint Properties", "Real Estate"),
        ("GPT", "GPT Group", "Real Estate"),
        ("GUD", "GUD Holdings", "Consumer Discretionary"),
        ("HDN", "HomeCo Daily Needs REIT", "Real Estate"),
        ("HLS", "Healius", "Healthcare"),
        ("HMC", "Home Consortium", "Real Estate"),
        ("HUB", "HUB24", "Financials"),
        ("HVN", "Harvey Norman", "Consumer Discretionary"),
        ("IAG", "Insurance Australia Group", "Financials"),
        ("IEL", "IDP Education", "Consumer Discretionary"),
        ("IFL", "Insignia Financial", "Financials"),
        ("IGO", "Independence Group", "Materials"),
        ("ILU", "Iluka Resources", "Materials"),
        ("INA", "Ingenia Group", "Real Estate"),
        ("ING", "Inghams", "Consumer Staples"),
        ("IPH", "IPH", "Industrials"),
        ("IPL", "Incitec Pivot", "Materials"),
        ("JBH", "JB Hi-Fi", "Consumer Discretionary"),
        ("JHG", "Janus Henderson", "Financials"),
        ("JHX", "James Hardie", "Materials"),
        ("KLS", "Kelsian Group", "Industrials"),
        ("LLC", "Lendlease", "Real Estate"),
        ("LNK", "Link Admin", "Information Technology"),
        ("LTR", "Liontown Resources", "Materials"),
        ("LYC", "Lynas Rare Earths", "Materials"),
        ("MFG", "Magellan Financial Group", "Financials"),
        ("MGR", "Mirvac", "Real Estate"),
        ("MIN", "Mineral Resources", "Materials"),
        ("MP1", "Megaport", "Information Technology"),
        ("MPL", "Medibank", "Financials"),
        ("MQG", "Macquarie Group", "Financials"),
        ("MTS", "Metcash", "Consumer Staples"),
        ("NAB", "National Australia Bank", "Financials"),
        ("NAN", "Nanosonics", "Healthcare"),
        ("NCM", "Newcrest Mining", "Materials"),
        ("NEC", "Nine Entertainment", "Communication Services"),
        ("NHC", "New Hope", "Energy"),
        ("NHF", "Nib Holdings", "Financials"),
        ("NIC", "Nickel Industries", "Materials"),
        ("NSR", "National Storage REIT", "Real Estate"),
        ("NST", "Northern Star Resources", "Materials"),
        ("NUF", "Nufarm", "Materials"),
        ("NWL", "Netwealth Group", "Financials"),
        ("NWS", "News Corp", "Communication Services"),
        ("NXT", "NextDC", "Information Technology"),
        ("ORA", "Orora", "Materials"),
        ("ORG", "Origin Energy", "Utilities"),
        ("ORI", "Orica", "Materials"),
        ("PDN", "Paladin Energy", "Energy"),
        ("PLS", "Pilbara Minerals", "Materials"),
        ("PME", "Pro Medicus", "Healthcare"),
        ("PMV", "Premier Investments", "Consumer Discretionary"),
        ("PNI", "Pinnacle Investment Management", "Financials"),
        ("PPT", "Perpetual", "Financials"),
        ("PRU", "Perseus Mining", "Materials"),
        ("QAN", "Qantas", "Industrials"),
        ("QBE", "QBE Insurance", "Financials"),
        ("QUB", "Qube Holdings", "Industrials"),
        ("REA", "REA Group", "Communication Services"),
        ("REH", "Reece Group", "Industrials"),
        ("RHC", "Ramsay Health Care", "Healthcare"),
        ("RIO", "Rio Tinto", "Materials"),
        ("RMD", "ResMed", "Healthcare"),
        ("RMS", "Ramelius Resources", "Materials"),
        ("RRL", "Regis Resources", "Materials"),
        ("RWC", "Reliance Worldwide Corporation", "Industrials"),
        ("S32", "South32", "Materials"),
        ("SCG", "Scentre Group", "Real Estate"),
        ("SCP", "SCA Property Group", "Real Estate"),
        ("SDF", "Steadfast Group", "Financials"),
        ("SEK", "Seek", "Communication Services"),
        ("SFR", "Sandfire Resources", "Materials"),
        ("SGM", "Sims Metal", "Materials"),
        ("SGP", "Stockland", "Real Estate"),
        ("SGR", "Star Entertainment Group", "Consumer Discretionary"),
        ("SHL", "Sonic Healthcare", "Healthcare"),
        ("SLR", "Silver Lake Resources", "Materials"),
        ("SOL", "Soul Patts", "Energy"),
        ("STO", "Santos", "Energy"),
        ("SUL", "Super Retail Group", "Consumer Discretionary"),
        ("SUN", "Suncorp", "Financials"),
        ("SVW", "Seven Group Holdings", "Industrials"),
        ("TLX", "Telix Pharmaceuticals", "Healthcare"),
        ("TAH", "Tabcorp", "Consumer Discretionary"),
        ("TCL", "Transurban", "Industrials"),
        ("TLC", "The Lottery Corporation", "Consumer Discretionary"),
        ("TLS", "Telstra", "Communication Services"),
        ("TNE", "TechnologyOne", "Information Technology"),
        ("TPG", "TPG Telecom", "Communication Services"),
        ("TWE", "Treasury Wine Estates", "Consumer Staples"),
        ("VCX", "Vicinity Centres", "Real Estate"),
        ("VEA", "Viva Energy", "Energy"),
        ("WBC", "Westpac", "Financials"),
        ("WEB", "Webjet", "Consumer Discretionary"),
        ("WES", "Wesfarmers", "Consumer Discretionary"),
        ("WHC", "Whitehaven Coal", "Energy"),
        ("WOR", "Worley", "Energy"),
        ("WOW", "Woolworths", "Consumer Staples"),
        ("WDS", "Woodside Energy", "Energy"),
        ("WPR", "Waypoint REIT", "Real Estate"),
        ("WTC", "Wisetech Global", "Information Technology"),
        ("XRO", "Xero", "Information Technology"),
        ("ZIP", "Zip", "Financials"),
    ]
    tickers  = [d[0] + ".AX" for d in data]
    names    = [d[1] for d in data]
    sectors  = [d[2] for d in data]
    return tickers, names, sectors

# Backwards compatibility alias
get_asx50_tickers = get_asx200_tickers


# ── 2. Fetch financial data ───────────────────────────────────────────────────

def safe_get(info, *keys, default=None):
    for k in keys:
        v = info.get(k)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            return v
    return default

def fmt_b(val):
    """Format a number in billions, or '—'."""
    if val is None:
        return "—"
    try:
        v = float(val)
        if abs(v) >= 1e12:
            return f"${v/1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"${v/1e9:.2f}B"
        if abs(v) >= 1e6:
            return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"
    except Exception:
        return "—"

def fmt_pct(val):
    if val is None:
        return "—"
    try:
        return f"{float(val)*100:.1f}%"
    except Exception:
        return "—"

def fmt_x(val, dp=1):
    if val is None:
        return "—"
    try:
        return f"{float(val):.{dp}f}x"
    except Exception:
        return "—"

def fmt_num(val, dp=1):
    if val is None:
        return "—"
    try:
        return f"{float(val):.{dp}f}"
    except Exception:
        return "—"

def valuation_signal(pe, pb, div_yield, ev_ebitda):
    """Traffic-light signal: Cheap / Fair / Expensive / N/A, plus driver reasons."""
    score = 0
    count = 0
    bullish = []   # metrics supporting cheap
    bearish = []   # metrics supporting expensive

    if pe is not None:
        count += 1
        if   pe < 12:  score += 2; bullish.append(f"Low P/E of {pe:.1f}x (below 12x threshold)")
        elif pe < 20:  score += 1
        elif pe > 30:  score -= 1; bearish.append(f"High P/E of {pe:.1f}x (above 30x premium)")
    if pb is not None:
        count += 1
        if   pb < 1.5: score += 2; bullish.append(f"Low P/B of {pb:.2f}x (below 1.5x threshold)")
        elif pb < 3:   score += 1
        elif pb > 5:   score -= 1; bearish.append(f"High P/B of {pb:.1f}x (above 5x premium)")
    if div_yield is not None:
        count += 1
        dy = div_yield * 100
        if   dy > 5:   score += 2; bullish.append(f"High yield of {dy:.1f}% (above 5% threshold)")
        elif dy > 3:   score += 1; bullish.append(f"Solid yield of {dy:.1f}%")
    if ev_ebitda is not None:
        count += 1
        if   ev_ebitda < 8:  score += 2; bullish.append(f"Low EV/EBITDA of {ev_ebitda:.1f}x (below 8x threshold)")
        elif ev_ebitda < 15: score += 1
        elif ev_ebitda > 25: score -= 1; bearish.append(f"High EV/EBITDA of {ev_ebitda:.1f}x (above 25x premium)")

    if count == 0:
        return "N/A", "#888888", []
    avg = score / count
    if   avg >= 1.5: return "Cheap",     "#27ae60", bullish
    elif avg >= 0.5: return "Fair",       "#f39c12", []
    else:            return "Expensive",  "#e74c3c", bearish

def fetch_company_data(ticker_ax, name_fallback, sector_fallback):
    try:
        tk = yf.Ticker(ticker_ax)
        info = tk.info or {}

        company_name  = safe_get(info, "longName", "shortName", default=name_fallback)
        sector        = safe_get(info, "sector",   default=sector_fallback)
        industry      = safe_get(info, "industry", default="")
        currency      = safe_get(info, "currency", default="AUD")
        price         = safe_get(info, "currentPrice", "regularMarketPrice", "previousClose")
        mkt_cap       = safe_get(info, "marketCap")
        pe_trailing   = safe_get(info, "trailingPE")
        pe_forward    = safe_get(info, "forwardPE")
        pb            = safe_get(info, "priceToBook")
        ev_ebitda     = safe_get(info, "enterpriseToEbitda")
        ev            = safe_get(info, "enterpriseValue")
        revenue       = safe_get(info, "totalRevenue")
        ebitda        = safe_get(info, "ebitda")
        net_income    = safe_get(info, "netIncomeToCommon")
        fcf           = safe_get(info, "freeCashflow")
        div_yield     = safe_get(info, "dividendYield")
        div_rate      = safe_get(info, "dividendRate")
        # yfinance 1.2+ returns dividendYield as a percentage (6.44 = 6.44%)
        # for ASX tickers rather than a decimal (0.0644).  Detect and normalise
        # by cross-checking against dividendRate / price.
        if div_yield is not None:
            _p = safe_get(info, "currentPrice", "regularMarketPrice", "previousClose")
            _r = div_rate
            if _p and _r and _p > 0:
                _expected_dec = _r / _p          # always a decimal (e.g. 0.0644)
                if div_yield > _expected_dec * 5:  # way above → percentage form
                    div_yield = div_yield / 100
            elif div_yield > 1:
                div_yield = div_yield / 100      # fallback heuristic
        payout_ratio  = safe_get(info, "payoutRatio")
        debt          = safe_get(info, "totalDebt")
        equity        = safe_get(info, "bookValue")        # per share
        shares        = safe_get(info, "sharesOutstanding")
        beta          = safe_get(info, "beta")
        eps_ttm       = safe_get(info, "trailingEps")
        roe           = safe_get(info, "returnOnEquity")
        roa           = safe_get(info, "returnOnAssets")
        gross_margin  = safe_get(info, "grossMargins")
        op_margin     = safe_get(info, "operatingMargins")
        net_margin    = safe_get(info, "profitMargins")
        revenue_growth= safe_get(info, "revenueGrowth")
        earnings_growth=safe_get(info, "earningsGrowth")
        week52_high   = safe_get(info, "fiftyTwoWeekHigh")
        week52_low    = safe_get(info, "fiftyTwoWeekLow")
        target_price  = safe_get(info, "targetMeanPrice")

        # % from 52-week high
        pct_from_high = None
        if price and week52_high:
            pct_from_high = (price - week52_high) / week52_high * 100

        # Upside to analyst target
        upside = None
        if price and target_price:
            upside = (target_price - price) / price * 100

        signal, signal_color, reasons = valuation_signal(pe_trailing, pb, div_yield, ev_ebitda)

        return {
            "ticker":         ticker_ax.replace(".AX", ""),
            "name":           company_name,
            "sector":         sector or sector_fallback,
            "industry":       industry,
            "currency":       currency,
            "price":          price,
            "mkt_cap":        mkt_cap,
            "pe_trailing":    pe_trailing,
            "pe_forward":     pe_forward,
            "pb":             pb,
            "ev_ebitda":      ev_ebitda,
            "ev":             ev,
            "revenue":        revenue,
            "ebitda":         ebitda,
            "net_income":     net_income,
            "fcf":            fcf,
            "div_yield":      div_yield,
            "div_rate":       div_rate,
            "payout_ratio":   payout_ratio,
            "debt":           debt,
            "shares":         shares,
            "beta":           beta,
            "eps_ttm":        eps_ttm,
            "roe":            roe,
            "roa":            roa,
            "gross_margin":   gross_margin,
            "op_margin":      op_margin,
            "net_margin":     net_margin,
            "revenue_growth": revenue_growth,
            "earnings_growth":earnings_growth,
            "week52_high":    week52_high,
            "week52_low":     week52_low,
            "pct_from_high":  pct_from_high,
            "target_price":   target_price,
            "upside":         upside,
            "signal":         signal,
            "signal_color":   signal_color,
            "reasons":        reasons,
            # display
            "d_price":        f"A${price:.2f}" if price else "—",
            "d_mkt_cap":      fmt_b(mkt_cap),
            "d_pe_trailing":  fmt_num(pe_trailing),
            "d_pe_forward":   fmt_num(pe_forward),
            "d_pb":           fmt_num(pb),
            "d_ev_ebitda":    fmt_num(ev_ebitda),
            "d_revenue":      fmt_b(revenue),
            "d_ebitda":       fmt_b(ebitda),
            "d_net_income":   fmt_b(net_income),
            "d_fcf":          fmt_b(fcf),
            "d_div_yield":    fmt_pct(div_yield),
            "d_payout_ratio": fmt_pct(payout_ratio),
            "d_roe":          fmt_pct(roe),
            "d_roa":          fmt_pct(roa),
            "d_net_margin":   fmt_pct(net_margin),
            "d_op_margin":    fmt_pct(op_margin),
            "d_beta":         fmt_num(beta, 2),
            "d_revenue_growth": fmt_pct(revenue_growth),
            "d_earnings_growth": fmt_pct(earnings_growth),
            "d_week52_high":  f"A${week52_high:.2f}" if week52_high else "—",
            "d_week52_low":   f"A${week52_low:.2f}"  if week52_low  else "—",
            "d_pct_from_high": f"{pct_from_high:.1f}%" if pct_from_high is not None else "—",
            "d_target_price": f"A${target_price:.2f}" if target_price else "—",
            "d_upside":       f"{upside:+.1f}%" if upside is not None else "—",
        }
    except Exception as e:
        print(f"    ERROR {ticker_ax}: {e}")
        return {
            "ticker": ticker_ax.replace(".AX", ""),
            "name":   name_fallback,
            "sector": sector_fallback,
            "signal": "N/A", "signal_color": "#888888", "reasons": [],
            **{k: None for k in [
                "industry","currency","price","mkt_cap","pe_trailing","pe_forward",
                "pb","ev_ebitda","ev","revenue","ebitda","net_income","fcf",
                "div_yield","div_rate","payout_ratio","debt","shares","beta",
                "eps_ttm","roe","roa","gross_margin","op_margin","net_margin",
                "revenue_growth","earnings_growth","week52_high","week52_low",
                "pct_from_high","target_price","upside"
            ]},
            **{k: "—" for k in [
                "d_price","d_mkt_cap","d_pe_trailing","d_pe_forward","d_pb",
                "d_ev_ebitda","d_revenue","d_ebitda","d_net_income","d_fcf",
                "d_div_yield","d_payout_ratio","d_roe","d_roa","d_net_margin",
                "d_op_margin","d_beta","d_revenue_growth","d_earnings_growth",
                "d_week52_high","d_week52_low","d_pct_from_high","d_target_price","d_upside"
            ]},
        }


# ── 3. HTML report generator ──────────────────────────────────────────────────

def build_sectors_html(sectors, sector_news=None):
    parts = []
    for s, comps in sorted(sectors.items()):
        sc = sector_color(s)
        cards = []
        for c in sorted(comps, key=lambda x: -(x.get("mkt_cap") or 0)):
            card = (
                '<div style="background:#fff;border-radius:6px;padding:10px 14px;'
                'box-shadow:0 1px 4px rgba(0,0,0,.08);min-width:140px">'
                '<div style="font-size:11px;color:#888">' + c["ticker"] + '</div>'
                '<div style="font-weight:700;font-size:13px">' + c["name"][:25] + '</div>'
                '<div style="font-size:12px;margin-top:4px">P/E: <b>' + c["d_pe_trailing"] + '</b>'
                ' &bull; Yield: <b style="color:#27ae60">' + c["d_div_yield"] + '</b></div>'
                '<div style="font-size:11px;color:#888">' + c["d_mkt_cap"] + '</div>'
                '<span style="background:' + c["signal_color"] + ';color:#fff;font-size:10px;'
                'padding:1px 6px;border-radius:8px">' + c["signal"] + '</span>'
                '</div>'
            )
            cards.append(card)
        # News panel for this sector
        news_panel = ""
        if sector_news:
            sd = sector_news.get(s, {})
            news_panel = build_news_panel_html(sd)
        block = (
            '<div style="margin-bottom:28px">'
            '<h3 style="font-size:15px;margin-bottom:12px;padding:8px 14px;background:' + sc +
            ';color:#fff;border-radius:6px;display:inline-block">' + s + '</h3>'
            '<div style="display:flex;flex-wrap:wrap;gap:8px">' +
            "".join(cards) +
            '</div>'
            + news_panel +
            '</div>'
        )
        parts.append(block)
    return "".join(parts)

def build_reasons_block(c):
    """Renders the Why Cheap / Why Expensive block for a company card."""
    reasons = c.get("reasons", [])
    sig = c.get("signal", "")
    if not reasons or sig not in ("Cheap", "Expensive"):
        return ""
    bg   = "#f0fff4" if sig == "Cheap" else "#fff5f5"
    col  = "#1a5c3a" if sig == "Cheap" else "#7b0000"
    bdr  = "#c3e6cb" if sig == "Cheap" else "#f5c6cb"
    items = "".join(f'<li style="margin:2px 0">{r}</li>' for r in reasons)
    return (
        '<div style="margin-top:10px;padding:8px 10px;background:' + bg + ';border-radius:6px;'
        'border:1px solid ' + bdr + '">'
        '<div style="font-size:10px;font-weight:700;color:' + col + ';margin-bottom:4px">'
        'WHY ' + sig.upper() + ':</div>'
        '<ul style="margin:0;padding-left:16px;font-size:11px;color:' + col + ';line-height:1.6">'
        + items +
        '</ul></div>'
    )

# ── News HTML helpers ─────────────────────────────────────────────────────────

def _html_esc(s):
    """Escape HTML special characters."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))

def _headline_html(h):
    """Render a headline as a hyperlink if URL is available, else plain text."""
    title = _html_esc(h.get("title", ""))
    url = h.get("url", "")
    if url:
        return (
            '<a href="' + _html_esc(url) + '" target="_blank" rel="noopener" '
            'style="color:inherit;text-decoration:none;'
            'border-bottom:1px dotted #aaa" '
            'title="Open article">' + title + '</a>'
        )
    return title

def _sentiment_badge_html(label):
    """Coloured sentiment badge span."""
    if label == "Bullish":
        return ('<span style="background:#27ae60;color:#fff;font-size:10px;'
                'padding:2px 8px;border-radius:8px;font-weight:600">&#x2191; Bullish</span>')
    if label == "Bearish":
        return ('<span style="background:#e74c3c;color:#fff;font-size:10px;'
                'padding:2px 8px;border-radius:8px;font-weight:600">&#x2193; Bearish</span>')
    if label:
        return ('<span style="background:#95a5a6;color:#fff;font-size:10px;'
                'padding:2px 8px;border-radius:8px;font-weight:600">&#x2192; Neutral</span>')
    return ""

def build_news_panel_html(sector_data):
    """Compact news panel for the By Sector view."""
    if not sector_data:
        return ""
    headlines = sector_data.get("headlines", [])
    sentiment = sector_data.get("sentiment", "")
    if not headlines:
        return ""
    badge = _sentiment_badge_html(sentiment)
    items = ""
    for h in headlines[:4]:
        title = _headline_html(h)
        date  = h.get("date", "")
        date_span = (
            '<span style="font-size:10px;color:#aaa;margin-left:8px;white-space:nowrap">'
            + date + '</span>'
        ) if date else ""
        items += (
            '<li style="margin:3px 0;display:flex;justify-content:space-between;align-items:baseline">'
            '<span style="font-size:11px;color:#444">' + title + '</span>'
            + date_span + '</li>'
        )
    return (
        '<div style="margin-top:12px;padding:10px 12px;background:#f0f7ff;'
        'border-radius:6px;border-left:3px solid #3498db">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
        '<span style="font-size:10px;font-weight:700;color:#1a3a5c;'
        'text-transform:uppercase;letter-spacing:.5px">&#x1f4f0; Macro News</span>'
        + badge
        + '</div>'
        '<ul style="margin:0;padding-left:14px;line-height:1.7">' + items + '</ul>'
        '</div>'
    )

def build_macro_context_html(sector_news):
    """Compact global macro box for the Overview tab."""
    if not sector_news:
        return ""
    macro_data = sector_news.get("_macro", {})
    headlines  = macro_data.get("headlines", [])
    sentiment  = macro_data.get("sentiment", "")
    if not headlines:
        return ""
    badge = _sentiment_badge_html(sentiment)
    fetched = sector_news.get("_fetched_str", "")
    fetched_note = (
        ' &nbsp;<span style="font-size:10px;color:#aaa">Updated ' + fetched + '</span>'
    ) if fetched else ""
    items = ""
    for h in headlines[:5]:
        title = _headline_html(h)
        date  = h.get("date", "")
        date_span = (
            '<span style="font-size:10px;color:#aaa;margin-left:8px;white-space:nowrap">'
            + date + '</span>'
        ) if date else ""
        items += (
            '<li style="margin:3px 0;display:flex;justify-content:space-between;align-items:baseline">'
            '<span style="font-size:12px;color:#333">' + title + '</span>'
            + date_span + '</li>'
        )
    return (
        '<div style="background:#fff;border-radius:10px;padding:16px 20px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:24px;border-left:4px solid #3498db">'
        '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        '<span style="font-size:14px;font-weight:700;color:#1a3a5c">&#x1f30d; Global Macro Context</span>'
        + badge + fetched_note
        + '</div>'
        '<p style="font-size:11px;color:#888;margin-bottom:10px">'
        'Key international &amp; domestic macro themes impacting ASX sectors. '
        'See the <b>Macro News</b> tab for full sector breakdown.'
        '</p>'
        '<ul style="margin:0;padding-left:16px;line-height:1.8">' + items + '</ul>'
        '</div>'
    )

def build_macro_tab_html(sector_news):
    """Full Macro News tab content."""
    if not sector_news:
        return (
            '<div style="background:#fff8e1;border-left:4px solid #f39c12;'
            'padding:16px 20px;border-radius:4px;color:#7f6000">'
            'News data not yet available. Click <b>&#x21bb; Refresh Data</b> to fetch headlines.'
            '</div>'
        )
    fetched_str     = sector_news.get("_fetched_str", "")
    macro_data      = sector_news.get("_macro", {})
    macro_headlines = macro_data.get("headlines", [])
    macro_sentiment = macro_data.get("sentiment", "Neutral")

    # Global macro box
    macro_items_html = ""
    for h in macro_headlines:
        title = _headline_html(h)
        date  = h.get("date", "")
        date_span = (
            '<span style="font-size:11px;color:#aaa;margin-left:12px;white-space:nowrap">'
            + date + '</span>'
        ) if date else ""
        macro_items_html += (
            '<li style="margin:5px 0;display:flex;justify-content:space-between;align-items:baseline">'
            '<span>' + title + '</span>' + date_span + '</li>'
        )
    if not macro_items_html:
        macro_items_html = '<li style="color:#aaa;font-style:italic">No macro headlines available</li>'

    global_box = (
        '<div style="background:#fff;border-radius:10px;padding:20px 24px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:28px">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        '<h3 style="font-size:16px;color:#1a3a5c;font-weight:700;margin:0">'
        '&#x1f30d; Global Macro Outlook</h3>'
        + _sentiment_badge_html(macro_sentiment)
        + '</div>'
        '<p style="font-size:12px;color:#888;margin-bottom:12px">'
        'Top international and domestic macro themes. Headlines sourced from Google News RSS. '
        'Sentiment scored by keyword analysis — bullish/bearish word frequency.'
        '</p>'
        '<ul style="padding-left:20px;line-height:1.9;font-size:13px;color:#333">'
        + macro_items_html
        + '</ul>'
        '</div>'
    )

    # Sector cards
    sector_order = [
        "Energy", "Materials", "Financials", "Health Care", "Real Estate",
        "Consumer Discretionary", "Consumer Staples", "Communication Services",
        "Industrials", "Utilities", "Information Technology",
    ]
    sector_cards = []
    for sector in sector_order:
        sd        = sector_news.get(sector, {})
        headlines = sd.get("headlines", [])
        sentiment = sd.get("sentiment", "")
        sc        = sector_color(sector)
        badge     = _sentiment_badge_html(sentiment)
        items_html = ""
        for h in headlines[:5]:
            title = _headline_html(h)
            date  = h.get("date", "")
            date_span = (
                '<span style="font-size:10px;color:#aaa;margin-left:8px;white-space:nowrap">'
                + date + '</span>'
            ) if date else ""
            items_html += (
                '<li style="margin:4px 0;display:flex;justify-content:space-between;align-items:baseline">'
                '<span style="font-size:12px;color:#444">' + title + '</span>'
                + date_span + '</li>'
            )
        if not items_html:
            items_html = '<li style="color:#aaa;font-size:12px;font-style:italic">No recent headlines</li>'
        card = (
            '<div style="background:#fff;border-radius:8px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08);overflow:hidden">'
            '<div style="background:' + sc + ';color:#fff;padding:10px 16px;'
            'display:flex;justify-content:space-between;align-items:center">'
            '<span style="font-weight:700;font-size:13px">' + sector + '</span>'
            + badge
            + '</div>'
            '<div style="padding:12px 14px">'
            '<ul style="margin:0;padding-left:14px;line-height:1.7">' + items_html + '</ul>'
            '</div>'
            '</div>'
        )
        sector_cards.append(card)

    footer = ""
    if fetched_str:
        footer = (
            '<p style="color:#aaa;font-size:11px;margin-top:16px">'
            'News headlines fetched: ' + fetched_str
            + ' &#x2022; Source: Google News RSS'
            + ' &#x2022; Sentiment: keyword-based analysis'
            + ' &#x2022; For informational purposes only'
            + '</p>'
        )

    return (
        global_box
        + '<h3 style="font-size:16px;color:#1a3a5c;font-weight:700;margin-bottom:16px">'
          'Sector News Breakdown</h3>'
        + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px">'
        + "".join(sector_cards)
        + '</div>'
        + footer
    )

SECTOR_COLORS = {
    "Financials":              "#1a3a5c",
    "Materials":               "#7b4f12",
    "Health Care":             "#1a5c3a",
    "Consumer Discretionary":  "#5c1a4f",
    "Consumer Staples":        "#4f5c1a",
    "Communication Services":  "#1a4f5c",
    "Industrials":             "#5c3a1a",
    "Energy":                  "#5c1a1a",
    "Real Estate":             "#1a1a5c",
    "Utilities":               "#3a5c1a",
    "Information Technology":  "#1a5c5c",
}

def sector_color(sector):
    return SECTOR_COLORS.get(sector, "#333333")

def bar_pct(val, max_val, color="#3498db"):
    if val is None or max_val is None or max_val == 0:
        return ""
    pct = min(abs(val) / abs(max_val) * 100, 100)
    return f'<div style="background:{color};height:6px;width:{pct:.1f}%;border-radius:3px;margin-top:2px"></div>'

def _build_card_reassessment(c, reassessments, company_news):
    """Compact reassessment block for company cards (Cheap/Fair stocks only)."""
    if not reassessments:
        return ""
    ticker = c.get("ticker", "")
    if c.get("signal") not in ("Cheap", "Fair"):
        return ""
    r = reassessments.get(ticker)
    if not r:
        return ""
    conv = _html_esc(r.get("conviction", "Medium"))
    conv_color = r.get("conviction_color", "#888")
    commentary = _html_esc(r.get("commentary", ""))
    c_sent = r.get("company_sentiment", "Neutral")
    s_sent = r.get("sector_sentiment", "Neutral")

    # Flags
    flags_html = ""
    for flag in r.get("flags", []):
        flags_html += (
            '<span style="background:#fff3cd;color:#856404;font-size:9px;'
            'padding:2px 6px;border-radius:4px;margin-right:4px;display:inline-block;'
            'margin-top:3px">&#x26a0; ' + _html_esc(flag) + '</span>'
        )

    # Company headlines
    news_items = ""
    cn = (company_news or {}).get(ticker, {})
    for h in cn.get("headlines", [])[:3]:
        news_items += (
            '<li style="font-size:10px;margin:2px 0;color:#555">'
            + _headline_html(h) + '</li>'
        )
    news_ul = ""
    if news_items:
        news_ul = '<ul style="margin:6px 0 0;padding-left:14px">' + news_items + '</ul>'

    return (
        '<div style="margin-top:10px;padding:10px 12px;background:#f8f9fa;'
        'border-radius:6px;border:1px solid #dee2e6">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        '<span style="font-size:10px;font-weight:700;color:#555;'
        'text-transform:uppercase;letter-spacing:.5px">NEWS CONVICTION</span>'
        '<span style="background:' + conv_color + ';color:#fff;font-size:10px;'
        'padding:2px 8px;border-radius:8px;font-weight:600">' + conv + '</span>'
        '<span style="font-size:9px;color:#aaa">Company: ' + c_sent
        + ' | Sector: ' + s_sent + '</span>'
        '</div>'
        '<p style="font-size:11px;color:#555;margin:0 0 4px;line-height:1.4">'
        + commentary + '</p>'
        + flags_html + news_ul
        + '</div>'
    )


def _build_manual_tab_html(companies, manual_summary, portfolio_summary):
    """Build the My Trades tab: trade form, holdings, side-by-side comparison."""
    ms = manual_summary
    ps = portfolio_summary

    # ── Stock options for dropdown ────────────────────────────────────────────
    options_html = '<option value="">— Select a stock —</option>'
    for c in sorted(companies, key=lambda x: x.get("ticker", "")):
        tick = c.get("ticker", "")
        short = tick.replace(".AX", "")
        name = c.get("name", "")
        price = c.get("price")
        sig = c.get("signal", "")
        price_str = "A${:.2f}".format(price) if price else "N/A"
        options_html += (
            '<option value="' + tick + '">'
            + short + ' — ' + _html_esc(name) + ' (' + price_str + ') [' + sig + ']'
            + '</option>'
        )

    # ── Cash and value display ────────────────────────────────────────────────
    m_cash  = ms.get("cash", 10000) if ms else 10000
    m_value = ms.get("total_value", 10000) if ms else 10000
    m_pnl   = ms.get("cum_pnl", 0) if ms else 0
    m_pnl_pct = ms.get("cum_pnl_pct", 0) if ms else 0
    m_pnl_col = "#27ae60" if m_pnl >= 0 else "#e74c3c"

    # ── Holdings table ────────────────────────────────────────────────────────
    holdings_rows = ""
    holdings = ms.get("holdings", {}) if ms else {}
    total_hv = sum(h.get("market_value", 0) for h in holdings.values())
    for tick in sorted(holdings.keys()):
        h = holdings[tick]
        short = tick.replace(".AX", "")
        name_h = _html_esc(h.get("name", ""))
        shares = h.get("shares", 0)
        avg = h.get("avg_cost", 0)
        cur = h.get("current_price", 0)
        mv = h.get("market_value", 0)
        pnl = h.get("unrealized_pnl", 0)
        pnl_pct = ((cur / avg - 1) * 100) if avg else 0
        pnl_col = "#27ae60" if pnl >= 0 else "#e74c3c"
        wt = (mv / m_value * 100) if m_value else 0
        holdings_rows += (
            '<tr>'
            '<td><b>' + short + '</b></td>'
            '<td>' + name_h + '</td>'
            '<td style="text-align:right">' + "{:.2f}".format(shares) + '</td>'
            '<td style="text-align:right">A$' + "{:.2f}".format(avg) + '</td>'
            '<td style="text-align:right">A$' + "{:.2f}".format(cur) + '</td>'
            '<td style="text-align:right">A$' + "{:,.2f}".format(mv) + '</td>'
            '<td style="text-align:right;color:' + pnl_col + ';font-weight:600">'
            'A$' + "{:+,.2f}".format(pnl) + ' (' + "{:+.1f}".format(pnl_pct) + '%)</td>'
            '<td style="text-align:right">' + "{:.1f}".format(wt) + '%</td>'
            '<td style="text-align:center">'
            '<button onclick="executeSell(\'' + tick + '\')" '
            'style="background:#e74c3c;color:#fff;border:none;padding:4px 12px;'
            'border-radius:4px;font-size:11px;cursor:pointer;font-weight:600">SELL ALL</button>'
            '</td></tr>'
        )
    if not holdings_rows:
        holdings_rows = (
            '<tr><td colspan="9" style="text-align:center;color:#aaa;padding:20px;'
            'font-style:italic">No holdings yet. Use the form above to buy stocks.</td></tr>'
        )

    # ── Trade log (last 15) ───────────────────────────────────────────────────
    trades = ms.get("trades", []) if ms else []
    trade_rows = ""
    for t in reversed(trades[-15:]):
        act = t.get("action", "")
        act_col = "#27ae60" if act == "BUY" else "#e74c3c"
        rpnl = t.get("realized_pnl")
        rpnl_str = "A${:+,.2f}".format(rpnl) if rpnl is not None else "—"
        rpnl_col = "#27ae60" if (rpnl is not None and rpnl >= 0) else "#e74c3c" if rpnl is not None else "#888"
        trade_rows += (
            '<tr>'
            '<td>' + t.get("date", "") + '</td>'
            '<td style="color:' + act_col + ';font-weight:700">' + act + '</td>'
            '<td><b>' + t.get("ticker", "").replace(".AX", "") + '</b></td>'
            '<td>' + _html_esc(t.get("name", "")) + '</td>'
            '<td style="text-align:right">' + "{:.2f}".format(t.get("shares", 0)) + '</td>'
            '<td style="text-align:right">A$' + "{:.2f}".format(t.get("price", 0)) + '</td>'
            '<td style="text-align:right">A$' + "{:,.2f}".format(t.get("value", 0)) + '</td>'
            '<td style="text-align:right;color:' + rpnl_col + '">' + rpnl_str + '</td>'
            '</tr>'
        )
    if not trade_rows:
        trade_rows = '<tr><td colspan="8" style="text-align:center;color:#aaa;padding:16px">No trades yet</td></tr>'

    # ── Side-by-side comparison ───────────────────────────────────────────────
    def _stat_box(label, val, color="#2c3e50"):
        return (
            '<div style="text-align:center">'
            '<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:.5px">'
            + label + '</div>'
            '<div style="font-size:18px;font-weight:700;color:' + color + '">'
            + val + '</div></div>'
        )

    p_val = ps.get("total_value", 10000) if ps else 10000
    p_pnl = ps.get("cum_pnl", 0) if ps else 0
    p_pnl_pct = ps.get("cum_pnl_pct", 0) if ps else 0
    p_pnl_col = "#27ae60" if p_pnl >= 0 else "#e74c3c"
    p_n = ps.get("n_holdings", 0) if ps else 0
    p_cash = ps.get("cash", 0) if ps else 0

    m_n = ms.get("n_holdings", 0) if ms else 0

    # Determine winner
    winner_text = ""
    if ms and ps and (m_pnl != 0 or p_pnl != 0):
        if m_pnl > p_pnl:
            winner_text = (
                '<span style="color:#8e44ad;font-weight:700">&#x1f3c6; Your picks are winning '
                'by A$' + "{:,.2f}".format(m_pnl - p_pnl) + '!</span>'
            )
        elif p_pnl > m_pnl:
            winner_text = (
                '<span style="color:#27ae60;font-weight:700">&#x1f916; Auto strategy leads '
                'by A$' + "{:,.2f}".format(p_pnl - m_pnl) + '</span>'
            )
        else:
            winner_text = '<span style="color:#888">Tied!</span>'

    comparison_html = (
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px">'

        # My Portfolio column
        '<div style="background:#f8f0ff;border:2px solid #8e44ad;border-radius:10px;padding:16px 20px">'
        '<h3 style="color:#8e44ad;font-size:14px;margin-bottom:12px;text-align:center">'
        '&#x1f3af; My Portfolio</h3>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
        + _stat_box("Total Value", "A${:,.2f}".format(m_value))
        + _stat_box("P&L", "A${:+,.2f} ({:+.1f}%)".format(m_pnl, m_pnl_pct), m_pnl_col)
        + _stat_box("Holdings", str(m_n))
        + _stat_box("Cash", "A${:,.2f}".format(m_cash))
        + '</div></div>'

        # Auto Strategy column
        '<div style="background:#f0fff4;border:2px solid #27ae60;border-radius:10px;padding:16px 20px">'
        '<h3 style="color:#27ae60;font-size:14px;margin-bottom:12px;text-align:center">'
        '&#x1f916; Auto Strategy</h3>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
        + _stat_box("Total Value", "A${:,.2f}".format(p_val))
        + _stat_box("P&L", "A${:+,.2f} ({:+.1f}%)".format(p_pnl, p_pnl_pct), p_pnl_col)
        + _stat_box("Holdings", str(p_n))
        + _stat_box("Cash", "A${:,.2f}".format(p_cash))
        + '</div></div>'

        '</div>'
    )

    if winner_text:
        comparison_html += (
            '<div style="text-align:center;margin-top:12px;font-size:14px">'
            + winner_text + '</div>'
        )

    # ── Assemble full tab ─────────────────────────────────────────────────────
    return (
        # Trade form
        '<div style="background:#fff;border-radius:10px;padding:20px 24px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px">'
        '<h3 style="color:#8e44ad;margin-bottom:14px">Place a Trade</h3>'
        '<div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">'

        '<div style="flex:2;min-width:250px">'
        '<label style="font-size:11px;font-weight:600;color:#555;display:block;margin-bottom:4px">STOCK</label>'
        '<select id="manualTicker" style="width:100%;padding:8px 10px;border:1px solid #ddd;'
        'border-radius:6px;font-size:13px">' + options_html + '</select></div>'

        '<div style="flex:1;min-width:140px">'
        '<label style="font-size:11px;font-weight:600;color:#555;display:block;margin-bottom:4px">'
        'AMOUNT (A$)</label>'
        '<input id="manualAmount" type="number" min="100" step="100" value="1000" '
        'style="width:100%;padding:8px 10px;border:1px solid #ddd;border-radius:6px;'
        'font-size:13px;box-sizing:border-box"></div>'

        '<div style="display:flex;gap:8px">'
        '<button onclick="executeBuy()" style="background:#27ae60;color:#fff;border:none;'
        'padding:10px 24px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px">'
        '&#x2191; BUY</button>'
        '</div>'

        '</div>'
        '<div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center">'
        '<span id="tradeMsg" style="font-size:12px;color:#888"></span>'
        '<span style="font-size:12px;color:#555">Available cash: '
        '<b style="color:#8e44ad">A$' + "{:,.2f}".format(m_cash) + '</b></span>'
        '</div>'
        '</div>'

        # Holdings table
        '<div style="background:#fff;border-radius:10px;padding:20px 24px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px">'
        '<h3 style="color:#1a3a5c;margin-bottom:12px">My Holdings</h3>'
        '<table style="width:100%;border-collapse:collapse;font-size:13px">'
        '<thead style="background:#8e44ad;color:#fff">'
        '<tr><th style="padding:8px 10px;text-align:left">Ticker</th>'
        '<th style="padding:8px 10px;text-align:left">Company</th>'
        '<th style="padding:8px 10px;text-align:right">Shares</th>'
        '<th style="padding:8px 10px;text-align:right">Avg Cost</th>'
        '<th style="padding:8px 10px;text-align:right">Price</th>'
        '<th style="padding:8px 10px;text-align:right">Value</th>'
        '<th style="padding:8px 10px;text-align:right">P&amp;L</th>'
        '<th style="padding:8px 10px;text-align:right">Weight</th>'
        '<th style="padding:8px 10px;text-align:center">Action</th>'
        '</tr></thead><tbody>'
        + holdings_rows
        + '</tbody></table></div>'

        # Side-by-side comparison
        '<div style="background:#fff;border-radius:10px;padding:20px 24px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:20px">'
        '<h3 style="color:#1a3a5c;margin-bottom:4px">Performance Comparison</h3>'
        '<p style="font-size:11px;color:#888;margin-bottom:8px">'
        'Your manual picks vs. the automated Cheap-signal strategy. Both started with A$10,000.</p>'
        + comparison_html
        + '</div>'

        # Trade log
        '<div style="background:#fff;border-radius:10px;padding:20px 24px;'
        'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
        '<h3 style="color:#1a3a5c;margin-bottom:12px">Trade History</h3>'
        '<table style="width:100%;border-collapse:collapse;font-size:12px">'
        '<thead style="background:#f8f9fa">'
        '<tr><th style="padding:6px 8px;text-align:left">Date</th>'
        '<th style="padding:6px 8px;text-align:left">Action</th>'
        '<th style="padding:6px 8px;text-align:left">Ticker</th>'
        '<th style="padding:6px 8px;text-align:left">Company</th>'
        '<th style="padding:6px 8px;text-align:right">Shares</th>'
        '<th style="padding:6px 8px;text-align:right">Price</th>'
        '<th style="padding:6px 8px;text-align:right">Value</th>'
        '<th style="padding:6px 8px;text-align:right">Realized P&amp;L</th>'
        '</tr></thead><tbody>'
        + trade_rows
        + '</tbody></table></div>'
    )


def generate_html(companies, last_updated=None, portfolio_summary=None,
                   sector_news=None, company_news=None, reassessments=None,
                   manual_summary=None, quant_data=None):
    # Lazy import so asx50_analysis works without portfolio.py
    try:
        from portfolio import generate_portfolio_html as _gen_pf
    except ImportError:
        _gen_pf = None
    try:
        from quant_analysis import generate_quant_html as _gen_quant
    except ImportError:
        _gen_quant = None
    # Sort by market cap descending for summary table
    sorted_by_cap = sorted(companies, key=lambda c: c.get("mkt_cap") or 0, reverse=True)
    sorted_by_sector = sorted(companies, key=lambda c: (c.get("sector",""), -(c.get("mkt_cap") or 0)))

    # Max values for bar charts
    max_cap   = max((c.get("mkt_cap") or 0) for c in companies) or 1
    max_rev   = max((c.get("revenue") or 0) for c in companies) or 1
    max_ebitda= max((c.get("ebitda")  or 0) for c in companies) or 1

    # Sector summary
    sectors = {}
    for c in companies:
        s = c.get("sector","Unknown")
        sectors.setdefault(s, []).append(c)

    # Signal counts
    signal_counts = {"Cheap": 0, "Fair": 0, "Expensive": 0, "N/A": 0}
    for c in companies:
        signal_counts[c.get("signal","N/A")] += 1

    def company_row(c, i):
        sc = sector_color(c.get("sector",""))
        sig = c.get("signal","N/A")
        sig_col = c.get("signal_color","#888")
        cap_bar = bar_pct(c.get("mkt_cap"), max_cap, "#3498db")
        pe = c.get("pe_trailing")
        pe_class = ""
        if pe is not None:
            if   pe < 12: pe_class = "color:#27ae60;font-weight:700"
            elif pe > 30: pe_class = "color:#e74c3c;font-weight:700"
        upside = c.get("upside")
        upside_col = "#27ae60" if (upside is not None and upside > 0) else "#e74c3c"
        return f"""
        <tr class="company-row" data-sector="{c.get('sector','')}" data-signal="{sig}">
          <td style="font-weight:700;color:#2c3e50">{i+1}</td>
          <td>
            <span style="font-weight:700;color:#2c3e50">{c['ticker']}</span><br>
            <small style="color:#666;font-size:11px">{c['name']}</small>
          </td>
          <td><span style="background:{sc};color:#fff;padding:2px 6px;border-radius:3px;font-size:11px">{c.get('sector','')}</span></td>
          <td style="text-align:right;font-weight:600">{c['d_price']}</td>
          <td style="text-align:right">
            {c['d_mkt_cap']}
            {cap_bar}
          </td>
          <td style="text-align:right;{pe_class}">{c['d_pe_trailing']}</td>
          <td style="text-align:right">{c['d_pe_forward']}</td>
          <td style="text-align:right">{c['d_ev_ebitda']}</td>
          <td style="text-align:right">{c['d_pb']}</td>
          <td style="text-align:right;color:#27ae60">{c['d_div_yield']}</td>
          <td style="text-align:right">{c['d_roe']}</td>
          <td style="text-align:right;color:{upside_col}">{c['d_upside']}</td>
          <td style="text-align:center">
            <span style="background:{sig_col};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{sig}</span>
          </td>
        </tr>"""

    def company_card(c):
        sc = sector_color(c.get("sector",""))
        sig = c.get("signal","N/A")
        sig_col = c.get("signal_color","#888")
        pe = c.get("pe_trailing")
        pe_style = ""
        if pe is not None:
            if   pe < 12: pe_style = "color:#27ae60;font-weight:700"
            elif pe > 30: pe_style = "color:#e74c3c;font-weight:700"
        upside = c.get("upside")
        upside_col = "#27ae60" if (upside is not None and upside > 0) else "#e74c3c"
        from52 = c.get("pct_from_high")
        from52_col = "#27ae60" if (from52 is not None and from52 > -10) else "#f39c12" if (from52 is not None and from52 > -25) else "#e74c3c"

        def metric_row(label, val, style=""):
            return f'<tr><td style="color:#888;font-size:12px;padding:3px 0">{label}</td><td style="text-align:right;font-size:12px;font-weight:600;{style}">{val}</td></tr>'

        return f"""
        <div class="card" data-sector="{c.get('sector','')}" data-signal="{sig}">
          <div style="background:{sc};color:#fff;padding:10px 14px;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;align-items:center">
            <div>
              <span style="font-size:18px;font-weight:700">{c['ticker']}</span>
              <span style="font-size:12px;opacity:.8;margin-left:8px">{(c.get('industry') or '')[:35]}</span>
            </div>
            <span style="background:{sig_col};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700">{sig}</span>
          </div>
          <div style="padding:12px 14px">
            <div style="font-size:13px;color:#444;margin-bottom:8px;font-weight:500">{c['name']}</div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:10px">
              <div>
                <div style="font-size:24px;font-weight:700;color:#2c3e50">{c['d_price']}</div>
                <div style="font-size:11px;color:#888">Market Cap: <b>{c['d_mkt_cap']}</b></div>
              </div>
              <div style="text-align:right">
                <div style="font-size:11px;color:{from52_col}">vs 52W High: {c['d_pct_from_high']}</div>
                <div style="font-size:11px;color:{upside_col}">Analyst Target: {c['d_target_price']} ({c['d_upside']})</div>
              </div>
            </div>
            <table style="width:100%;border-collapse:collapse">
              <tr><td colspan="2" style="font-size:11px;font-weight:700;color:{sc};padding:4px 0 2px">VALUATION</td></tr>
              {metric_row("Trailing P/E",   c['d_pe_trailing'], pe_style)}
              {metric_row("Forward P/E",    c['d_pe_forward'])}
              {metric_row("EV/EBITDA",      c['d_ev_ebitda'])}
              {metric_row("Price/Book",     c['d_pb'])}
              <tr><td colspan="2" style="font-size:11px;font-weight:700;color:{sc};padding:6px 0 2px">FINANCIALS</td></tr>
              {metric_row("Revenue",        c['d_revenue'])}
              {metric_row("EBITDA",         c['d_ebitda'])}
              {metric_row("Net Income",     c['d_net_income'])}
              {metric_row("Free Cash Flow", c['d_fcf'])}
              <tr><td colspan="2" style="font-size:11px;font-weight:700;color:{sc};padding:6px 0 2px">RETURNS & INCOME</td></tr>
              {metric_row("Dividend Yield", c['d_div_yield'], "color:#27ae60")}
              {metric_row("Payout Ratio",   c['d_payout_ratio'])}
              {metric_row("ROE",            c['d_roe'])}
              {metric_row("ROA",            c['d_roa'])}
              <tr><td colspan="2" style="font-size:11px;font-weight:700;color:{sc};padding:6px 0 2px">MARGINS & GROWTH</td></tr>
              {metric_row("Net Margin",     c['d_net_margin'])}
              {metric_row("Op. Margin",     c['d_op_margin'])}
              {metric_row("Rev. Growth",    c['d_revenue_growth'])}
              {metric_row("Earn. Growth",   c['d_earnings_growth'])}
              <tr><td colspan="2" style="font-size:11px;font-weight:700;color:{sc};padding:6px 0 2px">RISK</td></tr>
              {metric_row("Beta",           c['d_beta'])}
              {metric_row("52W High",       c['d_week52_high'])}
              {metric_row("52W Low",        c['d_week52_low'])}
            </table>
            {build_reasons_block(c)}
            {_build_card_reassessment(c, reassessments, company_news)}
          </div>
        </div>"""

    # Sector summary table
    sector_rows = ""
    for s, comps in sorted(sectors.items()):
        avg_pe   = None
        pes = [c.get("pe_trailing") for c in comps if c.get("pe_trailing") is not None]
        if pes: avg_pe = sum(pes)/len(pes)
        avg_yield = None
        yields = [c.get("div_yield") for c in comps if c.get("div_yield") is not None]
        if yields: avg_yield = sum(yields)/len(yields)
        total_cap = sum(c.get("mkt_cap") or 0 for c in comps)
        # News sentiment badge for this sector
        _sn = (sector_news or {}).get(s, {})
        _sent = _sn.get("sentiment", "")
        if _sent == "Bullish":
            news_cell = '<span style="color:#27ae60;font-weight:700">&#x2191; Bullish</span>'
        elif _sent == "Bearish":
            news_cell = '<span style="color:#e74c3c;font-weight:700">&#x2193; Bearish</span>'
        elif _sent:
            news_cell = '<span style="color:#95a5a6">&#x2192; Neutral</span>'
        else:
            news_cell = '<span style="color:#ccc">—</span>'
        sector_rows += f"""
        <tr>
          <td><span style="background:{sector_color(s)};color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">{s}</span></td>
          <td style="text-align:center">{len(comps)}</td>
          <td style="text-align:right">{fmt_b(total_cap)}</td>
          <td style="text-align:right">{fmt_num(avg_pe) if avg_pe else '—'}x</td>
          <td style="text-align:right">{fmt_pct(avg_yield) if avg_yield else '—'}</td>
          <td style="text-align:center">{news_cell}</td>
        </tr>"""

    # All company rows
    all_rows = "".join(company_row(c, i) for i, c in enumerate(sorted_by_cap))
    # All company cards
    all_cards = "".join(company_card(c) for c in sorted_by_sector)

    # Top picks (cheap signal, highest mkt cap)
    cheap = [c for c in companies if c.get("signal") == "Cheap"]
    cheap_sorted = sorted(cheap, key=lambda c: c.get("mkt_cap") or 0, reverse=True)[:5]
    top_picks_html = ""
    for c in cheap_sorted:
        reasons_html = "".join(
            f'<li style="margin:2px 0">{r}</li>'
            for r in c.get("reasons", [])
        )
        top_picks_html += f"""
        <div style="background:#f0fff4;border:1px solid #27ae60;border-radius:8px;padding:14px 16px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <b style="color:#1a5c3a;font-size:16px">{c['ticker']}</b>
              &nbsp;<span style="color:#666;font-size:13px">{c['name']}</span>
              &nbsp;<span style="background:#1a5c3a;color:#fff;font-size:10px;padding:1px 7px;border-radius:8px;vertical-align:middle">{c.get('sector','')}</span>
            </div>
            <div style="text-align:right">
              <span style="font-weight:700">{c['d_price']}</span>
              <span style="color:#888;font-size:11px;margin-left:8px">Mkt Cap {c['d_mkt_cap']}</span>
            </div>
          </div>
          <div style="display:flex;gap:20px;margin-top:8px;font-size:12px;color:#555;flex-wrap:wrap">
            <span>P/E: <b>{c['d_pe_trailing']}</b></span>
            <span>EV/EBITDA: <b>{c['d_ev_ebitda']}</b></span>
            <span>P/B: <b>{c['d_pb']}</b></span>
            <span>Yield: <b style="color:#27ae60">{c['d_div_yield']}</b></span>
            <span>ROE: <b>{c['d_roe']}</b></span>
            <span>Upside: <b>{c['d_upside']}</b></span>
          </div>
          {f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #c3e6cb"><div style="font-size:11px;font-weight:700;color:#1a5c3a;margin-bottom:4px">WHY CHEAP:</div><ul style="margin:0;padding-left:18px;font-size:12px;color:#2d6a4f">{reasons_html}</ul></div>' if reasons_html else ''}
          {_build_card_reassessment(c, reassessments, company_news)}
        </div>"""

    # Pre-compute news HTML (uses string concatenation, safe for f-string injection)
    macro_context_html = build_macro_context_html(sector_news)
    macro_tab_html     = build_macro_tab_html(sector_news)
    manual_tab_html    = _build_manual_tab_html(companies, manual_summary, portfolio_summary)

    # Pre-compute quant analysis tab HTML
    if _gen_quant and quant_data:
        quant_tab_html = _gen_quant(companies, quant_data)
    else:
        quant_tab_html = '<p style="color:#888;font-style:italic">Quant data not available yet. Click <b>Refresh Data</b> to compute.</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ASX200 Valuation Report — {REPORT_DATE}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f6f9; color: #2c3e50; }}
  .header {{ background: linear-gradient(135deg, #1a3a5c 0%, #2980b9 100%); color: #fff; padding: 30px 40px; }}
  .header h1 {{ font-size: 28px; font-weight: 800; }}
  .header p {{ opacity: .8; margin-top: 6px; font-size: 14px; }}
  .nav {{ background: #fff; border-bottom: 2px solid #e0e6ed; padding: 0 40px; display: flex; gap: 0; position: sticky; top: 0; z-index: 100; }}
  .nav a {{ padding: 14px 20px; font-size: 13px; font-weight: 600; color: #555; text-decoration: none; border-bottom: 3px solid transparent; transition: .2s; }}
  .nav a:hover, .nav a.active {{ color: #2980b9; border-bottom-color: #2980b9; }}
  .section {{ padding: 30px 40px; display: none; }}
  .section.active {{ display: block; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .stat-box {{ background: #fff; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .stat-box .label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: .5px; }}
  .stat-box .value {{ font-size: 26px; font-weight: 800; color: #2c3e50; margin-top: 4px; }}
  .stat-box .sub {{ font-size: 11px; color: #aaa; margin-top: 2px; }}
  h2 {{ font-size: 20px; font-weight: 700; margin-bottom: 16px; color: #1a3a5c; }}
  .filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
  .filter-btn {{ padding: 5px 14px; border: 1px solid #ddd; border-radius: 20px; font-size: 12px; cursor: pointer; background: #fff; color: #555; transition: .2s; }}
  .filter-btn:hover, .filter-btn.active {{ background: #2980b9; color: #fff; border-color: #2980b9; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); font-size: 13px; }}
  thead {{ background: #1a3a5c; color: #fff; }}
  th {{ padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; white-space: nowrap; }}
  th.sortable {{ cursor: pointer; user-select: none; position: relative; padding-right: 20px; }}
  th.sortable:hover {{ background: #24537a; }}
  th .sort-arrow {{ font-size: 10px; margin-left: 4px; opacity: 0.4; }}
  th.sort-asc .sort-arrow, th.sort-desc .sort-arrow {{ opacity: 1; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #f0f2f5; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fafc; }}
  .company-row {{ cursor: default; }}
  .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }}
  a[target="_blank"]:hover {{ border-bottom-color: #2980b9 !important; color: #2980b9 !important; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.09); overflow: hidden; transition: transform .15s, box-shadow .15s; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,.13); }}
  .disclaimer {{ background: #fff8e1; border-left: 4px solid #f39c12; padding: 14px 18px; border-radius: 4px; font-size: 12px; color: #7f6000; margin-top: 24px; }}
  .refresh-bar {{ display:flex; align-items:center; gap:12px; margin-top:10px; flex-wrap:wrap; }}
  #refresh-btn {{ background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.4); color:#fff; padding:5px 14px; border-radius:16px; font-size:12px; cursor:pointer; transition:.2s; }}
  #refresh-btn:hover {{ background:rgba(255,255,255,.25); }}
  #refresh-btn:disabled {{ opacity:.5; cursor:not-allowed; }}
  #refresh-status {{ font-size:12px; opacity:.8; }}
  #last-updated {{ font-size:13px; opacity:.75; }}
</style>
</head>
<body>

<div class="header">
  <h1>ASX200 Valuation Report</h1>
  <p>All figures in AUD unless otherwise noted &bull; Data: Yahoo Finance</p>
  <div class="refresh-bar">
    <span id="last-updated">Data as of {last_updated or REPORT_DATE}</span>
    <button id="refresh-btn" onclick="triggerRefresh()">&#x21bb; Refresh Data</button>
    <span id="refresh-status"></span>
  </div>
</div>

<nav class="nav">
  <a href="#" class="active" onclick="showSection('overview',this)">Overview</a>
  <a href="#" onclick="showSection('table',this)">Comparison Table</a>
  <a href="#" onclick="showSection('cards',this)">Company Cards</a>
  <a href="#" onclick="showSection('sectors',this)">By Sector</a>
  <a href="#" onclick="showSection('macro',this)" style="color:#3498db;font-weight:700">&#x1f4f0; Macro News</a>
  <a href="#" onclick="showSection('quant',this)" style="color:#e67e22;font-weight:700">&#x1f4c8; Quant</a>
  <a href="#" onclick="showSection('portfolio',this)" style="color:#27ae60;font-weight:700">&#x1f4b0; Portfolio</a>
  <a href="#" onclick="showSection('manual',this)" style="color:#8e44ad;font-weight:700">&#x1f3af; My Trades</a>
</nav>

<!-- OVERVIEW -->
<div id="overview" class="section active">
  <div class="stat-grid">
    <div class="stat-box">
      <div class="label">Companies Analysed</div>
      <div class="value">{len(companies)}</div>
      <div class="sub">ASX200 constituents</div>
    </div>
    <div class="stat-box">
      <div class="label" style="color:#27ae60">Cheap</div>
      <div class="value" style="color:#27ae60">{signal_counts['Cheap']}</div>
      <div class="sub">Attractive valuation</div>
    </div>
    <div class="stat-box">
      <div class="label" style="color:#f39c12">Fair Value</div>
      <div class="value" style="color:#f39c12">{signal_counts['Fair']}</div>
      <div class="sub">Fairly priced</div>
    </div>
    <div class="stat-box">
      <div class="label" style="color:#e74c3c">Expensive</div>
      <div class="value" style="color:#e74c3c">{signal_counts['Expensive']}</div>
      <div class="sub">Premium valuation</div>
    </div>
    <div class="stat-box">
      <div class="label">Data N/A</div>
      <div class="value" style="color:#888">{signal_counts['N/A']}</div>
      <div class="sub">Insufficient data</div>
    </div>
  </div>

  {macro_context_html}

  <h2>Top Picks — Cheap Signal</h2>
  {top_picks_html if top_picks_html else '<p style="color:#888;font-style:italic">No companies currently flagged as Cheap.</p>'}

  <h2 style="margin-top:28px">Sector Breakdown</h2>
  <table>
    <thead>
      <tr>
        <th>Sector</th>
        <th style="text-align:center">Companies</th>
        <th style="text-align:right">Total Market Cap</th>
        <th style="text-align:right">Avg P/E</th>
        <th style="text-align:right">Avg Div Yield</th>
        <th style="text-align:center">News Sentiment</th>
      </tr>
    </thead>
    <tbody>
      {sector_rows}
    </tbody>
  </table>

  <div class="disclaimer" style="margin-top:20px">
    <b>Valuation Signal Methodology:</b> The Cheap/Fair/Expensive signal is a simple composite of trailing P/E, Price/Book, EV/EBITDA, and dividend yield relative to thresholds. It is a screening tool only and does not constitute financial advice. Past performance is not indicative of future results.
  </div>
</div>

<!-- TABLE -->
<div id="table" class="section">
  <h2>Full Comparison Table</h2>
  <div class="filter-bar" id="tableFilters">
    <button class="filter-btn active" onclick="filterTable('all',this)">All</button>
    <button class="filter-btn" onclick="filterTable('Cheap',this)" style="border-color:#27ae60;color:#27ae60">Cheap</button>
    <button class="filter-btn" onclick="filterTable('Fair',this)" style="border-color:#f39c12;color:#f39c12">Fair</button>
    <button class="filter-btn" onclick="filterTable('Expensive',this)" style="border-color:#e74c3c;color:#e74c3c">Expensive</button>
  </div>
  <table id="mainTable">
    <thead>
      <tr>
        <th class="sortable" onclick="sortTable(0)"># <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(1)">Company <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(2)">Sector <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(3)" style="text-align:right">Price <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(4)" style="text-align:right">Mkt Cap <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(5)" style="text-align:right">P/E (TTM) <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(6)" style="text-align:right">Fwd P/E <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(7)" style="text-align:right">EV/EBITDA <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(8)" style="text-align:right">P/B <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(9)" style="text-align:right">Div Yield <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(10)" style="text-align:right">ROE <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(11)" style="text-align:right">Analyst Upside <span class="sort-arrow">&#9650;</span></th>
        <th class="sortable" onclick="sortTable(12)" style="text-align:center">Signal <span class="sort-arrow">&#9650;</span></th>
      </tr>
    </thead>
    <tbody id="tableBody">
      {all_rows}
    </tbody>
  </table>
</div>

<!-- CARDS -->
<div id="cards" class="section">
  <h2>Company Deep-Dive Cards</h2>
  <div class="filter-bar" id="cardFilters">
    <button class="filter-btn active" onclick="filterCards('all',this)">All</button>
    <button class="filter-btn" onclick="filterCards('Cheap',this)" style="border-color:#27ae60;color:#27ae60">Cheap</button>
    <button class="filter-btn" onclick="filterCards('Fair',this)" style="border-color:#f39c12;color:#f39c12">Fair</button>
    <button class="filter-btn" onclick="filterCards('Expensive',this)" style="border-color:#e74c3c;color:#e74c3c">Expensive</button>
    <button class="filter-btn" onclick="filterCards('Financials',this)">Financials</button>
    <button class="filter-btn" onclick="filterCards('Materials',this)">Materials</button>
    <button class="filter-btn" onclick="filterCards('Health Care',this)">Health Care</button>
    <button class="filter-btn" onclick="filterCards('Real Estate',this)">Real Estate</button>
    <button class="filter-btn" onclick="filterCards('Energy',this)">Energy</button>
  </div>
  <div class="cards-grid" id="cardsGrid">
    {all_cards}
  </div>
</div>

<!-- SECTORS -->
<div id="sectors" class="section">
  <h2>Sector Analysis</h2>
  <p style="color:#666;font-size:13px;margin-bottom:20px">Average valuation metrics by GICS sector across ASX200 constituents.</p>
  {build_sectors_html(sectors, sector_news)}
</div>

<!-- MACRO NEWS -->
<div id="macro" class="section">
  <h2>Macro &amp; News Context</h2>
  <p style="color:#666;font-size:13px;margin-bottom:20px">Current news headlines by GICS sector, with keyword-based sentiment analysis. Use this context alongside valuation signals for a more complete picture.</p>
  {macro_tab_html}
</div>

<!-- QUANT ANALYSIS -->
<div id="quant" class="section">
  <h2>&#x1f4c8; Quant Analysis — Technical &amp; Risk Metrics</h2>
  <p style="color:#666;font-size:13px;margin-bottom:20px">
    Technical indicators and risk metrics computed from 1-year historical price data.
    Use alongside valuation signals for a more complete picture.
  </p>
  {quant_tab_html}
</div>

<!-- PORTFOLIO -->
<div id="portfolio" class="section">
  <h2>Mock Portfolio — A$10,000 Initial Capital</h2>
  {_gen_pf(portfolio_summary) if _gen_pf else '<p style="color:#888">portfolio.py not found.</p>'}
</div>

<!-- MANUAL TRADES -->
<div id="manual" class="section">
  <h2>&#x1f3af; My Trades — Manual Paper Trading</h2>
  <p style="color:#666;font-size:13px;margin-bottom:16px">
    Pick your own stocks and compare performance against the automated strategy.
    Both portfolios started with A$10,000 and pay 0.1% brokerage per trade.
    <i>Requires the local server (launch_report.bat).</i>
  </p>
  {manual_tab_html}
</div>

<div style="text-align:center;padding:20px;color:#aaa;font-size:11px">
  ASX200 Valuation Report &bull; {REPORT_DATE} &bull; Data: Yahoo Finance &bull; For informational purposes only
</div>

<script>
function showSection(id, el) {{
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if (el) el.classList.add('active');
  return false;
}}
// Restore tab from URL hash on page load
(function() {{
  var h = location.hash.replace('#','');
  if (h && document.getElementById(h)) {{
    var link = document.querySelector('.nav a[onclick*=\"' + h + '\"]');
    showSection(h, link);
    location.hash = '';
  }}
}})();

function filterTable(val, btn) {{
  document.querySelectorAll('#tableFilters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#tableBody .company-row').forEach(row => {{
    if (val === 'all') {{
      row.style.display = '';
    }} else {{
      row.style.display = (row.dataset.signal === val) ? '' : 'none';
    }}
  }});
}}

function filterCards(val, btn) {{
  document.querySelectorAll('#cardFilters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#cardsGrid .card').forEach(card => {{
    if (val === 'all') {{
      card.style.display = '';
    }} else {{
      const matchSignal = card.dataset.signal === val;
      const matchSector = card.dataset.sector === val;
      card.style.display = (matchSignal || matchSector) ? '' : 'none';
    }}
  }});
}}

// ── Column sorting ──────────────────────────────────────────────────────────
var _sortCol = -1, _sortAsc = true;
function parseSortVal(text, colIdx) {{
  // Strip HTML tags if any
  var s = text.replace(/<[^>]*>/g, '').trim();
  // Text columns: Company(1), Sector(2), Signal(12)
  if (colIdx === 1 || colIdx === 2 || colIdx === 12) return s.toLowerCase();
  // Row number
  if (colIdx === 0) {{ var n = parseInt(s); return isNaN(n) ? 0 : n; }}
  // Numeric columns — strip currency symbols, %, commas, suffixes
  // Handle "—" or "N/A" as very low value so they sort to bottom
  if (s === '\u2014' || s === '—' || s === 'N/A' || s === '' || s === '-') return -1e18;
  // Market cap: e.g. "A$215.4B" or "$2.3T" or "A$890.5M"
  if (colIdx === 4) {{
    s = s.replace(/^A?\$/, '').replace(/,/g, '');
    var mult = 1;
    if (s.endsWith('T')) {{ mult = 1e12; s = s.slice(0, -1); }}
    else if (s.endsWith('B')) {{ mult = 1e9; s = s.slice(0, -1); }}
    else if (s.endsWith('M')) {{ mult = 1e6; s = s.slice(0, -1); }}
    else if (s.endsWith('K')) {{ mult = 1e3; s = s.slice(0, -1); }}
    var v = parseFloat(s);
    return isNaN(v) ? -1e18 : v * mult;
  }}
  // All other numeric: strip A$, $, %, ×, x, commas
  s = s.replace(/^A?\$/, '').replace(/%$/, '').replace(/×$/, '').replace(/x$/, '').replace(/,/g, '');
  var v = parseFloat(s);
  return isNaN(v) ? -1e18 : v;
}}

function sortTable(colIdx) {{
  var tbody = document.getElementById('tableBody');
  var rows = Array.from(tbody.querySelectorAll('tr.company-row'));
  if (rows.length === 0) return;

  // Toggle direction if same column clicked again
  if (_sortCol === colIdx) {{ _sortAsc = !_sortAsc; }}
  else {{ _sortCol = colIdx; _sortAsc = true; }}

  // Update header arrows
  document.querySelectorAll('#mainTable thead th').forEach(function(th, i) {{
    th.classList.remove('sort-asc', 'sort-desc');
    var arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.innerHTML = '&#9650;';
  }});
  var activeTh = document.querySelectorAll('#mainTable thead th')[colIdx];
  if (activeTh) {{
    activeTh.classList.add(_sortAsc ? 'sort-asc' : 'sort-desc');
    var arrow = activeTh.querySelector('.sort-arrow');
    if (arrow) arrow.innerHTML = _sortAsc ? '&#9650;' : '&#9660;';
  }}

  rows.sort(function(a, b) {{
    var aVal = parseSortVal(a.cells[colIdx].innerHTML, colIdx);
    var bVal = parseSortVal(b.cells[colIdx].innerHTML, colIdx);
    var cmp;
    if (typeof aVal === 'string' && typeof bVal === 'string') {{
      cmp = aVal.localeCompare(bVal);
    }} else {{
      cmp = (aVal > bVal ? 1 : aVal < bVal ? -1 : 0);
    }}
    return _sortAsc ? cmp : -cmp;
  }});

  // Re-number the # column and re-insert rows
  rows.forEach(function(row, idx) {{
    row.cells[0].textContent = idx + 1;
    tbody.appendChild(row);
  }});
}}

// ── Quant table sorting & filtering ─────────────────────────────────────────
var _qSortCol = -1, _qSortAsc = true;
function sortQuantTable(colIdx) {{
  var tbody = document.getElementById('quantBody');
  if (!tbody) return;
  var rows = Array.from(tbody.rows);
  if (_qSortCol === colIdx) {{ _qSortAsc = !_qSortAsc; }}
  else {{ _qSortCol = colIdx; _qSortAsc = (colIdx <= 1) ? true : false; }}
  rows.sort(function(a, b) {{
    var aCell = a.cells[colIdx], bCell = b.cells[colIdx];
    var aVal = aCell.getAttribute('data-sort') || aCell.textContent.trim();
    var bVal = bCell.getAttribute('data-sort') || bCell.textContent.trim();
    var aNum = parseFloat(aVal), bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {{
      return _qSortAsc ? aNum - bNum : bNum - aNum;
    }}
    return _qSortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  }});
  rows.forEach(function(row, idx) {{
    row.cells[0].textContent = idx + 1;
    tbody.appendChild(row);
  }});
}}
function filterQuant(val, btn) {{
  document.querySelectorAll('#quantFilters .filter-btn').forEach(function(b) {{
    b.style.background = '#fff'; b.style.color = b.dataset.origColor || '#555';
  }});
  btn.style.background = '#2c3e50'; btn.style.color = '#fff';
  var rows = document.querySelectorAll('#quantBody tr');
  rows.forEach(function(row) {{
    if (val === 'all') {{ row.style.display = ''; }}
    else {{ row.style.display = row.getAttribute('data-quant-signal') === val ? '' : 'none'; }}
  }});
}}

// ── Manual trading ──────────────────────────────────────────────────────────
function executeBuy() {{
  var ticker = document.getElementById('manualTicker').value;
  var amount = parseFloat(document.getElementById('manualAmount').value);
  var msg = document.getElementById('tradeMsg');
  if (!ticker) {{ msg.textContent = 'Please select a stock.'; msg.style.color='#e74c3c'; return; }}
  if (!amount || amount <= 0) {{ msg.textContent = 'Enter a valid amount.'; msg.style.color='#e74c3c'; return; }}
  msg.textContent = 'Processing...'; msg.style.color='#888';
  fetch('/api/manual/buy', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ticker: ticker, amount: amount}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(d) {{
    msg.textContent = d.msg;
    msg.style.color = d.ok ? '#27ae60' : '#e74c3c';
    if (d.ok) {{ setTimeout(function() {{ location.hash='#manual'; location.reload(); }}, 800); }}
  }})
  .catch(function(e) {{
    msg.textContent = 'Server not running. Use launch_report.bat.';
    msg.style.color = '#e74c3c';
  }});
}}

function executeSell(ticker) {{
  if (!confirm('Sell all shares of ' + ticker.replace('.AX','') + '?')) return;
  var msg = document.getElementById('tradeMsg');
  msg.textContent = 'Selling...'; msg.style.color='#888';
  fetch('/api/manual/sell', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ticker: ticker, shares: 'all'}})
  }})
  .then(function(r) {{ return r.json(); }})
  .then(function(d) {{
    msg.textContent = d.msg;
    msg.style.color = d.ok ? '#27ae60' : '#e74c3c';
    if (d.ok) {{ setTimeout(function() {{ location.hash='#manual'; location.reload(); }}, 800); }}
  }})
  .catch(function(e) {{
    msg.textContent = 'Server not running.';
    msg.style.color = '#e74c3c';
  }});
}}

// ── Auto-refresh (requires local server at localhost:8765) ──────────────────
function triggerRefresh() {{
  var btn = document.getElementById('refresh-btn');
  var status = document.getElementById('refresh-status');
  btn.disabled = true;
  status.textContent = 'Starting refresh...';
  fetch('/api/refresh', {{method: 'POST'}})
    .then(function() {{ pollRefreshStatus(); }})
    .catch(function(e) {{
      status.textContent = 'Run launch_report.bat to enable live refresh.';
      btn.disabled = false;
    }});
}}

function pollRefreshStatus() {{
  fetch('/api/status')
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      var status = document.getElementById('refresh-status');
      if (d.refresh_running) {{
        status.textContent = d.refresh_message + ' (' + d.refresh_progress + '/' + d.refresh_total + ')';
        setTimeout(pollRefreshStatus, 1500);
      }} else {{
        status.textContent = 'Done! Reloading...';
        setTimeout(function() {{ location.reload(); }}, 800);
      }}
    }})
    .catch(function() {{
      document.getElementById('refresh-status').textContent = 'Server not running.';
      document.getElementById('refresh-btn').disabled = false;
    }});
}}

// On page load: check server for age info
window.addEventListener('load', function() {{
  fetch('/api/status')
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.last_updated) {{
        var age = d.age_minutes !== null ? ' (' + d.age_minutes + ' min ago)' : '';
        document.getElementById('last-updated').textContent = 'Data as of ' + d.last_updated + age;
      }}
      if (d.refresh_running) {{
        document.getElementById('refresh-btn').disabled = true;
        pollRefreshStatus();
      }}
    }})
    .catch(function() {{ /* static file mode — ignore */ }});
}});
</script>
</body>
</html>"""
    return html


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Step 1: Fetching ASX200 constituent list...")
    tickers, names, sectors = get_asx200_tickers()
    print(f"  {len(tickers)} companies to analyse\n")

    print("Step 2: Fetching financial data from Yahoo Finance...")
    companies = []
    for i, (tick, name, sector) in enumerate(zip(tickers, names, sectors)):
        print(f"  [{i+1:2d}/{len(tickers)}] {tick} — {name}")
        data = fetch_company_data(tick, name, sector)
        companies.append(data)

    print(f"\nStep 3: Updating mock portfolio...")
    portfolio_summary = None
    try:
        from portfolio import PortfolioManager
        pm = PortfolioManager()
        if pm.load():
            pm.update(companies)
        else:
            pm.initialize(companies)
        portfolio_summary = pm.get_summary()
        print(f"  Portfolio value: A${portfolio_summary['total_value']:,.2f} "
              f"({'+' if portfolio_summary['cum_pnl']>=0 else ''}A${portfolio_summary['cum_pnl']:,.2f})")
    except Exception as e:
        print(f"  Portfolio error: {e}")

    print(f"\nStep 4: Fetching sector news...")
    sector_news = None
    try:
        from news_analysis import fetch_sector_news
        sector_news = fetch_sector_news()
        macro_sent = sector_news.get("_macro", {}).get("sentiment", "N/A")
        print(f"  Global macro sentiment: {macro_sent}")
    except Exception as e:
        print(f"  News fetch error: {e}")

    print(f"\nStep 5: Fetching company news for reassessment...")
    company_news = None
    reassessments = None
    try:
        from news_analysis import fetch_company_news, reassess_stock
        company_news = fetch_company_news(companies)
        reassessments = {}
        sn = sector_news or {}
        for c in companies:
            ticker = c.get("ticker", "")
            if ticker in (company_news or {}) and c.get("signal") in ("Cheap", "Fair"):
                sector = c.get("sector", "")
                sector_sent = sn.get(sector, {}).get("sentiment", "Neutral")
                reassessments[ticker] = reassess_stock(c, company_news[ticker], sector_sent)
        print(f"  Reassessed {len(reassessments)} stocks")
    except Exception as e:
        print(f"  Company news error: {e}")

    print(f"\nStep 6: Generating HTML report...")
    html = generate_html(companies, portfolio_summary=portfolio_summary,
                         sector_news=sector_news, company_news=company_news,
                         reassessments=reassessments)

    out_path = os.path.join(DIR, "ASX200_Valuation_Report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport saved to:\n  {out_path}")
    print(f"\nValuation summary:")
    for sig in ["Cheap", "Fair", "Expensive", "N/A"]:
        count = sum(1 for c in companies if c.get("signal") == sig)
        print(f"  {sig:10s}: {count}")
