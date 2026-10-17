from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit


INTEGER_FIELDS = {
    "id", "level", "reviews", "weight_g", "stock", "warranty_months",
    "favorites", "views", "return_days",
}
FLOAT_FIELDS = {"price", "rating"}
FIELDS = (
    "id", "name", "price", "currency", "category", "rarity", "level",
    "availability", "rating", "reviews", "added_at", "description", "stats",
    "edition", "region", "seller", "shipping", "condition", "weight_g",
    "stock", "warranty_months", "material", "favorites", "views", "offer_type",
    "return_days", "packaging", "enchantment", "url",
)
SCHEMA = {
    field: "integer" if field in INTEGER_FIELDS else "number" if field in FLOAT_FIELDS
    else "date" if field == "added_at" else "url" if field == "url" else "string"
    for field in FIELDS
}


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return None if text in {"", "-", "—"} else text


def parse_number(value: object, integer: bool = False) -> int | float | None:
    text = clean_text(value)
    if text is None:
        return None
    text = text.replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        raise ValueError(f"Niepoprawna liczba: {value!r}")
    number = Decimal(text)
    if not number.is_finite() or number < 0:
        raise ValueError(f"Liczba poza zakresem: {value!r}")
    if integer:
        if number != number.to_integral_value():
            raise ValueError(f"Oczekiwano liczby całkowitej: {value!r}")
        return int(number)
    result = float(number)
    if not math.isfinite(result):
        raise ValueError(f"Liczba poza zakresem: {value!r}")
    return result


def parse_price(value: object) -> tuple[float | None, str | None]:
    text = clean_text(value)
    if text is None:
        return None, None
    match = re.fullmatch(r"(.+?)\s*(zł|PLN|€|EUR|\$|USD)", text, re.IGNORECASE)
    if not match:
        raise ValueError(f"Nieznany format ceny: {value!r}")
    currencies = {"zł": "PLN", "pln": "PLN", "€": "EUR", "eur": "EUR", "$": "USD", "usd": "USD"}
    price = parse_number(match.group(1))
    if price is None or Decimal(str(price)).as_tuple().exponent < -2:
        raise ValueError(f"Niepoprawna precyzja ceny: {value!r}")
    return price, currencies[match.group(2).lower()]


def parse_date(value: object, reference: date | None = None) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    reference = reference or date.today()
    relative = {"dzisiaj": 0, "wczoraj": 1}
    if text.lower() in relative:
        return (reference - timedelta(days=relative[text.lower()])).isoformat()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Nieznany format daty: {value!r}")


def normalize_record(raw: dict, rejected: Counter | None = None) -> dict:
    rejected = rejected if rejected is not None else Counter()
    prepared = dict(raw)
    if "price_raw" in prepared:
        try:
            prepared["price"], prepared["currency"] = parse_price(prepared["price_raw"])
        except (ValueError, InvalidOperation):
            prepared["price"], prepared["currency"] = None, None
            rejected["price"] += 1
    result = {}
    for field in FIELDS:
        value = prepared.get(field)
        try:
            if field in INTEGER_FIELDS:
                cleaned = parse_number(value, integer=True)
            elif field in FLOAT_FIELDS:
                cleaned = parse_number(value)
            elif field == "added_at":
                cleaned = parse_date(value)
            else:
                cleaned = clean_text(value)
            if field == "id" and cleaned is not None and cleaned < 1:
                raise ValueError("ID musi być dodatnie")
            if field == "rating" and cleaned is not None and not 0 <= cleaned <= 5:
                raise ValueError("Ocena poza przedziałem 0–5")
            if field == "currency" and cleaned is not None and cleaned not in {"PLN", "EUR", "USD"}:
                raise ValueError("Nieznana waluta")
            if field == "url" and cleaned is not None:
                parsed = urlsplit(cleaned)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValueError("Niepoprawny URL")
            result[field] = cleaned
        except (ValueError, InvalidOperation):
            rejected[field] += 1
            result[field] = None
    return result
