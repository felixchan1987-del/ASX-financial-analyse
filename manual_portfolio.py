"""
ASX200 Manual Portfolio Manager
================================
User-directed paper trading portfolio for side-by-side comparison
against the automated Cheap-signal strategy.

Same $10k initial capital and 0.1% brokerage as the auto portfolio,
but the user decides what to buy and sell.
"""

import json
import os
from datetime import date, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
MANUAL_FILE     = os.path.join(DIR, "manual_portfolio_state.json")
INITIAL_CAPITAL = 10_000.0
BROKERAGE_PCT   = 0.001   # 0.1% per trade


class ManualPortfolio:
    def __init__(self, path=MANUAL_FILE):
        self.path  = path
        self.state = None

    # ── Persistence ──────────────────────────────────────────────────────────

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
        if self.state:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)

    # ── Initialise ───────────────────────────────────────────────────────────

    def initialize(self):
        today = date.today().strftime("%Y-%m-%d")
        self.state = {
            "initialized":    today,
            "initial_capital": INITIAL_CAPITAL,
            "cash":           INITIAL_CAPITAL,
            "holdings":       {},
            "trades":         [],
            "daily_history":  [{
                "date":              today,
                "portfolio_value":   INITIAL_CAPITAL,
                "cash":              INITIAL_CAPITAL,
                "holdings_value":    0.0,
                "daily_pnl":         0.0,
                "daily_pnl_pct":     0.0,
                "cumulative_pnl":    0.0,
                "cumulative_pnl_pct": 0.0,
                "n_holdings":        0,
            }],
        }
        self.save()

    # ── Buy ───────────────────────────────────────────────────────────────────

    def buy(self, ticker, dollar_amount, price, name=""):
        """Buy a stock with a dollar amount. Returns (success: bool, message: str)."""
        if not self.state:
            return False, "Portfolio not initialized"
        if price <= 0:
            return False, "Invalid price"
        if dollar_amount <= 0:
            return False, "Amount must be positive"

        brokerage = dollar_amount * BROKERAGE_PCT
        total_cost = dollar_amount + brokerage
        if total_cost > self.state["cash"]:
            avail = self.state["cash"]
            return False, "Insufficient cash. Available: A${:.2f}, Required: A${:.2f}".format(avail, total_cost)

        shares = dollar_amount / price
        self.state["cash"] -= total_cost

        # Update or create holding
        h = self.state["holdings"]
        if ticker in h:
            old_shares = h[ticker]["shares"]
            old_cost   = h[ticker]["avg_cost"]
            new_shares = old_shares + shares
            # Weighted average cost
            h[ticker]["avg_cost"]  = (old_shares * old_cost + shares * price) / new_shares
            h[ticker]["shares"]    = new_shares
            h[ticker]["current_price"] = price
            h[ticker]["market_value"]  = new_shares * price
            h[ticker]["unrealized_pnl"] = new_shares * (price - h[ticker]["avg_cost"])
        else:
            h[ticker] = {
                "name":            name,
                "shares":          shares,
                "avg_cost":        price,
                "current_price":   price,
                "market_value":    shares * price,
                "unrealized_pnl":  0.0,
            }

        # Record trade
        self.state["trades"].append({
            "date":      date.today().strftime("%Y-%m-%d"),
            "action":    "BUY",
            "ticker":    ticker,
            "name":      name,
            "shares":    round(shares, 4),
            "price":     price,
            "value":     round(dollar_amount, 2),
            "brokerage": round(brokerage, 2),
            "realized_pnl": None,
        })

        self.save()
        return True, "Bought {:.2f} shares of {} at A${:.2f} (brokerage A${:.2f})".format(
            shares, ticker, price, brokerage)

    # ── Sell ──────────────────────────────────────────────────────────────────

    def sell(self, ticker, shares_to_sell, price):
        """Sell shares of a stock. Use shares_to_sell='all' to sell entire position.
        Returns (success: bool, message: str)."""
        if not self.state:
            return False, "Portfolio not initialized"
        h = self.state["holdings"]
        if ticker not in h:
            return False, "{} is not in your portfolio".format(ticker)

        holding = h[ticker]
        max_shares = holding["shares"]

        if shares_to_sell == "all":
            shares_to_sell = max_shares
        else:
            shares_to_sell = float(shares_to_sell)

        if shares_to_sell <= 0:
            return False, "Shares must be positive"
        if shares_to_sell > max_shares * 1.001:  # small float tolerance
            return False, "You only hold {:.2f} shares of {}".format(max_shares, ticker)

        # Cap to actual holdings
        shares_to_sell = min(shares_to_sell, max_shares)

        proceeds  = shares_to_sell * price
        brokerage = proceeds * BROKERAGE_PCT
        net       = proceeds - brokerage
        cost_basis = shares_to_sell * holding["avg_cost"]
        realized_pnl = net - cost_basis

        self.state["cash"] += net

        # Update or remove holding
        remaining = max_shares - shares_to_sell
        if remaining < 0.0001:
            name = holding.get("name", "")
            del h[ticker]
        else:
            name = holding.get("name", "")
            holding["shares"]       = remaining
            holding["current_price"] = price
            holding["market_value"]  = remaining * price
            holding["unrealized_pnl"] = remaining * (price - holding["avg_cost"])

        # Record trade
        self.state["trades"].append({
            "date":      date.today().strftime("%Y-%m-%d"),
            "action":    "SELL",
            "ticker":    ticker,
            "name":      name,
            "shares":    round(shares_to_sell, 4),
            "price":     price,
            "value":     round(proceeds, 2),
            "brokerage": round(brokerage, 2),
            "realized_pnl": round(realized_pnl, 2),
        })

        self.save()
        return True, "Sold {:.2f} shares of {} at A${:.2f} (P&L: A${:+.2f})".format(
            shares_to_sell, ticker, price, realized_pnl)

    # ── Re-price ─────────────────────────────────────────────────────────────

    def reprice(self, companies):
        """Update all holding prices from latest market data and snapshot history."""
        if not self.state:
            return
        by_ticker = {c["ticker"]: c for c in companies}
        for ticker, holding in self.state["holdings"].items():
            raw = ticker.replace(".AX", "")
            c = by_ticker.get(raw)
            if c and c.get("price"):
                holding["current_price"]  = c["price"]
                holding["market_value"]   = holding["shares"] * c["price"]
                holding["unrealized_pnl"] = holding["shares"] * (c["price"] - holding["avg_cost"])

        # Daily snapshot
        holdings_val = sum(h["market_value"] for h in self.state["holdings"].values())
        total_val    = self.state["cash"] + holdings_val
        cum_pnl      = total_val - INITIAL_CAPITAL
        cum_pnl_pct  = (cum_pnl / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL else 0

        history = self.state.get("daily_history", [])
        prev_val = history[-1]["portfolio_value"] if history else INITIAL_CAPITAL
        daily_pnl     = total_val - prev_val
        daily_pnl_pct = (daily_pnl / prev_val * 100) if prev_val else 0

        today = date.today().strftime("%Y-%m-%d")
        entry = {
            "date":              today,
            "portfolio_value":   round(total_val, 2),
            "cash":              round(self.state["cash"], 2),
            "holdings_value":    round(holdings_val, 2),
            "daily_pnl":         round(daily_pnl, 2),
            "daily_pnl_pct":     round(daily_pnl_pct, 2),
            "cumulative_pnl":    round(cum_pnl, 2),
            "cumulative_pnl_pct": round(cum_pnl_pct, 2),
            "n_holdings":        len(self.state["holdings"]),
        }
        # Upsert today
        if history and history[-1]["date"] == today:
            history[-1] = entry
        else:
            history.append(entry)
        self.state["daily_history"] = history

        self.save()

    # ── Summary ──────────────────────────────────────────────────────────────

    def get_summary(self):
        if not self.state:
            return None
        holdings_val = sum(h["market_value"] for h in self.state["holdings"].values())
        total_val    = self.state["cash"] + holdings_val
        cum_pnl      = total_val - INITIAL_CAPITAL
        cum_pnl_pct  = (cum_pnl / INITIAL_CAPITAL) * 100 if INITIAL_CAPITAL else 0
        history      = self.state.get("daily_history", [])
        prev_val     = history[-2]["portfolio_value"] if len(history) >= 2 else INITIAL_CAPITAL
        daily_pnl     = total_val - prev_val
        daily_pnl_pct = (daily_pnl / prev_val * 100) if prev_val else 0

        return {
            "total_value":     round(total_val, 2),
            "cash":            round(self.state["cash"], 2),
            "holdings_value":  round(holdings_val, 2),
            "cum_pnl":         round(cum_pnl, 2),
            "cum_pnl_pct":     round(cum_pnl_pct, 2),
            "daily_pnl":       round(daily_pnl, 2),
            "daily_pnl_pct":   round(daily_pnl_pct, 2),
            "n_holdings":      len(self.state["holdings"]),
            "initialized":     self.state.get("initialized", ""),
            "holdings":        self.state.get("holdings", {}),
            "trades":          self.state.get("trades", []),
            "history":         history,
            "initial_capital":  INITIAL_CAPITAL,
        }
