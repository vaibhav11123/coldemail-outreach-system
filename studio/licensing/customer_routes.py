"""Customer-facing licence activation and recovery UI (Option A offline-capable)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.requests import Request

from studio.licensing.activation import activate_device, build_activation_request
from studio.licensing.device import load_or_create_device_identity
from studio.licensing.service import license_store
from studio.paths import app_data_dir


DELIVERY_SLA = (
    "After payment clears, personalized files are prepared manually and sent within "
    "24 hours on business days. Most deliveries are faster."
)


def build_customer_licensing_router(
    *,
    render: Callable[..., Any],
    require_token: Callable[[str | None], None],
    support_email: str,
    refund_copy: str,
) -> APIRouter:
    router = APIRouter(tags=["customer-licensing"])

    def _page(
        request: Request,
        *,
        error: str | None = None,
        status: str | None = None,
        email: str = "",
        license_id: str = "",
        package_dir: str = "",
    ):
        device = load_or_create_device_identity()
        return render(
            request,
            "activate.html",
            nav="activate",
            device=device.public_record(),
            error=error,
            status=status,
            email=email,
            license_id=license_id,
            package_dir=package_dir,
            support=support_email,
            refund=refund_copy,
            delivery_sla=DELIVERY_SLA,
        )

    @router.get("/activate", response_class=HTMLResponse)
    async def activate_get(request: Request):
        return _page(request)

    @router.get("/activate/help", response_class=HTMLResponse)
    async def activate_help(request: Request):
        return render(
            request,
            "activate_help.html",
            nav="help",
            support=support_email,
        )

    @router.post("/activate")
    async def activate_post(
        request: Request,
        page_token: str = Form(...),
        action: str = Form(...),
        email: str = Form(""),
        license_id: str = Form(""),
        package_dir: str = Form(""),
        replace_device_id: str = Form(""),
        aslic_file: UploadFile | None = File(None),
    ):
        require_token(page_token)
        license_id = (license_id or "").strip()
        email = (email or "").strip()
        package_dir = (package_dir or "").strip()
        replace = (replace_device_id or "").strip() or None

        if action == "download_request":
            if not license_id:
                return _page(request, error="Licence key is required.", email=email)
            device = load_or_create_device_identity()
            req = build_activation_request(device, license_id)
            payload = {
                **req.to_dict(),
                "customer_email": email or None,
                "format": "academic-studio-activation-request",
                "version": 1,
                "instructions": (
                    "Email this file to the seller with your payment reference. "
                    "They will return CustomerLicense.aslic for this device."
                ),
            }
            body = json.dumps(payload, indent=2) + "\n"
            return Response(
                body,
                media_type="application/json",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="activation_request_{license_id}.json"'
                    )
                },
            )

        if action == "install_aslic":
            if not package_dir or aslic_file is None:
                return _page(
                    request,
                    error="Package folder and .aslic file are required.",
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            dest_dir = Path(package_dir).expanduser()
            if not dest_dir.is_dir():
                return _page(
                    request,
                    error="Package folder does not exist.",
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            raw = await aslic_file.read()
            try:
                text = raw.decode("utf-8")
                json.loads(text)  # basic sanity
            except Exception:
                return _page(
                    request,
                    error="Uploaded file is not a valid licence document.",
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            aslic_path = dest_dir / "CustomerLicense.aslic"
            aslic_path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
            # Also keep a copy under app data for recovery
            backup = app_data_dir() / "activations" / (license_id or "unknown") / "CustomerLicense.aslic"
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(aslic_path.read_text(encoding="utf-8"), encoding="utf-8")
            marker = app_data_dir() / "protected_package_path.txt"
            marker.write_text(str(dest_dir.resolve()), encoding="utf-8")
            return RedirectResponse(
                "/reader?flash=Licence%20file%20installed.%20Opening%20Catalog%20Reader.",
                status_code=303,
            )

        if action == "activate_local":
            if not license_id or not email:
                return _page(
                    request,
                    error="Email and licence key are required.",
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            store = license_store()
            rec = store.get(license_id)
            if not rec:
                return _page(
                    request,
                    error=(
                        "Licence not found on this machine’s issuer store. "
                        "For purchases fulfilled by the seller, download an activation "
                        "request and install the returned .aslic instead."
                    ),
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            if rec.customer_email and rec.customer_email.lower() != email.lower():
                return _page(
                    request,
                    error="Email does not match the purchase record for this licence.",
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            device = load_or_create_device_identity()
            req = build_activation_request(device, license_id)
            if package_dir:
                aslic_path = Path(package_dir).expanduser() / "CustomerLicense.aslic"
            else:
                aslic_path = app_data_dir() / "activations" / license_id / "CustomerLicense.aslic"
            aslic_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                activate_device(
                    store,
                    req,
                    aslic_path=aslic_path,
                    replace_device_id=replace,
                )
            except PermissionError as exc:
                return _page(
                    request,
                    error=str(exc),
                    email=email,
                    license_id=license_id,
                    package_dir=package_dir,
                )
            if package_dir:
                marker = app_data_dir() / "protected_package_path.txt"
                marker.write_text(str(Path(package_dir).expanduser().resolve()), encoding="utf-8")
            return RedirectResponse(
                "/reader?flash=Activated%20on%20this%20device.",
                status_code=303,
            )

        return _page(request, error="Unknown action.", email=email, license_id=license_id)

    return router
