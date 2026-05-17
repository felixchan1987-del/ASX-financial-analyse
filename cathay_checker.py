#!/usr/bin/env python3
"""
国泰航空里程兑换机票监控器
Cathay Pacific Award Ticket Availability Checker

监控指定航线的经济舱里程兑换座位，有新座位时发送 Gmail 提醒。
Monitors economy award seats on specified routes and sends Gmail alerts.

Required environment variables:
  GMAIL_USER          - Gmail address used to send alerts
  GMAIL_APP_PASSWORD  - Gmail App Password (not regular password)
  NOTIFY_EMAIL        - Recipient email (defaults to GMAIL_USER if unset)

Optional:
  DRY_RUN=1           - Print alert without sending email (for testing)
"""

import asyncio
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── Routes to monitor ────────────────────────────────────────────────────────
ROUTES = [
    ("SYD", "HKG", "悉尼 → 香港"),
    ("HKG", "SYD", "香港 → 悉尼"),
    ("LHR", "SYD", "伦敦 → 悉尼"),
    ("CDG", "SYD", "巴黎 → 悉尼"),
    ("FRA", "SYD", "法兰克福 → 悉尼"),
    ("AMS", "SYD", "阿姆斯特丹 → 悉尼"),
    ("ZRH", "SYD", "苏黎世 → 悉尼"),
    ("FCO", "SYD", "罗马 → 悉尼"),
]

# ── Date sampling ────────────────────────────────────────────────────────────
# Check every SAMPLE_INTERVAL days up to DAYS_AHEAD days from now
DAYS_AHEAD = 90
SAMPLE_INTERVAL = 7  # weekly sampling

# ── Paths ────────────────────────────────────────────────────────────────────
CACHE_FILE = Path("cathay_availability.json")
DEBUG_DIR = Path("debug_screenshots")

# ── Email credentials (from env) ─────────────────────────────────────────────
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"


# ── Cache helpers ─────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(data: dict) -> None:
    CACHE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


# ── Email sender ──────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str) -> None:
    if DRY_RUN:
        print("[DRY RUN] Would send email:")
        print(f"  To:      {NOTIFY_EMAIL}")
        print(f"  Subject: {subject}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        srv.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())
    print(f"  Email sent → {NOTIFY_EMAIL}")


def build_email(new_seats: list[dict]) -> tuple[str, str]:
    """Return (subject, html_body) for the notification email."""
    total = len(new_seats)
    subject = f"✈️ 国泰航空新里程票 — {total} 个经济舱座位可兑换"

    rows = ""
    for s in new_seats:
        rows += (
            f"<tr>"
            f"<td style='padding:6px 12px'>{s['route']}</td>"
            f"<td style='padding:6px 12px'>{s['date']}</td>"
            f"<td style='padding:6px 12px'>{s.get('flight', '—')}</td>"
            f"<td style='padding:6px 12px'>{s.get('departure', '—')}</td>"
            f"<td style='padding:6px 12px'>{s.get('arrival', '—')}</td>"
            f"<td style='padding:6px 12px'>{s.get('miles', '—')}</td>"
            f"</tr>"
        )

    book_url = "https://www.cathaypacific.com/cx/en_HK/flights/redeem-flights.html"
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:720px;margin:0 auto">
  <h2 style="color:#006564">✈️ 国泰航空里程兑换提醒</h2>
  <p>以下航线出现了 <strong>新的经济舱里程兑换座位</strong>，请尽快查看！</p>
  <table border="1" cellspacing="0" cellpadding="0"
         style="border-collapse:collapse;width:100%;font-size:14px">
    <thead style="background:#006564;color:white">
      <tr>
        <th style="padding:8px 12px">航线</th>
        <th style="padding:8px 12px">出发日期</th>
        <th style="padding:8px 12px">航班号</th>
        <th style="padding:8px 12px">出发时间</th>
        <th style="padding:8px 12px">到达时间</th>
        <th style="padding:8px 12px">所需里程</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="margin-top:20px">
    <a href="{book_url}"
       style="background:#006564;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">
      立即前往国泰里程兑换页面
    </a>
  </p>
  <p style="color:#888;font-size:12px;margin-top:24px">
    此提醒由自动监控程序发送 · {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
  </p>
</body>
</html>"""
    return subject, body


# ── Playwright scraper ────────────────────────────────────────────────────────

AWARD_URL = "https://www.cathaypacific.com/cx/en_HK/flights/redeem-flights.html"

# City-code → full name mapping for better readability
CITY_NAMES = {
    "SYD": "悉尼", "HKG": "香港", "LHR": "伦敦", "CDG": "巴黎",
    "FRA": "法兰克福", "AMS": "阿姆斯特丹", "ZRH": "苏黎世", "FCO": "罗马",
}


def _save_debug_screenshot(page_obj, label: str) -> None:
    """Save a screenshot to debug_screenshots/ for troubleshooting."""
    try:
        DEBUG_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_DIR / f"{ts}_{label}.png"
        asyncio.get_event_loop().run_until_complete(page_obj.screenshot(path=str(path)))
    except Exception:
        pass


async def _dismiss_overlays(page) -> None:
    """Close cookie banners and promotional popups."""
    selectors = [
        "button[id*='accept'], button[id*='cookie']",
        "button:text('Accept all')",
        "button:text('接受')",
        "button:text('同意')",
        "[data-testid='cookie-accept-btn']",
        ".cookie-banner button",
        "[aria-label='Close']",
        "button.modal-close",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            pass


async def _fill_airport(page, field_label: str, iata: str) -> bool:
    """
    Type an IATA code into an airport autocomplete field and select the result.
    Returns True on success.
    """
    # Cathay Pacific uses input fields labelled "From" / "To" with autocomplete
    field_selectors = [
        f"input[placeholder*='{field_label}']",
        f"input[aria-label*='{field_label}']",
        f"[data-testid*='{field_label.lower()}'] input",
        f"label:has-text('{field_label}') + * input",
        "input[name='from']" if field_label == "From" else "input[name='to']",
    ]
    input_el = None
    for sel in field_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                input_el = el
                break
        except Exception:
            continue

    if input_el is None:
        print(f"    ⚠ Could not find '{field_label}' airport field")
        return False

    await input_el.click()
    await input_el.fill("")
    await page.wait_for_timeout(300)
    await input_el.type(iata, delay=80)
    await page.wait_for_timeout(1200)

    # Pick the first autocomplete suggestion that contains the IATA code
    option_selectors = [
        f"[role='option']:has-text('{iata}')",
        f"[role='listbox'] li:has-text('{iata}')",
        f".airport-option:has-text('{iata}')",
        f"[data-testid*='suggestion']:has-text('{iata}')",
        f"li:has-text('{iata}')",
    ]
    for sel in option_selectors:
        try:
            opt = page.locator(sel).first
            if await opt.is_visible(timeout=3000):
                await opt.click()
                await page.wait_for_timeout(500)
                return True
        except Exception:
            continue

    # If no dropdown appeared, press Enter and hope for the best
    await input_el.press("Enter")
    await page.wait_for_timeout(500)
    return True


async def _select_date(page, date_str: str) -> bool:
    """
    Open the date picker and select a date.
    date_str is 'YYYY-MM-DD'.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    # Try clicking the date input or a "departure date" button
    date_triggers = [
        "input[type='date']",
        "[data-testid*='date'] input",
        "[placeholder*='Date']",
        "[aria-label*='Departure date']",
        "button[aria-label*='departure']",
        ".date-picker-trigger",
        "[data-testid='departure-date']",
    ]
    clicked = False
    for sel in date_triggers:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.click()
                clicked = True
                await page.wait_for_timeout(800)
                break
        except Exception:
            continue

    if not clicked:
        print("    ⚠ Could not open date picker")
        return False

    # Try selecting the date via ARIA cell
    formatted = dt.strftime("%-d %B %Y")  # e.g. "25 December 2024"
    day_selectors = [
        f"[aria-label='{formatted}']",
        f"[data-date='{date_str}']",
        f"td[data-day='{dt.day}']:not(.disabled)",
        f"[role='gridcell']:has-text('{dt.day}'):not(.past):not([aria-disabled])",
    ]
    # Navigate calendar months if needed (try up to 3 forward months)
    for _ in range(3):
        for sel in day_selectors:
            try:
                cell = page.locator(sel).first
                if await cell.is_visible(timeout=1500):
                    await cell.click()
                    await page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        # Go to next month
        next_btns = [
            "button[aria-label='Next month']",
            "button[aria-label='next']",
            ".calendar-nav-next",
            "[data-testid='calendar-next']",
        ]
        for sel in next_btns:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=1500):
                    await btn.click()
                    await page.wait_for_timeout(600)
                    break
            except Exception:
                continue

    print(f"    ⚠ Could not select date {date_str}")
    return False


async def _click_search(page) -> bool:
    search_selectors = [
        "button[type='submit']",
        "button:has-text('Search')",
        "button:has-text('搜索')",
        "button:has-text('搜尋')",
        "[data-testid='search-button']",
        "[data-testid='submit-btn']",
        "button.search-btn",
        "input[type='submit']",
    ]
    for sel in search_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                return True
        except Exception:
            continue
    print("    ⚠ Could not find search button")
    return False


def _parse_api_response(data: dict | list, origin: str, dest: str, date: str) -> list[dict]:
    """
    Parse JSON data captured from the Cathay Pacific award search API.
    Returns a list of available economy-award flight dicts.
    """
    results = []
    if isinstance(data, dict):
        items = (
            data.get("flights") or
            data.get("results") or
            data.get("data", {}).get("flights") or
            data.get("itineraries") or
            []
        )
    elif isinstance(data, list):
        items = data
    else:
        return []

    for item in items:
        if not isinstance(item, dict):
            continue

        # Look for economy cabin class award availability
        cabins = (
            item.get("cabins") or
            item.get("fareOptions") or
            item.get("classOfService") or
            []
        )
        eco_miles = None
        if isinstance(cabins, list):
            for cab in cabins:
                if not isinstance(cab, dict):
                    continue
                code = str(cab.get("code", cab.get("cabinClass", ""))).upper()
                if code in ("Y", "ECONOMY", "ECO"):
                    miles = (
                        cab.get("miles") or
                        cab.get("points") or
                        cab.get("awardMiles") or
                        cab.get("price")
                    )
                    avail = cab.get("available", cab.get("availability", True))
                    seats = cab.get("seats", cab.get("availableSeats", 1))
                    if miles and avail and seats:
                        eco_miles = miles
                    break
        elif isinstance(cabins, dict):
            eco = cabins.get("economy") or cabins.get("Y") or {}
            eco_miles = eco.get("miles") or eco.get("points")

        if eco_miles is None:
            # Flat structure: direct economy fields
            eco_miles = (
                item.get("economyMiles") or
                item.get("economyPoints") or
                item.get("miles")
            )

        if eco_miles is None:
            continue

        flight_num = (
            item.get("flightNumber") or
            item.get("flight") or
            item.get("flightNo") or
            "—"
        )
        dep = item.get("departureTime") or item.get("departure") or item.get("dep", "")
        arr = item.get("arrivalTime") or item.get("arrival") or item.get("arr", "")

        results.append({
            "flight": str(flight_num),
            "departure": str(dep)[:5] if dep else "—",
            "arrival": str(arr)[:5] if arr else "—",
            "miles": str(eco_miles),
        })

    return results


async def _parse_dom_results(page, origin: str, dest: str) -> list[dict]:
    """
    Fallback: parse the rendered DOM for economy award availability.
    Returns list of flight dicts (may be empty if the DOM structure changed).
    """
    results = []

    # Wait for flight cards to appear
    card_selectors = [
        "[class*='flight-card']",
        "[class*='FlightCard']",
        "[class*='flight-result']",
        "[class*='itinerary']",
        "[data-testid*='flight']",
        ".result-item",
    ]
    found_selector = None
    for sel in card_selectors:
        try:
            await page.wait_for_selector(sel, timeout=8000)
            found_selector = sel
            break
        except PlaywrightTimeout:
            continue

    if not found_selector:
        return []

    cards = await page.query_selector_all(found_selector)
    for card in cards:
        try:
            # Extract flight number
            fn_el = await card.query_selector(
                "[class*='flight-number'],[class*='flightNumber'],[data-testid*='flight-num']"
            )
            flight_num = (await fn_el.inner_text()).strip() if fn_el else "—"

            # Extract times
            dep_el = await card.query_selector(
                "[class*='departure-time'],[class*='depart'],[class*='dep-time']"
            )
            arr_el = await card.query_selector(
                "[class*='arrival-time'],[class*='arrive'],[class*='arr-time']"
            )
            dep_time = (await dep_el.inner_text()).strip()[:5] if dep_el else "—"
            arr_time = (await arr_el.inner_text()).strip()[:5] if arr_el else "—"

            # Look for economy award price
            eco_el = await card.query_selector(
                "[data-cabin='Y'],[data-class='economy'],[class*='economy-award'],"
                "[class*='Economy']:not([class*='sold']):not([class*='unavailable'])"
            )
            if not eco_el:
                eco_el = await card.query_selector("[class*='miles'],[class*='points']")

            if eco_el:
                eco_text = (await eco_el.inner_text()).strip()
                if any(ch.isdigit() for ch in eco_text):
                    results.append({
                        "flight": flight_num,
                        "departure": dep_time,
                        "arrival": arr_time,
                        "miles": eco_text,
                    })
        except Exception:
            continue

    return results


async def search_route_date(page, origin: str, dest: str, date: str) -> list[dict]:
    """
    Search for economy award availability on one route/date.
    Uses network request interception as primary method; DOM parse as fallback.
    """
    api_results: list[dict] = []
    api_captured = False

    async def on_response(response):
        nonlocal api_results, api_captured
        url = response.url.lower()
        if any(kw in url for kw in ("award", "redeem", "miles", "flight/search", "avail")):
            if response.status == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        data = await response.json()
                        parsed = _parse_api_response(data, origin, dest, date)
                        if parsed:
                            api_results = parsed
                            api_captured = True
                    except Exception:
                        pass

    page.on("response", on_response)

    try:
        await page.goto(AWARD_URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        await _dismiss_overlays(page)

        ok_from = await _fill_airport(page, "From", origin)
        ok_to = await _fill_airport(page, "To", dest)
        ok_date = await _select_date(page, date)

        if not (ok_from and ok_to and ok_date):
            page.remove_listener("response", on_response)
            return []

        await _click_search(page)
        # Wait for results (API response or DOM)
        await page.wait_for_timeout(8000)

    except PlaywrightTimeout as exc:
        print(f"    ⚠ Timeout: {exc}")
        page.remove_listener("response", on_response)
        return []
    except Exception as exc:
        print(f"    ⚠ Error: {exc}")
        page.remove_listener("response", on_response)
        return []

    page.remove_listener("response", on_response)

    if api_captured:
        return api_results

    # Fallback: parse DOM
    return await _parse_dom_results(page, origin, dest)


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run_checks() -> list[dict]:
    """
    Iterate over all routes × dates, compare with cache, return list of
    newly-available seat dicts ready for email.
    """
    cache = load_cache()
    new_seats: list[dict] = []

    today = datetime.utcnow().date()
    dates = []
    offset = 1
    while offset <= DAYS_AHEAD:
        dates.append((today + timedelta(days=offset)).strftime("%Y-%m-%d"))
        offset += SAMPLE_INTERVAL

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-HK",
            timezone_id="Asia/Hong_Kong",
            extra_http_headers={
                "Accept-Language": "en-HK,en;q=0.9,zh-HK;q=0.8",
            },
        )
        # Mask webdriver flag
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        for origin, dest, route_name in ROUTES:
            route_key = f"{origin}-{dest}"
            print(f"\n{'─'*50}")
            print(f"航线: {route_name}  ({route_key})")
            print(f"{'─'*50}")

            for date in dates:
                cache_key = f"{route_key}:{date}"
                was_available = bool(cache.get(cache_key))

                print(f"  {date} … ", end="", flush=True)
                flights = await search_route_date(page, origin, dest, date)

                if flights:
                    print(f"{len(flights)} 个航班可兑换")
                    if not was_available:
                        # Newly opened availability
                        for f in flights:
                            new_seats.append({
                                "route": route_name,
                                "date": date,
                                **f,
                            })
                    cache[cache_key] = flights
                else:
                    print("无可用座位")
                    cache[cache_key] = []

                await asyncio.sleep(3)  # polite delay between requests

        await browser.close()

    save_cache(cache)
    return new_seats


def main() -> int:
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M UTC}] 开始检查国泰航空里程兑换票…")

    if not DRY_RUN and not (GMAIL_USER and GMAIL_APP_PASSWORD):
        print("ERROR: GMAIL_USER and GMAIL_APP_PASSWORD must be set.", file=sys.stderr)
        return 1

    new_seats = asyncio.run(run_checks())

    if new_seats:
        print(f"\n🎉 发现 {len(new_seats)} 个新的里程兑换座位！正在发送邮件提醒…")
        subject, body = build_email(new_seats)
        send_email(subject, body)
        print("完成。")
    else:
        print("\n暂无新增可兑换座位。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
