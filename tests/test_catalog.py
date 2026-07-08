"""Unit tests for Gooten catalog normalization."""

from app.addons.suppliers.gooten.catalog import normalize_gooten_catalog


def test_gooten_normalizes_sku_from_options():
    items = normalize_gooten_catalog(
        [{"Name": "Mug", "Options": [{"SKU": "MUG-11", "Name": "11oz"}]}]
    )
    assert len(items) == 1
    assert items[0].supplier_product_id == "MUG-11"
