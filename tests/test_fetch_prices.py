import fetch_prices
from datetime import datetime
from zoneinfo import ZoneInfo

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


def test_in_send_window_true_at_nine_am():
    now = datetime(2026, 8, 20, 9, 2, tzinfo=ZoneInfo("Australia/Sydney"))
    assert fetch_prices.in_send_window(now) is True


def test_in_send_window_false_outside_window():
    now = datetime(2026, 8, 20, 12, 0, tzinfo=ZoneInfo("Australia/Sydney"))
    assert fetch_prices.in_send_window(now) is False


def test_load_history_returns_empty_dict_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", tmp_path / "missing.json")
    assert fetch_prices.load_history() == {}


def test_load_and_save_history_roundtrip(tmp_path, monkeypatch):
    history_file = tmp_path / "nested" / "history.json"
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", history_file)
    fetch_prices.save_history({"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}})
    assert fetch_prices.load_history() == {"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}}


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
    assert "全部抓取失败" in subject
    assert "抓取失败" in body


def test_build_email_flags_partial_failure():
    products = [
        {"id": "p1", "name": "Product One", "url": "https://example.com/p1"},
        {"id": "p2", "name": "Product Two", "url": "https://example.com/p2"},
    ]
    today_results = {
        "p1": {"name": "Product One", "url": "https://example.com/p1", "price": 10.0, "rrp": 15.0},
        "p2": None,
    }
    subject, body = fetch_prices.build_email(
        "2026-08-20", products, today_results, ["Product Two: timeout"], {}
    )
    assert "有抓取失败" in subject
    assert "全部抓取失败" not in subject


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
