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

    async def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {**payload, "PartnerBillingKey": self._billing_key}
        data = await self._request("POST", "/api/orders", json=body)
        return data if isinstance(data, dict) else {"result": data}

    async def get_order(self, order_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/orders/{order_id}")
        return data if isinstance(data, dict) else {"result": data}
