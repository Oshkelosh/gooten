"""Gooten catalog normalization."""

from __future__ import annotations

from typing import Any

from schemas.supplier import (
    POD_INVENTORY_PLACEHOLDER,
    SupplierCatalogItem,
    SupplierCatalogProduct,
    SupplierCatalogVariant,
)


def normalize_gooten_catalog(raw: Any) -> list[SupplierCatalogItem]:
    items: list[SupplierCatalogItem] = []
    blueprints: list[dict[str, Any]] = []
    if isinstance(raw, list):
        blueprints = [b for b in raw if isinstance(b, dict)]
    elif isinstance(raw, dict):
        for key in ("Blueprints", "blueprints", "data", "items"):
            val = raw.get(key)
            if isinstance(val, list):
                blueprints = [b for b in val if isinstance(b, dict)]
                break

    for blueprint in blueprints:
        name = str(blueprint.get("Name") or blueprint.get("name") or "Gooten product")
        options = blueprint.get("Options") or blueprint.get("options") or []
        if isinstance(options, list) and options:
            for option in options:
                if not isinstance(option, dict):
                    continue
                sku = str(option.get("SKU") or option.get("sku") or "").strip()
                if not sku:
                    continue
                option_name = str(option.get("Name") or option.get("name") or name)
                items.append(
                    SupplierCatalogItem(
                        external_key=f"gooten:{sku}",
                        name=f"{name} — {option_name}",
                        description=blueprint.get("Description") or blueprint.get("description"),
                        price_cents=0,
                        sku=sku,
                        image_url=option.get("ImageUrl") or blueprint.get("ImageUrl"),
                        supplier_value="gooten",
                        supplier_product_id=sku,
                        supplier_variant_id="",
                        inventory_quantity=POD_INVENTORY_PLACEHOLDER,
                    )
                )
            continue
        sku = str(blueprint.get("SKU") or blueprint.get("sku") or blueprint.get("Id") or "").strip()
        if not sku:
            continue
        items.append(
            SupplierCatalogItem(
                external_key=f"gooten:{sku}",
                name=name,
                description=blueprint.get("Description") or blueprint.get("description"),
                price_cents=0,
                sku=sku,
                image_url=blueprint.get("ImageUrl") or blueprint.get("imageUrl"),
                supplier_value="gooten",
                supplier_product_id=sku,
                supplier_variant_id="",
                inventory_quantity=POD_INVENTORY_PLACEHOLDER,
            )
        )
    return items


def normalize_gooten_catalog_products(raw: Any) -> list[SupplierCatalogProduct]:
    """Map Gooten blueprints to grouped catalog products."""
    products: list[SupplierCatalogProduct] = []
    blueprints: list[dict[str, Any]] = []
    if isinstance(raw, list):
        blueprints = [b for b in raw if isinstance(b, dict)]
    elif isinstance(raw, dict):
        for key in ("Blueprints", "blueprints", "data", "items"):
            val = raw.get(key)
            if isinstance(val, list):
                blueprints = [b for b in val if isinstance(b, dict)]
                break

    for blueprint in blueprints:
        blueprint_id = str(
            blueprint.get("Id") or blueprint.get("id") or blueprint.get("BlueprintId") or ""
        ).strip()
        name = str(blueprint.get("Name") or blueprint.get("name") or "Gooten product")
        description = blueprint.get("Description") or blueprint.get("description")
        blueprint_image = blueprint.get("ImageUrl") or blueprint.get("imageUrl")
        product_images = [str(blueprint_image).strip()] if blueprint_image else []
        options = blueprint.get("Options") or blueprint.get("options") or []
        variants: list[SupplierCatalogVariant] = []

        if isinstance(options, list) and options:
            if not blueprint_id:
                blueprint_id = str(blueprint.get("SKU") or blueprint.get("sku") or name).strip()
            for option in options:
                if not isinstance(option, dict):
                    continue
                sku = str(option.get("SKU") or option.get("sku") or "").strip()
                if not sku:
                    continue
                option_name = str(option.get("Name") or option.get("name") or name)
                option_image = option.get("ImageUrl") or blueprint_image
                image_urls = [str(option_image).strip()] if option_image else list(product_images)
                variants.append(
                    SupplierCatalogVariant(
                        external_key=f"gooten:{sku}",
                        title=option_name,
                        attributes={},
                        price_cents=0,
                        sku=sku,
                        inventory_quantity=POD_INVENTORY_PLACEHOLDER,
                        supplier_product_id=sku,
                        supplier_variant_id="",
                        image_urls=image_urls,
                    )
                )
        else:
            sku = str(blueprint.get("SKU") or blueprint.get("sku") or blueprint_id or "").strip()
            if not sku:
                continue
            blueprint_id = blueprint_id or sku
            variants.append(
                SupplierCatalogVariant(
                    external_key=f"gooten:{sku}",
                    title=name,
                    attributes={},
                    price_cents=0,
                    sku=sku,
                    inventory_quantity=POD_INVENTORY_PLACEHOLDER,
                    supplier_product_id=sku,
                    supplier_variant_id="",
                    image_urls=product_images,
                )
            )

        if not variants or not blueprint_id:
            continue
        products.append(
            SupplierCatalogProduct(
                external_product_key=f"gooten:{blueprint_id}",
                name=name,
                description=description if isinstance(description, str) else None,
                product_type=None,
                image_urls=product_images,
                image_alt_texts=[],
                variants=variants,
                supplier_value="gooten",
            )
        )
    return products
