"""Unit tests for the Gooten supplier addon shipping quotes."""

from unittest.mock import AsyncMock

import pytest

from app.addons.suppliers.gooten.addon import GootenAddon


def test_supports_shipping_quotes():
    assert GootenAddon().supports_shipping_quotes() is True


@pytest.mark.asyncio
async def test_quote_shipping_returns_cents():
    addon = GootenAddon()
    addon._config = {}
    addon._client = AsyncMock()
    addon._client.get_shipping_prices = AsyncMock(
        return_value={
            "Items": [
                {
                    "ShippingOptions": [
                        {"MethodType": "Expedited", "Name": "Expedited", "Price": {"Price": 15.0}},
                        {"MethodType": "Standard", "Name": "Standard", "Price": {"Price": 4.99}},
                    ]
                }
            ]
        }
    )
    cents = await addon.quote_shipping(
        [{"supplier_product_id": "SKU-1", "quantity": 1}],
        {"country": "US"},
    )
    assert cents == 499


@pytest.mark.asyncio
async def test_quote_shipping_none_without_country():
    addon = GootenAddon()
    addon._config = {}
    addon._client = AsyncMock()
    cents = await addon.quote_shipping(
        [{"supplier_product_id": "SKU-1", "quantity": 1}],
        {},
    )
    assert cents is None
    addon._client.get_shipping_prices.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_shipping_returns_none_on_api_error():
    from app.addons.suppliers.gooten.client import GootenAPIError

    addon = GootenAddon()
    addon._config = {}
    addon._client = AsyncMock()
    addon._client.get_shipping_prices = AsyncMock(
        side_effect=GootenAPIError("bad request", status_code=400)
    )
    cents = await addon.quote_shipping(
        [{"supplier_product_id": "SKU-1", "quantity": 1}],
        {"country": "US"},
    )
    assert cents is None


@pytest.mark.asyncio
async def test_quote_shipping_details_honors_selected_method():
    addon = GootenAddon()
    addon._config = {}
    addon._client = AsyncMock()
    addon._client.get_shipping_prices = AsyncMock(
        return_value={
            "Items": [
                {
                    "ShippingOptions": [
                        {"MethodType": "Expedited", "Name": "Expedited", "Price": {"Price": 15.0}},
                        {"MethodType": "Standard", "Name": "Standard", "Price": {"Price": 4.99}},
                    ]
                }
            ]
        }
    )
    details = await addon.quote_shipping_details(
        [{"supplier_product_id": "SKU-1", "quantity": 1}],
        {"country": "US"},
        selected_id="Expedited",
    )
    assert details is not None
    assert details["cents"] == 1500
    assert details["selected_id"] == "Expedited"


@pytest.mark.asyncio
async def test_create_order_sends_ship_type():
    addon = GootenAddon()
    addon._config = {"default_ship_type": "Standard"}
    addon._client = AsyncMock()
    addon._client.create_order = AsyncMock(return_value={"OrderId": "ord-1"})
    result = await addon.create_order(
        [{"supplier_product_id": "SKU-1", "quantity": 1}],
        {"line1": "1 Main", "city": "Austin", "postal_code": "78701", "country": "US"},
        shipping_method="Expedited",
    )
    assert result["success"] is True
    payload = addon._client.create_order.await_args.args[0]
    assert payload["Items"][0]["ShipType"] == "Expedited"
