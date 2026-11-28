"""Commercial editions — two customer products; licence included in the purchase price.

Global Research Dataset and Academic Studio are the only sold SKUs.
Encrypted catalog + device binding are Studio capabilities, not a separate paid tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SKU(str, Enum):
    STANDARD_DATASET = "standard_dataset"
    ACADEMIC_STUDIO = "academic_studio"
    # Internal alias for Studio encrypted packaging (not sold separately).
    PROTECTED_DATASET = "protected_dataset"


@dataclass(frozen=True)
class ProductEdition:
    sku: SKU
    title: str
    list_price_usd: float
    sold_separately: bool
    includes_full_catalog: bool
    machine_readable_exports: bool  # unrestricted CSV/Excel/JSON/SQLite
    encrypted_catalog: bool
    device_bound: bool
    includes_studio_features: bool
    max_devices: int
    licence_included: bool
    licence_duration: str
    protection_summary: str


_EDITIONS: dict[SKU, ProductEdition] = {
    SKU.STANDARD_DATASET: ProductEdition(
        sku=SKU.STANDARD_DATASET,
        title="Global Research Dataset",
        list_price_usd=14.99,
        sold_separately=True,
        includes_full_catalog=True,
        machine_readable_exports=True,
        encrypted_catalog=False,
        device_bound=False,
        includes_studio_features=False,
        max_devices=0,
        licence_included=True,
        licence_duration="perpetual",
        protection_summary=(
            "Individual perpetual licence included in purchase. Personalized forensic "
            "fingerprints and signed delivery manifests — redistribution deterrence, "
            "not copy prevention. No separate activation fee."
        ),
    ),
    SKU.ACADEMIC_STUDIO: ProductEdition(
        sku=SKU.ACADEMIC_STUDIO,
        title="Academic Studio",
        list_price_usd=39.99,
        sold_separately=True,
        includes_full_catalog=True,
        machine_readable_exports=True,  # full dataset access inside Studio + exports
        encrypted_catalog=True,
        device_bound=True,
        includes_studio_features=True,
        max_devices=2,
        licence_included=True,
        licence_duration="perpetual",
        protection_summary=(
            "Individual perpetual software licence included in purchase. Two authorized "
            "devices, SQLCipher catalog, device-bound key delivery, replacement and "
            "revocation. No separate activation fee."
        ),
    ),
    # Kept so existing packages/tests that reference protected_dataset still resolve.
    # Not listed in customer-facing editions().
    SKU.PROTECTED_DATASET: ProductEdition(
        sku=SKU.PROTECTED_DATASET,
        title="Academic Studio (encrypted catalog packaging)",
        list_price_usd=39.99,
        sold_separately=False,
        includes_full_catalog=True,
        machine_readable_exports=False,
        encrypted_catalog=True,
        device_bound=True,
        includes_studio_features=True,
        max_devices=2,
        licence_included=True,
        licence_duration="perpetual",
        protection_summary="Internal packaging alias for Academic Studio — not a separate SKU.",
    ),
}


def editions() -> dict[SKU, ProductEdition]:
    """Customer-facing sold editions only."""
    return {k: v for k, v in _EDITIONS.items() if v.sold_separately}


def all_editions() -> dict[SKU, ProductEdition]:
    return dict(_EDITIONS)


def get_edition(sku: SKU | str) -> ProductEdition:
    if isinstance(sku, str):
        sku = SKU(sku)
    return _EDITIONS[sku]
