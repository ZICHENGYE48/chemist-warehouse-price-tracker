"""Fetch Chemist Warehouse prices, update history, build email report."""
import json
import re
from datetime import datetime
from pathlib import Path

import requests

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


def build_email(today: str, products: list, today_results: dict, errors: list, history: dict) -> tuple:
    earlier_dates = sorted(d for d in history if d < today)
    prev_results = history[earlier_dates[-1]] if earlier_dates else {}

    rows = []
    for product in products:
        pid = product["id"]
        current = today_results.get(pid)
        if current is None:
            rows.append(
                f'<tr><td>{product["name"]}</td>'
                f'<td colspan="3" style="color:#b00020">抓取失败，请检查</td></tr>'
            )
            continue
        price = current["price"]
        rrp = current["rrp"]
        previous = prev_results.get(pid)
        if previous is None:
            delta_html = "—"
        else:
            delta = round(price - previous["price"], 2)
            if delta < 0:
                delta_html = f'<span style="color:green">↓ ${abs(delta):.2f}</span>'
            elif delta > 0:
                delta_html = f'<span style="color:#b00020">↑ ${delta:.2f}</span>'
            else:
                delta_html = '<span style="color:gray">持平</span>'
        rows.append(
            f'<tr><td><a href="{product["url"]}">{product["name"]}</a></td>'
            f'<td>${price:.2f}</td><td>{delta_html}</td><td>${rrp:.2f}</td></tr>'
        )

    error_note = ""
    subject_suffix = ""
    if errors:
        error_note = "<p><b>抓取失败:</b> " + "; ".join(errors) + "</p>"
        subject_suffix = "（有抓取失败）"

    body = (
        f"<h2>Chemist Warehouse 每日价格报告 - {today}</h2>"
        + error_note
        + '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
        + "<tr><th>商品</th><th>今日价</th><th>涨跌</th><th>RRP</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    subject = f"[价格监控] {today} Chemist Warehouse 报告{subject_suffix}"
    return subject, body


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_one(product: dict) -> dict:
    response = requests.get(
        product["url"], headers={"User-Agent": USER_AGENT}, timeout=15
    )
    response.raise_for_status()
    return parse_product_page(response.text)


def fetch_all(products: list) -> tuple:
    results = {}
    errors = []
    for product in products:
        try:
            parsed = fetch_one(product)
            results[product["id"]] = {
                "name": product["name"],
                "url": product["url"],
                "price": parsed["price"],
                "rrp": parsed["rrp"],
            }
        except Exception as exc:
            results[product["id"]] = None
            errors.append(f"{product['name']}: {exc}")
    return results, errors
