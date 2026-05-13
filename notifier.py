import logging
import re
import requests
from scrapers.base import Offer

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

_MD2_ESCAPE_RE = re.compile(r'([_\[\]()~`>#+\-=|{}.!\\])')


def _esc(text: str) -> str:
    return _MD2_ESCAPE_RE.sub(r'\\\1', str(text))


def _fmt_price(amount: float) -> str:
    return _esc(f"${amount:,.0f}")


def _format_offer(offer: Offer, product_name: str) -> str:
    lines = [
        f"🛍 *{_esc(product_name)}*",
        f"📦 {_esc(offer.title)}",
        f"🏪 {_esc(offer.site)}",
    ]

    price_line = f"💰 *{_fmt_price(offer.price)}*"
    if offer.original_price:
        pct = offer.discount_pct
        price_line += f"  ~{_fmt_price(offer.original_price)}~"
        if pct:
            price_line += f"  *\\-{_esc(f'{pct:.0f}')}%*"
    lines.append(price_line)

    if offer.installments:
        marker = "✅" if offer.has_interest_free else "💳"
        lines.append(f"{marker} {_esc(offer.installments)}")

    lines.append(f"🔗 [Ver oferta]({offer.url})")
    return "\n".join(lines)


def send_offer(offer: Offer, product_name: str, token: str, chat_id: str) -> bool:
    text = _format_offer(offer, product_name)
    url = TELEGRAM_API.format(token=token)
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2", "disable_web_page_preview": False},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


def send_summary(total: int, token: str, chat_id: str) -> None:
    if total == 0:
        text = "✅ Revisión completada\\. No se encontraron ofertas nuevas hoy\\."
    else:
        text = f"✅ Revisión completada\\. Se enviaron *{_esc(str(total))}* ofertas nuevas\\."
    url = TELEGRAM_API.format(token=token)
    try:
        requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"},
            timeout=15,
        )
    except Exception as e:
        logger.warning("Could not send summary: %s", e)
