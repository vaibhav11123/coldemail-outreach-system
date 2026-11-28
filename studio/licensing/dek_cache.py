"""OS-backed DEK cache after successful entitlement unwrap (minimize re-prompting).

Plaintext DEK still exists briefly in process memory while the catalog is open —
this does not claim otherwise. Cache entries are scoped to licence + device.
"""

from __future__ import annotations

from studio.licensing.crypto import b64d, b64e
from studio.secrets_store import delete_secret, get_secret, set_secret


def _key(license_id: str, device_id: str) -> str:
    return f"licensing.dek.{license_id}.{device_id}"


def cache_dek(license_id: str, device_id: str, dek: bytes) -> None:
    if len(dek) != 32:
        raise ValueError("DEK must be 32 bytes")
    set_secret(_key(license_id, device_id), b64e(dek))


def load_cached_dek(license_id: str, device_id: str) -> bytes | None:
    raw = get_secret(_key(license_id, device_id))
    if not raw:
        return None
    dek = b64d(raw)
    if len(dek) != 32:
        return None
    return dek


def clear_cached_dek(license_id: str, device_id: str) -> None:
    delete_secret(_key(license_id, device_id))


def clear_all_cached_deks_for_license(license_id: str, device_ids: list[str] | None = None) -> int:
    """Remove cached plaintext DEKs for a licence (call on revoke).

    Clears known device ids plus any local secrets.json entries with the
    licensing.dek.<license_id>. prefix. OS keyring entries without local
    mirrors may remain until overwritten — operator should wipe keyring on
    refund when using non-local secret backends.
    """
    from studio.secrets_store import delete_secrets_with_prefix

    removed = 0
    for device_id in device_ids or []:
        clear_cached_dek(license_id, device_id)
        removed += 1
    removed += delete_secrets_with_prefix(f"licensing.dek.{license_id}.")
    return removed
