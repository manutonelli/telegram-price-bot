import json
import logging
import re
import requests
from typing import Optional
from .base import Offer

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.fravega.com/l/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


def _parse_installments(product: dict) -> Optional[str]:
    best = product.get("bestInstallment") or {}
    quantity = best.get("quantity")
    rate = best.get("interestRate")
    amount = best.get("installmentAmount") or best.get("amount")
    if quantity and amount is not None:
        if rate == 0 or rate is None:
            return f"{quantity}x sin interés (${float(amount):,.0f} c/u)"
        return f"{quantity}x de ${float(amount):,.0f}"
    return None


def search(keyword: str, max_results: int = 10) -> list[Offer]:
    offers = []
    try:
        resp = requests.get(
            SEARCH_URL, params={"keyword": keyword}, headers=HEADERS, timeout=20
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Fravega request failed for '%s': %s", keyword, e)
        return []

    match = _NEXT_DATA_RE.search(resp.text)
    if not match:
        logger.warning("Fravega: __NEXT_DATA__ not found for '%s'", keyword)
        return []

    try:
        data = json.loads(match.group(1))
        products = data.get("props", {}).get("pageProps", {}).get("products", [])
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Fravega: failed to parse JSON for '%s': %s", keyword, e)
        return []

    for product in products[:max_results]:
        price = product.get("price") or product.get("currentPrice")
        if not price:
            continue
        price = float(price)

        original_price = product.get("originalPrice") or product.get("listPrice")
        if original_price:
            original_price = float(original_price)
            if original_price <= price:
                original_price = None

        slug = product.get("slug") or product.get("url") or ""
        url = f"https://www.fravega.com/p/{slug}" if not slug.startswith("http") else slug

        image = product.get("image") or product.get("thumbnail") or ""
        if image and not image.startswith("http"):
            image = "https:" + image

        offers.append(
            Offer(
                site="Fravega",
                title=product.get("title") or product.get("name") or "",
                price=price,
                url=url,
                original_price=original_price,
                installments=_parse_installments(product),
                image_url=image,
            )
        )

    return offers
