"""Fetch Chemist Warehouse prices, update history, build email report."""
import json
import re
from datetime import datetime
from pathlib import Path

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = ROOT / "products.json"
HISTORY_FILE = ROOT / "docs" / "data" / "history.json"


def parse_product_page(html: str) -> dict:
    match = NEXT_DATA_RE.search(html)
    if not match:
        raise ValueError("__NEXT_DATA__ script tag not found")
    data = json.loads(match.group(1))
    product_wrapper = data["props"]["pageProps"]["product"]
    price_entry = product_wrapper["prices"][0]
    return {
        "price": price_entry["price"]["value"]["amount"],
        "rrp": price_entry["price"]["rrp"]["amount"],
    }


def in_send_window(now: datetime) -> bool:
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return abs((now - target).total_seconds()) <= 5 * 60


def load_products() -> list:
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
