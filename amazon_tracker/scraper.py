import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

AMAZON_DOMAINS = {
    "amazon.com", "amazon.com.au", "amazon.co.uk", "amazon.ca",
    "amazon.de", "amazon.fr", "amazon.co.jp", "amazon.in",
}


def normalize_url(url: str):
    """Return (clean_url, asin) from any Amazon product URL, following short-link redirects."""
    url = url.strip()

    parsed = urlparse(url)
    host = parsed.netloc.lstrip("www.")

    # Follow redirects for shortened links (amzn.to, a.co, etc.)
    if host not in AMAZON_DOMAINS:
        try:
            r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=10)
            url = r.url
            parsed = urlparse(url)
            host = parsed.netloc.lstrip("www.")
        except requests.RequestException:
            return None, None

    if host not in AMAZON_DOMAINS:
        return None, None

    asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", parsed.path)
    if not asin_match:
        return None, None

    asin = asin_match.group(1)
    clean_url = f"https://www.{host}/dp/{asin}"
    return clean_url, asin


def fetch_product(url: str) -> dict:
    """Scrape product name, price, currency, and image from an Amazon page."""
    session = requests.Session()
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch page: {e}")

    soup = BeautifulSoup(resp.text, "lxml")

    # Detect CAPTCHA / robot check
    if soup.find("form", {"action": re.compile(r"validateCaptcha", re.I)}):
        raise RuntimeError(
            "Amazon is showing a CAPTCHA. Try again in a few minutes, or use a VPN."
        )

    # Product name
    title_el = soup.find("span", id="productTitle")
    name = title_el.get_text(strip=True) if title_el else "Unknown Product"

    # Image — prefer the main landing image
    image_url = None
    for img_id in ("landingImage", "imgBlkFront", "main-image"):
        el = soup.find("img", id=img_id)
        if el:
            image_url = el.get("data-old-hires") or el.get("src")
            break

    # Price — try selectors in order of reliability
    price, currency = _extract_price(soup)
    if price is None:
        raise RuntimeError(
            "Could not find a price on this page. "
            "The product may be out of stock, or Amazon may have blocked the request."
        )

    return {"name": name, "price": price, "currency": currency, "image_url": image_url}


def _extract_price(soup):
    """Try multiple CSS selectors to extract the numeric price and currency symbol."""
    # Most reliable: the hidden a-offscreen span inside a price block
    for container_id in (
        "corePrice_feature_div",
        "corePriceDisplay_desktop_feature_div",
        "apex_desktop_newAccordionRow",
        None,  # fallback: search whole page
    ):
        container = soup.find(id=container_id) if container_id else soup
        if not container:
            continue
        offscreen = container.find("span", class_="a-offscreen")
        if offscreen:
            text = offscreen.get_text(strip=True)
            return _parse_price_text(text)

    # Fallback: legacy price block IDs
    for el_id in ("priceblock_ourprice", "priceblock_dealprice", "priceblock_saleprice"):
        el = soup.find(id=el_id)
        if el:
            return _parse_price_text(el.get_text(strip=True))

    # Fallback: priceToPay span
    el = soup.find("span", class_="priceToPay")
    if el:
        offscreen = el.find("span", class_="a-offscreen")
        target = offscreen or el
        return _parse_price_text(target.get_text(strip=True))

    return None, "$"


def _parse_price_text(text: str):
    """Parse '$29.99', 'A$29.99', 'AU$29.99', '£29.99' etc. into (float, symbol)."""
    text = text.strip()
    currency_match = re.match(r"^([A-Z]{0,2}[\$£€¥₹]|[A-Z]{2,3}\s)", text)
    currency = currency_match.group(0).strip() if currency_match else "$"
    numeric_str = re.sub(r"[^\d.]", "", text)
    try:
        return float(numeric_str), currency
    except ValueError:
        return None, "$"
