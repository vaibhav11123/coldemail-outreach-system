"""Customer delivery ledger for leak attribution (not automatic accusation)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    license_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    customer_email TEXT,
    sku TEXT NOT NULL,
    fingerprint_salt TEXT NOT NULL,
    export_id_scheme TEXT NOT NULL,
    package_sha256 TEXT,
    manifest_sha256 TEXT,
    file_hashes_json TEXT NOT NULL,
    notes TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deliveries_customer ON deliveries(customer_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_license ON deliveries(license_id);

CREATE TABLE IF NOT EXISTS export_id_samples (
    delivery_id TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    export_id TEXT NOT NULL,
    PRIMARY KEY (delivery_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS idx_export_id_lookup ON export_id_samples(export_id);
"""


@dataclass
class DeliveryRecord:
    delivery_id: str
    license_id: str
    customer_id: str
    customer_email: str | None
    sku: str
    fingerprint_salt: str
    export_id_scheme: str
    package_sha256: str | None
    manifest_sha256: str | None
    file_hashes: dict[str, str]
    created_at: int


class DeliveryLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_delivery(
        self,
        *,
        license_id: str,
        customer_id: str,
        sku: str,
        fingerprint_salt: str,
        file_hashes: dict[str, str],
        export_id_samples: dict[str, str] | None = None,
        customer_email: str | None = None,
        package_sha256: str | None = None,
        manifest_sha256: str | None = None,
        notes: str | None = None,
        export_id_scheme: str = "hmac-sha256-v1",
    ) -> DeliveryRecord:
        delivery_id = f"del_{uuid.uuid4().hex[:16]}"
        created_at = int(time.time())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO deliveries(
                    delivery_id, license_id, customer_id, customer_email, sku,
                    fingerprint_salt, export_id_scheme, package_sha256, manifest_sha256,
                    file_hashes_json, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    license_id,
                    customer_id,
                    customer_email,
                    sku,
                    fingerprint_salt,
                    export_id_scheme,
                    package_sha256,
                    manifest_sha256,
                    json.dumps(file_hashes, sort_keys=True),
                    notes,
                    created_at,
                ),
            )
            for canonical_id, export_id in (export_id_samples or {}).items():
                conn.execute(
                    """
                    INSERT INTO export_id_samples(delivery_id, canonical_id, export_id)
                    VALUES (?, ?, ?)
                    """,
                    (delivery_id, canonical_id, export_id),
                )
            conn.commit()
        return DeliveryRecord(
            delivery_id=delivery_id,
            license_id=license_id,
            customer_id=customer_id,
            customer_email=customer_email,
            sku=sku,
            fingerprint_salt=fingerprint_salt,
            export_id_scheme=export_id_scheme,
            package_sha256=package_sha256,
            manifest_sha256=manifest_sha256,
            file_hashes=file_hashes,
            created_at=created_at,
        )

    def find_by_export_ids(self, export_ids: list[str]) -> list[dict[str, Any]]:
        """Map leaked export IDs to candidate deliveries. Not proof of guilt alone."""
        if not export_ids:
            return []
        placeholders = ",".join("?" for _ in export_ids)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT s.export_id, s.canonical_id, d.delivery_id, d.customer_id,
                       d.license_id, d.sku, d.created_at
                FROM export_id_samples s
                JOIN deliveries d ON d.delivery_id = s.delivery_id
                WHERE s.export_id IN ({placeholders})
                """,
                list(export_ids),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_by_file_hash(self, sha256_hex: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM deliveries").fetchall()
        hits = []
        for row in rows:
            hashes = json.loads(row["file_hashes_json"])
            if sha256_hex in hashes.values() or sha256_hex in {
                row["package_sha256"],
                row["manifest_sha256"],
            }:
                hits.append(dict(row))
        return hits


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
