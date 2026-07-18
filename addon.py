"""Gooten print-on-demand supplier integration."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr

from app.addons.suppliers.base import SupplierAddon
from app.addons.suppliers.gooten.catalog import normalize_gooten_catalog_products
from app.addons.suppliers.gooten.client import (
    GootenAPIError,
    GootenClient,
    parse_shipping_price_options,
)
from schemas.supplier import SupplierCatalogProduct
from app.addons.log import exception, info, warning
from app.addons.config_serialization import dump_addon_config


class GootenConfig(BaseModel):
    recipe_id: str = Field(default=..., min_length=1, description="Gooten Recipe ID")
    partner_billing_key: SecretStr = Field(default=..., description="Partner billing key")
    is_active: bool = Field(default=False)
    default_ship_type: str = Field(default="Standard")

    @classmethod
    def config_model(cls):
        return cls


def _map_address(address: Dict[str, Any]) -> Dict[str, Any]:
    from app.addons.suppliers.address import canonical_address

    addr = canonical_address(address)
    payload = {
        "Line1": addr["line1"],
        "City": addr["city"],
        "PostalCode": addr["zip"],
        "CountryCode": addr["country_code"],
    }
    if addr["state"]:
        payload["State"] = addr["state"]
    if addr["line2"]:
        payload["Line2"] = addr["line2"]
    return payload


class GootenAddon(SupplierAddon):
    addon_id: str = "gooten"
    addon_name: str = "Gooten"
    addon_description: str = "Print-on-demand via Gooten API."
    addon_category: str = "supplier"
    version: str = "1.0.0"

    _config: Dict[str, Any] | None = None
    _client: GootenClient | None = None

    @classmethod
    def config_schema(cls):
        return GootenConfig

    async def initialize(self, config: dict) -> None:
        validated = GootenConfig(**config)
        self._config = dump_addon_config(validated)
        self._client = GootenClient(
            validated.recipe_id,
            validated.partner_billing_key.get_secret_value(),
        )
        self.is_enabled = validated.is_active
        info("Gooten", "Initialized recipe_id={}", validated.recipe_id)

    async def validate_config(self, config: dict) -> None:
        from app.core.exceptions import ValidationError

        validated = GootenConfig(**config)
        billing_key = validated.partner_billing_key.get_secret_value()
        if not billing_key:
            return
        client = GootenClient(validated.recipe_id, billing_key)
        try:
            await client.list_blueprints()
        except GootenAPIError as exc:
            if exc.status_code == 401:
                raise ValidationError(
                    message="Invalid partner billing key — check your credentials"
                ) from exc
            if exc.status_code == 403:
                raise ValidationError(
                    message="Billing key is valid but missing required permissions: catalog:read"
                ) from exc
            raise ValidationError(message=f"Gooten API error: {exc}") from exc

    async def shutdown(self) -> None:
        self._client = None
        self._config = None
        self.is_enabled = False

    def _require_client(self) -> GootenClient:
        if self._client is None:
            raise GootenAPIError("Gooten addon is not initialized")
        return self._client

    async def list_products(self, **kwargs: Any) -> List[Dict[str, Any]]:
        data = await self._require_client().list_blueprints()
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ("Blueprints", "blueprints", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    return [r for r in val if isinstance(r, dict)]
        return []

    async def fetch_catalog_for_import(self, **kwargs: Any) -> List[SupplierCatalogProduct]:
        data = await self._require_client().list_blueprints()
        return normalize_gooten_catalog_products(data)

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        for row in await self.list_products():
            sku = str(row.get("SKU") or row.get("sku") or row.get("Id") or "")
            if sku == product_id:
                return row
        return {"error": f"Gooten SKU '{product_id}' not found"}

    def supports_shipping_quotes(self) -> bool:
        return True

    async def quote_shipping(
        self,
        items: List[Dict[str, Any]],
        shipping_address: Dict[str, Any],
        *,
        currency: str | None = None,
    ) -> int | None:
        """Live Gooten rates; prefer Standard, else cheapest per item. None → Site Settings."""
        details = await self.quote_shipping_details(
            items, shipping_address, currency=currency
        )
        if details is None:
            return None
        return int(details["cents"])

    async def quote_shipping_details(
        self,
        items: List[Dict[str, Any]],
        shipping_address: Dict[str, Any],
        *,
        selected_id: str | None = None,
        currency: str | None = None,
    ) -> Dict[str, Any] | None:
        """Live Gooten ShipTypes (aggregated across items); selected_id overrides default."""
        from app.services.countries import normalize_country_code
        from app.addons.suppliers.shipping_quote import pick_shipping_option

        client = self._require_client()
        try:
            country_raw = (shipping_address or {}).get("country") or (
                shipping_address or {}
            ).get("country_code")
            country_code = normalize_country_code(str(country_raw) if country_raw else None)
            if not country_code:
                return None
            cart_items = []
            for item in items:
                sku = str(item.get("supplier_product_id") or "").strip()
                if not sku:
                    continue
                cart_items.append(
                    {"SKU": sku, "Quantity": int(item.get("quantity") or 1)}
                )
            if not cart_items:
                return None
            data = await client.get_shipping_prices(
                cart_items,
                country_code,
                currency_code=str(currency or "USD").upper(),
            )
            options = parse_shipping_price_options(data)
            chosen = pick_shipping_option(
                options,
                selected_id=selected_id,
                preferred_ids=("standard",),
            )
            if chosen is None:
                return None
            return {
                "cents": int(chosen["cents"]),
                "selected_id": str(chosen["id"]),
                "options": options,
            }
        except GootenAPIError as exc:
            warning("Gooten", "quote_shipping error: {}", exc)
            return None
        except Exception:
            exception("Gooten", "quote_shipping unexpected error")
            return None

    async def create_order(
        self,
        items: List[Dict[str, Any]],
        shipping_address: Dict[str, Any],
        *,
        external_id: str | None = None,
        supplier_ref: str | None = None,
        shipping_method: str | None = None,
        currency: str | None = None,
    ) -> Dict[str, Any]:
        del supplier_ref
        client = self._require_client()
        cfg = self._config or {}
        try:
            ship_type = (
                (shipping_method or "").strip()
                or str(cfg.get("default_ship_type") or "Standard")
            )
            order_items = []
            for item in items:
                sku = str(item.get("supplier_product_id") or "").strip()
                if not sku:
                    continue
                order_items.append(
                    {
                        "SKU": sku,
                        "Quantity": int(item.get("quantity") or 1),
                        "ShipType": ship_type,
                    }
                )
            if not order_items:
                return {"success": False, "error": "No valid Gooten line items"}

            payload: Dict[str, Any] = {
                "ShipToAddress": _map_address(shipping_address),
                "Items": order_items,
            }
            if currency:
                payload["CurrencyCode"] = str(currency).upper()
            if external_id:
                payload["OrderReferenceId"] = external_id

            data = await client.create_order(payload)
            order_id = str(data.get("OrderId") or data.get("id") or "")
            return {
                "success": True,
                "order_id": order_id,
                "status": data.get("Status", "submitted"),
                "gooten_order_id": order_id,
            }
        except GootenAPIError as exc:
            warning("Gooten", "create_order error: {}", exc)
            return {"success": False, "error": str(exc)}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        try:
            data = await self._require_client().get_order(order_id)
            return {"order_id": order_id, "status": data.get("Status", "unknown")}
        except GootenAPIError as exc:
            return {"order_id": order_id, "status": "error", "detail": str(exc)}

    async def sync_inventory(self) -> None:
        products = await self.list_products()
        info("Gooten", "Catalog has {} blueprints", len(products))

    def get_routers(self) -> List[APIRouter]:
        from app.addons.suppliers.gooten.routes import api_router

        return [api_router]

    def get_admin_routes(self) -> List[APIRouter]:
        from app.addons.suppliers.gooten.routes import admin_router

        return [admin_router]

    def get_admin_templates(self) -> str:
        from pathlib import Path

        return str(Path(__file__).resolve().parent / "templates")

    def get_admin_static(self) -> str:
        from pathlib import Path

        return str(Path(__file__).resolve().parent / "static")
