# Gooten (`gooten`) — AGENTS

## Role

Print-on-demand via Gooten API. Addon ID: `gooten`. Fulfillment key: `gooten`.

## File map

- `README.md`
- `__init__.py`
- `addon.py`
- `catalog.py`
- `client.py`
- `oshkelosh-addon.json`
- `routes.py`
- `templates/`
- `tests/`

## Package specifics

**Category ceiling:** Many suppliers may be active; fulfillment runs on order `paid`; supplier IDs on variants; sync keys in package README.
**Config fields:** `recipe_id` (string), `partner_billing_key` (secret), `is_active` (bool), `default_ship_type` (string)
- Variant dedup key: `gooten:{sku}`

## Invariants

- Implement the matching category ABC; do not patch host `app/services/*.py` with provider branches
- Credentials and enable flags live in `addon_configs` (admin UI), not host `.env`
- Use `app/addons/log.py` for structured logging
- Admin mutating forms need CSRF; use `render_addon_admin_page` correctly (do not pass `flash` via `**_common_ctx`)
- Webhook parse paths must not write the DB — core owns idempotency
- Nested `.git` (if present): this package is its own repo; the host gitignores this directory

## Prefer / Avoid

- Prefer: extend this package and the category ABC; keep provider API clients here
- Avoid: editing host `app/services/` for this provider; putting secrets in host `.env`

## See also

- [README.md](README.md) — package how-to
- [../README.md](../README.md) — category guide
- [../../AGENTS.md](../../AGENTS.md) — host addon boundary
- [../../README.md](../../README.md) — plugin development
- [../../../../AGENTS.md](../../../../AGENTS.md), [../../../../DESIGN.md](../../../../DESIGN.md)
