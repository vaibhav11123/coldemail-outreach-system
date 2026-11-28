"""Commercial editions — shared licence + catalog format across Reader and Studio."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SKU(str, Enum):
    STANDARD_DATASET = "standard_dataset"
    PROTECTED_DATASET = "protected_dataset"
    ACADEMIC_STUDIO = "academic_studio"


@dataclass(frozen=True)
class ProductEdition:
    sku: SKU
    title: str
    list_price_usd: float
    includes_full_catalog: bool
    machine_readable_exports: bool  # unrestricted CSV/Excel/JSON
    encrypted_catalog: bool
    device_bound: bool
    includes_studio_features: bool
    max_devices: int
    protection_summary: str


_EDITIONS: dict[SKU, ProductEdition] = {
    SKU.STANDARD_DATASET: ProductEdition(
        sku=SKU.STANDARD_DATASET,
        title="Standard Dataset",
        list_price_usd=14.99,
        includes_full_catalog=True,
        machine_readable_exports=True,
        encrypted_catalog=False,
        device_bound=False,
        includes_studio_features=False,
        max_devices=0,
        protection_summary="Redistribution deterrence via forensic fingerprinting and signed delivery manifests — not copy prevention.",
    ),
    SKU.PROTECTED_DATASET: ProductEdition(
        sku=SKU.PROTECTED_DATASET,
        title="Protected Dataset",
        list_price_usd=24.99,
        includes_full_catalog=True,
        machine_readable_exports=False,
        encrypted_catalog=True,
        device_bound=True,
        includes_studio_features=False,
        max_devices=2,
        protection_summary="SQLCipher catalog + device-bound key delivery; controlled exports with fingerprints.",
    ),
    SKU.ACADEMIC_STUDIO: ProductEdition(
        sku=SKU.ACADEMIC_STUDIO,
        title="Academic Studio",
        list_price_usd=39.99,
        includes_full_catalog=True,
        machine_readable_exports=False,
        encrypted_catalog=True,
        device_bound=True,
        includes_studio_features=True,
        max_devices=2,
        protection_summary="Same encrypted catalog as Protected Dataset plus research matching, correspondence, and application management under a device-bound software licence.",
    ),
}


def editions() -> dict[SKU, ProductEdition]:
    return dict(_EDITIONS)


def get_edition(sku: SKU | str) -> ProductEdition:
    if isinstance(sku, str):
        sku = SKU(sku)
    return _EDITIONS[sku]
