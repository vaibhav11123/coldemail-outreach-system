# Keygen vs in-house licensing — engineering evaluation

**Status:** Decision recorded for engineering (not deferred to demand validation)  
**Date:** 2026-11-28  
**Sources:** [keygen.sh](https://keygen.sh/), [pricing](https://keygen.sh/pricing/), [offline cryptography docs](https://keygen.sh/docs/api/cryptography/)

## Recommendation (current)

**Do not subscribe to Keygen.** Keep our Ed25519 / X25519 stack. For ₹0 fixed cost:

1. **Low volume (1–10/week):** manual fulfilment via `python -m studio.dataset fulfil` on the operator machine — no always-on licensing server.
2. **Later automation:** optional Cloudflare Workers + D1 + Web Crypto for payment webhooks and entitlements (still $0 within free-tier limits); packaging stays local Python.
3. Keygen remains an optional façade adapter only if volume/ops later justify a paid control plane.

Rationale:
1. We already ship Ed25519 licences, X25519 sealed DEKs, `.aslic` / `.asdb`, two-device limits, offline TTL entitlements, webhooks, and a delivery ledger tailored to dataset fingerprinting.
2. Keygen’s cryptographic schemes (RSA-SHA256 / Ed25519 license files, machine files) are strong but **not drop-in compatible** with our sealed-DEK + SQLCipher catalog format — integration is an adapter project, not a flip.
3. Keygen cloud pricing (~$49/mo Tier 1+) violates the **₹0 mandatory monthly** commercial policy (`ZERO_COST_COMMERCIAL.md`).
4. Self-host Keygen CE/EE still requires ops and dual-format bridge work.
5. Dataset forensic fingerprinting + delivery ledger remain ours regardless of Keygen.

## Comparison

| Criterion | Our stack | Keygen Cloud / EE |
| --- | --- | --- |
| Operating cost | Infra only (issuer + payment webhooks + downloads) | Flat monthly by ALU / tier; EE self-host license |
| Device activation | Implemented (local store → needs production DB) | First-class machines API |
| Offline licences | Signed entitlement TTL in `.aslic` | Cryptographic license/machine files + TTL |
| Crypto compatibility | Ed25519 + X25519 sealed DEK (custom) | Multiple schemes; Ed25519 available; different file format |
| Key management | Must vault issuer keys ourselves | Cloud holds private keys; public keys embeddable |
| Customer recovery | APIs scaffolded | Dashboard + APIs |
| Webhooks | Shared-secret scaffold | Production webhooks + logs |
| DR / availability | Must build | Cloud SLA / EE self-host |
| Vendor lock-in | None | API + license file formats; CE helps |
| Export / migration | JSON + SQLite ledger today | Documented API export; still a project |
| Dataset fingerprinting | First-class | Not provided — remains ours |

## If we integrate Keygen later

- Keep `LicenseStore` / entitlement interfaces as the façade.
- Map purchase → Keygen license + machine activation.
- Continue issuing our `.aslic` sealed DEK **or** wrap Keygen machine-file checkout as the outer entitlement and keep DEK seal in our issuer.
- Never embed issuer private keys in customer apps (Keygen docs agree: account public key only).

## What must still be built either way

- Secure issuer key storage + encrypted backups (local first; vault later)
- Payment provider webhooks with idempotency **when automating** (MoR after approval)
- Atomic device allocation (when online activation is required)
- Customer recovery workflow (email + re-issue; portal later)
- Signed installers / Store distribution (Microsoft Store path preferred for Windows)

See `PROTECTION_ROADMAP.md`, `ZERO_COST_COMMERCIAL.md`, and `COMMERCIAL_DISTRIBUTION.md`.
