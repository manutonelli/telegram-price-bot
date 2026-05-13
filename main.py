#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from scrapers import mercadolibre, fravega, garbarino
from scrapers.base import Offer
from notifier import send_offer, send_summary

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("price-bot")

PRODUCTS_FILE = Path(__file__).parent / "products.json"
SEEN_FILE = Path(__file__).parent / "seen.json"
SEEN_TTL_HOURS = 24
SCRAPERS = [mercadolibre, fravega, garbarino]


def load_products() -> list[dict]:
    with open(PRODUCTS_FILE) as f:
        return json.load(f)


def load_seen() -> dict[str, float]:
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def save_seen(seen: dict[str, float]) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def prune_seen(seen: dict[str, float]) -> dict[str, float]:
    now = time.time()
    ttl = SEEN_TTL_HOURS * 3600
    return {url: ts for url, ts in seen.items() if now - ts < ttl}


def is_interesting(offer: Offer, product: dict) -> bool:
    max_price = product.get("max_price")
    min_discount = product.get("min_discount_pct", 0)

    if max_price and offer.price <= max_price:
        return True
    if min_discount and offer.discount_pct and offer.discount_pct >= min_discount:
        return True
    if offer.has_interest_free:
        return True
    return False


def run() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        sys.exit(1)

    products = load_products()
    seen = prune_seen(load_seen())
    total_sent = 0

    for product in products:
        product_name = product["name"]
        keywords = product.get("keywords", [product_name])
        logger.info("Checking product: %s", product_name)
        all_offers: list[Offer] = []

        for keyword in keywords:
            for scraper in SCRAPERS:
                try:
                    results = scraper.search(keyword, max_results=5)
                    all_offers.extend(results)
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning("%s scraper error for '%s': %s", scraper.__name__, keyword, e)

        seen_urls_this_run: set[str] = set()
        for offer in all_offers:
            if not offer.url or offer.url in seen_urls_this_run:
                continue
            seen_urls_this_run.add(offer.url)

            if offer.url in seen:
                continue
            if not is_interesting(offer, product):
                continue

            logger.info("  ALERT %s @ $%s (discount=%s%%, interest_free=%s)",
                        offer.site, offer.price, offer.discount_pct, offer.has_interest_free)

            ok = send_offer(offer, product_name, token, chat_id)
            if ok:
                seen[offer.url] = time.time()
                total_sent += 1
                time.sleep(1)

    save_seen(seen)
    send_summary(total_sent, token, chat_id)
    logger.info("Done. Sent %d notifications.", total_sent)
    return total_sent


if __name__ == "__main__":
    run()
