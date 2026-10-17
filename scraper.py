from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as conditions
from selenium.webdriver.support.ui import WebDriverWait

from cleaning import FIELDS, SCHEMA, normalize_record


ROOT = Path(__file__).resolve().parent
RECORD_SELECTOR = "tr.product-row, article.product-card"
LABELS = {
    "Kategoria": "category", "Rzadkość": "rarity", "Poziom": "level",
    "Dostępność": "availability", "Ocena": "rating", "Opinie": "reviews",
    "Dodano": "added_at",
}
LIST_SCRIPT = """
return Array.from(document.querySelectorAll('tr.product-row, article.product-card')).map(node => {
    const text = selector => node.querySelector(selector)?.textContent.trim() ?? null;
    const fields = {};
    for (const pair of node.querySelectorAll('.card-fields > div')) {
        fields[pair.querySelector('dt').textContent.trim()] = pair.querySelector('dd').textContent.trim();
    }
    const table = node.matches('tr');
    return {
        id: node.dataset.id,
        name: text(table ? '.name-cell strong' : 'h4'),
        category: text(table ? '.field-category' : '.card-category'),
        rarity: text(table ? '.field-rarity' : '.card-rarity'),
        price_raw: text(table ? '.field-price' : '.card-price'),
        level: text('.field-level'), availability: text('.field-availability'),
        rating: text('.field-rating'), reviews: text('.field-reviews'),
        added_at: text('.field-added_at'),
        url: node.querySelector('a.product-link')?.href,
        labels: fields, structure: table ? 'table' : 'card'
    };
});
"""
DETAIL_SCRIPT = """
const record = {};
for (const pair of document.querySelectorAll('#detail-fields > div')) {
    const key = Array.from(pair.classList).find(name => name.startsWith('field-'))?.slice(6);
    if (key) record[key] = pair.querySelector('dd').innerText.trim();
}
for (const [key, selector] of Object.entries({
    name: '#detail-name', description: '#detail-description',
    price_raw: '#detail-price', stats: '#detail-stats', enchantment: '#detail-enchantment'
})) record[key] = document.querySelector(selector)?.innerText.trim() ?? null;
return record;
"""


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class RateLimiter:
    def __init__(self, interval: float):
        self.interval = interval
        self.last_finished = 0.0

    def wait(self) -> None:
        remaining = self.interval - (time.monotonic() - self.last_finished)
        if remaining > 0:
            time.sleep(remaining)

    def finish(self) -> None:
        self.last_finished = time.monotonic()


class Scraper:
    def __init__(self, options: argparse.Namespace):
        self.options = options
        self.output = options.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.diagnostics = self.output / "diagnostics"
        self.diagnostics.mkdir(exist_ok=True)
        self.logger = logging.getLogger("catalogue")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        for handler in (logging.FileHandler(self.output / "scraper.log", encoding="utf-8"), logging.StreamHandler()):
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.driver = None
        self.session = requests.Session()
        if urlsplit(options.base_url).hostname in {"127.0.0.1", "localhost", "::1"}:
            self.session.trust_env = False
        self.session.headers["User-Agent"] = "Lab1EducationalScraper/1.0"
        self.limiter = RateLimiter(options.delay)
        self.errors = 0
        self.json_urls = set()
        self.rejected = Counter()

    def diagnose(self, label: str, error: Exception) -> None:
        self.errors += 1
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:80]
        stem = self.diagnostics / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{safe_label}"
        stem.with_suffix(".txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
        if self.driver is not None:
            for extension, action in (
                (".html", lambda: stem.with_suffix(".html").write_text(self.driver.page_source, encoding="utf-8")),
                (".png", lambda: self.driver.save_screenshot(str(stem.with_suffix(".png")))),
                (".json", lambda: save_json(stem.with_suffix(".json"), {
                    "browser": self.driver.get_log("browser"),
                    "performance": self.driver.get_log("performance"),
                })),
            ):
                try:
                    action()
                except Exception as diagnostic_error:
                    self.logger.error("Nie zapisano %s: %s", extension, diagnostic_error)
        self.logger.error("Błąd operacji %s: %s", label, error, exc_info=True)

    def retry(self, label: str, action):
        for attempt in range(self.options.attempts):
            try:
                return action()
            except Exception as error:
                self.diagnose(label, error)
                if attempt + 1 == self.options.attempts:
                    raise
                delay = 2 ** attempt
                self.logger.info("Ponowienie %s za %s s (próba %s)", label, delay, attempt + 2)
                time.sleep(delay)

    def get_http(self, url: str) -> requests.Response:
        def request():
            self.limiter.wait()
            try:
                response = self.session.get(url, timeout=self.options.timeout)
                response.raise_for_status()
                response.encoding = "utf-8"
                return response
            finally:
                self.limiter.finish()
        return self.retry("http_" + urlsplit(url).path, request)

    def create_browser(self):
        os.environ.setdefault("SE_CACHE_PATH", str(ROOT / ".cache" / "selenium"))
        os.environ.setdefault("SE_AVOID_STATS", "true")
        if self.options.browser == "edge":
            options = webdriver.EdgeOptions()
            browser_class = webdriver.Edge
            from selenium.webdriver.edge.service import Service
        else:
            options = webdriver.ChromeOptions()
            browser_class = webdriver.Chrome
            from selenium.webdriver.chrome.service import Service
        if not self.options.headed:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-background-networking")
        if urlsplit(self.options.base_url).hostname in {"127.0.0.1", "localhost", "::1"}:
            options.add_argument("--no-proxy-server")
        capability = "ms:loggingPrefs" if self.options.browser == "edge" else "goog:loggingPrefs"
        options.set_capability(capability, {"performance": "ALL", "browser": "ALL"})
        service = Service(executable_path=str(self.options.driver.resolve())) if self.options.driver else Service()
        self.driver = browser_class(options=options, service=service)
        self.driver.set_page_load_timeout(self.options.timeout)
        self.wait = WebDriverWait(self.driver, self.options.timeout, poll_frequency=0.15)

    def navigate(self, url: str) -> None:
        self.limiter.wait()
        try:
            self.driver.get(url)
        finally:
            self.limiter.finish()

    def observe_json_requests(self) -> None:
        for entry in self.driver.get_log("performance"):
            message = json.loads(entry["message"])["message"]
            if message["method"] != "Network.responseReceived":
                continue
            response = message["params"]["response"]
            url = response["url"]
            if (urlsplit(url).netloc == urlsplit(self.options.base_url).netloc
                    and ("json" in response.get("mimeType", "") or urlsplit(url).path.endswith(".json"))):
                self.json_urls.add(url)

    def read_listing(self, url: str) -> tuple[list[dict], list[str]]:
        self.navigate(url)
        self.wait.until(conditions.presence_of_element_located((By.CSS_SELECTOR, RECORD_SELECTOR)))
        self.wait.until(lambda driver: driver.find_elements(By.CSS_SELECTOR, "#pagination a"))
        while True:
            button = self.driver.find_element(By.ID, "load-more")
            if not button.is_displayed():
                break
            count = len(self.driver.find_elements(By.CSS_SELECTOR, RECORD_SELECTOR))
            self.wait.until(conditions.element_to_be_clickable((By.ID, "load-more")))
            self.limiter.wait()
            try:
                button.click()
                self.wait.until(lambda driver: len(driver.find_elements(By.CSS_SELECTOR, RECORD_SELECTOR)) > count)
                self.wait.until(lambda driver: not driver.find_element(By.ID, "load-more").is_displayed()
                                or driver.find_element(By.ID, "load-more").is_enabled())
            finally:
                self.limiter.finish()
        records = self.driver.execute_script(LIST_SCRIPT)
        for record in records:
            for label, value in record.pop("labels").items():
                if label in LABELS:
                    record[LABELS[label]] = value
            if not record["id"] or not record["url"] or not record["name"]:
                raise ValueError("Rekord bez ID, nazwy lub odnośnika")
        links = [element.get_attribute("href") for element in self.driver.find_elements(By.CSS_SELECTOR, "#pagination a")]
        self.observe_json_requests()
        return records, links

    def read_details(self, listing: dict) -> dict:
        self.navigate(listing["url"])
        self.wait.until(conditions.visibility_of_element_located((By.ID, "product-detail")))
        self.wait.until(lambda driver: driver.find_elements(By.CSS_SELECTOR, "#detail-fields > div"))
        details = self.driver.find_element(By.CSS_SELECTOR, "details.secret-detail")
        if details.get_attribute("open") is None:
            self.wait.until(conditions.element_to_be_clickable((By.CSS_SELECTOR, "details.secret-detail summary"))).click()
        self.wait.until(conditions.visibility_of_element_located((By.ID, "detail-enchantment")))
        fields = self.driver.execute_script(DETAIL_SCRIPT)
        if str(fields.get("id")) != str(listing["id"]):
            raise ValueError("ID szczegółów nie zgadza się z ID na liście")
        listing_clean = normalize_record(listing)
        details_clean = normalize_record({**fields, "url": listing["url"]})
        for field in ("name", "price", "currency", "category", "rarity", "level", "availability", "rating", "reviews", "added_at"):
            if listing_clean[field] != details_clean[field]:
                raise ValueError(f"Różne wartości pola {field} na liście i w szczegółach")
        merged = {**fields, **{key: value for key, value in listing.items() if key != "structure"}}
        self.observe_json_requests()
        return normalize_record(merged, self.rejected)

    def compare_source(self, records: list[dict], listings: list[dict], visited: list[str]) -> dict:
        for url in sorted(self.json_urls):
            started = time.perf_counter()
            response = self.get_http(url)
            source = response.json()
            if not isinstance(source, dict) or not isinstance(source.get("products"), list):
                continue
            source_records = {
                product["id"]: normalize_record({**product, "url": urljoin(self.options.base_url, f"/product/{product['id']}")})
                for product in source["products"]
            }
            json_seconds = time.perf_counter() - started
            differences = []
            for record in records:
                expected = source_records.get(record["id"])
                if expected is None:
                    differences.append({"id": record["id"], "field": "id", "issue": "brak w źródle"})
                    continue
                for field in FIELDS:
                    if record[field] != expected[field]:
                        differences.append({"id": record["id"], "field": field, "dom": record[field], "json": expected[field]})
            expected_ids = set(source_records)
            expected_listings = None
            if isinstance(source.get("pages"), list):
                page_numbers = [int(re.search(r"/page/(\d+)", page_url).group(1)) for page_url in visited]
                expected_listings = sum(len(source["pages"][number - 1]) for number in page_numbers)
                expected_ids = {product_id for number in page_numbers for product_id in source["pages"][number - 1]}
            actual_ids = {record["id"] for record in records}
            listing_ids = {int(record["id"]) for record in listings}
            result = {
                "url": url, "source_product_count": len(source_records),
                "json_seconds": round(json_seconds, 4), "differences": differences,
                "expected_listings_on_visited_pages": expected_listings,
                "actual_listings_on_visited_pages": len(listings),
                "missing_listing_ids": sorted(expected_ids - listing_ids),
                "unexpected_listing_ids": sorted(listing_ids - expected_ids),
                "missing_detail_ids": sorted(listing_ids - actual_ids),
                "all_source_ids_collected": actual_ids == set(source_records),
                "discovered_from": "Network.responseReceived w logu przeglądarki",
            }
            save_json(self.output / "source_comparison.json", result)
            return result
        raise ValueError("Nie wykryto źródła JSON katalogu w żądaniach przeglądarki")

    def run(self) -> None:
        started = time.perf_counter()
        summary = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "base_url": self.options.base_url, "headless": not self.options.headed,
            "browser": self.options.browser, "delay_seconds": self.options.delay,
            "attempts": self.options.attempts, "timeout_seconds": self.options.timeout,
            "partial_run": self.options.pages is not None or self.options.limit is not None,
        }
        try:
            self.retry("browser_start", self.create_browser)
            queue = [urljoin(self.options.base_url, "/page/1")]
            visited = []
            listings = []
            page_counts = []
            while queue and (self.options.pages is None or len(visited) < self.options.pages):
                url = queue.pop(0)
                if url in visited:
                    continue
                raw = self.get_http(url).text
                raw_count = len(BeautifulSoup(raw, "html.parser").select(RECORD_SELECTOR))
                page_records, links = self.retry(f"listing_{len(visited) + 1}", lambda: self.read_listing(url))
                visited.append(url)
                listings.extend(page_records)
                page_counts.append({"url": url, "raw_html_records": raw_count, "dom_records": len(page_records),
                                    "table": sum(record["structure"] == "table" for record in page_records),
                                    "cards": sum(record["structure"] == "card" for record in page_records)})
                for link in links:
                    parsed = urlsplit(link)
                    if (parsed.netloc == urlsplit(self.options.base_url).netloc
                            and re.fullmatch(r"/page/\d+/?", parsed.path)
                            and link not in visited and link not in queue):
                        queue.append(link)
                self.logger.info("Lista %s: %s rekordów (HTML: %s)", url, len(page_records), raw_count)
            save_json(self.output / "raw_listings.json", listings)
            unique = {}
            for listing in listings:
                product_id = int(listing["id"])
                if product_id in unique:
                    if normalize_record(unique[product_id]) != normalize_record(listing):
                        raise ValueError(f"Sprzeczne dane duplikatu ID {product_id}")
                else:
                    unique[product_id] = listing
            selected = list(unique.values())
            if self.options.limit:
                selected = selected[:self.options.limit]
            records = []
            for listing in selected:
                record = self.retry(f"product_{listing['id']}", lambda: self.read_details(listing))
                records.append(record)
                save_json(self.output / "products.partial.json", records)
                if len(records) % 25 == 0 or len(records) == len(selected):
                    self.logger.info("Szczegóły: %s/%s", len(records), len(selected))
            summary["browser_seconds"] = round(time.perf_counter() - started, 4)
            comparison = self.compare_source(records, listings, visited)
            save_json(self.output / "products.json", records)
            with (self.output / "products.csv").open("w", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(records)
            summary.update({
                "pages": page_counts, "page_count": len(visited), "listing_count": len(listings),
                "unique_listing_count": len(unique), "record_count": len(records),
                "attribute_count": len(FIELDS), "duplicates_before": len(listings) - len(unique),
                "duplicates_after": len(records) - len({record['id'] for record in records}),
                "rejected_values": {field: self.rejected[field] for field in FIELDS}, "schema": SCHEMA,
                "source_comparison": comparison,
            })
            integrity_ok = (not comparison["differences"] and not comparison["missing_listing_ids"]
                            and not comparison["unexpected_listing_ids"] and not any(self.rejected.values())
                            and (comparison["expected_listings_on_visited_pages"] is None
                                 or comparison["expected_listings_on_visited_pages"] == len(listings)))
            complete = (not summary["partial_run"] and comparison["all_source_ids_collected"]
                        and len(records) >= 400 and len(FIELDS) >= 22 and len(visited) >= 5)
            summary["integrity_ok"] = integrity_ok
            summary["complete_lab_run"] = complete and integrity_ok
            if not integrity_ok or (not summary["partial_run"] and not complete):
                raise ValueError("Wynik nie przeszedł kontroli kompletności lub zgodności ze źródłem JSON")
            summary["status"] = "success"
        except Exception as error:
            summary["status"] = "failed"
            summary["failure"] = str(error)
            self.diagnose("run_failed", error)
            raise
        finally:
            summary["error_count"] = self.errors
            summary["scrape_seconds"] = round(time.perf_counter() - started, 4)
            save_json(self.output / "run_summary.json", summary)
            if self.driver is not None:
                self.driver.quit()
            self.session.close()
            self.logger.info("Podsumowanie: status=%s, strony=%s, rekordy=%s, błędy=%s, czas=%.2f s",
                             summary.get("status"), summary.get("page_count", 0), summary.get("record_count", 0),
                             self.errors, summary["scrape_seconds"])


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parser na 5.0 :)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--pages", type=int, help="Limit stron, tylko do próbnego uruchomienia")
    parser.add_argument("--limit", type=int, help="Limit szczegółów, tylko do próbnego uruchomienia")
    parser.add_argument("--browser", choices=("chrome", "edge"), default="chrome")
    parser.add_argument("--driver", type=Path, help="Opcjonalna ścieżka do chromedriver/msedgedriver")
    parser.add_argument("--headed", action="store_true", help="Pokaż okno przeglądarki")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--attempts", type=int, default=3, help="Łączna liczba prób każdej operacji")
    options = parser.parse_args()
    if (not math.isfinite(options.delay) or not math.isfinite(options.timeout)
            or options.delay < 0.5 or options.timeout <= 0 or not 1 <= options.attempts <= 8):
        parser.error("Wymagane: delay >= 0.5, timeout > 0, attempts od 1 do 8")
    if any(value is not None and value < 1 for value in (options.pages, options.limit)):
        parser.error("Limity stron i produktów muszą być dodatnie")
    parsed = urlsplit(options.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("base-url musi być adresem HTTP lub HTTPS")
    options.base_url = f"{parsed.scheme}://{parsed.netloc}"
    return options


if __name__ == "__main__":
    try:
        Scraper(arguments()).run()
    except KeyboardInterrupt:
        print("Przerwano. Dotychczasowe szczegóły są w products.partial.json.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"Parser zakończony błędem: {error}", file=sys.stderr)
        raise SystemExit(1)
