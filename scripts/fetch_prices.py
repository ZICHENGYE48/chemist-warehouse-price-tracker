"""Fetch Chemist Warehouse prices, update history, build email report."""
import json
import re
from datetime import datetime

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


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
