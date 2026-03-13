"""
ASX200 Mock Portfolio Manager
===============================
Simulates a $10,000 paper-trading portfolio driven by valuation signals.

Strategy:
  - Buy Cheap-signal stocks equally weighted (up to MAX_POSITIONS)
  - Trim 50% when signal changes Cheap → Fair
  - Full exit when signal changes to Expensive
  - New Cheap stocks are auto-bought with freed-up cash
  - Always reserve CASH_RESERVE_PCT (10%) in cash

Tracks daily P&L and adjusts each time data is refreshed.
"""

import json
import os
import math
from datetime import date, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE   = os.path.join(DIR, "portfolio_state.json")
INITIAL_CAPITAL  = 10_000.0
CASH_RESERVE_PCT = 0.10    # keep 10 % in cash at all times
BROKERAGE_PCT    = 0.001   # 0.1 % per trade (realistic for online brokers)
MAX_POSITIONS    = 10      # maximum simultaneous holdings
MIN_TRADE_VALUE  = 250     # ignore trades smaller than $250


# ══════════════════════════════════════════════════════════════════════════════
#  SVG chart
# ══════════════════════════════════════════════════════════════════════════════

def svg_sparkline(history, width=820, height=220):
    """Pure-SVG area + line chart of portfolio value over time."""
    if not history:
        return '<p style="color:#888;padding:20px">No history yet.</p>'
    if len(history) == 1:
        v = history[0]["portfolio_value"]
        return (f'<p style="padding:20px;color:#666">Portfolio started {history[0]["date"]} '
                f'— Value: <b>A${v:,.2f}</b>. Check back tomorrow for a chart.</p>')

    values = [h["portfolio_value"] for h in history]
    dates  = [h["date"]            for h in history]
    n      = len(values)

    PL, PR, PT, PB = 65, 30, 20, 32   # padding left / right / top / bottom
    cw = width  - PL - PR
    ch = height - PT - PB

    lo = min(values); hi = max(values)
    span = max(hi - lo, 1)
    y_lo = lo - span * 0.08
    y_hi = hi + span * 0.08
    y_span = y_hi - y_lo

    def px(i):
        return PL + (i / (n - 1)) * cw if n > 1 else PL

    def py(v):
        return PT + ch - ((v - y_lo) / y_span) * ch

    pts = [(px(i), py(v)) for i, v in enumerate(values)]
    is_gain   = values[-1] >= INITIAL_CAPITAL
    line_col  = "#27ae60" if is_gain else "#e74c3c"
    area_col  = "rgba(39,174,96,0.07)" if is_gain else "rgba(231,76,60,0.07)"

    polyline  = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    base_y    = PT + ch
    area_path = (f"{pts[0][0]:.1f},{base_y} " +
                 " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) +
                 f" {pts[-1][0]:.1f},{base_y}")

    # Y-axis gridlines + labels
    grid = ""
    for i in range(5):
        v  = y_lo + y_span * i / 4
        yp = py(v)
        grid += (f'<line x1="{PL}" y1="{yp:.0f}" x2="{PL+cw}" y2="{yp:.0f}" '
                 f'stroke="#f0f2f5" stroke-width="1"/>'
                 f'<text x="{PL-8}" y="{yp+4:.0f}" text-anchor="end" '
                 f'font-size="10" fill="#aaa">${v:,.0f}</text>')

    # Dashed reference at $10 k
    init_ref = ""
    if y_lo <= INITIAL_CAPITAL <= y_hi:
        yr = py(INITIAL_CAPITAL)
        init_ref = (f'<line x1="{PL}" y1="{yr:.0f}" x2="{PL+cw}" y2="{yr:.0f}" '
                    f'stroke="#ccc" stroke-dasharray="5,3" stroke-width="1.5"/>'
                    f'<text x="{PL+6}" y="{yr-4:.0f}" font-size="9" fill="#bbb">$10k</text>')

    # X-axis date labels (≤6 evenly spaced)
    step = max(1, (n - 1) // 5)
    idx_set = set(range(0, n, step)) | {n - 1}
    xlabels = "".join(
        f'<text x="{px(i):.0f}" y="{PT+ch+20}" text-anchor="middle" '
        f'font-size="9" fill="#aaa">{dates[i]}</text>'
        for i in sorted(idx_set)
    )

    # Dots when series is short
    dots = ("".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{line_col}" stroke="#fff" stroke-width="1.5"/>'
        for x, y in pts)
        if n <= 40 else "")

    # Final-value label
    lx, ly = pts[-1]
    final  = (f'<text x="{min(lx+8, PL+cw-10):.0f}" y="{ly+4:.0f}" '
              f'font-size="11" font-weight="bold" fill="{line_col}">A${values[-1]:,.0f}</text>')

    return (f'<svg width="100%" viewBox="0 0 {width} {height}" style="overflow:visible;display:block">'
            f'{grid}{init_ref}'
            f'<polygon points="{area_path}" fill="{area_col}" stroke="none"/>'
            f'<polyline points="{polyline}" fill="none" stroke="{line_col}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
            f'{dots}{xlabels}{final}</svg>')


# ══════════════════════════════════════════════════════════════════════════════
#  Portfolio HTML renderer
# ══════════════════════════════════════════════════════════════════════════════

def generate_portfolio_html(summary):
    """Returns the inner HTML for the Portfolio tab."""

    if not summary:
        return """
        <div style="text-align:center;padding:60px 20px;color:#888">
          <div style="font-size:52px">&#x1f4ca;</div>
          <h3 style="margin:16px 0 8px;color:#555">Portfolio Not Initialised</h3>
          <p>Run <b>launch_report.bat</b> to start the server.<br>
             The portfolio is created automatically on the first data fetch.</p>
        </div>"""

    tv   = summary["total_value"]
    cash = summary["cash"]
    hv   = summary["holdings_value"]
    cpnl = summary["cum_pnl"]
    cpct = summary["cum_pnl_pct"]
    dpnl = summary["daily_pnl"]
    dpct = summary["daily_pnl_pct"]
    nh   = summary["n_holdings"]
    init = summary["initialized"]

    pc   = "#27ae60" if cpnl >= 0 else "#e74c3c"
    dpc  = "#27ae60" if dpnl >= 0 else "#e74c3c"
    ps   = "+" if cpnl >= 0 else ""
    ds   = "+" if dpnl >= 0 else ""

    # ── Holdings table ────────────────────────────────────────────────────────
    h_rows = ""
    for ticker, h in sorted(summary["holdings"].items(),
                             key=lambda x: -x[1]["market_value"]):
        upnl  = h.get("unrealized_pnl", 0)
        cost  = h["shares"] * h["avg_cost"]
        upct  = (upnl / cost * 100) if cost else 0
        uc    = "#27ae60" if upnl >= 0 else "#e74c3c"
        us    = "+" if upnl >= 0 else ""
        sig   = h.get("current_signal", "")
        scol  = {"Cheap": "#27ae60", "Fair": "#f39c12",
                 "Expensive": "#e74c3c"}.get(sig, "#888")
        wt    = h["market_value"] / tv * 100 if tv else 0
        reasons = "".join(f"<li>{r}</li>" for r in h.get("reasons", []))
        rsec  = (f'<ul style="margin:3px 0 0;padding-left:14px;font-size:10px;'
                 f'color:#888;line-height:1.5">{reasons}</ul>') if reasons else ""

        h_rows += (
            f'<tr>'
            f'<td style="font-weight:700">{ticker}</td>'
            f'<td style="font-size:12px;color:#555">{h["name"][:28]}{rsec}</td>'
            f'<td style="text-align:right;font-size:12px">{h["shares"]:.2f}</td>'
            f'<td style="text-align:right;font-size:12px">A${h["avg_cost"]:.2f}</td>'
            f'<td style="text-align:right;font-size:12px;font-weight:600">A${h["current_price"]:.2f}</td>'
            f'<td style="text-align:right;font-size:12px;font-weight:600">A${h["market_value"]:,.2f}</td>'
            f'<td style="text-align:right;font-size:12px;color:{uc};font-weight:600">'
            f'{us}A${upnl:,.2f}<br><small>({us}{upct:.1f}%)</small></td>'
            f'<td style="text-align:right;font-size:11px;color:#999">{wt:.1f}%</td>'
            f'<td style="text-align:center"><span style="background:{scol};color:#fff;'
            f'padding:1px 7px;border-radius:8px;font-size:10px">{sig}</span></td>'
            f'</tr>'
        )
    if not h_rows:
        h_rows = ('<tr><td colspan="9" style="text-align:center;color:#888;padding:20px">'
                  'No holdings — fully in cash</td></tr>')

    # ── Trade log ─────────────────────────────────────────────────────────────
    t_rows = ""
    for t in reversed(summary.get("trades", [])[-30:]):
        ac    = {"BUY": "#27ae60", "SELL": "#e74c3c", "TRIM": "#f39c12"}.get(t.get("action",""), "#888")
        pnl_v = t.get("realized_pnl")
        pnl_s = (f'<span style="color:{"#27ae60" if pnl_v and pnl_v>=0 else "#e74c3c"}">'
                 f'{"+" if pnl_v and pnl_v>=0 else ""}A${pnl_v:,.2f}</span>'
                 if pnl_v is not None else "—")
        t_rows += (
            f'<tr>'
            f'<td style="font-size:11px;color:#999">{t.get("date","")}</td>'
            f'<td><span style="background:{ac};color:#fff;padding:1px 7px;'
            f'border-radius:4px;font-size:11px;font-weight:700">{t.get("action","")}</span></td>'
            f'<td style="font-weight:700">{t.get("ticker","")}</td>'
            f'<td style="font-size:12px;color:#555">{t.get("name","")[:24]}</td>'
            f'<td style="text-align:right;font-size:12px">{t.get("shares",0):.2f}</td>'
            f'<td style="text-align:right;font-size:12px">A${t.get("price",0):.2f}</td>'
            f'<td style="text-align:right;font-size:12px">A${t.get("value",0):,.2f}</td>'
            f'<td style="text-align:right;font-size:12px">{pnl_s}</td>'
            f'<td style="font-size:11px;color:#888">{t.get("reason","")[:75]}</td>'
            f'</tr>'
        )
    if not t_rows:
        t_rows = ('<tr><td colspan="9" style="text-align:center;color:#888;padding:20px">'
                  'No trades recorded yet.</td></tr>')

    # ── Daily performance table ───────────────────────────────────────────────
    p_rows = ""
    for h in reversed(summary.get("history", [])[-10:]):
        dv  = h.get("daily_pnl", 0)
        dc  = "#27ae60" if dv >= 0 else "#e74c3c"
        cv  = h.get("cumulative_pnl", 0)
        cc  = "#27ae60" if cv >= 0 else "#e74c3c"
        p_rows += (
            f'<tr>'
            f'<td style="font-size:12px;color:#999">{h["date"]}</td>'
            f'<td style="text-align:right;font-weight:600">A${h["portfolio_value"]:,.2f}</td>'
            f'<td style="text-align:right;font-size:12px">A${h["holdings_value"]:,.2f}</td>'
            f'<td style="text-align:right;font-size:12px">A${h["cash"]:,.2f}</td>'
            f'<td style="text-align:right;font-size:12px;color:{dc}">'
            f'{"+" if dv>=0 else ""}A${dv:,.2f} '
            f'({"+" if h.get("daily_pnl_pct",0)>=0 else ""}{h.get("daily_pnl_pct",0):.2f}%)</td>'
            f'<td style="text-align:right;font-size:12px;color:{cc}">'
            f'{"+" if cv>=0 else ""}A${cv:,.2f} '
            f'({"+" if h.get("cumulative_pnl_pct",0)>=0 else ""}{h.get("cumulative_pnl_pct",0):.2f}%)</td>'
            f'<td style="text-align:center;font-size:12px">{h.get("n_holdings",0)}</td>'
            f'</tr>'
        )
    if not p_rows:
        p_rows = ('<tr><td colspan="7" style="text-align:center;color:#888;padding:20px">'
                  'No history yet.</td></tr>')

    chart = svg_sparkline(summary.get("history", []))
    strat = summary.get("strategy", {})
    res_pct = int(strat.get("cash_reserve_pct", CASH_RESERVE_PCT) * 100)
    brk_pct = strat.get("brokerage_pct", BROKERAGE_PCT) * 100
    max_pos = strat.get("max_positions", MAX_POSITIONS)

    return f"""
    <div class="stat-grid">
      <div class="stat-box">
        <div class="label">Portfolio Value</div>
        <div class="value">A${tv:,.2f}</div>
        <div class="sub">Started A$10,000 on {init}</div>
      </div>
      <div class="stat-box">
        <div class="label" style="color:{pc}">Total Gain / Loss</div>
        <div class="value" style="color:{pc}">{ps}A${cpnl:,.2f}</div>
        <div class="sub">{ps}{cpct:.2f}% since inception</div>
      </div>
      <div class="stat-box">
        <div class="label" style="color:{dpc}">Today's P&amp;L</div>
        <div class="value" style="color:{dpc}">{ds}A${dpnl:,.2f}</div>
        <div class="sub">{ds}{dpct:.2f}% today</div>
      </div>
      <div class="stat-box">
        <div class="label">Invested</div>
        <div class="value">A${hv:,.2f}</div>
        <div class="sub">{hv/tv*100:.0f}% of portfolio</div>
      </div>
      <div class="stat-box">
        <div class="label">Cash</div>
        <div class="value">A${cash:,.2f}</div>
        <div class="sub">{cash/tv*100:.0f}% of portfolio</div>
      </div>
      <div class="stat-box">
        <div class="label">Positions</div>
        <div class="value">{nh}</div>
        <div class="sub">Active holdings</div>
      </div>
    </div>

    <div style="background:#fff;border-radius:10px;padding:20px 24px;
                box-shadow:0 1px 4px rgba(0,0,0,.08);margin-bottom:24px">
      <h3 style="font-size:15px;color:#1a3a5c;margin-bottom:14px">Portfolio Value History</h3>
      {chart}
    </div>

    <h2>Current Holdings</h2>
    <table style="margin-bottom:24px">
      <thead><tr>
        <th>Ticker</th><th>Company / Signal Drivers</th>
        <th style="text-align:right">Shares</th>
        <th style="text-align:right">Avg Cost</th>
        <th style="text-align:right">Price</th>
        <th style="text-align:right">Value</th>
        <th style="text-align:right">Unrealised P&amp;L</th>
        <th style="text-align:right">Weight</th>
        <th style="text-align:center">Signal</th>
      </tr></thead>
      <tbody>{h_rows}</tbody>
    </table>

    <h2>Strategy</h2>
    <div style="background:#f0f7ff;border-left:4px solid #2980b9;border-radius:4px;
                padding:16px 20px;margin-bottom:24px;font-size:13px">
      <b>Active Strategy:</b> {strat.get('description','Equal-weight Cheap signals')}<br><br>
      <b>Rebalancing Rules (checked on every data refresh):</b>
      <ul style="margin:8px 0 0;padding-left:20px;line-height:2">
        <li>&#x1f7e2; <b>BUY</b> &mdash; any new Cheap-signal stock not already held,
            equal-weight with cash above the {res_pct}% reserve</li>
        <li>&#x26a0;&#xfe0f; <b>TRIM 50%</b> &mdash; when a held stock's signal changes
            <b>Cheap &rarr; Fair</b></li>
        <li>&#x1f534; <b>FULL EXIT</b> &mdash; when signal changes to <b>Expensive</b></li>
        <li>&#x1f4b0; Brokerage: <b>{brk_pct:.1f}%</b> per trade &bull;
            Max positions: <b>{max_pos}</b> &bull;
            Cash reserve: <b>{res_pct}%</b></li>
      </ul>
      <div style="margin-top:10px;font-size:11px;color:#7a9fc0;font-style:italic">
        Strategy self-adjusts daily as signals update — no manual intervention needed.
        This is a paper portfolio for educational purposes only.
      </div>
    </div>

    <h2>Daily Performance (Last 10 Days)</h2>
    <table style="margin-bottom:24px">
      <thead><tr>
        <th>Date</th>
        <th style="text-align:right">Portfolio Value</th>
        <th style="text-align:right">Invested</th>
        <th style="text-align:right">Cash</th>
        <th style="text-align:right">Daily P&amp;L</th>
        <th style="text-align:right">Cumulative P&amp;L</th>
        <th style="text-align:center">Positions</th>
      </tr></thead>
      <tbody>{p_rows}</tbody>
    </table>

    <h2>Trade Log (Last 30)</h2>
    <table>
      <thead><tr>
        <th>Date</th><th>Action</th><th>Ticker</th><th>Company</th>
        <th style="text-align:right">Shares</th>
        <th style="text-align:right">Price</th>
        <th style="text-align:right">Value</th>
        <th style="text-align:right">Realised P&amp;L</th>
        <th>Reason</th>
      </tr></thead>
      <tbody>{t_rows}</tbody>
    </table>

    <div class="disclaimer" style="margin-top:24px">
      <b>Disclaimer:</b> This is a simulated paper-trading portfolio for educational
      purposes only. Prices from Yahoo Finance may be delayed. This does not constitute
      financial advice. No real money is involved.
    </div>"""


# ══════════════════════════════════════════════════════════════════════════════
#  Portfolio Manager
# ══════════════════════════════════════════════════════════════════════════════

class PortfolioManager:

    def __init__(self, path=PORTFOLIO_FILE):
        self.path  = path
        self.state = None

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                return True
            except Exception:
                pass
        return False

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    # ── Initialise ────────────────────────────────────────────────────────────

    def initialize(self, companies):
        """Create the portfolio from scratch. Called only once on day 1."""
        today  = date.today().isoformat()
        cheap  = [c for c in companies
                  if c.get("signal") == "Cheap" and c.get("price")]

        cash     = INITIAL_CAPITAL   # start with full capital; purchases are deducted
        holdings = {}
        trades   = []

        if cheap:
            n_buy     = min(len(cheap), MAX_POSITIONS)
            deployable = INITIAL_CAPITAL * (1 - CASH_RESERVE_PCT)  # 90 % to deploy
            per_stock  = deployable / n_buy
            for c in cheap[:n_buy]:
                price    = c["price"]
                shares   = (per_stock * (1 - BROKERAGE_PCT)) / price
                cost     = shares * price
                brokerage = cost * BROKERAGE_PCT
                cash    -= (cost + brokerage)
                holdings[c["ticker"]] = {
                    "name":              c["name"],
                    "shares":            round(shares, 4),
                    "avg_cost":          round(price, 4),
                    "current_price":     round(price, 4),
                    "market_value":      round(shares * price, 2),
                    "unrealized_pnl":    0.0,
                    "signal_at_purchase": "Cheap",
                    "current_signal":    "Cheap",
                    "reasons":           c.get("reasons", []),
                }
                trades.append({
                    "date":       today,
                    "action":     "BUY",
                    "ticker":     c["ticker"],
                    "name":       c["name"],
                    "shares":     round(shares, 4),
                    "price":      round(price, 4),
                    "value":      round(cost, 2),
                    "brokerage":  round(brokerage, 2),
                    "reason":     "Initial allocation — " + "; ".join(c.get("reasons", [])),
                })

        total_value = sum(h["market_value"] for h in holdings.values()) + cash

        self.state = {
            "initialized":    today,
            "initial_capital": INITIAL_CAPITAL,
            "cash":            round(cash, 2),
            "holdings":        holdings,
            "trades":          trades,
            "daily_history":   [{
                "date":                today,
                "portfolio_value":     round(total_value, 2),
                "cash":                round(cash, 2),
                "holdings_value":      round(total_value - cash, 2),
                "daily_pnl":           0.0,
                "daily_pnl_pct":       0.0,
                "cumulative_pnl":      round(total_value - INITIAL_CAPITAL, 2),
                "cumulative_pnl_pct":  round((total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100, 4),
                "n_holdings":          len(holdings),
            }],
            "strategy": {
                "description":      ("Equal-weight Cheap-signal stocks; trim on Fair, "
                                     "exit on Expensive; auto-buy new Cheap with spare cash"),
                "cash_reserve_pct": CASH_RESERVE_PCT,
                "brokerage_pct":    BROKERAGE_PCT,
                "max_positions":    MAX_POSITIONS,
            },
        }
        self.save()
        print(f"Portfolio initialised: {len(holdings)} holdings, "
              f"cash A${cash:,.2f}, total A${total_value:,.2f}")
        return self.state

    # ── Daily update ──────────────────────────────────────────────────────────

    def update(self, companies):
        """Re-price holdings, compute P&L, rebalance. Called after every data refresh."""
        if self.state is None:
            return self.initialize(companies)

        today      = date.today().isoformat()
        prev_hist  = self.state["daily_history"][-1]
        prev_value = prev_hist["portfolio_value"]

        by_ticker = {c["ticker"]: c for c in companies if c.get("price")}

        # ── 1. Re-price current holdings ─────────────────────────────────────
        for ticker, h in list(self.state["holdings"].items()):
            c = by_ticker.get(ticker)
            if c and c.get("price"):
                new_price          = c["price"]
                h["current_price"] = round(new_price, 4)
                h["market_value"]  = round(h["shares"] * new_price, 2)
                h["unrealized_pnl"] = round(
                    h["market_value"] - h["shares"] * h["avg_cost"], 2)
                h["current_signal"] = c.get("signal", h.get("current_signal", ""))
                h["reasons"]        = c.get("reasons", h.get("reasons", []))

        # ── 2. Rebalance ──────────────────────────────────────────────────────
        new_trades = self._rebalance(by_ticker, today)
        self.state["trades"].extend(new_trades)

        # ── 3. Snapshot P&L ───────────────────────────────────────────────────
        hv          = sum(h["market_value"] for h in self.state["holdings"].values())
        total_value = hv + self.state["cash"]
        daily_pnl   = total_value - prev_value
        daily_pct   = daily_pnl / prev_value * 100 if prev_value else 0
        cum_pnl     = total_value - INITIAL_CAPITAL
        cum_pct     = cum_pnl / INITIAL_CAPITAL * 100

        entry = {
            "date":                today,
            "portfolio_value":     round(total_value, 2),
            "cash":                round(self.state["cash"], 2),
            "holdings_value":      round(hv, 2),
            "daily_pnl":           round(daily_pnl, 2),
            "daily_pnl_pct":       round(daily_pct, 4),
            "cumulative_pnl":      round(cum_pnl, 2),
            "cumulative_pnl_pct":  round(cum_pct, 4),
            "n_holdings":          len(self.state["holdings"]),
        }

        # Upsert: replace today's entry if it already exists, else append
        if self.state["daily_history"] and self.state["daily_history"][-1]["date"] == today:
            self.state["daily_history"][-1] = entry
        else:
            self.state["daily_history"].append(entry)

        self.save()
        print(f"Portfolio updated: value A${total_value:,.2f} "
              f"({'+' if cum_pnl>=0 else ''}A${cum_pnl:,.2f}, "
              f"{'+' if cum_pct>=0 else ''}{cum_pct:.2f}%)")
        return self.state

    # ── Rebalancing engine ────────────────────────────────────────────────────

    def _rebalance(self, by_ticker, today):
        trades = []

        # ── Sells / trims ─────────────────────────────────────────────────────
        for ticker, h in list(self.state["holdings"].items()):
            c          = by_ticker.get(ticker)
            new_signal = c.get("signal", "") if c else ""
            old_signal = h.get("current_signal", "Cheap")

            if new_signal == "Expensive" and old_signal != "Expensive":
                # Full exit
                proceeds  = h["shares"] * h["current_price"]
                brokerage = proceeds * BROKERAGE_PCT
                net       = proceeds - brokerage
                pnl       = round(net - h["shares"] * h["avg_cost"], 2)
                self.state["cash"] = round(self.state["cash"] + net, 2)
                trades.append({
                    "date": today, "action": "SELL",
                    "ticker": ticker, "name": h["name"],
                    "shares": round(h["shares"], 4),
                    "price": h["current_price"],
                    "value": round(proceeds, 2),
                    "brokerage": round(brokerage, 2),
                    "realized_pnl": pnl,
                    "reason": f"Signal degraded {old_signal} → Expensive. Full exit.",
                })
                del self.state["holdings"][ticker]

            elif new_signal == "Fair" and old_signal == "Cheap":
                # Trim 50 %
                sell_shares = round(h["shares"] * 0.5, 4)
                sell_value  = sell_shares * h["current_price"]
                if sell_value < MIN_TRADE_VALUE:
                    continue
                brokerage = sell_value * BROKERAGE_PCT
                net       = sell_value - brokerage
                pnl       = round(net - sell_shares * h["avg_cost"], 2)
                self.state["cash"] = round(self.state["cash"] + net, 2)
                h["shares"]       = round(h["shares"] - sell_shares, 4)
                h["market_value"] = round(h["shares"] * h["current_price"], 2)
                h["current_signal"] = "Fair"
                trades.append({
                    "date": today, "action": "TRIM",
                    "ticker": ticker, "name": h["name"],
                    "shares": sell_shares,
                    "price": h["current_price"],
                    "value": round(sell_value, 2),
                    "brokerage": round(brokerage, 2),
                    "realized_pnl": pnl,
                    "reason": "Signal changed Cheap → Fair. Trimmed 50%.",
                })

        # ── Buys ──────────────────────────────────────────────────────────────
        held      = set(self.state["holdings"].keys())
        new_cheap = [
            c for c in by_ticker.values()
            if c.get("signal") == "Cheap"
            and c["ticker"] not in held
            and c.get("price")
            and len(held) < MAX_POSITIONS
        ]

        available = self.state["cash"] - INITIAL_CAPITAL * CASH_RESERVE_PCT

        if new_cheap and available > MIN_TRADE_VALUE:
            per_stock = available / len(new_cheap)
            for c in new_cheap:
                alloc = min(per_stock, available * 0.9)
                if alloc < MIN_TRADE_VALUE:
                    break
                price     = c["price"]
                shares    = (alloc * (1 - BROKERAGE_PCT)) / price
                cost      = shares * price
                brokerage = cost * BROKERAGE_PCT
                total_out = cost + brokerage
                if total_out > available:
                    continue
                self.state["cash"]  = round(self.state["cash"] - total_out, 2)
                available          -= total_out
                self.state["holdings"][c["ticker"]] = {
                    "name":              c["name"],
                    "shares":            round(shares, 4),
                    "avg_cost":          round(price, 4),
                    "current_price":     round(price, 4),
                    "market_value":      round(cost, 2),
                    "unrealized_pnl":    0.0,
                    "signal_at_purchase": "Cheap",
                    "current_signal":    "Cheap",
                    "reasons":           c.get("reasons", []),
                }
                held.add(c["ticker"])
                trades.append({
                    "date": today, "action": "BUY",
                    "ticker": c["ticker"], "name": c["name"],
                    "shares": round(shares, 4),
                    "price": round(price, 4),
                    "value": round(cost, 2),
                    "brokerage": round(brokerage, 2),
                    "reason": "New Cheap signal. " + "; ".join(c.get("reasons", [])),
                })

        return trades

    # ── Summary dict (for HTML renderer) ─────────────────────────────────────

    def get_summary(self):
        if not self.state:
            return None
        hv    = sum(h["market_value"] for h in self.state["holdings"].values())
        tv    = hv + self.state["cash"]
        cpnl  = tv - INITIAL_CAPITAL
        cpct  = cpnl / INITIAL_CAPITAL * 100
        hist  = self.state["daily_history"]
        today = hist[-1] if hist else {}
        return {
            "total_value":     round(tv, 2),
            "cash":            round(self.state["cash"], 2),
            "holdings_value":  round(hv, 2),
            "cum_pnl":         round(cpnl, 2),
            "cum_pnl_pct":     round(cpct, 2),
            "daily_pnl":       today.get("daily_pnl", 0),
            "daily_pnl_pct":   today.get("daily_pnl_pct", 0),
            "n_holdings":      len(self.state["holdings"]),
            "initialized":     self.state.get("initialized"),
            "holdings":        self.state["holdings"],
            "trades":          self.state["trades"],
            "history":         self.state["daily_history"],
            "strategy":        self.state.get("strategy", {}),
            "initial_capital": INITIAL_CAPITAL,
        }
