import json
import logging
import re
import requests
from typing import Optional
from .base import Offer

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.garbarino.com/search"
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


def _clean_price(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r'[^\d]', '', str(value))
    return float(cleaned) if cleaned else None


def _parse_installments(product: dict) -> Optional[str]:
    installment = product.get("bestInstallment") or product.get("installment") or {}
    quantity = installment.get("quantity") or installment.get("installments")
    rate = installment.get("interestRate") or installment.get("rate")
    amount = installment.get("amount") or installment.get("installmentAmount")
    if quantity and amount is not None:
        amount_clean = _clean_price(amount)
        if rate == 0 or rate is None:
            return f"{quantity}x sin interés (${amount_clean:,.0f} c/u)"
        return f"{quantity}x de ${amount_clean:,.0f}"
    return None


def search(keyword: str, max_results: int = 10) -> list[Offer]:
    offers = []
    try:
        resp = requests.get(
            SEARCH_URL, params={"q": keyword}, headers=HEADERS, timeout=20
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Garbarino request failed for '%s': %s", keyword, e)
        return []

    match = _NEXT_DATA_RE.search(resp.text)
    if not match:
        logger.warning("Garbarino: __NEXT_DATA__ not found for '%s'", keyword)
        return []

    try:
        data = json.loads(match.group(1))
        page_props = data.get("props", {}).get("pageProps", {})
        products = (
            page_props.get("products")
            or page_props.get("items")
            or page_props.get("searchResults", {}).get("products", [])
            or []
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Garbarino: failed to parse JSON for '%s': %s", keyword, e)
        return []

    for product in products[:max_results]:
        price = _clean_price(
            product.get("price") or product.get("currentPrice") or product.get("salePrice")
        )
        if not price:
            continue

        original_price = _clean_price(
            product.get("originalPrice") or product.get("listPrice") or product.get("regularPrice")
        )
        if original_price and original_price <= price:
            original_price = None

        slug = product.get("slug") or product.get("url") or product.get("urlKey") or ""
        url = (
            f"https://www.garbarino.com/{slug}"
            if slug and not slug.startswith("http")
            else slug
        )

        image = product.get("image") or product.get("thumbnail") or ""
        if image and not image.startswith("http"):
            image = "https:" + image

        offers.append(
            Offer(
                site="Garbarino",
                title=product.get("name") or product.get("title") or "",
                price=price,
                url=url,
                original_price=original_price,
                installments=_parse_installments(product),
                image_url=image,
            )
        )

    return offers
