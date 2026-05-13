from dataclasses import dataclass
from typing import Optional


@dataclass
class Offer:
    site: str
    title: str
    price: float
    url: str
    original_price: Optional[float] = None
    installments: Optional[str] = None  # e.g. "12x sin interés"
    image_url: Optional[str] = None

    @property
    def discount_pct(self) -> Optional[float]:
        if self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100, 1)
        return None

    @property
    def has_interest_free(self) -> bool:
        if not self.installments:
            return False
        text = self.installments.lower()
        return "sin inter" in text or "sin int" in text or "0%" in text
