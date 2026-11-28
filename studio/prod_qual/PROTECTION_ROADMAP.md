# Protection roadmap

Shared licensing + encrypted catalog for **Standard Dataset**, **Protected Dataset (Academic Data Reader)**, and **Academic Studio**.

Status key: `[x]` implemented in-repo · `[~]` scaffold / partial · `[ ]` not started

## P0 — Dataset protection

- [x] Customer-specific dataset packaging (`studio/dataset/package_standard.py`)
- [x] Unique relational export identifiers (HMAC surrogate IDs)
- [x] Encrypted `.asdb` catalog (SQLCipher via `sqlcipher3`)
- [x] Outer AES-256-GCM `.aspkg` transit container
- [x] Signed manifests (`manifest.json` + Ed25519)
- [x] Offline dataset reader API + localhost Reader UI (`/reader`)
- [x] Customer-specific export watermarking (banner, XLSX props, hidden provenance, export IDs, row order)
- [ ] Full spreadsheet-like Desktop Reader (Tauri) — deferred; Python/FastAPI Reader ships first
- [ ] Collusion-resistant fingerprint codes for partial copies

## P0 — Licensing

- [x] Purchase-to-entitlement workflow (`LicenseStore` + `/api/licensing/webhook/payment`)
- [x] Cryptographic device identity (Ed25519 + X25519)
- [x] Secure key delivery (X25519 sealed DEK in `.aslic`)
- [x] Two-device activation + replacement hook
- [x] Signed offline entitlements with TTL / clock skew check
- [x] Revocation flag (webhook + next activation)
- [x] FastAPI licensing API (`/api/licensing/*`)
- [~] Keygen production adapter (local JSON store is interim)
- [ ] Passkeys / verified-email purchase gate in product UI
- [~] Payment webhook → entitlement assignment (shared-secret webhook scaffold)

## P1 — Application security

- [x] Packaging scan for secrets / issuer keys (`studio/packaging_scan.py`)
- [x] OS-backed DEK cache after unlock (`studio/licensing/dek_cache.py`)
- [x] Unauthorized package transfer tests (forwarded `.asdb` without `.aslic` / wrong device)
- [ ] Compile commercial engine (Nuitka) / native Tauri + Rust licence component
- [ ] Sign application installers
- [ ] Signed software updates
- [ ] Independent penetration test before paid launch
- [ ] Hardware-backed keys (Secure Enclave / TPM) where available

## P1 — Commercial enforcement

- [x] Delivery ledger with export-ID lookup (`studio/licensing/ledger.py`)
- [x] Draft individual / commercial licence terms (`studio/legal/`)
- [x] Takedown procedure draft (`studio/legal/TAKEDOWN.md`)
- [~] Piracy monitoring scaffold (local corpus + ledger compare; live crawlers not wired)
- [ ] Dataset update channel for legitimate customers
- [ ] Make ongoing updates the commercial moat (process, not only code)

## Explicit non-goals (do not build)

- Ordinary ZIP passwords as the sole control
- Excel worksheet “protection” as security
- VBA-only licence checks
- MAC-address locking alone
- Base64 “encryption”
- Hardcoded catalog keys in the app binary
- Fake faculty records as watermarks
- Blockchain certificates as copy prevention
