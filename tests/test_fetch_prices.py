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
    now = datetime(2026, 8, 20, 10, 0, tzinfo=ZoneInfo("Australia/Sydney"))
    assert fetch_prices.in_send_window(now) is False


def test_load_history_returns_empty_dict_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", tmp_path / "missing.json")
    assert fetch_prices.load_history() == {}


def test_load_and_save_history_roundtrip(tmp_path, monkeypatch):
    history_file = tmp_path / "nested" / "history.json"
    monkeypatch.setattr(fetch_prices, "HISTORY_FILE", history_file)
    fetch_prices.save_history({"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}})
    assert fetch_prices.load_history() == {"2026-08-20": {"p1": {"price": 1.0, "rrp": 2.0}}}
