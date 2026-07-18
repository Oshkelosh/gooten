"""Unit tests for Gooten shipping-quote helpers."""

from app.addons.suppliers.gooten.client import (
    parse_shipping_price_options,
    pick_shipping_prices_cents,
)
from app.addons.suppliers.shipping_quote import pick_shipping_option


def _option(method: str, price: float) -> dict:
    return {
        "MethodType": method,
        "Name": method,
        "Price": {"Price": price, "CurrencyCode": "USD"},
    }


def test_pick_prefers_standard_per_item():
    response = {
        "Items": [
            {"ShippingOptions": [_option("Expedited", 20.0), _option("Standard", 6.0)]},
        ]
    }
    assert pick_shipping_prices_cents(response) == 600


def test_pick_sums_across_items():
    response = {
        "Items": [
            {"ShippingOptions": [_option("Standard", 5.0)]},
            {"ShippingOptions": [_option("Standard", 3.5)]},
        ]
    }
    assert pick_shipping_prices_cents(response) == 850


def test_pick_cheapest_when_no_standard():
    response = {
        "Items": [
            {"ShippingOptions": [_option("Expedited", 20.0), _option("Overnight", 12.0)]},
        ]
    }
    assert pick_shipping_prices_cents(response) == 1200


def test_pick_empty_or_malformed_returns_none():
    assert pick_shipping_prices_cents({"Items": []}) is None
    assert pick_shipping_prices_cents({"Items": [{"ShippingOptions": []}]}) is None
    assert pick_shipping_prices_cents("nope") is None


def test_parse_and_select_expedited_across_items():
    response = {
        "Items": [
            {"ShippingOptions": [_option("Expedited", 20.0), _option("Standard", 6.0)]},
            {"ShippingOptions": [_option("Expedited", 15.0), _option("Standard", 4.0)]},
        ]
    }
    options = parse_shipping_price_options(response)
    chosen = pick_shipping_option(options, selected_id="Expedited")
    assert chosen is not None
    assert chosen["cents"] == 3500
