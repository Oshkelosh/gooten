# Gooten (`gooten`)

Print-on-demand via Gooten API.

## Overview

| | |
|---|---|
| Addon ID | `gooten` |
| Category | supplier |
| Version | 1.0.0 |
| Category guide | [../README.md](../README.md) |
| Fulfillment key | `gooten` |

Multiple suppliers can be enabled at the same time. Fulfillment runs when an order becomes **paid**.

## Enable and configure

1. Install this package under `app/addons/suppliers/gooten/`
2. Open **Admin → Suppliers → Gooten** at `/admin/suppliers/gooten`
3. Enter API credentials and enable the addon

## Configuration schema

| Field | Type | Description |
|-------|------|-------------|
| `recipe_id` | string | Gooten Recipe ID |
| `partner_billing_key` | secret | Partner billing key |
| `is_active` | bool | Whether the addon is active |
| `default_ship_type` | string | Default shipping type (default Standard) |

## Routes

### Public API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/suppliers/gooten/products` | List catalog products |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/suppliers/gooten` | Config form |
| POST | `/admin/suppliers/gooten/save` | Save config |
| POST | `/admin/suppliers/gooten/sync` | Trigger catalog sync |

## Core integration

- **Variant supplier fields:** paid-order fulfillment reads Gooten SKUs from each **ProductVariant** row
- **Fulfillment:** creates Gooten order using recipe ID and billing key
- **Grouping:** line items grouped by fulfillment key `gooten`

## Variant supplier fields

| Field | Description |
|-------|-------------|
| `supplier_addon_id` | `gooten` |
| `supplier_product_id` | Gooten blueprint SKU |

## Catalog sync

Supported. Admin sync at `/admin/suppliers/gooten` or `POST /api/v1/admin/suppliers/gooten/sync`.

**Import model:** grouped products; one variant per blueprint/option combination.

| Key | Format |
|-----|--------|
| Variant dedup key | `gooten:{sku}` |

**Prerequisites:**

- Catalog sync expands blueprint/option combinations.

## Known limitations

Catalog import sets prices to **0** — set sell prices in Oshkelosh after import.

## Provider setup

- Obtain Recipe ID and Partner billing key from Gooten.

## Package layout

```
gooten/
├── README.md
├── addon.py
├── catalog.py
├── client.py
├── routes.py
└── templates/
```

## See also

- [Supplier addon development](../README.md)
- [Oshkelosh addon guide](../../README.md)
