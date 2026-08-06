"""Gooten addon routes."""

from typing import Any

from app.addons.suppliers.shared_routes import build_supplier_routers


def _parse_form(form: Any) -> tuple[dict[str, Any], bool]:
    return {
        "recipe_id": form.get("recipe_id", ""),
        "partner_billing_key": form.get("partner_billing_key", ""),
        "is_active": form.get("is_active") == "on",
        "default_ship_type": form.get("default_ship_type") or "Standard",
        "necktag_image_url": (form.get("necktag_image_url") or "").strip(),
    }, form.get("is_active") == "on"


admin_router, api_router, _env = build_supplier_routers(
    "gooten",
    template_name="config.html",
    page_title="Gooten",
    secret_keys=("partner_billing_key",),
    parse_config_form=_parse_form,
)
