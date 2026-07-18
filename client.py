"""Gooten API client."""

from __future__ import annotations

from typing import Any

import httpx

GOOTEN_BASE = "https://api.print.io"


class GootenAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GootenClient:
    def __init__(
        self,
        recipe_id: str,
        partner_billing_key: str,
        *,
        timeout: float = 60.0,
    ):
        self._recipe_id = recipe_id
        self._billing_key = partner_billing_key
        self._timeout = timeout

    def _params(self) -> dict[str, str]:
        return {"recipeId": self._recipe_id}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{GOOTEN_BASE}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                method, url, params=self._params(), json=json
            )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            message = resp.text
            if isinstance(data, dict):
                message = str(data.get("Message") or data.get("message") or resp.text)
            raise GootenAPIError(message, status_code=resp.status_code, body=data)
        return data

    async def list_blueprints(self) -> Any:
        return await self._request("GET", "/api/catalog/blueprints")

    async def get_shipping_prices(
        self,
        items: list[dict[str, Any]],
        country_code: str,
        *,
        currency_code: str = "USD",
    ) -> Any:
        """POST shippingprices — available shipping options/costs for a cart.

        Note: this endpoint uses a different path style than the catalog/order
        calls; callers wrap this in try/except and fall back to Site Settings.
        """
        body = {
            "Items": items,
            "CountryCode": country_code,
            "CurrencyCode": currency_code,
            "PartnerBillingKey": self._billing_key,
        }
        return await self._request("POST", "/api/v/5/source/api/shippingprices", json=body)

    async def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {**payload, "PartnerBillingKey": self._billing_key}
        data = await self._request("POST", "/api/orders", json=body)
        return data if isinstance(data, dict) else {"result": data}

    async def get_order(self, order_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/orders/{order_id}")
        return data if isinstance(data, dict) else {"result": data}


def _option_price(option: dict[str, Any]) -> int | None:
    from app.addons.suppliers.shipping_quote import to_cents

    price = option.get("Price")
    if isinstance(price, dict):
        return to_cents(price.get("Price"))
    return to_cents(price)


def _response_items(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        for key in ("Items", "items"):
            val = response.get(key)
            if isinstance(val, list):
                return [i for i in val if isinstance(i, dict)]
    elif isinstance(response, list):
        return [i for i in response if isinstance(i, dict)]
    return []


def _item_method_maps(
    response: Any,
) -> list[dict[str, dict[str, Any]]]:
    """Per-item map of MethodType key → {id, name, cents}."""
    item_maps: list[dict[str, dict[str, Any]]] = []
    for item in _response_items(response):
        options = item.get("ShippingOptions")
        if not isinstance(options, list):
            continue
        imap: dict[str, dict[str, Any]] = {}
        for option in options:
            if not isinstance(option, dict):
                continue
            cents = _option_price(option)
            if cents is None:
                continue
            method = str(option.get("MethodType") or option.get("Name") or "").strip()
            if not method:
                continue
            key = method.lower()
            name = str(option.get("Name") or method).strip()
            existing = imap.get(key)
            if existing is None or cents < int(existing["cents"]):
                imap[key] = {"id": method, "name": name, "cents": cents}
        if imap:
            item_maps.append(imap)
    return item_maps


def _item_fallback(imap: dict[str, dict[str, Any]]) -> dict[str, Any]:
    preferred = [
        row
        for row in imap.values()
        if "standard" in str(row.get("id") or "").lower()
        or "standard" in str(row.get("name") or "").lower()
    ]
    pool = preferred or list(imap.values())
    return min(pool, key=lambda row: int(row["cents"]))


def parse_shipping_price_options(response: Any) -> list[dict[str, Any]]:
    """Aggregate Gooten per-item ShipTypes into cart-level checkout options."""
    item_maps = _item_method_maps(response)
    if not item_maps:
        return []

    common = set(item_maps[0].keys())
    for imap in item_maps[1:]:
        common &= set(imap.keys())
    keys = sorted(common) if common else sorted({k for imap in item_maps for k in imap})

    options: list[dict[str, Any]] = []
    for key in keys:
        total = 0
        name = key
        option_id = key
        found = False
        for imap in item_maps:
            if key in imap:
                row = imap[key]
                if not found:
                    name = str(row["name"])
                    option_id = str(row["id"])
                    found = True
            else:
                row = _item_fallback(imap)
            total += int(row["cents"])
        options.append({"id": option_id, "name": name, "cents": total})
    return options


def pick_shipping_prices_cents(response: Any) -> int | None:
    """Sum the chosen option per cart item; prefer Standard, else cheapest.

    Gooten returns shipping options per item (each item ships independently),
    so the total is the sum of the selected option for each item. Within an
    item, prefer a Standard method, else the cheapest. Returns ``None`` when
    nothing can be priced.
    """
    from app.addons.suppliers.shipping_quote import pick_shipping_option

    chosen = pick_shipping_option(
        parse_shipping_price_options(response),
        preferred_ids=("standard",),
    )
    return int(chosen["cents"]) if chosen else None
