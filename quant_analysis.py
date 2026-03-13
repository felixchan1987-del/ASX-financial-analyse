"""
Quant Analysis module for ASX200 Report.
Fetches 1-year historical price data via yfinance, computes technical
indicators (RSI, MACD, SMA crossovers, Bollinger Bands, ATR) and risk
metrics (volatility, Sharpe ratio, max drawdown), then generates the
HTML for the Quant Analysis tab.

Cached to quant_cache.json (max age 4 h).
"""

import json, os, time, math
from datetime import datetime, date
import yfinance as yf
import pandas as pd

# ── constants ─────────────────────────────────────────────────────────────────
DIR              = os.path.dirname(os.path.abspath(__file__))
QUANT_CACHE_FILE = os.path.join(DIR, "quant_cache.json")
QUANT_CACHE_MAX  = 4 * 3600          # 4 hours
RISK_FREE_RATE   = 0.0435            # RBA cash rate
TRADING_DAYS     = 252
MIN_DATA_POINTS  = 50                # minimum for any indicator
CHART_DAYS       = 90                # last N days for SVG mini-chart

# ── helpers ───────────────────────────────────────────────────────────────────

def _html_esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def _fmt_pct(v, dp=1):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return "{:+.{d}f}%".format(v * 100, d=dp)


def _fmt_num(v, dp=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return "{:,.{d}f}".format(v, d=dp)


def _color_rsi(rsi):
    if rsi is None: return "#888"
    if rsi >= 70:   return "#e74c3c"
    if rsi >= 60:   return "#ef5350"
    if rsi <= 30:   return "#27ae60"
    if rsi <= 40:   return "#66bb6a"
    return "#333"


def _color_sharpe(s):
    if s is None: return "#888"
    if s >= 1.0:  return "#27ae60"
    if s >= 0.5:  return "#66bb6a"
    if s >= 0:    return "#333"
    if s >= -0.5: return "#ef5350"
    return "#e74c3c"


# ── historical data fetching ──────────────────────────────────────────────────

def fetch_historical_data(tickers_ax, period="1y", progress_cb=None):
    """
    Fetch 1-year daily OHLCV for all tickers via yfinance.
    Returns dict keyed by ticker WITHOUT .AX suffix.
    """
    result = {}
    total = len(tickers_ax)
    for idx, ticker_ax in enumerate(tickers_ax, 1):
        raw = ticker_ax.replace(".AX", "")
        if progress_cb:
            progress_cb(idx, total, ticker_ax)
        try:
            df = yf.Ticker(ticker_ax).history(period=period)
            if df is None or df.empty:
                result[raw] = []
                continue
            rows = []
            for dt, row in df.iterrows():
                rows.append({
                    "date":   dt.strftime("%Y-%m-%d"),
                    "open":   round(float(row.get("Open", 0)), 4),
                    "high":   round(float(row.get("High", 0)), 4),
                    "low":    round(float(row.get("Low", 0)), 4),
                    "close":  round(float(row.get("Close", 0)), 4),
                    "volume": int(row.get("Volume", 0)),
                })
            result[raw] = rows
        except Exception as e:
            print("  yfinance history error for {}: {}".format(ticker_ax, e))
            result[raw] = []
        time.sleep(0.3)
    return result


# ── technical indicator calculations ──────────────────────────────────────────

def _calc_rsi(closes, period=14):
    delta = closes.diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0/period, min_periods=period).mean()
    rs  = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _calc_macd(closes, fast=12, slow=26, signal=9):
    ema_fast    = closes.ewm(span=fast, adjust=False).mean()
    ema_slow    = closes.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


def _calc_sma(closes, period):
    return closes.rolling(period).mean()


def _calc_bollinger(closes, period=20, num_std=2):
    sma   = closes.rolling(period).mean()
    std   = closes.rolling(period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    return upper, lower, sma


def _calc_atr(highs, lows, closes, period=14):
    prev_close = closes.shift(1)
    tr = pd.concat([
        highs - lows,
        (highs - prev_close).abs(),
        (lows  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _calc_risk_metrics(closes):
    daily_ret = closes.pct_change().dropna()
    if len(daily_ret) < 20:
        return None
    ann_vol = float(daily_ret.std() * (TRADING_DAYS ** 0.5))
    total_ret = (closes.iloc[-1] / closes.iloc[0]) - 1.0
    n_days    = len(closes)
    ann_ret   = float((1.0 + total_ret) ** (TRADING_DAYS / n_days) - 1.0)
    sharpe    = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0
    cummax    = closes.cummax()
    drawdown  = (closes - cummax) / cummax
    max_dd    = float(drawdown.min())
    return {
        "ann_volatility": ann_vol,
        "ann_return":     ann_ret,
        "sharpe_ratio":   sharpe,
        "max_drawdown":   max_dd,
    }


# ── signal interpretation ─────────────────────────────────────────────────────

def _rsi_signal(rsi):
    if rsi is None: return 0, "N/A"
    if rsi < 30:    return  2, "Oversold"
    if rsi < 40:    return  1, "Near oversold"
    if rsi > 70:    return -2, "Overbought"
    if rsi > 60:    return -1, "Near overbought"
    return 0, "Neutral"


def _macd_signal(hist):
    """hist is the histogram Series; we look at last two values."""
    if hist is None or len(hist) < 2: return 0, "N/A"
    h1, h0 = float(hist.iloc[-2]), float(hist.iloc[-1])
    if math.isnan(h0) or math.isnan(h1): return 0, "N/A"
    if h0 > 0 and h0 > h1:  return  2, "Bullish+"
    if h0 > 0 and h0 <= h1: return  1, "Weakening+"
    if h0 < 0 and h0 > h1:  return -1, "Recovering-"
    if h0 < 0 and h0 <= h1: return -2, "Bearish-"
    return 0, "Neutral"


def _sma_signal(price, sma50, sma200, closes_sma50, closes_sma200):
    """Determine trend and detect golden/death cross (last 5 days)."""
    if sma50 is None or sma200 is None or math.isnan(sma50) or math.isnan(sma200):
        return 0, "N/A", None
    sig = 0
    if price > sma50 and sma50 > sma200:
        sig = 2; label = "Strong uptrend"
    elif price > sma200 and price <= sma50:
        sig = 1; label = "Pullback in uptrend"
    elif price < sma200 and price >= sma50:
        sig = -1; label = "Potential reversal"
    elif price < sma50 and sma50 < sma200:
        sig = -2; label = "Strong downtrend"
    else:
        label = "Mixed"
    # cross detection (last 5 bars)
    cross = None
    n = len(closes_sma50)
    if n >= 6:
        for i in range(max(1, n-5), n):
            prev50 = closes_sma50.iloc[i-1]
            prev200 = closes_sma200.iloc[i-1]
            cur50 = closes_sma50.iloc[i]
            cur200 = closes_sma200.iloc[i]
            if pd.notna(prev50) and pd.notna(prev200) and pd.notna(cur50) and pd.notna(cur200):
                if prev50 < prev200 and cur50 >= cur200:
                    cross = "golden"; sig = min(sig + 1, 3)
                elif prev50 > prev200 and cur50 <= cur200:
                    cross = "death"; sig = max(sig - 1, -3)
    return sig, label, cross


def _bb_signal(pct_b):
    if pct_b is None or math.isnan(pct_b): return 0, "N/A"
    if pct_b < 0.0:  return  2, "Below lower"
    if pct_b < 0.2:  return  1, "Near lower"
    if pct_b > 1.0:  return -2, "Above upper"
    if pct_b > 0.8:  return -1, "Near upper"
    return 0, "Mid-band"


# ── composite quant score ─────────────────────────────────────────────────────

SCORE_THRESHOLDS = [
    ( 4.0, "Bullish",      "#27ae60"),
    ( 1.5, "Lean Bullish", "#66bb6a"),
    (-1.5, "Neutral",      "#f39c12"),
    (-4.0, "Lean Bearish", "#ef5350"),
]
SCORE_WORST = ("Bearish", "#e74c3c")


def _composite_score(rsi_sig, macd_sig, sma_sig, bb_sig, sharpe):
    score = rsi_sig * 2 + macd_sig * 2 + sma_sig * 3 + bb_sig * 1
    # sharpe component
    if sharpe is not None and not math.isnan(sharpe):
        if   sharpe >  1.5: s = 2
        elif sharpe >  0.5: s = 1
        elif sharpe > -0.5: s = 0
        elif sharpe > -1.5: s = -1
        else:                s = -2
        score += s * 2
        total_weight = 10
    else:
        total_weight = 8
    normalised = score / total_weight * 5.0 if total_weight else 0.0
    normalised = max(-10.0, min(10.0, normalised))
    for threshold, label, color in SCORE_THRESHOLDS:
        if normalised >= threshold:
            return round(normalised, 1), label, color
    return round(normalised, 1), SCORE_WORST[0], SCORE_WORST[1]


# ── compute all indicators for one stock ──────────────────────────────────────

def compute_indicators(price_history, beta=None):
    """
    Compute all technical indicators and risk metrics for a single stock.
    price_history: list of dicts with keys date, open, high, low, close, volume.
    Returns dict of all indicators, or None if insufficient data.
    """
    if len(price_history) < MIN_DATA_POINTS:
        return None
    df = pd.DataFrame(price_history)
    closes = df["close"].astype(float)
    highs  = df["high"].astype(float)
    lows   = df["low"].astype(float)

    last_close = float(closes.iloc[-1])

    # RSI
    rsi_series = _calc_rsi(closes)
    rsi_val    = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None
    rsi_sig, rsi_lbl = _rsi_signal(rsi_val)

    # MACD
    macd_line, sig_line, hist = _calc_macd(closes)
    macd_val = float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else None
    sig_val  = float(sig_line.iloc[-1])  if pd.notna(sig_line.iloc[-1])  else None
    hist_val = float(hist.iloc[-1])      if pd.notna(hist.iloc[-1])      else None
    macd_sig, macd_lbl = _macd_signal(hist)

    # SMA 50 / 200
    sma50_s  = _calc_sma(closes, 50)
    sma200_s = _calc_sma(closes, 200)
    sma50_val  = float(sma50_s.iloc[-1])  if pd.notna(sma50_s.iloc[-1])  else None
    sma200_val = float(sma200_s.iloc[-1]) if pd.notna(sma200_s.iloc[-1]) else None
    sma_sig, sma_lbl, cross_type = _sma_signal(last_close, sma50_val, sma200_val, sma50_s, sma200_s)

    # Bollinger Bands
    bb_upper, bb_lower, bb_mid = _calc_bollinger(closes)
    bb_u = float(bb_upper.iloc[-1]) if pd.notna(bb_upper.iloc[-1]) else None
    bb_l = float(bb_lower.iloc[-1]) if pd.notna(bb_lower.iloc[-1]) else None
    bw   = (bb_u - bb_l) if (bb_u is not None and bb_l is not None and (bb_u - bb_l) > 0) else None
    pct_b = (last_close - bb_l) / bw if bw else None
    bb_sig, bb_lbl = _bb_signal(pct_b)

    # ATR
    atr_s   = _calc_atr(highs, lows, closes)
    atr_val = float(atr_s.iloc[-1]) if pd.notna(atr_s.iloc[-1]) else None
    atr_pct = (atr_val / last_close * 100) if (atr_val and last_close) else None

    # Risk metrics
    risk = _calc_risk_metrics(closes)

    sharpe = risk["sharpe_ratio"] if risk else None

    # Composite score
    q_score, q_label, q_color = _composite_score(rsi_sig, macd_sig, sma_sig, bb_sig, sharpe)

    # Collect last CHART_DAYS closes + sma50 for mini-chart
    chart_closes = [float(v) for v in closes.iloc[-CHART_DAYS:].tolist()]
    chart_sma50  = []
    for v in sma50_s.iloc[-CHART_DAYS:]:
        chart_sma50.append(float(v) if pd.notna(v) else None)

    return {
        "last_close":     last_close,
        "rsi":            round(rsi_val, 1) if rsi_val is not None else None,
        "rsi_signal":     rsi_sig,
        "rsi_label":      rsi_lbl,
        "macd_line":      round(macd_val, 3) if macd_val is not None else None,
        "macd_sig_line":  round(sig_val, 3) if sig_val is not None else None,
        "macd_histogram": round(hist_val, 3) if hist_val is not None else None,
        "macd_signal":    macd_sig,
        "macd_label":     macd_lbl,
        "sma50":          round(sma50_val, 2) if sma50_val is not None else None,
        "sma200":         round(sma200_val, 2) if sma200_val is not None else None,
        "sma_signal":     sma_sig,
        "sma_label":      sma_lbl,
        "cross_type":     cross_type,
        "bb_upper":       round(bb_u, 2) if bb_u is not None else None,
        "bb_lower":       round(bb_l, 2) if bb_l is not None else None,
        "bb_pct_b":       round(pct_b, 2) if pct_b is not None else None,
        "bb_signal":      bb_sig,
        "bb_label":       bb_lbl,
        "atr":            round(atr_val, 2) if atr_val is not None else None,
        "atr_pct":        round(atr_pct, 1) if atr_pct is not None else None,
        "ann_volatility": round(risk["ann_volatility"], 3) if risk else None,
        "ann_return":     round(risk["ann_return"], 3) if risk else None,
        "sharpe_ratio":   round(risk["sharpe_ratio"], 2) if risk else None,
        "max_drawdown":   round(risk["max_drawdown"], 3) if risk else None,
        "beta":           beta,
        "quant_score":    q_score,
        "quant_label":    q_label,
        "quant_color":    q_color,
        "chart_closes":   chart_closes,
        "chart_sma50":    chart_sma50,
    }


def _empty_indicators(beta=None):
    return {
        "last_close": None, "rsi": None, "rsi_signal": 0, "rsi_label": "N/A",
        "macd_line": None, "macd_sig_line": None, "macd_histogram": None,
        "macd_signal": 0, "macd_label": "N/A",
        "sma50": None, "sma200": None, "sma_signal": 0, "sma_label": "N/A", "cross_type": None,
        "bb_upper": None, "bb_lower": None, "bb_pct_b": None, "bb_signal": 0, "bb_label": "N/A",
        "atr": None, "atr_pct": None,
        "ann_volatility": None, "ann_return": None, "sharpe_ratio": None, "max_drawdown": None,
        "beta": beta,
        "quant_score": 0, "quant_label": "N/A", "quant_color": "#888",
        "chart_closes": [], "chart_sma50": [],
    }


# ── SVG mini-chart ────────────────────────────────────────────────────────────

def svg_price_chart(chart_closes, chart_sma50, width=260, height=70):
    """
    Render inline SVG sparkline: price line + SMA50 dashed overlay + area fill.
    """
    if not chart_closes or len(chart_closes) < 5:
        return '<svg width="{}" height="{}" xmlns="http://www.w3.org/2000/svg"></svg>'.format(width, height)

    pad_top, pad_bot = 4, 4
    h = height - pad_top - pad_bot
    n = len(chart_closes)

    all_vals = [v for v in chart_closes if v is not None]
    sma_vals = [v for v in chart_sma50 if v is not None]
    if sma_vals:
        all_vals.extend(sma_vals)
    vmin = min(all_vals)
    vmax = max(all_vals)
    if vmax == vmin:
        vmax = vmin + 1

    def _x(i):
        return round(i / (n - 1) * width, 1)

    def _y(v):
        return round(pad_top + h - (v - vmin) / (vmax - vmin) * h, 1)

    # price line points
    pts = []
    for i, v in enumerate(chart_closes):
        if v is not None:
            pts.append("{},{}".format(_x(i), _y(v)))
    price_line = " ".join(pts)

    # area fill (price line + close bottom)
    area_pts = price_line + " {},{} {},{}".format(_x(n-1), height, _x(0), height)

    # determine colour: green if last close > sma50 (or no sma50), else red
    last_sma = None
    for v in reversed(chart_sma50):
        if v is not None:
            last_sma = v
            break
    if last_sma is not None and chart_closes[-1] < last_sma:
        line_col  = "#e74c3c"
        fill_col  = "rgba(231,76,60,0.10)"
    else:
        line_col  = "#27ae60"
        fill_col  = "rgba(39,174,96,0.10)"

    # sma50 line points
    sma_line = ""
    if chart_sma50:
        sma_pts = []
        for i, v in enumerate(chart_sma50):
            if v is not None:
                sma_pts.append("{},{}".format(_x(i), _y(v)))
        if sma_pts:
            sma_line = (
                '<polyline points="' + " ".join(sma_pts) + '" '
                'fill="none" stroke="#f39c12" stroke-width="1" '
                'stroke-dasharray="3,2" opacity="0.7"/>'
            )

    svg = (
        '<svg width="' + str(width) + '" height="' + str(height) + '" '
        'xmlns="http://www.w3.org/2000/svg" style="display:block">'
        '<polygon points="' + area_pts + '" fill="' + fill_col + '"/>'
        '<polyline points="' + price_line + '" fill="none" '
        'stroke="' + line_col + '" stroke-width="1.5"/>'
        + sma_line +
        '</svg>'
    )
    return svg


# ── main entry point ──────────────────────────────────────────────────────────

def fetch_quant_data(companies, force_refresh=False, progress_cb=None):
    """
    Main entry point.  Fetches historical data, computes all indicators.
    Returns dict mapping ticker (no .AX) -> indicator dict.
    """
    # check cache
    if not force_refresh and os.path.exists(QUANT_CACHE_FILE):
        try:
            with open(QUANT_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age = time.time() - cached.get("_fetched", 0)
            if age < QUANT_CACHE_MAX:
                print("  Quant cache loaded ({:.0f} min old)".format(age / 60))
                return cached
        except Exception:
            pass

    print("  Fetching 1-year historical data for {} tickers...".format(len(companies)))
    tickers_ax = [c["ticker"] + ".AX" for c in companies if c.get("ticker")]

    def _progress(idx, total, t):
        if progress_cb:
            progress_cb("Quant: fetching {} ({}/{})".format(t, idx, total))
        if idx % 10 == 0 or idx == total:
            print("    Historical data: {}/{} done".format(idx, total))

    hist = fetch_historical_data(tickers_ax, progress_cb=_progress)

    # build result
    result = {}
    for c in companies:
        ticker = c.get("ticker", "")
        prices = hist.get(ticker, [])
        beta   = c.get("beta")
        indicators = compute_indicators(prices, beta=beta)
        if indicators is None:
            indicators = _empty_indicators(beta)
        # generate SVG
        indicators["price_chart_svg"] = svg_price_chart(
            indicators.get("chart_closes", []),
            indicators.get("chart_sma50", []),
        )
        result[ticker] = indicators

    # save cache
    result["_fetched"]     = time.time()
    result["_fetched_str"] = datetime.now().strftime("%d %b %Y %H:%M")
    try:
        with open(QUANT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f)
        print("  Quant cache saved ({} tickers)".format(len(companies)))
    except Exception as e:
        print("  Quant cache save error: {}".format(e))

    return result


# ── HTML generation ───────────────────────────────────────────────────────────

def generate_quant_html(companies, quant_data):
    """Build the inner HTML for the Quant Analysis tab."""
    if not quant_data or not companies:
        return '<p style="color:#888;font-style:italic">Quant data not available yet. Click <b>Refresh Data</b> to compute.</p>'

    # ── gather summary stats ──────────────────────────────────────────────
    valid = []
    for c in companies:
        q = quant_data.get(c.get("ticker", ""))
        if isinstance(q, dict) and q.get("quant_label") != "N/A":
            valid.append(q)

    n_valid = len(valid)
    if n_valid == 0:
        return '<p style="color:#888;font-style:italic">No quant data computed yet. Click <b>Refresh Data</b>.</p>'

    above_sma200 = sum(1 for q in valid if q.get("sma200") and q.get("last_close") and q["last_close"] > q["sma200"])
    above_pct    = above_sma200 / n_valid * 100 if n_valid else 0
    avg_rsi      = sum(q["rsi"] for q in valid if q.get("rsi") is not None) / max(1, sum(1 for q in valid if q.get("rsi") is not None))
    n_bullish    = sum(1 for q in valid if q.get("quant_label") in ("Bullish", "Lean Bullish"))
    n_bearish    = sum(1 for q in valid if q.get("quant_label") in ("Bearish", "Lean Bearish"))
    sharpes      = [q["sharpe_ratio"] for q in valid if q.get("sharpe_ratio") is not None]
    avg_sharpe   = sum(sharpes) / len(sharpes) if sharpes else 0
    drawdowns    = [q["max_drawdown"] for q in valid if q.get("max_drawdown") is not None]
    avg_dd       = sum(drawdowns) / len(drawdowns) if drawdowns else 0

    fetched_str = quant_data.get("_fetched_str", "")

    # ── stat boxes ────────────────────────────────────────────────────────
    above_color = "#27ae60" if above_pct >= 60 else ("#e74c3c" if above_pct < 40 else "#f39c12")
    rsi_color   = _color_rsi(avg_rsi)

    html = (
        '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">'
        # Box 1: Above SMA200
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Above SMA200</div>'
        '<div style="font-size:26px;font-weight:800;color:' + above_color + '">'
        + str(above_sma200) + '<span style="font-size:14px;font-weight:400"> / ' + str(n_valid) + '</span></div>'
        '<div style="font-size:12px;color:' + above_color + '">' + "{:.0f}".format(above_pct) + '% of stocks</div>'
        '</div>'
        # Box 2: Avg RSI
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Avg RSI (14)</div>'
        '<div style="font-size:26px;font-weight:800;color:' + rsi_color + '">' + "{:.1f}".format(avg_rsi) + '</div>'
        '<div style="font-size:12px;color:#888">'
        + ("Overbought zone" if avg_rsi > 70 else ("Oversold zone" if avg_rsi < 30 else "Neutral zone")) + '</div>'
        '</div>'
        # Box 3: Bullish
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Bullish Signals</div>'
        '<div style="font-size:26px;font-weight:800;color:#27ae60">' + str(n_bullish) + '</div>'
        '<div style="font-size:12px;color:#27ae60">of ' + str(n_valid) + ' stocks</div>'
        '</div>'
        # Box 4: Bearish
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Bearish Signals</div>'
        '<div style="font-size:26px;font-weight:800;color:#e74c3c">' + str(n_bearish) + '</div>'
        '<div style="font-size:12px;color:#e74c3c">of ' + str(n_valid) + ' stocks</div>'
        '</div>'
        # Box 5: Avg Sharpe
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Avg Sharpe</div>'
        '<div style="font-size:26px;font-weight:800;color:' + _color_sharpe(avg_sharpe) + '">' + "{:.2f}".format(avg_sharpe) + '</div>'
        '<div style="font-size:12px;color:#888">Risk-adjusted return</div>'
        '</div>'
        # Box 6: Avg Max DD
        '<div style="flex:1;min-width:130px;background:#f8f9fa;border-radius:8px;padding:14px;text-align:center">'
        '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">Avg Max Drawdown</div>'
        '<div style="font-size:26px;font-weight:800;color:#e74c3c">' + "{:.1f}%".format(avg_dd * 100) + '</div>'
        '<div style="font-size:12px;color:#888">Peak-to-trough (1yr)</div>'
        '</div>'
        '</div>'
    )

    if fetched_str:
        html += '<div style="text-align:right;font-size:11px;color:#aaa;margin-bottom:8px">Quant data as of ' + _html_esc(fetched_str) + '</div>'

    # ── filter bar ────────────────────────────────────────────────────────
    html += (
        '<div id="quantFilters" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">'
        '<button class="filter-btn active" onclick="filterQuant(\'all\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#2c3e50;color:#fff;'
        'cursor:pointer;font-size:12px;font-weight:600">All</button>'
        '<button class="filter-btn" onclick="filterQuant(\'Bullish\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#fff;'
        'cursor:pointer;font-size:12px;color:#27ae60;font-weight:600">Bullish</button>'
        '<button class="filter-btn" onclick="filterQuant(\'Lean Bullish\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#fff;'
        'cursor:pointer;font-size:12px;color:#66bb6a;font-weight:600">Lean Bullish</button>'
        '<button class="filter-btn" onclick="filterQuant(\'Neutral\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#fff;'
        'cursor:pointer;font-size:12px;color:#f39c12;font-weight:600">Neutral</button>'
        '<button class="filter-btn" onclick="filterQuant(\'Lean Bearish\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#fff;'
        'cursor:pointer;font-size:12px;color:#ef5350;font-weight:600">Lean Bearish</button>'
        '<button class="filter-btn" onclick="filterQuant(\'Bearish\',this)" '
        'style="padding:5px 14px;border:1px solid #ddd;border-radius:4px;background:#fff;'
        'cursor:pointer;font-size:12px;color:#e74c3c;font-weight:600">Bearish</button>'
        '</div>'
    )

    # ── sortable table ────────────────────────────────────────────────────
    html += (
        '<div style="overflow-x:auto">'
        '<table id="quantTable" style="width:100%;border-collapse:collapse;font-size:12px">'
        '<thead><tr style="background:#2c3e50;color:#fff">'
        '<th style="padding:8px 6px;text-align:left;cursor:pointer" onclick="sortQuantTable(0)">#</th>'
        '<th style="padding:8px 6px;text-align:left;cursor:pointer;min-width:140px" onclick="sortQuantTable(1)">Company</th>'
        '<th style="padding:8px 4px;text-align:center;min-width:265px">Price Chart (90d)</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(3)">RSI</th>'
        '<th style="padding:8px 6px;text-align:center;cursor:pointer" onclick="sortQuantTable(4)">MACD</th>'
        '<th style="padding:8px 6px;text-align:center;cursor:pointer;min-width:110px" onclick="sortQuantTable(5)">SMA Trend</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(6)">BB %B</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(7)">Volatility</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(8)">Sharpe</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(9)">Max DD</th>'
        '<th style="padding:8px 6px;text-align:right;cursor:pointer" onclick="sortQuantTable(10)">Beta</th>'
        '<th style="padding:8px 6px;text-align:center;cursor:pointer;min-width:90px" onclick="sortQuantTable(11)">Score</th>'
        '</tr></thead>'
        '<tbody id="quantBody">'
    )

    sorted_companies = sorted(companies, key=lambda c: (
        quant_data.get(c.get("ticker",""), {}).get("quant_score", 0) if isinstance(quant_data.get(c.get("ticker",""), {}), dict) else 0
    ), reverse=True)

    for idx, c in enumerate(sorted_companies, 1):
        ticker = c.get("ticker", "")
        q = quant_data.get(ticker)
        if not isinstance(q, dict):
            q = _empty_indicators()

        signal_label = q.get("quant_label", "N/A")
        row_bg = "#fff" if idx % 2 == 1 else "#f8f9fa"

        # RSI cell
        rsi_val = q.get("rsi")
        rsi_str = "{:.1f}".format(rsi_val) if rsi_val is not None else "—"
        rsi_col = _color_rsi(rsi_val)

        # MACD badge
        macd_lbl = q.get("macd_label", "N/A")
        macd_s   = q.get("macd_signal", 0)
        if macd_s >= 2:   macd_col = "#27ae60"
        elif macd_s >= 1: macd_col = "#66bb6a"
        elif macd_s <= -2: macd_col = "#e74c3c"
        elif macd_s <= -1: macd_col = "#ef5350"
        else: macd_col = "#888"

        # SMA trend
        sma_lbl   = q.get("sma_label", "N/A")
        sma_s     = q.get("sma_signal", 0)
        cross     = q.get("cross_type")
        if sma_s >= 2:   sma_col = "#27ae60"
        elif sma_s >= 1: sma_col = "#66bb6a"
        elif sma_s <= -2: sma_col = "#e74c3c"
        elif sma_s <= -1: sma_col = "#ef5350"
        else: sma_col = "#888"
        sma_extra = ""
        if cross == "golden":
            sma_extra = ' <span style="color:#f39c12;font-weight:700" title="Golden Cross detected">&#x2728;</span>'
        elif cross == "death":
            sma_extra = ' <span style="color:#e74c3c;font-weight:700" title="Death Cross detected">&#x2620;</span>'

        # BB %B
        pct_b = q.get("bb_pct_b")
        bb_str = "{:.2f}".format(pct_b) if pct_b is not None else "—"

        # Volatility
        vol = q.get("ann_volatility")
        vol_str = "{:.1f}%".format(vol * 100) if vol is not None else "—"

        # Sharpe
        sharpe = q.get("sharpe_ratio")
        sharpe_str = "{:.2f}".format(sharpe) if sharpe is not None else "—"
        sharpe_col = _color_sharpe(sharpe)

        # Max DD
        dd = q.get("max_drawdown")
        dd_str = "{:.1f}%".format(dd * 100) if dd is not None else "—"

        # Beta
        beta = q.get("beta")
        beta_str = "{:.2f}".format(beta) if beta is not None else "—"

        # Score badge
        score     = q.get("quant_score", 0)
        score_col = q.get("quant_color", "#888")
        score_lbl = q.get("quant_label", "N/A")

        # SVG chart
        chart_svg = q.get("price_chart_svg", "")

        html += (
            '<tr data-quant-signal="' + _html_esc(signal_label) + '" '
            'style="background:' + row_bg + ';border-bottom:1px solid #eee">'
            # col 0: row number
            '<td style="padding:6px;color:#aaa;font-size:11px">' + str(idx) + '</td>'
            # col 1: company
            '<td style="padding:6px" data-sort="' + _html_esc(ticker) + '">'
            '<div style="font-weight:700;font-size:13px">' + _html_esc(ticker) + '</div>'
            '<div style="font-size:11px;color:#888">' + _html_esc(c.get("name","")[:25]) + '</div>'
            '<div style="font-size:10px;color:#aaa">A$' + _fmt_num(q.get("last_close"), 2) + '</div>'
            '</td>'
            # col 2: chart
            '<td style="padding:4px;text-align:center">' + chart_svg + '</td>'
            # col 3: RSI
            '<td style="padding:6px;text-align:right;font-weight:600;color:' + rsi_col + '" '
            'data-sort="' + ("{:.1f}".format(rsi_val) if rsi_val is not None else "-999") + '">'
            + rsi_str +
            '<div style="font-size:10px;font-weight:400;color:#888">' + _html_esc(q.get("rsi_label","")) + '</div>'
            '</td>'
            # col 4: MACD
            '<td style="padding:6px;text-align:center" data-sort="' + str(macd_s) + '">'
            '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;'
            'font-weight:600;color:#fff;background:' + macd_col + '">' + _html_esc(macd_lbl) + '</span></td>'
            # col 5: SMA Trend
            '<td style="padding:6px;text-align:center" data-sort="' + str(sma_s) + '">'
            '<span style="color:' + sma_col + ';font-weight:600;font-size:11px">'
            + _html_esc(sma_lbl) + '</span>' + sma_extra + '</td>'
            # col 6: BB %B
            '<td style="padding:6px;text-align:right" data-sort="' + ("{:.2f}".format(pct_b) if pct_b is not None else "-999") + '">'
            + bb_str + '</td>'
            # col 7: Volatility
            '<td style="padding:6px;text-align:right" data-sort="' + ("{:.3f}".format(vol) if vol is not None else "-999") + '">'
            + vol_str + '</td>'
            # col 8: Sharpe
            '<td style="padding:6px;text-align:right;font-weight:600;color:' + sharpe_col + '" '
            'data-sort="' + ("{:.2f}".format(sharpe) if sharpe is not None else "-999") + '">'
            + sharpe_str + '</td>'
            # col 9: Max DD
            '<td style="padding:6px;text-align:right;color:#e74c3c" '
            'data-sort="' + ("{:.3f}".format(dd) if dd is not None else "-999") + '">'
            + dd_str + '</td>'
            # col 10: Beta
            '<td style="padding:6px;text-align:right" '
            'data-sort="' + ("{:.2f}".format(beta) if beta is not None else "-999") + '">'
            + beta_str + '</td>'
            # col 11: Score
            '<td style="padding:6px;text-align:center" data-sort="' + str(score) + '">'
            '<span style="display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;'
            'font-weight:700;color:#fff;background:' + score_col + '">'
            + "{:.1f}".format(score) + '</span>'
            '<div style="font-size:10px;color:' + score_col + ';margin-top:2px">' + _html_esc(score_lbl) + '</div>'
            '</td>'
            '</tr>'
        )

    html += '</tbody></table></div>'

    # ── methodology box ───────────────────────────────────────────────────
    html += (
        '<details style="margin-top:20px;background:#f0f4f8;border-radius:8px;padding:14px">'
        '<summary style="cursor:pointer;font-weight:700;color:#2c3e50;font-size:13px">'
        '&#x1f4d6; Methodology &amp; Indicator Guide</summary>'
        '<div style="margin-top:10px;font-size:12px;color:#555;line-height:1.7">'
        '<p><b>RSI (14)</b> — Relative Strength Index measures momentum on a 0-100 scale. '
        'Below 30 = oversold (potential buy), above 70 = overbought (potential sell).</p>'
        '<p><b>MACD (12,26,9)</b> — Moving Average Convergence Divergence. '
        'Histogram rising = bullish momentum, falling = bearish momentum.</p>'
        '<p><b>SMA Trend</b> — Price position relative to 50-day and 200-day Simple Moving Averages. '
        'Price above both = uptrend. Golden Cross (SMA50 crosses above SMA200) = bullish signal.</p>'
        '<p><b>BB %B</b> — Bollinger Band %B shows where price sits relative to the 20-day bands '
        '(0 = lower band, 1 = upper band). Below 0 = oversold, above 1 = overbought.</p>'
        '<p><b>Volatility</b> — Annualised standard deviation of daily returns (trailing 1 year).</p>'
        '<p><b>Sharpe Ratio</b> — Risk-adjusted return: (annualised return - 4.35% RBA rate) / volatility. '
        'Above 1.0 = good, above 2.0 = excellent.</p>'
        '<p><b>Max Drawdown</b> — Largest peak-to-trough decline in the trailing 1-year period.</p>'
        '<p><b>Quant Score</b> — Weighted composite: SMA trend (30%), RSI (20%), MACD (20%), '
        'Sharpe (20%), Bollinger (10%). Scale: -10 (very bearish) to +10 (very bullish).</p>'
        '</div></details>'
    )

    return html


# ── standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Quick test — fetching BHP.AX 1-year history...")
    hist = fetch_historical_data(["BHP.AX"], period="1y")
    bhp = hist.get("BHP", [])
    print("  Got {} data points".format(len(bhp)))
    if bhp:
        ind = compute_indicators(bhp, beta=1.1)
        if ind:
            print("  RSI: {}, MACD: {}, SMA50: {}, SMA200: {}".format(
                ind["rsi"], ind["macd_label"], ind["sma50"], ind["sma200"]))
            print("  Sharpe: {}, Max DD: {}%".format(
                ind["sharpe_ratio"], round(ind["max_drawdown"]*100,1) if ind["max_drawdown"] else "N/A"))
            print("  Quant Score: {} ({})".format(ind["quant_score"], ind["quant_label"]))
            svg = svg_price_chart(ind["chart_closes"], ind["chart_sma50"])
            print("  SVG length: {} chars".format(len(svg)))
