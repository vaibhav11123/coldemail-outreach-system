"""Canonical licensing policy constants (customer-facing + engineering).

Perpetual usage ≠ unlimited updates, indefinite support, or third-party AI credits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LicencePolicy:
    product: str
    sku: str
    licence_included_in_price: bool
    purchase_type: str
    usage_duration: str
    authorized_users: int
    authorized_devices: str  # "unrestricted" or number as string
    offline_usage: str
    personal_backups: bool
    data_analysis: bool
    personal_research: bool
    professional_use_by_licensee: bool
    unauthorized_redistribution: str
    unauthorized_resale: str
    sublicensing: str
    licence_sharing: str
    customer_fingerprinting: bool
    signed_licence: bool
    device_bound_activation: bool
    licence_recovery: bool
    device_replacement: bool
    additional_activation_charge: bool
    updates_included: str
    support_included: str
    third_party_ai: str
    refund_revocation: str


DATASET_POLICY = LicencePolicy(
    product="Global Research Dataset",
    sku="standard_dataset",
    licence_included_in_price=True,
    purchase_type="one-time",
    usage_duration="perpetual for purchased version",
    authorized_users=1,
    authorized_devices="unrestricted for licensed user",
    offline_usage="full",
    personal_backups=True,
    data_analysis=True,
    personal_research=True,
    professional_use_by_licensee=True,
    unauthorized_redistribution="prohibited",
    unauthorized_resale="prohibited",
    sublicensing="prohibited",
    licence_sharing="prohibited",
    customer_fingerprinting=True,
    signed_licence=True,
    device_bound_activation=False,
    licence_recovery=True,
    device_replacement=False,
    additional_activation_charge=False,
    updates_included=(
        "Dataset corrections for the purchased version may be offered; "
        "duration of included updates is a commercial policy set before launch "
        "(not unlimited by default)."
    ),
    support_included=(
        "Support window for the purchased version is documented at launch; "
        "not indefinite by default."
    ),
    third_party_ai="Not applicable to the raw dataset product.",
    refund_revocation=(
        "Refunds after download are contractual for already-downloaded files; "
        "raw files already on the customer's disk cannot be remotely erased."
    ),
)

STUDIO_POLICY = LicencePolicy(
    product="Academic Studio",
    sku="academic_studio",
    licence_included_in_price=True,
    purchase_type="one-time",
    usage_duration="perpetual for purchased version",
    authorized_users=1,
    authorized_devices="2",
    offline_usage="supported under signed bounded offline entitlement",
    personal_backups=True,
    data_analysis=True,
    personal_research=True,
    professional_use_by_licensee=True,
    unauthorized_redistribution="prohibited",
    unauthorized_resale="prohibited",
    sublicensing="prohibited",
    licence_sharing="prohibited",
    customer_fingerprinting=True,
    signed_licence=True,
    device_bound_activation=True,
    licence_recovery=True,
    device_replacement=True,
    additional_activation_charge=False,
    updates_included=(
        "Software updates for the purchased major version may be included for a "
        "documented period; perpetual licence does not mean unlimited future versions."
    ),
    support_included=(
        "Customer support window documented at launch; not indefinite by default."
    ),
    third_party_ai=(
        "Customer connects their own AI providers (BYOAI). Purchase price does not "
        "include third-party AI API credits."
    ),
    refund_revocation=(
        "On refund/chargeback, entitlement is revoked and fails at next validation; "
        "raw dataset exports already downloaded cannot be remotely erased."
    ),
)


def policies() -> dict[str, dict]:
    return {
        "standard_dataset": asdict(DATASET_POLICY),
        "academic_studio": asdict(STUDIO_POLICY),
    }
