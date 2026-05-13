import logging
import requests
from typing import Optional
from .base import Offer

logger = logging.getLogger(__name__)

ML_SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
HEADERS = {"User-Agent": "price-bot/1.0"}


def _parse_installments(installments: dict) -> Optional[str]:
    if not installments:
        return None
    quantity = installments.get("quantity", 0)
    rate = installments.get("rate", -1)
    amount = installments.get("amount")
    if quantity and rate == 0 and amount:
        return f"{quantity}x sin interés (${amount:,.0f} c/u)"
    if quantity and amount:
        return f"{quantity}x de ${amount:,.0f}"
    return None


def search(keyword: str, max_results: int = 10) -> list[Offer]:
    offers = []
    try:
        resp = requests.get(
            ML_SEARCH_URL,
            params={"q": keyword, "limit": max_results, "site_id": "MLA"},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("MercadoLibre request failed for '%s': %s", keyword, e)
        return []

    for item in data.get("results", []):
        price = item.get("price", 0)
        original_price = None

        for price_info in item.get("prices", {}).get("presentation", {}).get("prices", []):
            if price_info.get("type") == "standard":
                original_price = price_info.get("amount")
                break

        installments_raw = item.get("installments") or {}
        installments_str = _parse_installments(installments_raw)
        thumbnail = item.get("thumbnail", "").replace("http://", "https://")

        offers.append(
            Offer(
                site="MercadoLibre",
                title=item.get("title", ""),
                price=price,
                url=item.get("permalink", ""),
                original_price=original_price,
                installments=installments_str,
                image_url=thumbnail,
            )
        )

    return offers
