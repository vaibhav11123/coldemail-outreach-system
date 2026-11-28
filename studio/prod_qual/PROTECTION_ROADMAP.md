# Protection roadmap

Shared licensing + encrypted catalog for **Standard Dataset**, **Protected Dataset (Academic Data Reader)**, and **Academic Studio**.

Status key: `[x]` implemented in-repo · `[~]` scaffold / partial · `[ ]` not started

## P0 — Dataset protection

- [x] Customer-specific dataset packaging (`studio/dataset/package_standard.py`)
- [x] Unique relational export identifiers (HMAC surrogate IDs)
- [x] Encrypted `.asdb` catalog (SQLCipher via `sqlcipher3`)
- [x] Signed manifests (`manifest.json` + Ed25519)
- [x] Offline dataset reader API (`studio/dataset/reader.py` + CLI)
- [x] Customer-specific export watermarking (banner, XLSX props, hidden provenance, export IDs, row order)
- [ ] Full spreadsheet-like Desktop Reader UI (Tauri) — deferred; Python reader CLI ships first
- [ ] Collusion-resistant fingerprint codes for partial copies

## P0 — Licensing

- [x] Purchase-to-entitlement workflow (`LicenseStore.register_purchase` → activate)
- [x] Cryptographic device identity (Ed25519 + X25519)
- [x] Secure key delivery (X25519 sealed DEK in `.aslic`)
- [x] Two-device activation + replacement hook
- [x] Signed offline entitlements with TTL / clock skew check
- [x] Revocation flag (enforced on next activation / entitlement issue)
- [~] Keygen or FastAPI production licensing service (local JSON store is interim)
- [ ] Passkeys / verified-email purchase gate in product UI
- [ ] Payment webhook → entitlement assignment

## P1 — Application security

- [~] Packaging scan for secrets / issuer keys (`studio/packaging_scan.py`)
- [ ] Compile commercial engine (Nuitka) / native Tauri shell
- [ ] Sign application installers
- [ ] Signed software updates
- [ ] OS keychain-only DEK caching (currently unwrap per session from `.aslic`)
- [ ] Unauthorized package transfer test suite in CI matrix (covered partially by unit tests)
- [ ] Independent penetration test before paid launch

## P1 — Commercial enforcement

- [x] Delivery ledger with export-ID lookup (`studio/licensing/ledger.py`)
- [ ] Published individual / commercial licence terms pages
- [ ] Automated public-web piracy monitoring
- [ ] Takedown procedure runbook
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
