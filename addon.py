"""Gooten print-on-demand supplier integration."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr

from app.addons.suppliers.base import SupplierAddon
from app.addons.suppliers.gooten.catalog import normalize_gooten_catalog_products
from app.addons.suppliers.gooten.client import GootenAPIError, GootenClient
from schemas.supplier import SupplierCatalogProduct
from app.addons.log import info, warning
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
    payload = {
        "Line1": address.get("line1", ""),
        "City": address.get("city", ""),
        "PostalCode": address.get("zip", ""),
        "CountryCode": address.get("country", ""),
    }
    if address.get("state"):
        payload["State"] = address["state"]
    if address.get("line2"):
        payload["Line2"] = address["line2"]
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

    async def create_order(
        self,
        items: List[Dict[str, Any]],
        shipping_address: Dict[str, Any],
        *,
        external_id: str | None = None,
        supplier_ref: str | None = None,
    ) -> Dict[str, Any]:
        del supplier_ref
        client = self._require_client()
        cfg = self._config or {}
        try:
            order_items = []
            for item in items:
                sku = str(item.get("supplier_product_id") or "").strip()
                if not sku:
                    continue
                order_items.append(
                    {
                        "SKU": sku,
                        "Quantity": int(item.get("quantity") or 1),
                        "ShipType": str(cfg.get("default_ship_type") or "Standard"),
                    }
                )
            if not order_items:
                return {"success": False, "error": "No valid Gooten line items"}

            payload: Dict[str, Any] = {
                "ShipToAddress": _map_address(shipping_address),
                "Items": order_items,
            }
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
