# Chemist Warehouse 价格监控 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天悉尼时间 9am 通过 GitHub Actions 自动抓取 7 个 Chemist Warehouse 商品价格，与历史比对，发邮件到 gdzjjack@gmail.com，并在 GitHub Pages 上展示价格走势图。

**Architecture:** 单个 Python 脚本 `scripts/fetch_prices.py` 负责抓取商品页、解析内嵌的 `__NEXT_DATA__` JSON、更新 `docs/data/history.json`、生成邮件正文；GitHub Actions workflow 负责定时触发、提交历史文件、通过 SMTP 发邮件；`docs/index.html` 是一个纯前端静态页面，用 Chart.js 读取 `history.json` 画价格走势图，由 GitHub Pages 直接从 `main:/docs` 提供服务。

**Tech Stack:** Python 3.12 + `requests`（抓取）+ `zoneinfo`（悉尼时区）+ `pytest`（测试）；GitHub Actions（`actions/checkout`, `actions/setup-python`, `dawidd6/action-send-mail`）；纯 HTML/JS + Chart.js CDN（前端，无构建步骤）。

## Global Constraints

- 已验证的价格提取路径：`__NEXT_DATA__` script 标签（标签属性顺序为 `id`, `type`, `nonce`，不能假设只有两个属性）→ `json.loads` → `data["props"]["pageProps"]["product"]["prices"][0]["price"]["value"]["amount"]`（当前价）和 `["price"]["rrp"]["amount"]`（原价）。
- 7 个商品固定，配置在 `products.json`，不做商品管理 UI。
- 每天固定发一封邮件，不管有无变化。
- Cron 用两条（`0 22 * * *` 覆盖 AEDT，`0 23 * * *` 覆盖 AEST），脚本内部用 `Australia/Sydney` 时区二次校验，只在悉尼本地时间 8:55–9:05 窗口内真正抓取+发信，`workflow_dispatch` 手动触发时用 `--force` 跳过窗口检查。
- 单个商品抓取失败不能让整体失败：该商品记为 `null`，邮件里单独列出失败商品，其余商品照常处理。
- `docs/` 是 GitHub Pages 发布目录，`docs/index.html` 只创建一次（不由脚本每次重新生成），靠 `fetch('data/history.json')` 动态读数据。
- 邮件发送方式：Gmail SMTP + 应用专用密码，通过 `dawidd6/action-send-mail`，凭据存在 repo secrets `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD`。

---

## 已确认的 7 个商品（来自真实小票 + 逐一核实的商品页）

| id | name | url |
|---|---|---|
| `cerave-lotion-1l` | CeraVe Daily Moisturising Lotion 1L | https://www.chemistwarehouse.com.au/buy/91315/cerave-daily-moisturising-lotion-1l |
| `swisse-fish-oil-1500-400` | Swisse Ultiboost Odourless High Strength Wild Fish Oil 1500mg 400 Capsules | https://www.chemistwarehouse.com.au/buy/67489/swisse-ultiboost-odourless-high-strength-wild-fish-oil-1500mg-400-capsules |
| `ostelin-vitd3-300` | Ostelin Vitamin D3 1000IU 300 Capsules Exclusive Size | https://www.chemistwarehouse.com.au/buy/68620/ostelin-vitamin-d3-1000iu-300-capsules-exclusive-size |
| `blackmores-epo-190` | Blackmores Evening Primrose Oil 190 Capsules | https://www.chemistwarehouse.com.au/buy/53030/blackmores-evening-primrose-oil-190-capsules |
| `swisse-mens-mv-90` | Swisse Mens Multivitamin 50+ 90 Tablets | https://www.chemistwarehouse.com.au/buy/116801/swisse-mens-multivitamin-50-90-tablets |
| `swisse-womens-mv-90` | Swisse Womens Multivitamin 50+ 90 Tablets | https://www.chemistwarehouse.com.au/buy/116797/swisse-womens-multivitamin-50-90-tablets |
| `blackmores-lutein-120` | Blackmores Lutein Defence 120 Tablets | https://www.chemistwarehouse.com.au/buy/135139/blackmores-lutein-defence-120-tablets |

（注：Swisse 男/女士 Ultivite 系列已改名为 Multivitamin，旧 SKU 58347/58346 已下架返回 404，上面用的是当前有效的新 SKU 116801/116797。）

---

### Task 1: 项目脚手架 — products.json、依赖、gitignore

**Files:**
- Create: `products.json`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `pytest.ini`

**Interfaces:**
- Produces: `products.json` 是一个 JSON 数组，每项 `{"id": str, "name": str, "url": str}`，后续所有任务都从这里读取商品列表。

- [ ] **Step 1: 创建 products.json**

```json
[
  {
    "id": "cerave-lotion-1l",
    "name": "CeraVe Daily Moisturising Lotion 1L",
    "url": "https://www.chemistwarehouse.com.au/buy/91315/cerave-daily-moisturising-lotion-1l"
  },
  {
    "id": "swisse-fish-oil-1500-400",
    "name": "Swisse Ultiboost Odourless High Strength Wild Fish Oil 1500mg 400 Capsules",
    "url": "https://www.chemistwarehouse.com.au/buy/67489/swisse-ultiboost-odourless-high-strength-wild-fish-oil-1500mg-400-capsules"
  },
  {
    "id": "ostelin-vitd3-300",
    "name": "Ostelin Vitamin D3 1000IU 300 Capsules Exclusive Size",
    "url": "https://www.chemistwarehouse.com.au/buy/68620/ostelin-vitamin-d3-1000iu-300-capsules-exclusive-size"
  },
  {
    "id": "blackmores-epo-190",
    "name": "Blackmores Evening Primrose Oil 190 Capsules",
    "url": "https://www.chemistwarehouse.com.au/buy/53030/blackmores-evening-primrose-oil-190-capsules"
  },
  {
    "id": "swisse-mens-mv-90",
    "name": "Swisse Mens Multivitamin 50+ 90 Tablets",
    "url": "https://www.chemistwarehouse.com.au/buy/116801/swisse-mens-multivitamin-50-90-tablets"
  },
  {
    "id": "swisse-womens-mv-90",
    "name": "Swisse Womens Multivitamin 50+ 90 Tablets",
    "url": "https://www.chemistwarehouse.com.au/buy/116797/swisse-womens-multivitamin-50-90-tablets"
  },
  {
    "id": "blackmores-lutein-120",
    "name": "Blackmores Lutein Defence 120 Tablets",
    "url": "https://www.chemistwarehouse.com.au/buy/135139/blackmores-lutein-defence-120-tablets"
  }
]
```

- [ ] **Step 2: 创建 requirements.txt**

```
requests==2.32.3
```

- [ ] **Step 3: 创建 requirements-dev.txt**

```
-r requirements.txt
pytest==8.3.3
```

- [ ] **Step 4: 创建 .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
email_body.html
.venv/
```

- [ ] **Step 5: 创建 pytest.ini**

```ini
[pytest]
pythonpath = scripts
```

- [ ] **Step 6: 验证 products.json 是合法 JSON 且有 7 项**

Run: `python3 -c "import json; d = json.load(open('products.json')); assert len(d) == 7; print('OK', len(d))"`
Expected: `OK 7`

- [ ] **Step 7: Commit**

```bash
git add products.json requirements.txt requirements-dev.txt .gitignore pytest.ini
git commit -m "chore: scaffold price-watch project"
```

---

### Task 2: 解析商品页价格 — `parse_product_page`

**Files:**
- Create: `scripts/fetch_prices.py`
- Test: `tests/test_fetch_prices.py`

**Interfaces:**
- Produces: `parse_product_page(html: str) -> dict`，返回 `{"price": float, "rrp": float}`；解析失败（找不到 `__NEXT_DATA__`）抛 `ValueError`。后续所有任务都会在同一个 `scripts/fetch_prices.py` 文件末尾追加代码。

- [ ] **Step 1: 创建 scripts/fetch_prices.py 骨架 + 测试 fixture**

`scripts/fetch_prices.py`:

```python
"""Fetch Chemist Warehouse prices, update history, build email report."""
import json
import re

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def parse_product_page(html: str) -> dict:
    raise NotImplementedError
```

`tests/test_fetch_prices.py`:

```python
import fetch_prices

FIXTURE_HTML = """<!DOCTYPE html><html><body>
<div>some page content</div>
<script id="__NEXT_DATA__" type="application/json" nonce="testNonce123">{"props":{"pageProps":{"product":{"prices":[{"sku":"1234","price":{"value":{"amount":47.99,"currencyCode":"AUD"},"rrp":{"amount":79.99,"currencyCode":"AUD"}}}]}}}}</script>
</body></html>"""


def test_parse_product_page_extracts_price_and_rrp():
    result = fetch_prices.parse_product_page(FIXTURE_HTML)
    assert result == {"price": 47.99, "rrp": 79.99}


def test_parse_product_page_raises_when_next_data_missing():
    try:
        fetch_prices.parse_product_page("<html><body>no data here</body></html>")
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_fetch_prices.py -v`
Expected: 两个测试都 FAIL（`NotImplementedError`）

- [ ] **Step 3: 实现 parse_product_page**

把 `scripts/fetch_prices.py` 里的 `parse_product_page` 替换为：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_fetch_prices.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_prices.py tests/test_fetch_prices.py
git commit -m "feat: parse price and rrp from __NEXT_DATA__"
```

---

### Task 3: 悉尼时间发信窗口判断 — `in_send_window`

**Files:**
- Modify: `scripts/fetch_prices.py`（追加到文件末尾）
- Test: `tests/test_fetch_prices.py`（追加）

**Interfaces:**
- Consumes: 无（纯函数，只依赖标准库 `datetime`/`zoneinfo`）
- Produces: `in_send_window(now: datetime) -> bool`，`now` 必须带 `Australia/Sydney` 时区，返回是否在 9:00 ±5 分钟窗口内。

- [ ] **Step 1: 追加失败测试**

在 `tests/test_fetch_prices.py` 顶部导入区加入：

```python
from datetime import datetime
from zoneinfo import ZoneInfo
```

文件末尾追加：

```python
def test_in_send_window_true_at_nine_am():
    now = datetime(2026, 8, 20, 9, 2, tzinfo=ZoneInfo("Australia/Sydney"))
    assert fetch_prices.in_send_window(now) is True


def test_in_send_window_false_outside_window():
    now = datetime(2026, 8, 20, 10, 0, tzinfo=ZoneInfo("Australia/Sydney"))
    assert fetch_prices.in_send_window(now) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_fetch_prices.py -v -k in_send_window`
Expected: FAIL（`AttributeError: module 'fetch_prices' has no attribute 'in_send_window'`）

- [ ] **Step 3: 实现 in_send_window**

在 `scripts/fetch_prices.py` 顶部 `import re` 后加入：

```python
from datetime import datetime
```

文件末尾追加：

```python
def in_send_window(now: datetime) -> bool:
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return abs((now - target).total_seconds()) <= 5 * 60
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_fetch_prices.py -v -k in_send_window`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_prices.py tests/test_fetch_prices.py
git commit -m "feat: add Sydney-time send window check"
```

---

### Task 4: 历史数据读写 — `load_history` / `save_history`

**Files:**
- Modify: `scripts/fetch_prices.py`（追加）
- Test: `tests/test_fetch_prices.py`（追加）

**Interfaces:**
- Produces: `load_history() -> dict`（文件不存在时返回 `{}`），`save_history(history: dict) -> None`（写入 `HISTORY_FILE`，自动创建父目录）。`HISTORY_FILE` 是模块级 `Path` 常量，测试通过 `monkeypatch.setattr(fetch_prices, "HISTORY_FILE", ...)` 重定向。

- [ ] **Step 1: 追加失败测试**

`tests/test_fetch_prices.py` 末尾追加：

```python
def test_load_history_returns_empty_dict_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", tmp_path / "missing.json")
    assert fetch_prices.load_history() == {}


def test_load_and_save_history_roundtrip(tmp_path, monkeypatch):
    history_file = tmp_path / "nested" / "history.json"
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", history_file)
    fetch_prices.save_history({"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}})
    assert fetch_prices.load_history() == {"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_fetch_prices.py -v -k history`
Expected: FAIL（`AttributeError`，`load_history`/`save_history`/`HISTORY_FILE` 都不存在）

- [ ] **Step 3: 实现**

在 `scripts/fetch_prices.py` 顶部导入区补充：

```python
from pathlib import Path
```

紧跟在 import 块之后加入模块级常量：

```python
ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_FILE = ROOT / "products.json"
HISTORY_FILE = ROOT / "docs" / "data" / "history.json"
```

文件末尾追加：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_fetch_prices.py -v -k history`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_prices.py tests/test_fetch_prices.py
git commit -m "feat: load/save price history JSON"
```

---

### Task 5: 邮件正文生成 — `build_email`

**Files:**
- Modify: `scripts/fetch_prices.py`（追加）
- Test: `tests/test_fetch_prices.py`（追加）

**Interfaces:**
- Consumes: `products: list[dict]`（同 `products.json` 结构）、`today_results: dict[str, dict|None]`（key 是 product id，值是 `{"name","url","price","rrp"}` 或 `None`）、`errors: list[str]`、`history: dict[str, dict]`（同 `today_results` 结构，按日期为 key）
- Produces: `build_email(today: str, products: list, today_results: dict, errors: list, history: dict) -> tuple[str, str]`，返回 `(subject, html_body)`。

- [ ] **Step 1: 追加失败测试**

`tests/test_fetch_prices.py` 末尾追加：

```python
def test_build_email_shows_price_drop():
    products = [{"id": "p1", "name": "Product One", "url": "https://example.com/p1"}]
    today_results = {
        "p1": {"name": "Product One", "url": "https://example.com/p1", "price": 20.0, "rrp": 30.0}
    }
    history = {
        "2026-08-19": {
            "p1": {"name": "Product One", "url": "https://example.com/p1", "price": 25.0, "rrp": 30.0}
        }
    }
    subject, body = fetch_prices.build_email("2026-08-20", products, today_results, [], history)
    assert "2026-08-20" in subject
    assert "$20.00" in body
    assert "$5.00" in body
    assert "Product One" in body


def test_build_email_flags_fetch_failure():
    products = [{"id": "p1", "name": "Product One", "url": "https://example.com/p1"}]
    subject, body = fetch_prices.build_email(
        "2026-08-20", products, {"p1": None}, ["Product One: timeout"], {}
    )
    assert "有抓取失败" in subject
    assert "抓取失败" in body
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_fetch_prices.py -v -k build_email`
Expected: FAIL（`AttributeError: module 'fetch_prices' has no attribute 'build_email'`）

- [ ] **Step 3: 实现 build_email**

文件末尾追加：

```python
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
        subject_suffix = "（有抓取失败）" if len(errors) < len(products) else "（全部抓取失败）"

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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_fetch_prices.py -v -k build_email`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_prices.py tests/test_fetch_prices.py
git commit -m "feat: build daily email report with price deltas"
```

---

### Task 6: 网络抓取层 — `fetch_one` / `fetch_all`

**Files:**
- Modify: `scripts/fetch_prices.py`（追加）
- Test: `tests/test_fetch_prices.py`（追加）
- Modify: `requirements.txt`（已在 Task 1 加入 `requests`，此任务开始真正使用）

**Interfaces:**
- Consumes: `parse_product_page`（Task 2）
- Produces: `fetch_one(product: dict) -> dict`（返回 `{"price","rrp"}`，网络/HTTP 错误直接抛出）；`fetch_all(products: list) -> tuple[dict, list[str]]`（返回 `(results, errors)`，`results[id]` 是 `{"name","url","price","rrp"}` 或 `None`，单个商品失败不影响其余商品）。

- [ ] **Step 1: 追加失败测试（用 monkeypatch 模拟 requests.get，不发真实网络请求）**

`tests/test_fetch_prices.py` 末尾追加：

```python
class FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_all_continues_after_one_failure(monkeypatch):
    products = [
        {"id": "ok", "name": "OK Product", "url": "https://example.com/ok"},
        {"id": "bad", "name": "Bad Product", "url": "https://example.com/bad"},
    ]

    def fake_get(url, headers=None, timeout=None):
        if "ok" in url:
            return FakeResponse(FIXTURE_HTML)
        return FakeResponse("not found", status=404)

    monkeypatch.setattr(fetch_prices.requests, "get", fake_get)
    results, errors = fetch_prices.fetch_all(products)
    assert results["ok"] == {
        "name": "OK Product",
        "url": "https://example.com/ok",
        "price": 47.99,
        "rrp": 79.99,
    }
    assert results["bad"] is None
    assert len(errors) == 1
    assert "Bad Product" in errors[0]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_fetch_prices.py -v -k fetch_all`
Expected: FAIL（`AttributeError: module 'fetch_prices' has no attribute 'requests'`，因为还没 import requests / 定义函数）

- [ ] **Step 3: 实现 fetch_one / fetch_all**

在 `scripts/fetch_prices.py` 顶部导入区加入：

```python
import requests
```

文件末尾追加：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_fetch_prices.py -v`
Expected: 全部（此时应有 9 个）测试 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_prices.py tests/test_fetch_prices.py requirements.txt
git commit -m "feat: fetch product pages over HTTP with per-product error isolation"
```

---

### Task 7: CLI 入口 — `main()` + GitHub Actions 输出

**Files:**
- Modify: `scripts/fetch_prices.py`（追加）

**Interfaces:**
- Consumes: 本文件内此前定义的所有函数（`load_products`, `fetch_all`, `load_history`, `save_history`, `build_email`, `in_send_window`）
- Produces: 命令行入口，支持 `--dry-run`（只打印结果，不写文件不发信号）和 `--force`（跳过悉尼时间窗口检查，供 `workflow_dispatch` 手动触发使用）；正常运行时写 `docs/data/history.json`、写 `email_body.html`、并向 `$GITHUB_OUTPUT` 写 `should_run` 和 `subject`。

- [ ] **Step 1: 实现 write_github_output 和 main()**

在 `scripts/fetch_prices.py` 顶部导入区加入：

```python
import argparse
import os
from zoneinfo import ZoneInfo
```

文件末尾追加：

```python
SYDNEY_TZ = ZoneInfo("Australia/Sydney")
EMAIL_BODY_FILE = ROOT / "email_body.html"


def write_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        return
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    now = datetime.now(SYDNEY_TZ)
    if not args.force and not args.dry_run and not in_send_window(now):
        print(f"Sydney time is {now.isoformat()}, outside 8:55-9:05 window. Skipping.")
        write_github_output("should_run", "false")
        return

    products = load_products()
    results, errors = fetch_all(products)
    today = now.date().isoformat()

    history = load_history()
    history[today] = results

    subject, body = build_email(today, products, results, errors, history)

    if args.dry_run:
        print(subject)
        print(body)
        for product in products:
            print(product["id"], results.get(product["id"]))
        return

    save_history(history)
    EMAIL_BODY_FILE.write_text(body, encoding="utf-8")
    write_github_output("subject", subject)
    write_github_output("should_run", "true")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 本地跑一次真实 dry-run，验证端到端抓取逻辑（这一步会真的访问 chemistwarehouse.com.au）**

Run: `pip install -r requirements.txt && python scripts/fetch_prices.py --dry-run --force`
Expected: 打印出邮件 subject/body，以及 7 个商品各自的 `{"name":..., "url":..., "price":..., "rrp":...}`，全部非 `None`（如果某个商品返回 `None`，检查该商品 URL 是否仍然有效，商品页可能又下架/改版）

- [ ] **Step 3: 跑单元测试全集，确认没有破坏之前的测试**

Run: `pip install -r requirements-dev.txt && pytest -v`
Expected: 全部 passed（9 个测试）

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch_prices.py
git commit -m "feat: add CLI entrypoint with dry-run and force flags"
```

---

### Task 8: 静态展示页 — docs/index.html

**Files:**
- Create: `docs/index.html`
- Create: `docs/data/history.json`
- Create: `docs/.nojekyll`

**Interfaces:**
- Consumes: `docs/data/history.json`，结构为 `{"YYYY-MM-DD": {product_id: {"name","url","price","rrp"} | null}}`（由 Task 7 的 `main()` 写入）。

- [ ] **Step 1: 创建空历史文件占位**

`docs/data/history.json`:

```json
{}
```

- [ ] **Step 2: 创建 .nojekyll（禁用 GitHub Pages 的 Jekyll 处理，避免下划线目录/构建步骤干扰静态文件）**

`docs/.nojekyll`: 创建一个空文件（内容为空）。

- [ ] **Step 3: 创建 docs/index.html**

```html
<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Chemist Warehouse 价格走势</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; }
  h1 { font-size: 1.4rem; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 2rem; }
  th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
  canvas { margin-bottom: 3rem; max-width: 100%; }
</style>
</head>
<body>
<h1>Chemist Warehouse 价格走势</h1>
<p id="updated">加载中...</p>
<table id="current-table">
  <thead><tr><th>商品</th><th>当前价</th><th>RRP</th></tr></thead>
  <tbody></tbody>
</table>
<div id="charts"></div>
<script>
async function main() {
  const res = await fetch('data/history.json');
  const history = await res.json();
  const dates = Object.keys(history).sort();
  if (dates.length === 0) {
    document.getElementById('updated').textContent = '暂无数据，等待第一次抓取运行';
    return;
  }
  const latestDate = dates[dates.length - 1];
  document.getElementById('updated').textContent = '最近更新: ' + latestDate;

  const productIds = new Set();
  dates.forEach(d => Object.keys(history[d]).forEach(id => productIds.add(id)));

  const tbody = document.querySelector('#current-table tbody');
  const chartsDiv = document.getElementById('charts');

  productIds.forEach(id => {
    const latest = history[latestDate][id];
    const name = latest ? latest.name : id;
    const row = document.createElement('tr');
    row.innerHTML = '<td>' + name + '</td>' +
      '<td>' + (latest ? '$' + latest.price.toFixed(2) : '—') + '</td>' +
      '<td>' + (latest ? '$' + latest.rrp.toFixed(2) : '—') + '</td>';
    tbody.appendChild(row);

    const canvas = document.createElement('canvas');
    chartsDiv.appendChild(canvas);
    const prices = dates.map(d => (history[d][id] ? history[d][id].price : null));
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [{ label: name, data: prices, spanGaps: true }],
      },
      options: { responsive: true, plugins: { title: { display: true, text: name } } },
    });
  });
}
main();
</script>
</body>
</html>
```

- [ ] **Step 4: 本地验证页面能正确渲染（用真实抓取产生的 history.json 覆盖测试）**

Run:
```bash
cp docs/data/history.json /tmp/history_backup.json
python3 -c "
import json, datetime
d = json.load(open('/tmp/history_backup.json'))
d['2026-08-20'] = {'cerave-lotion-1l': {'name': 'CeraVe Daily Moisturising Lotion 1L', 'url': 'https://www.chemistwarehouse.com.au/buy/91315/cerave-daily-moisturising-lotion-1l', 'price': 38.99, 'rrp': 38.99}}
json.dump(d, open('docs/data/history.json', 'w'))
"
cd docs && python3 -m http.server 8000
```
在浏览器打开 `http://localhost:8000`，确认表格显示 CeraVe 的价格、下方出现一条走势图曲线。确认后按 Ctrl+C 停止服务器，并执行：
```bash
cd /Users/jack/chemist-warehouse-price-tracker
echo '{}' > docs/data/history.json
```
把 history.json 恢复成空，避免把本地测试数据提交进仓库。

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/data/history.json docs/.nojekyll
git commit -m "feat: add price history static page"
```

---

### Task 9: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/price-check.yml`

**Interfaces:**
- Consumes: `scripts/fetch_prices.py`（Task 7）的 CLI（`--force` 用于 `workflow_dispatch`）及其 `$GITHUB_OUTPUT` 键 `should_run` / `subject`；`email_body.html`（Task 7 生成）；repo secrets `GMAIL_USERNAME` / `GMAIL_APP_PASSWORD`（在 Task 10 配置）。

- [ ] **Step 1: 创建 workflow 文件**

`.github/workflows/price-check.yml`:

```yaml
name: Price Check

on:
  schedule:
    - cron: '0 22 * * *'
    - cron: '0 23 * * *'
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  check-prices:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch prices
        id: fetch
        run: |
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            python scripts/fetch_prices.py --force
          else
            python scripts/fetch_prices.py
          fi

      - name: Commit updated history
        if: steps.fetch.outputs.should_run == 'true'
        run: |
          git config user.name "price-watch-bot"
          git config user.email "actions@users.noreply.github.com"
          git add docs/data/history.json
          git diff --cached --quiet || git commit -m "chore: price data $(date -u +%Y-%m-%d)"
          git push

      - name: Send email report
        if: steps.fetch.outputs.should_run == 'true'
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: smtp.gmail.com
          server_port: 465
          username: ${{ secrets.GMAIL_USERNAME }}
          password: ${{ secrets.GMAIL_APP_PASSWORD }}
          subject: ${{ steps.fetch.outputs.subject }}
          to: gdzjjack@gmail.com
          from: Chemist Warehouse Price Watch
          html_body: file://email_body.html
```

- [ ] **Step 2: 本地校验 YAML 语法**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/price-check.yml')); print('valid yaml')"`
Expected: `valid yaml`（如果本机没有 `pyyaml`，先 `pip install pyyaml` 再跑，这是一次性校验工具，不需要写进 requirements）

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/price-check.yml
git commit -m "feat: add scheduled GitHub Actions workflow for price checks"
```

---

### Task 10: 部署 — 建仓库、配置 Pages 和 Secrets、端到端验证

这个任务需要你（用户）在浏览器里完成两步人工操作：生成 Gmail 应用专用密码、gh CLI 登录授权。

**Files:** 无代码改动，纯部署操作。

- [ ] **Step 1: 安装并登录 gh CLI**

Run: `brew install gh`
然后 Run: `gh auth login`（按提示选择 GitHub.com → HTTPS → 用浏览器登录，需要你在弹出的浏览器页面里确认）

验证: `gh auth status` 应显示已登录账号。

- [ ] **Step 2: 生成 Gmail 应用专用密码**

去 https://myaccount.google.com/apppasswords （需要 gdzjjack@gmail.com 账号已开启两步验证），生成一个新的应用专用密码，记下 16 位密码（只显示一次）。

- [ ] **Step 3: 创建远程仓库并推送**

Run:
```bash
cd /Users/jack/chemist-warehouse-price-tracker
gh repo create chemist-warehouse-price-tracker --public --source=. --remote=origin --push
```
Expected: 输出仓库创建成功的链接，且本地分支已关联 `origin` 并推送。

- [ ] **Step 4: 配置 repo secrets**

Run:
```bash
gh secret set GMAIL_USERNAME --body "gdzjjack@gmail.com"
gh secret set GMAIL_APP_PASSWORD
```
第二条命令会提示粘贴 Step 2 里拿到的应用专用密码。

验证: `gh secret list` 应列出 `GMAIL_USERNAME` 和 `GMAIL_APP_PASSWORD`。

- [ ] **Step 5: 开启 GitHub Pages（来源设为 main 分支 /docs 目录）**

Run:
```bash
gh api -X PUT repos/{owner}/chemist-warehouse-price-tracker/pages \
  -f "source[branch]=main" -f "source[path]=/docs" 2>/dev/null || \
gh api -X POST repos/{owner}/chemist-warehouse-price-tracker/pages \
  -f "source[branch]=main" -f "source[path]=/docs"
```
`{owner}` 替换成 `gh api user -q .login` 输出的用户名。如果两条命令都报错，去 `https://github.com/<owner>/chemist-warehouse-price-tracker/settings/pages` 手动把 Source 设为 `Deploy from a branch`，Branch 选 `main` / `/docs`，点 Save。

验证: 几分钟后访问 `https://<owner>.github.io/chemist-warehouse-price-tracker/` 能看到 Task 8 的价格走势页（此时 history.json 还是空的，表格为空、提示"暂无数据"是正常的）。

- [ ] **Step 6: 手动触发一次 workflow，端到端验证**

Run: `gh workflow run "Price Check"`
等待约 1 分钟后 Run: `gh run list --workflow="Price Check" --limit 1`，确认状态是 `completed` / `success`。

验证三件事：
1. `gh run view --log` 里能看到 7 个商品的抓取结果
2. gdzjjack@gmail.com 收到了主题形如 `[价格监控] 2026-08-20 Chemist Warehouse 报告` 的邮件
3. 刷新 `https://<owner>.github.io/chemist-warehouse-price-tracker/` 页面，表格和走势图显示了当天的价格数据

如果邮件没收到，先查 `gh run view --log` 里 `Send email report` 这一步的报错（常见原因：应用专用密码复制时带了空格，或两步验证没开启导致密码生成失败）。

- [ ] **Step 7: 确认定时任务已生效**

不需要额外操作——workflow 文件里的 `schedule` 触发器合并后自动生效。可以在 `https://github.com/<owner>/chemist-warehouse-price-tracker/actions/workflows/price-check.yml` 页面看到下次预计运行时间。
