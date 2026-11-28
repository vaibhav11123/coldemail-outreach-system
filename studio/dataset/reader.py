"""Academic Data Reader — offline query API over an activated .asdb catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studio.dataset.asdb import catalog_meta, export_rows_controlled, open_asdb
from studio.licensing.device import DeviceIdentity, load_or_create_device_identity
from studio.licensing.entitlement import Entitlement, read_aslic


@dataclass
class CatalogSession:
    asdb_path: Path
    entitlement: Entitlement
    dek: bytes
    meta: dict[str, str]

    def connect(self):
        return open_asdb(self.asdb_path, self.dek)

    def search(
        self,
        *,
        query: str | None = None,
        university: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conn = self.connect()
        try:
            clauses = []
            params: list[Any] = []
            if query:
                clauses.append(
                    "(display_name LIKE ? OR email LIKE ? OR paper_title LIKE ? OR note LIKE ?)"
                )
                q = f"%{query}%"
                params.extend([q, q, q, q])
            if university:
                clauses.append("university LIKE ?")
                params.append(f"%{university}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            sql = (
                "SELECT export_id, display_name, email, university, status, funding, "
                "eligibility, deadline, paper_title, paper_year "
                f"FROM faculty{where} ORDER BY display_name LIMIT ?"
            )
            params.append(int(limit))
            cur = conn.execute(sql, params)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def controlled_export(self, limit: int | None = 100) -> list[dict[str, Any]]:
        if not self.entitlement.features.get("controlled_exports", True):
            raise PermissionError("Exports not permitted for this entitlement")
        conn = self.connect()
        try:
            return export_rows_controlled(conn, limit=limit, include_canonical=False)
        finally:
            conn.close()

    def record_count(self) -> int:
        return int(self.meta.get("record_count", "0"))


def activate_local_catalog(
    package_dir: Path,
    *,
    issuer_public_hex: str | None = None,
    device: DeviceIdentity | None = None,
) -> CatalogSession:
    """Open a Protected Dataset / Studio package after .aslic is present."""
    aslic = package_dir / "CustomerLicense.aslic"
    asdb = package_dir / "ResearchCatalog.asdb"
    if not aslic.exists():
        raise FileNotFoundError("CustomerLicense.aslic missing — activate this device first")
    if not asdb.exists():
        raise FileNotFoundError("ResearchCatalog.asdb missing")

    expected = bytes.fromhex(issuer_public_hex) if issuer_public_hex else None
    ent = read_aslic(aslic, expected_issuer_public=expected)
    device = device or load_or_create_device_identity()
    dek = ent.unwrap_dek(device)
    conn = open_asdb(asdb, dek)
    try:
        meta = catalog_meta(conn)
    finally:
        conn.close()
    return CatalogSession(asdb_path=asdb, entitlement=ent, dek=dek, meta=meta)
