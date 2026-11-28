# Purchase → delivery → activation → usage (authoritative)

**Constraint:** ₹0 upfront / ₹0 mandatory monthly (`ZERO_COST_COMMERCIAL.md`).  
**Primary ops mode until volume warrants automation:** **Option A — manual personalized fulfilment**.  
**Status key:** `[x]` true in-repo today · `[~]` partial · `[ ]` external / not built · `BLOCKED` third party

This document reconciles the commercial lifecycle against **what the repository actually contains**, not aspirational roadmaps.

---

## 1. Audit findings (concrete)

### Actual dataset packaging (`python -m studio.dataset fulfil --sku dataset`)

| Expected delivery asset | In-repo today |
| --- | --- |
| Personalized Excel / CSV / JSON | `[x]` `faculty_catalog.xlsx/.csv/.json` |
| SQLite export | `[x]` `faculty_catalog.sqlite` (added with this lifecycle pass) |
| Signed manifest | `[x]` `manifest.json` + `manifest.sig` |
| Fingerprints / export IDs | `[x]` HMAC scheme |
| START_HERE / licence / dictionary | `[x]` customer-facing text files (lifecycle pass) |
| Coverage / quality PDFs | `[ ]` not generated; quality report remains a packaging gap |
| Full 1,021 faculty inventory | `[~]` schema + loaders; package uses whatever SQLite source is passed (`--sqlite`) or mini bundled |

### Actual Academic Studio

| Expected | In-repo today |
| --- | --- |
| Localhost complete workstation UI | `[x]` FastAPI + Jinja |
| Encrypted catalog package | `[x]` `.asdb` / `.aspkg` + manifest |
| Device-bound `.aslic` crypto | `[x]` Ed25519 + X25519 seal |
| Graphical activate / recover UI | `[x]` `/activate` (lifecycle pass) |
| Offline activation-request file | `[x]` download + `issue-licence` CLI |
| PyInstaller specs | `[~]` `studio/packaging/build_*.spec` + stage script — **no built EXE/DMG in CI artifacts** |
| Signed Windows / notarized macOS | `[ ]` / Apple `$99` if chosen |
| Microsoft Store listing | `[ ]` Partner Center external |
| Bundled production catalog in installer | `[ ]` not produced as shippable binary yet |

### Actual marketplaces / payments

| Item | Status |
| --- | --- |
| Written product acceptance (FastSpring / 2CO / Paddle / Cashfree / Razorpay) | `BLOCKED` — not obtained |
| PayPal Business Individual KYC | `[ ]` operator |
| Fake-receipt resistance | `[~]` operator must verify provider dashboard; CLI requires `--verified-payment` attestation |
| Instant identical marketplace file for personalized dataset | **Incompatible** — see §2 |

### Actual purchase journey (simulated in-repo)

Happy path that **works today** without paid hosting:

1. Customer pays via approved link/marketplace (external).
2. Operator verifies payment in provider UI (`--verified-payment` on fulfil).
3. Operator runs `fulfil` → personalized package + ledger receipt.
4. Operator delivers package privately (Drive / R2 / email link) within disclosed SLA.
5. Dataset: customer opens Excel/CSV immediately.
6. Studio: customer installs app (when binary exists) or runs local build → `/activate` → request file or local activate → uses Reader + workspace.

---

## 2. Resolving the marketplace contradiction

**Instant identical marketplace file + personalized fingerprints + offline device licences do not compose.**

| Product | Public identical file? | Personalized? | How |
| --- | --- | --- | --- |
| **Dataset** | No | Yes — every buyer | Option A: marketplace sells “voucher”; real ZIP delivered privately after verify + `fulfil` |
| **Studio installer** | Yes (goal) | Licence / catalog key | Public installer; catalogue may ship inside installer **or** as private package; `.aslic` binds device |
| **Studio encrypted catalog** | Prefer private or sealed | Per-licence DEK | Same packaging stack as today |

### Option A — Manual personalized fulfilment (**selected default**)

1. Purchase on approved channel.  
2. Customer receives **purchase confirmation + delivery SLA** (target: **≤ 24 hours**, often sooner).  
3. Operator verifies payment against provider records (not customer-uploaded screenshots alone).  
4. `python -m studio.dataset fulfil … --verified-payment`.  
5. Private delivery of package.  
6. Studio: customer submits activation request from `/activate` → operator `issue-licence` → customer installs `.aslic`.

### Option B — Automated fulfilment (**later**)

Requires approved provider webhooks + packaging host (Workers cannot run full SQLCipher packaging). Same licence/packaging codepaths; automation wraps them. Defer until ≥ ~50 sales/week or provider approval forces it.

---

## 3. Public vs private files

| Public | Customer-specific | Never distribute |
| --- | --- | --- |
| Studio installer / screenshots / demo video / sample / docs | Dataset ZIP, `.aslic`, personalized manifest, private download URL | Issuer private key, master DEK material, payment creds, delivery ledger, unfingerprinted master DB |

Forwarding the **public installer** must not unlock another person’s catalog without their licence.

---

## 4. Failure matrix (required behaviour)

| Scenario | Behaviour |
| --- | --- |
| Paid, nothing received | Operator re-verify payment → re-`fulfil` or resend link; log in ledger |
| Download interrupted | Re-issue same private link / regenerate identical licence package |
| ZIP corrupt | Compare `manifest` hashes → regenerate |
| Licence email lost | Purchase-linked recovery via `/activate` recovery + operator re-send `.aslic` |
| Licence rejected | UI shows specific error (revoked / wrong device / issuer mismatch / expired) |
| New computer | Device replace (max 2) via activation with `--replace-device` / UI |
| App won’t start | Diagnostics doc + backup/restore (`/backup`) |
| AV flags installer | Prefer Store-signed build; document SmartScreen until reputation |
| AI/email fail | Offline draft + export `.eml`; connections optional |
| Crash / catalog corrupt | Backup restore; re-download purchased catalog package |
| Update fails | Keep previous working version |
| Marketplace suspend | Fallback approved channel (direct PayPal / second MoR) |
| Hosting gone | Re-upload to alternate free host; ledger proves entitlement |
| Refund | Revoke Studio entitlement; dataset files contractual (see licence) |

---

## 5. Locked commercial parameters

| | Dataset | Studio |
| --- | --- | --- |
| Price | **$14.99** | **$39.99** |
| Licence | Included, perpetual individual | Included, 2 devices |
| Delivery | Personalized ZIP | Installer (public) + licence / catalog delivery |
| Fulfilment | Existing CLI | Existing issuer + `/activate` |
| Fixed cost target | ₹0 | ₹0 |

---

## 6. Delivery SLA (disclose to customers)

> After payment clears, personalized files are prepared manually and sent within **24 hours** on business days. Most deliveries are faster. You will receive a private download link by email. Academic Studio activation uses your licence id and this device — no second payment.

---

## 7. Operator commands

```bash
# After verifying payment in PayPal/MoR dashboard:
.venv/bin/python -m studio.dataset fulfil \
  --sku dataset|studio \
  --out /secure/deliveries/CUST \
  --customer CUST_ID --email user@edu \
  --provider paypal --payment-ref TXN \
  --verified-payment

# Customer emailed activation_request.json:
.venv/bin/python -m studio.dataset issue-licence \
  --license-id lic_… \
  --request /path/activation_request.json \
  --out /path/CustomerLicense.aslic
```

Customer UI: `/activate` · Products: `/offer`.

---

## 8. Reconciled commercial delivery checklist

### Dataset presentation
- [x] Multi-format personalized package (CSV/JSON/XLSX/SQLite)
- [x] START_HERE + licence + data dictionary text
- [~] Real coverage stats / quality PDF (needs production corpus)
- [~] Free sample asset (demo rows exist; polished sample ZIP not published)
- [ ] Marketplace cover art

### Studio presentation
- [x] Actual UI screenshots + long demo video (artifacts)
- [x] Graphical activation page
- [~] Installer specs (unbuilt binaries)
- [ ] Installer demo on clean OS
- [ ] Store listing assets

### Marketplace readiness
- [ ] Confirmed eligible marketplaces
- [x] Pricing locked $14.99 / $39.99
- [x] Licence-included policy docs
- [~] Refund policy draft in legal + offer page
- [x] Delivery instructions in package + SLA above
- [ ] Seller KYC

### Delivery qualification
- [x] Personalized package generation
- [x] Verified-payment attestation on fulfil
- [x] Private delivery procedure (manual)
- [x] Device activation crypto + UI
- [x] Licence recovery UX (request re-issue path)
- [x] Device replacement API/CLI
- [~] Cross-platform installation (specs only)
- [ ] Complete live test purchase with real money

---

## 9. What we will not build yet

Paid gateways, always-on PostgreSQL, Keygen, affiliate SaaS, or Workers packaging. Automation waits for merchant approval + volume.
