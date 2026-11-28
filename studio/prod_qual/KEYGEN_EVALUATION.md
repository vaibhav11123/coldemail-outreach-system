# Keygen vs in-house licensing — engineering evaluation

**Status:** Decision recorded for engineering (not deferred to demand validation)  
**Date:** 2026-11-28  
**Sources:** [keygen.sh](https://keygen.sh/), [pricing](https://keygen.sh/pricing/), [offline cryptography docs](https://keygen.sh/docs/api/cryptography/)

## Recommendation (current)

**Complete our own lightweight production licensing control plane**, keeping Keygen as an optional adapter behind the existing entitlement interface if volume/ops later justify it.

Rationale:
1. We already ship Ed25519 licences, X25519 sealed DEKs, `.aslic` / `.asdb`, two-device limits, offline TTL entitlements, webhooks, and a delivery ledger tailored to dataset fingerprinting.
2. Keygen’s cryptographic schemes (RSA-SHA256 / Ed25519 license files, machine files) are strong but **not drop-in compatible** with our sealed-DEK + SQLCipher catalog format — integration is an adapter project, not a flip.
3. Early ALU-based cloud pricing (~$49/mo Tier 1 and up; free Dev tier limited) is fine for SaaS, but our products are **one-time $14.99 / $39.99** with perpetual individual licences — control-plane cost must stay lean.
4. Self-host Keygen CE/EE reduces vendor lock-in but still requires ops, migration planning, and dual-format bridge work.
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

- Production issuer with vaulted keys + rotation
- Payment provider webhooks (Stripe/etc.) with idempotency
- Atomic device allocation
- Customer portal for recovery / device replacement
- Signed installers and update channel

See `PROTECTION_ROADMAP.md` for status.
