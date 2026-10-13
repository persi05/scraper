"""Generate a reproducible, deliberately messy catalogue from 100 source items."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source-items.json"
OUTPUT = ROOT / "public" / "catalog.json"
SEED = 20261013
VARIANTS = ("Standard", "Północ", "Południe", "Kolekcjonerski")


def make_catalogue() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))[:100]
    if len(source) != 100:
        raise ValueError("Potrzeba 100 rekordów bazowych")
    randomizer = random.Random(SEED)
    products = []
    for variant_no, variant in enumerate(VARIANTS):
        for index, item in enumerate(source):
            product_id = variant_no * 100 + index + 1
            level = int(item.get("level") or 1)
            price = round(1299 + level * 7.3 + index * 11.8 + variant_no * 219 + randomizer.randint(-150, 150), 2)
            currency = "EUR" if product_id % 11 == 0 else "USD" if product_id % 17 == 0 else "PLN"
            if currency == "EUR":
                price = round(price / 4.3, 2)
            elif currency == "USD":
                price = round(price / 3.9, 2)
            product = {
                "id": product_id,
                "name": f"{item['name']} - {variant}",
                "price": price,
                "currency": currency,
                "category": item.get("itemTypeName") or "Inne",
                "rarity": item.get("rarityName") or "Zwykły",
                "level": level,
                "availability": "Dostępny" if product_id % 7 else "Na zamówienie",
                "rating": round(2.5 + (product_id % 25) / 10, 1),
                "reviews": (product_id * 7) % 240,
                "added_at": (date(2026, 1, 1) + timedelta(days=(product_id * 3) % 280)).isoformat(),
                "description": f"{item['name']} w edycji {variant.lower()}. Przedmiot kategorii {item.get('itemTypeName') or 'Inne'} dla poziomu {level}.",
                "stats": f"Moc: {level * 2 + variant_no}; Ochrona: {level + index % 9}; Bonus: {variant_no + 1}",
                "edition": variant,
                "region": ("Północ", "Południe", "Wschód", "Zachód")[product_id % 4],
                "seller": None if product_id % 5 == 0 else f"Kupiec {product_id % 31 + 1}",
                "shipping": ("1–2 dni", "3–5 dni", "Odbiór osobisty")[product_id % 3],
                "condition": "Nowy" if product_id % 9 else "Używany",
                "weight_g": 20 + (product_id * 17) % 4980,
                "stock": (product_id * 13) % 91,
                "warranty_months": None if product_id % 5 == 1 else (6, 12, 24)[product_id % 3],
                "material": ("Stal", "Skóra", "Drewno", "Kryształ")[product_id % 4],
                "favorites": (product_id * 11) % 300,
                "views": 120 + (product_id * 37) % 8000,
                "offer_type": "Kup teraz" if product_id % 4 else "Licytacja",
                "return_days": (14, 21, 30)[product_id % 3],
                "packaging": ("Skrzynia", "Woreczek", "Szkatułka")[product_id % 3],
                "enchantment": ("Ogień", "Lód", "Błyskawica", "Brak")[product_id % 4],
            }
            products.append(product)

    pages = [list(range(start, start + 80)) for start in (1, 81, 161, 241, 321)]
    for page_index in range(1, 5):
        pages[page_index].extend((page_index * 2 - 1, page_index * 2))
    for page in pages:
        randomizer.shuffle(page)

    result = {
        "metadata": {
            "base_items": 100,
            "unique_products": 400,
            "listing_count": 408,
            "page_count": 5,
            "duplicate_listings": 8,
            "seed": SEED,
            "note": "Katalog demonstracyjny z fikcyjnymi cenami i danymi handlowymi.",
        },
        "products": products,
        "pages": pages,
    }
    return result


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    data = make_catalogue()
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zapisano {OUTPUT}: {len(data['products'])} produktów, {sum(map(len, data['pages']))} wystąpień.")
