# Protection & production licensing roadmap (authoritative)

**Products:** Global Research Dataset (`$14.99` provisional) · Academic Studio (`$39.99` provisional)  
**Rule:** Licence included in purchase · no activation surcharge · no standalone Protected `$24.99` SKU  
**Internal alias:** `protected_dataset` packaging retained (not sold)  
**Linked trackers:** `COMPLETE_PRODUCT_ROADMAP.md` · `SECURITY_QUALIFICATION.md` · `KEYGEN_EVALUATION.md` · `ZERO_COST_COMMERCIAL.md` · `COMMERCIAL_DISTRIBUTION.md`

Status: `[x]` implemented, tested, verified in-repo · `[~]` partial · `[ ]` not implemented · `BLOCKED` external · `N/A` justified

**Honesty:** Automated tests establish regression and initial crypto isolation — **not** absolute piracy prevention, hardware binding, or production payment readiness.

---

## Commercial consolidation (P0)

- [x] Two sold SKUs only — `studio/licensing/products.py`
- [x] Licence included flags + API exposure — `/api/licensing/editions`
- [x] Canonical licence policies (perpetual ≠ updates/support/AI) — `studio/licensing/policy.py`, `studio/legal/UPDATES_AND_SUPPORT.md`
- [x] Retain encrypted catalog / Reader / licensing stack (no deletion for SKU consolidation)
- [x] Integrate graphical Reader into Studio nav + Directory/Dashboard links — `/reader`
- [x] Keygen evaluation recorded — no Keygen spend; in-house + optional Workers later (`KEYGEN_EVALUATION.md`)
- [x] Zero fixed-cost commercial policy — `ZERO_COST_COMMERCIAL.md`
- [x] Manual fulfilment CLI — `python -m studio.dataset fulfil`

## Protection stack retention

| Component | Status | Location |
| --- | --- | --- |
| `studio/licensing/` | [x] retain & extend | package |
| `studio/dataset/` | [x] retain & extend | package |
| Ed25519 licence issuer | [x] | `licensing/crypto.py` |
| X25519 sealed DEK | [x] | activation / package_protected |
| SQLCipher `.asdb` | [x] | `dataset/asdb.py` |
| `.aslic` licence format | [x] | activation |
| Device identity | [~] software/keyring; hardware stub | `device.py`, `device_backend.py` |
| Device activation | [~] local store; needs production DB | `activation.py`, API |
| Device replacement | [~] tested locally | activation tests |
| Licence revocation | [~] flag + next validation | API revoke |
| HMAC export IDs | [x] | `fingerprint.py` |
| Customer row ordering | [x] | `permute_rows` |
| XLSX provenance | [x] | package_standard |
| Signed manifests | [x] | package_standard / protected |
| Delivery ledger | [~] strengthen ops durability | `ledger.py` |
| Reader CLI | [x] | `python -m studio.dataset read` |
| Graphical Reader | [~] localhost UI integrated; desktop polish remains | `/reader` |
| Feature entitlements | [x] | products + entitlement |
| Local `LicenseStore` | [~] **dev/test only** — not production issuer | `activation.py` |
| Forensic inspector | [x] scaffold | `dataset/forensic.py` + CLI |
| Piracy monitor | [~] local corpus + ledger; no live crawlers | `monitor.py` |

## Device identity & licence protection (P0)

- [x] Cryptographic device keypair (Ed25519 + X25519) — not MAC locking
- [x] Versioned backend adapter + documented software fallback guarantees/limitations
- [x] Honest `/api/licensing/device` security summary (`exportable_private_keys`, hardware stub status)
- [ ] Hardware-backed non-exportable keys (Secure Enclave / TPM) — adapter stub only
- [ ] Atomic server-side device allocation under concurrency
- [ ] Activation replay/nonce protection
- [ ] Clock rollback detection + trusted server time
- [ ] Signing-key rotation & emergency revocation
- [ ] Integrity checks against patched validation binaries

**Known limitation:** Current `device_identity` private keys are **exportable** (file or OS keyring). X25519 alone does not equal hardware binding.

## Dataset protection (P0/P1)

- [x] Fingerprinting without altering factual fields
- [x] Multi-format packaging Excel/CSV/JSON (+ SQLite path)
- [x] Signed manifests + SHA-256 via packaging
- [x] Forensic inspection report (confidence, conflicts, limitations; no auto-accusation)
- [ ] Collusion-resistant codes for partial copies
- [ ] Expiring authenticated download URLs
- [ ] Full transformation survival battery (see `SECURITY_QUALIFICATION.md` §Dataset)

## Production licensing control plane (P0)

- [x] Manual fulfilment path (payment verify → package → ledger receipt) for low volume
- [~] Payment webhook scaffold (shared secret, **fail-closed if unset**) — needs approved provider + idempotency
- [~] Cloudflare security-audit skill run-1 **incomplete** — see `CLOUDFLARE_SECURITY_AUDIT.md` (not a release-gate pen-test)
- [ ] Optional Workers + D1 entitlement API (only when automation thresholds hit)
- [ ] Vaulted / encrypted-backup production issuer keys
- [ ] Customer portal (purchase, devices, recovery) — defer; email recovery first
- [ ] Refund/chargeback entitlement automation beyond revoke flag
- [ ] Durable audit trail / monitoring / DR drills
- [ ] Keygen adapter — **N/A unless policy changes** (see `KEYGEN_EVALUATION.md`)

## Application delivery security (P0)

- [ ] Windows: prefer Microsoft Store MSIX (free eligible signing) + direct download
- [ ] Signed Windows installers (Authenticode) if distributing outside Store
- [ ] Signed + notarized macOS installers — Apple $99/yr if selected; local browser Studio is $0 interim
- [ ] Signed software update manifests/payloads
- [x] Packaging scan excludes issuer secrets
- [~] OS-backed customer credential storage (keyring)
- [~] Localhost API host + page-token CSRF
- [x] Workspace backup/restore (`/backup`)

## Piracy monitoring (P1)

- [~] Marker + export-ID scan of local corpora
- [ ] Scheduled public source checks (storefronts, GitHub, forums) without bypassing access controls
- [ ] Incident dedupe + manual review workflow UI
- [x] Takedown procedure draft — `legal/TAKEDOWN.md`

## Release gates (must all be green before “production-ready”)

See also `RELEASE_READINESS.md`. Do **not** declare ready from test counts alone.

| Gate | Status |
| --- | --- |
| 1,021 faculty completeness | [~] schema/loaders; full zip audit env-dependent |
| Export format reconciliation | [~] |
| No fingerprint-induced factual changes | [x] tested on mini corpus |
| Source provenance | [~] |
| Licence issuance per purchase | [~] local store |
| Unauthorized activation rejected | [x] local tests |
| Licence recovery | [~] |
| Payment lifecycle | [ ] |
| Installer integrity | [ ] |
| Software updates | [ ] |
| No issuer secrets in packages | [x] |
| Zero unresolved critical vulns | [~] |
| Customer work survives failures | [~] backup |
| Advertised offline features | [~] |
| Nontechnical core workflows | [~] |
| Security review | [ ] |
| Documentation complete | [ ] |
| Pricing includes licence costs | [x] policy |
| End-to-end commercial delivery | [ ] |

## Explicit non-claims

- Absolute copy-proofing of delivered Excel/CSV/JSON/SQLite
- Unbreakable encryption against a determined authorized-device attacker
- Hardware binding before a real SE/TPM backend ships and is stress-tested
- That fingerprint matches prove the buyer pirated the product

## Explicit non-goals

- Ordinary ZIP passwords as sole control
- Excel worksheet “protection” as security
- VBA-only licence checks
- MAC-address locking alone
- Base64 “encryption”
- Hardcoded catalog keys in the app binary
- Fake faculty records as watermarks
- Blockchain certificates as copy prevention
- Demand validation / preorders as a gate for finishing P0/P1 engineering
