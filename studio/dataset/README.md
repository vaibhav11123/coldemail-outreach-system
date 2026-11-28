# Dataset packaging & licensing

Shared protection stack for:

| SKU | Price (suggested) | Delivery |
| --- | --- | --- |
| `standard_dataset` | $14.99 | Fingerprinted Excel/CSV/JSON — full facts, unique export IDs |
| `protected_dataset` | $24.99 | SQLCipher `ResearchCatalog.asdb` + device-bound `.aslic` |
| `academic_studio` | $39.99 | Same encrypted catalog + Studio features under the same licence |

## What this does

- Customer-specific **export IDs** (HMAC) without changing names, emails, pubs, or affiliations
- Signed **delivery manifests** (Ed25519) and a **delivery ledger** for leak attribution
- **Device identity** via Ed25519 + X25519 (not MAC spoofing)
- **DEK sealed** to the authorized device; SQLCipher encrypts the catalog at rest
- Offline entitlements with TTL; revocation takes effect on next validation

## What this does not claim

- Absolute prevention of extraction after authorized decryption
- That fingerprint hits alone prove a buyer pirated (theft from the buyer is possible)
- Production Keygen / payment webhooks (local `LicenseStore` is the scaffold)

## CLI

```bash
export STUDIO_FORCE_LOCAL_SECRETS=1
.venv/bin/python -m studio.dataset editions
.venv/bin/python -m studio.dataset package-standard --out /tmp/std --customer cust_a --email a@example.com
.venv/bin/python -m studio.dataset package-protected --out /tmp/prot --customer cust_a --email a@example.com --activate
.venv/bin/python -m studio.dataset read --package /tmp/prot --query Ada
```

Issuer private keys belong on the licensing server only. For local demos, a `dev_issuer.json` is created under the studio data dir — never ship it in customer packages (`packaging_scan` rejects it).
