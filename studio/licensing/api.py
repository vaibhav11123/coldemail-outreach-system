"""FastAPI licensing API: purchase webhook, activation, revoke, device replace."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from studio.licensing.activation import (
    ActivationRequest,
    activate_device,
    build_activation_request,
)
from studio.licensing.crypto import b64d, b64e
from studio.licensing.device import load_or_create_device_identity
from studio.licensing.products import editions, get_edition
from studio.licensing.service import issuer_keys, license_store, webhook_secret
from studio.paths import app_data_dir


class PurchaseWebhook(BaseModel):
    customer_id: str = Field(min_length=1, max_length=128)
    customer_email: str = Field(min_length=3, max_length=320)
    sku: str
    external_payment_id: str | None = None


class ActivateBody(BaseModel):
    license_id: str
    device_id: str
    device_fingerprint: str
    ed25519_public: str
    x25519_public: str
    challenge: str
    challenge_signature: str
    nonce: str
    requested_at: int
    replace_device_id: str | None = None
    aslic_basename: str = "CustomerLicense.aslic"


class LocalActivateBody(BaseModel):
    """Convenience for the installed app: build challenge on-device and activate."""

    license_id: str
    replace_device_id: str | None = None
    package_dir: str | None = None


def build_licensing_router() -> APIRouter:
    router = APIRouter(prefix="/api/licensing", tags=["licensing"])

    @router.get("/editions")
    def list_editions() -> dict[str, Any]:
        out = {}
        for sku, ed in editions().items():
            out[sku.value] = {
                "title": ed.title,
                "list_price_usd": ed.list_price_usd,
                "licence_included": ed.licence_included,
                "licence_duration": ed.licence_duration,
                "includes_full_catalog": ed.includes_full_catalog,
                "machine_readable_exports": ed.machine_readable_exports,
                "encrypted_catalog": ed.encrypted_catalog,
                "device_bound": ed.device_bound,
                "includes_studio_features": ed.includes_studio_features,
                "max_devices": ed.max_devices,
                "protection_summary": ed.protection_summary,
                "sold_separately": ed.sold_separately,
            }
        return {"editions": out}

    @router.get("/issuer-public")
    def issuer_public() -> dict[str, str]:
        return {"issuer_public": issuer_keys().export_public_hex(), "alg": "ed25519"}

    @router.get("/device")
    def device_public() -> dict[str, Any]:
        return load_or_create_device_identity().public_record()

    @router.post("/webhook/payment")
    def payment_webhook(
        body: PurchaseWebhook,
        x_studio_webhook_secret: str | None = Header(default=None),
    ) -> dict[str, Any]:
        expected = webhook_secret()
        if expected:
            if not x_studio_webhook_secret or not secrets.compare_digest(
                x_studio_webhook_secret, expected
            ):
                raise HTTPException(status_code=401, detail="Invalid webhook secret")
        try:
            get_edition(body.sku)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Unknown SKU: {body.sku}") from exc
        store = license_store()
        rec = store.register_purchase(
            customer_id=body.customer_id,
            customer_email=body.customer_email,
            sku=body.sku,
        )
        return {
            "ok": True,
            "license_id": rec.license_id,
            "customer_id": rec.customer_id,
            "sku": rec.sku,
            "fingerprint_salt": rec.fingerprint_salt,
            "external_payment_id": body.external_payment_id,
            "notice": "DEK retained server-side only; never returned on this endpoint.",
        }

    @router.post("/activate")
    def activate(body: ActivateBody) -> dict[str, Any]:
        store = license_store()
        try:
            req = ActivationRequest(
                license_id=body.license_id,
                device_id=body.device_id,
                device_fingerprint=body.device_fingerprint,
                ed25519_public=b64d(body.ed25519_public),
                x25519_public=b64d(body.x25519_public),
                challenge=b64d(body.challenge),
                challenge_signature=b64d(body.challenge_signature),
                nonce=body.nonce,
                requested_at=body.requested_at,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Malformed activation request") from exc
        out_dir = app_data_dir() / "activations" / body.license_id
        out_dir.mkdir(parents=True, exist_ok=True)
        aslic_path = out_dir / body.aslic_basename
        try:
            ent = activate_device(
                store,
                req,
                aslic_path=aslic_path,
                replace_device_id=body.replace_device_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown licence") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {
            "ok": True,
            "license_id": ent.license_id,
            "sku": ent.sku,
            "expires_at": ent.expires_at,
            "aslic_path": str(aslic_path),
            "aslic": aslic_path.read_text(encoding="utf-8"),
        }

    @router.post("/activate-local")
    def activate_local(body: LocalActivateBody) -> dict[str, Any]:
        device = load_or_create_device_identity()
        req = build_activation_request(device, body.license_id)
        store = license_store()
        if body.package_dir:
            aslic_path = Path(body.package_dir) / "CustomerLicense.aslic"
        else:
            aslic_path = (
                app_data_dir() / "activations" / body.license_id / "CustomerLicense.aslic"
            )
        aslic_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            ent = activate_device(
                store,
                req,
                aslic_path=aslic_path,
                replace_device_id=body.replace_device_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown licence") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {
            "ok": True,
            "license_id": ent.license_id,
            "device_id": device.device_id,
            "expires_at": ent.expires_at,
            "aslic_path": str(aslic_path),
        }

    @router.post("/revoke/{license_id}")
    def revoke(
        license_id: str,
        x_studio_webhook_secret: str | None = Header(default=None),
    ) -> dict[str, Any]:
        expected = webhook_secret()
        if expected:
            if not x_studio_webhook_secret or not secrets.compare_digest(
                x_studio_webhook_secret, expected
            ):
                raise HTTPException(status_code=401, detail="Invalid webhook secret")
        store = license_store()
        try:
            store.revoke(license_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown licence") from exc
        return {"ok": True, "license_id": license_id, "revoked": True}

    @router.get("/status/{license_id}")
    def status(license_id: str) -> dict[str, Any]:
        rec = license_store().get(license_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Unknown licence")
        edition = get_edition(rec.sku)
        return {
            "license_id": rec.license_id,
            "customer_id": rec.customer_id,
            "sku": rec.sku,
            "revoked": rec.revoked,
            "device_count": len(rec.activated_devices),
            "max_devices": edition.max_devices,
            "devices": [
                {"device_id": did, "fingerprint": meta.get("fingerprint"), "activated_at": meta.get("activated_at")}
                for did, meta in rec.activated_devices.items()
            ],
        }

    return router
