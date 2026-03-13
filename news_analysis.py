"""
News-based sector analysis for ASX200 Report.
Fetches headlines from Google News RSS (free, no API key required).
Results are cached for 6 hours to avoid hammering the feed.
"""

import json
import os
import re
import time
import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
from email.utils import parsedate

DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_CACHE_FILE = os.path.join(DIR, "news_cache.json")
NEWS_CACHE_MAX_AGE = 6 * 3600  # 6 hours

# ── Per-sector search queries ─────────────────────────────────────────────────
SECTOR_QUERIES = {
    "Energy": [
        "Australia oil LNG energy sector 2026",
        "oil price OPEC geopolitical supply 2026",
    ],
    "Materials": [
        "iron ore copper mining Australia 2026",
        "BHP Rio Tinto commodity prices 2026",
    ],
    "Financials": [
        "RBA interest rate Australia banking 2026",
        "Australian bank earnings profits 2026",
    ],
    "Health Care": [
        "CSL healthcare pharmaceutical Australia 2026",
        "ASX health sector biotech 2026",
    ],
    "Real Estate": [
        "Australia property market REIT 2026",
        "Australian commercial real estate housing 2026",
    ],
    "Consumer Discretionary": [
        "Australia retail consumer spending 2026",
        "Wesfarmers Australian consumer sector 2026",
    ],
    "Consumer Staples": [
        "Woolworths Coles grocery Australia 2026",
        "Australia food inflation consumer staples 2026",
    ],
    "Communication Services": [
        "Telstra Australia telecom NBN 2026",
        "Australian media communication sector 2026",
    ],
    "Industrials": [
        "Australia infrastructure construction 2026",
        "Transurban Brambles ASX industrials 2026",
    ],
    "Utilities": [
        "Australia electricity renewable energy transition 2026",
        "AGL Origin energy utility ASX 2026",
    ],
    "Information Technology": [
        "ASX technology stocks AI 2026",
        "Pro Medicus technology Australia 2026",
    ],
}

# Global macro themes affecting multiple sectors
GLOBAL_MACRO_QUERIES = [
    "US China trade tariffs 2026",
    "Federal Reserve interest rates inflation 2026",
    "Australia RBA economy GDP 2026",
    "Middle East geopolitical oil 2026",
    "AUD US dollar exchange rate 2026",
]

# ── Sentiment keyword stems ───────────────────────────────────────────────────
BEARISH_STEMS = {
    "war", "crisis", "sanction", "conflict", "attack", "declin", "fall",
    "crash", "recession", "slowdown", "concern", "risk", "threat", "plung",
    "slump", "drop", "loss", "deficit", "downgra", "cut", "weak", "poor",
    "tariff", "ban", "shortage", "strike", "collaps", "bankrupt", "default",
    "fraud", "investiga", "disappoint", "warn", "pressure", "fear", "drag",
    "headwind", "miss", "overval", "downside",
}
BULLISH_STEMS = {
    "growth", "boost", "surge", "record", "recovery", "rally", "gain",
    "profit", "beat", "upgrade", "expansion", "invest", "strong", "rise",
    "increas", "improv", "exceed", "outperform", "dividend", "acqui",
    "deal", "approv", "rebound", "upside", "optimis", "opportuni",
    "accelerat", "positive", "robust", "solid", "success", "milestone",
    "partner", "breakout",
}


# ── RSS fetcher ───────────────────────────────────────────────────────────────

def _fetch_rss(query, max_items=5, timeout=8):
    """Fetch Google News RSS headlines for a query.
    Returns list of dicts: [{"title": str, "date": str}, ...]
    """
    encoded = urllib.parse.quote(query)
    url = "https://news.google.com/rss/search?q={}&hl=en-AU&gl=AU&ceid=AU:en".format(encoded)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ASX-Research/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:max_items]:
            title_el = item.find("title")
            pub_el   = item.find("pubDate")
            if title_el is None or not title_el.text:
                continue
            # Remove " - Source Name" suffix Google appends to titles
            title = re.sub(r'\s+-\s+[A-Z][^-]{1,60}$', '', title_el.text).strip()
            if not title:
                continue
            pub_date = ""
            if pub_el is not None and pub_el.text:
                try:
                    t = parsedate(pub_el.text)
                    if t:
                        pub_date = datetime.date(t[0], t[1], t[2]).strftime("%d %b")
                except Exception:
                    pass
            # Capture article URL from <link> element
            link_el = item.find("link")
            link_url = ""
            if link_el is not None:
                link_url = (link_el.text or "").strip()
                if not link_url and link_el.tail:
                    link_url = link_el.tail.strip()
            items.append({"title": title, "date": pub_date, "url": link_url})
        return items
    except Exception:
        return []


# ── Sentiment scoring ─────────────────────────────────────────────────────────

def _score_sentiment(headlines):
    """Keyword-based sentiment: returns (score, label).
    score > 0 = bullish, score < 0 = bearish.
    """
    if not headlines:
        return 0, "Neutral"
    text = " ".join(h["title"].lower() for h in headlines)
    words = re.findall(r'\b\w+\b', text)
    bull = sum(1 for w in words if any(w.startswith(s) for s in BULLISH_STEMS) and len(w) >= 4)
    bear = sum(1 for w in words if any(w.startswith(s) for s in BEARISH_STEMS) and len(w) >= 4)
    score = bull - bear
    if score >= 2:
        return score, "Bullish"
    elif score <= -2:
        return score, "Bearish"
    else:
        return score, "Neutral"


# ── Main public function ──────────────────────────────────────────────────────

def fetch_sector_news(force_refresh=False):
    """
    Fetch news analysis for all GICS sectors + global macro.

    Returns a dict with keys:
      - GICS sector names  (e.g. "Energy", "Financials", ...)
      - "_macro"           (global macro themes)
      - "_fetched"         (unix timestamp of last fetch)
      - "_fetched_str"     (human-readable timestamp)

    Each sector entry:
      {"headlines": [{"title":..,"date":..},...], "sentiment": str, "sentiment_score": int}

    Results are cached for 6 hours unless force_refresh=True.
    """
    if not force_refresh and os.path.exists(NEWS_CACHE_FILE):
        try:
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age = time.time() - cached.get("_fetched", 0)
            if age < NEWS_CACHE_MAX_AGE:
                return cached
        except Exception:
            pass

    result = {}
    print("  Fetching sector news from Google News RSS...")

    for sector, queries in SECTOR_QUERIES.items():
        all_items = []
        for q in queries:
            all_items.extend(_fetch_rss(q, max_items=3))
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for item in all_items:
            if item["title"] not in seen:
                seen.add(item["title"])
                unique.append(item)
        score, label = _score_sentiment(unique)
        result[sector] = {
            "headlines":       unique[:6],
            "sentiment":       label,
            "sentiment_score": score,
        }
        print("    {}: {} ({} headlines)".format(sector, label, len(unique)))

    # Global macro
    macro_items = []
    for q in GLOBAL_MACRO_QUERIES:
        macro_items.extend(_fetch_rss(q, max_items=3))
    seen = set()
    macro_unique = []
    for item in macro_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            macro_unique.append(item)
    score, label = _score_sentiment(macro_unique)
    result["_macro"] = {
        "headlines":       macro_unique[:10],
        "sentiment":       label,
        "sentiment_score": score,
    }

    result["_fetched"]     = time.time()
    result["_fetched_str"] = datetime.datetime.now().strftime("%d %b %Y %H:%M")

    try:
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("  News cache saved ({} sectors + macro).".format(len(SECTOR_QUERIES)))
    except Exception as e:
        print("  News cache save failed: {}".format(e))

    return result


# ── Per-company news for Cheap / Fair reassessment ───────────────────────────

COMPANY_NEWS_CACHE_KEY = "_company_news"

# High-severity keywords that raise red flags regardless of overall sentiment
RISK_KEYWORDS = [
    ("scandal", "Scandal reported"),
    ("fraud", "Fraud allegation"),
    ("asic", "ASIC regulatory action"),
    ("investigation", "Under investigation"),
    ("class action", "Class action risk"),
    ("recall", "Product recall"),
    ("downgrade", "Analyst downgrade"),
    ("profit warning", "Profit warning"),
    ("guidance cut", "Guidance cut"),
    ("write-down", "Write-down"),
    ("writedown", "Write-down"),
    ("impairment", "Asset impairment"),
    ("ceo resign", "CEO resignation"),
    ("ceo step", "CEO departure"),
    ("management change", "Management shake-up"),
    ("board shake", "Board shake-up"),
    ("suspend", "Trading/operations suspension"),
    ("delist", "Delisting risk"),
    ("default", "Default risk"),
    ("bankrupt", "Bankruptcy risk"),
]

CONVICTION_COLORS = {
    "High":    "#27ae60",
    "Medium":  "#3498db",
    "Low":     "#f39c12",
    "Caution": "#e74c3c",
}


def fetch_company_news(companies, force_refresh=False):
    """
    Fetch company-specific news for Cheap and Fair stocks.
    Returns dict: {ticker: {"headlines": [...], "sentiment": str, "sentiment_score": int}}
    """
    # Check cache
    if not force_refresh and os.path.exists(NEWS_CACHE_FILE):
        try:
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age = time.time() - cached.get("_fetched", 0)
            if age < NEWS_CACHE_MAX_AGE and COMPANY_NEWS_CACHE_KEY in cached:
                return cached[COMPANY_NEWS_CACHE_KEY]
        except Exception:
            pass

    targets = [c for c in companies
               if c.get("signal") in ("Cheap", "Fair") and c.get("price")]

    result = {}
    print("  Fetching company-specific news for {} stocks...".format(len(targets)))

    for c in targets:
        ticker = c.get("ticker", "")
        # Strip .AX suffix for search query
        short_tick = ticker.replace(".AX", "")
        name = c.get("name", short_tick)
        # Build search query: quoted company name + ASX + ticker code
        query = '"{}" ASX {} 2026'.format(name, short_tick)
        headlines = _fetch_rss(query, max_items=5)

        if not headlines:
            # Fallback: try just ticker + ASX
            query = "{} ASX stock news".format(short_tick)
            headlines = _fetch_rss(query, max_items=3)

        score, label = _score_sentiment(headlines)
        result[ticker] = {
            "headlines": headlines[:5],
            "sentiment": label,
            "sentiment_score": score,
        }
        print("    {}: {} (score {}, {} headlines)".format(
            short_tick, label, score, len(headlines)))
        time.sleep(0.3)  # rate-limit courtesy

    # Save into the existing news cache file under _company_news key
    try:
        cache_data = {}
        if os.path.exists(NEWS_CACHE_FILE):
            with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        cache_data[COMPANY_NEWS_CACHE_KEY] = result
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        print("  Company news cached ({} stocks).".format(len(result)))
    except Exception as e:
        print("  Company news cache save failed: {}".format(e))

    return result


def reassess_stock(company, company_news, sector_sentiment):
    """
    Produce a reassessment for a Cheap/Fair stock based on news context.

    Parameters
    ----------
    company : dict          — company data dict (has "ticker", "name", "signal", "sector")
    company_news : dict     — {"headlines": [...], "sentiment": str, "sentiment_score": int}
    sector_sentiment : str  — "Bullish", "Neutral", or "Bearish"

    Returns
    -------
    dict with keys: conviction, conviction_color, commentary, company_sentiment,
                    sector_sentiment, flags
    """
    c_sent = company_news.get("sentiment", "Neutral")
    s_sent = sector_sentiment or "Neutral"
    headlines = company_news.get("headlines", [])
    signal = company.get("signal", "Fair")
    name = company.get("name", company.get("ticker", "?"))
    short_tick = company.get("ticker", "").replace(".AX", "")

    # ── Detect risk flags ────────────────────────────────────────────────────
    flags = []
    all_text = " ".join(h.get("title", "").lower() for h in headlines)
    seen_flags = set()
    for keyword, flag_label in RISK_KEYWORDS:
        if keyword in all_text and flag_label not in seen_flags:
            flags.append(flag_label)
            seen_flags.add(flag_label)

    # ── Conviction matrix ────────────────────────────────────────────────────
    matrix = {
        ("Bullish",  "Bullish"):  "High",
        ("Bullish",  "Neutral"):  "High",
        ("Neutral",  "Bullish"):  "Medium",
        ("Neutral",  "Neutral"):  "Medium",
        ("Bullish",  "Bearish"):  "Medium",
        ("Neutral",  "Bearish"):  "Low",
        ("Bearish",  "Bullish"):  "Low",
        ("Bearish",  "Neutral"):  "Caution",
        ("Bearish",  "Bearish"):  "Caution",
    }
    conviction = matrix.get((c_sent, s_sent), "Medium")

    # Risk flags can downgrade conviction
    if flags and conviction in ("High", "Medium"):
        conviction = "Low"
    if len(flags) >= 2:
        conviction = "Caution"

    conv_color = CONVICTION_COLORS.get(conviction, "#888")

    # ── Build commentary ─────────────────────────────────────────────────────
    parts = []
    parts.append("{} ({}) is rated {} on valuation metrics.".format(name, short_tick, signal))

    if c_sent == "Bearish":
        parts.append("Company-specific news is predominantly negative.")
    elif c_sent == "Bullish":
        parts.append("Recent company news flow is supportive.")
    else:
        parts.append("Company news flow is mixed/neutral.")

    if s_sent == "Bearish":
        parts.append("The broader sector faces headwinds.")
    elif s_sent == "Bullish":
        parts.append("Sector tailwinds are favourable.")

    if flags:
        parts.append("Flagged risks: " + "; ".join(flags) + ".")

    if conviction == "Caution":
        parts.append("Despite attractive valuation, news signals warrant caution.")
    elif conviction == "High":
        parts.append("News signals support the valuation thesis.")

    commentary = " ".join(parts)

    return {
        "conviction":        conviction,
        "conviction_color":  conv_color,
        "commentary":        commentary,
        "company_sentiment": c_sent,
        "sector_sentiment":  s_sent,
        "flags":             flags,
    }
