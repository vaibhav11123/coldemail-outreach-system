"""Academic Data Reader — localhost UI over an activated protected package."""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from studio.dataset.reader import CatalogSession, activate_local_catalog
from studio.licensing.dek_cache import cache_dek, load_cached_dek
from studio.licensing.device import load_or_create_device_identity
from studio.paths import PACKAGE_ROOT, app_data_dir
from studio.status_labels import register_template_filters

TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))
register_template_filters(TEMPLATES.env)


def _default_package_dir() -> Path | None:
    env = os.environ.get("STUDIO_PROTECTED_PACKAGE")
    if env:
        return Path(env)
    marker = app_data_dir() / "protected_package_path.txt"
    if marker.exists():
        path = Path(marker.read_text(encoding="utf-8").strip())
        if (path / "ResearchCatalog.asdb").exists():
            return path
    candidate = app_data_dir() / "protected_package"
    if (candidate / "ResearchCatalog.asdb").exists():
        return candidate
    return None


def _package_issuer_public_hex(package_dir: Path) -> str | None:
    """Trust package-embedded issuer (manifest / .aslic), not operator issuer_keys()."""
    trusted = (os.environ.get("STUDIO_TRUSTED_ISSUER_PUBLIC") or "").strip()
    if trusted:
        return trusted
    for name in ("manifest.json", "CustomerLicense.aslic"):
        path = package_dir / name
        if not path.is_file():
            continue
        try:
            import json

            doc = json.loads(path.read_text(encoding="utf-8"))
            if name == "manifest.json":
                hex_key = (doc.get("issuer_public") or "").strip()
            else:
                hex_key = (doc.get("issuer_public") or "").strip()
            if hex_key:
                return hex_key
        except Exception:  # noqa: BLE001
            continue
    return None


def _humanize_licence_error(exc: Exception) -> str:
    msg = str(exc)
    if "issuer public key mismatch" in msg.lower():
        return (
            "We couldn't open your research catalog. "
            "Your catalog could not be verified against this installation of Academic Studio. "
            "Your research workspace and saved applications have not been changed. "
            "Select your purchased catalog again, or recover your purchase. "
            "Technical details · Error AS-LIC-ISSUER-MISMATCH"
        )
    if "expired" in msg.lower():
        return (
            "This entitlement has expired. Recover your purchase or contact support. "
            "Technical details · Error AS-LIC-EXPIRED"
        )
    if "signature" in msg.lower():
        return (
            "The licence file could not be verified (signature invalid or package corrupted). "
            "Technical details · Error AS-LIC-SIGNATURE"
        )
    if "device" in msg.lower() or "unwrap" in msg.lower():
        return (
            "This catalogue is bound to a different device. "
            "Use activation recovery to move your licence. "
            "Technical details · Error AS-LIC-DEVICE"
        )
    return msg


def _open_session(package_dir: Path) -> CatalogSession:
    device = load_or_create_device_identity()
    # Prefer package-embedded issuer public; never force operator issuer_keys().
    issuer_hex = _package_issuer_public_hex(package_dir)
    session = activate_local_catalog(
        package_dir,
        issuer_public_hex=issuer_hex,
        device=device,
    )
    cached = load_cached_dek(session.entitlement.license_id, device.device_id)
    if cached is None:
        cache_dek(session.entitlement.license_id, device.device_id, session.dek)
    return session


def build_reader_router(render_ctx) -> APIRouter:
    """render_ctx(request, nav, **extra) -> dict for templates."""
    router = APIRouter(tags=["reader"])

    @router.get("/reader", response_class=HTMLResponse)
    def reader_home(
        request: Request,
        q: str | None = None,
        university: str | None = None,
        sort: str = "display_name",
        status: str | None = None,
        funding: str | None = None,
    ):
        package_dir = _default_package_dir()
        error = None
        rows: list[dict[str, Any]] = []
        meta: dict[str, str] = {}
        record_count = 0
        entitlement = None
        if not package_dir:
            error = (
                "No protected package configured. Set STUDIO_PROTECTED_PACKAGE to a "
                "folder containing ResearchCatalog.asdb and CustomerLicense.aslic."
            )
        else:
            try:
                session = _open_session(package_dir)
                meta = session.meta
                record_count = session.record_count()
                entitlement = session.entitlement
                rows = session.search(query=q or None, university=university or None, limit=200)
                if status:
                    rows = [r for r in rows if (r.get("status") or "unknown") == status]
                if funding:
                    rows = [r for r in rows if (r.get("funding") or "unknown") == funding]
                reverse = sort.startswith("-")
                key = sort.lstrip("-") or "display_name"
                allowed = {
                    "display_name",
                    "university",
                    "email",
                    "status",
                    "funding",
                    "paper_year",
                    "export_id",
                }
                if key in allowed:
                    rows.sort(
                        key=lambda r: (r.get(key) is None, str(r.get(key) or "").lower()),
                        reverse=reverse,
                    )
            except Exception as exc:  # noqa: BLE001
                error = _humanize_licence_error(exc)
        ctx = render_ctx(
            request,
            nav="reader",
            package_dir=str(package_dir) if package_dir else "",
            error=error,
            rows=rows,
            meta=meta,
            record_count=record_count,
            q=q or "",
            university=university or "",
            sort=sort,
            status=status or "",
            funding=funding or "",
            entitlement=entitlement,
        )
        return TEMPLATES.TemplateResponse(request, "reader.html", ctx)

    @router.post("/reader/configure")
    def reader_configure(
        request: Request,
        package_dir: str = Form(...),
        page_token: str = Form(...),
    ):
        # Token checked by comparing to cookie set for this process
        import secrets as _secrets

        cookie = request.cookies.get("studio_page_token")
        if (
            not cookie
            or not page_token
            or not _secrets.compare_digest(cookie, page_token)
        ):
            return RedirectResponse("/reader?err=1&flash=Invalid+session+token", status_code=303)
        path = Path(package_dir).expanduser().resolve()
        if not path.is_dir():
            return RedirectResponse("/reader?err=1&flash=Package+folder+not+found", status_code=303)
        # Allow customer Downloads / Studio data; reject arbitrary system paths
        def _under(root: Path) -> bool:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                return False

        if not (_under(app_data_dir().resolve()) or _under(Path.home().resolve())):
            return RedirectResponse(
                "/reader?err=1&flash=Package+must+be+under+your+home+or+Studio+data+directory",
                status_code=303,
            )
        markers = ("ResearchCatalog.asdb", "ResearchCatalog.aspkg", "CustomerLicense.aslic", "manifest.json")
        if not any((path / m).exists() for m in markers):
            return RedirectResponse(
                "/reader?err=1&flash=Folder+does+not+look+like+a+Studio+package",
                status_code=303,
            )
        dest = app_data_dir() / "protected_package_path.txt"
        dest.write_text(str(path) + "\n", encoding="utf-8")
        os.environ["STUDIO_PROTECTED_PACKAGE"] = str(path)
        return RedirectResponse("/reader", status_code=303)

    @router.get("/reader/export.csv")
    def reader_export_csv(request: Request, limit: int = 100):
        if not request.cookies.get("studio_page_token"):
            return RedirectResponse("/reader?err=1&flash=Session+required", status_code=303)
        package_dir = _default_package_dir()
        if not package_dir:
            return RedirectResponse("/reader", status_code=303)
        try:
            session = _open_session(package_dir)
            rows = session.controlled_export(limit=min(max(limit, 1), 500))
        except Exception:
            return RedirectResponse("/reader", status_code=303)
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        else:
            buf.write("export_id\n")
        data = buf.getvalue().encode("utf-8")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="controlled_export.csv"'
            },
        )

    return router


def resolve_configured_package() -> Path | None:
    env = _default_package_dir()
    if env:
        return env
    marker = app_data_dir() / "protected_package_path.txt"
    if marker.exists():
        path = Path(marker.read_text(encoding="utf-8").strip())
        if path.exists():
            return path
    return None
