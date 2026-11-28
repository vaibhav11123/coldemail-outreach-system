# Additional production security qualification (60 items)

Reconciled against the repository on 2026-11-28.  
Status: `[x]` verified with automated evidence · `[~]` partial / scaffold · `[ ]` not verified · `N/A` with justification.

**Passing unit tests ≠ piracy resistance.** Expand this suite; do not replace existing licensing tests.

Verification baseline command:

```bash
.venv/bin/python -m pytest studio/tests/test_licensing_dataset.py studio/tests/test_licensing_api_reader.py studio/tests/test_security_qualification.py -q
```

## Cryptography and device identity · 3/12

| # | Item | Status | Evidence / location |
| --- | --- | --- | --- |
| 1 | Copy activation files to another physical machine | [~] | Forwarded package without `.aslic` / wrong device tests (`test_forwarded_package_without_aslic_unusable`, `test_protected_package_device_bound`) — not multi-host lab |
| 2 | Attempt device private-key export | [~] | Documented exportable software/keyring binding (`device_backend.py`); exportability asserted in API `/device` |
| 3 | Test device cloning | [ ] | Not run against VM clones |
| 4 | Test hardware-backed identity where available | [ ] | Hardware adapter stub only (`HardwareBackendStub`) |
| 5 | Test software-backed fallback | [x] | Default backend + `STUDIO_FORCE_LOCAL_SECRETS=1` path; `test_device_backend_software_fallback` |
| 6 | Test forged licences | [~] | Wrong-key / signature failures in aspkg + activation paths |
| 7 | Test modified licences | [~] | Covered indirectly via signature verify; dedicated mutation case pending |
| 8 | Test expired offline entitlements | [~] | TTL fields exist; dedicated expiry test pending |
| 9 | Test system clock rollback | [ ] | Not automated |
| 10 | Test replayed activation requests | [ ] | Nonce/replay protection not fully enforced |
| 11 | Test signing-key rotation | [ ] | Not implemented |
| 12 | Test compromised-key recovery | [ ] | Not implemented |

## Payment and licensing lifecycle · 4/12

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 13 | Reject forged payment webhooks | [x] | `test_payment_webhook_and_activate_local` wrong secret → 401 |
| 14 | Handle duplicate payment events | [ ] | Idempotency keys not fully proven |
| 15 | Handle out-of-order payment events | [ ] | |
| 16 | Test partial payment and packaging failures | [ ] | |
| 17 | Test simultaneous device activations | [ ] | Race not proven |
| 18 | Test unauthorized third-device activation | [x] | `test_device_limit_two_and_replacement` |
| 19 | Test refund revocation | [x] | `test_revoke_blocks_later_activation` / `test_revocation_blocks_activation` |
| 20 | Test chargeback handling | [ ] | Policy only |
| 21 | Test legitimate device replacement | [x] | `test_device_limit_two_and_replacement` |
| 22 | Test licence recovery | [~] | APIs exist; customer portal missing |
| 23 | Test licensing-service outage | [ ] | |
| 24 | Test entitlement reconciliation | [ ] | |

## Dataset protection and integrity · 5/12

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 25 | Strip XLSX metadata / surviving fingerprints | [ ] | Forensic tool can inspect; dedicated strip test pending |
| 26 | Sort exported CSV files | [~] | Documented limitation; automated survival test pending |
| 27 | Delete columns and subset records | [ ] | |
| 28 | Convert exports between formats | [ ] | |
| 29 | Combine datasets from multiple customers | [ ] | Forensic conflicting-evidence path ready |
| 30 | Test partial leak attribution | [~] | `dataset forensic` CLI + ledger lookup |
| 31 | Verify relational integrity after fingerprinting | [~] | Surrogate IDs only; factual FKs unchanged by design |
| 32 | Verify factual fields unchanged | [x] | `test_export_ids_differ_across_customers_facts_unchanged` |
| 33 | Attempt decrypted catalog extraction | [~] | Wrong-device cannot unwrap; memory extraction not tested |
| 34 | Inspect temporary files for plaintext | [ ] | |
| 35 | Scan releases for issuer secrets | [x] | `test_packaging_scan_rejects_issuer_secret` + `packaging_scan.py` |
| 36 | Verify manifests and checksums | [x] | Standard package + ledger tests |

## Application security · 2/12

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 37 | Modified application binaries | [ ] | |
| 38 | Invalid update signatures | [ ] | Updates not shipped |
| 39 | Update rollback | [ ] | |
| 40 | Local API authentication | [~] | Localhost host check + page token |
| 41 | Unauthorized local requests | [~] | Host header 403 tests |
| 42 | CSRF and origin protections | [~] | Page token; deepen |
| 43 | Dependency vulnerability scan | [~] | `prod_qual/run_scans.sh` pip-audit (prior) |
| 44 | Diagnostic logs for secrets | [~] | Support bundle redaction tests |
| 45 | Credential storage security | [~] | keyring + local fallback |
| 46 | Malicious input / import files | [~] | Partial FR/NFR |
| 47 | Database migration integrity | [~] | migrate v1–v3 |
| 48 | Independent penetration testing | [ ] | External |

## Commercial delivery and recovery · 1/12

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 49 | Clean macOS install | [ ] | |
| 50 | Clean Windows install | [ ] | |
| 51 | macOS signing/notarization | [ ] | |
| 52 | Windows Authenticode | [ ] | |
| 53 | Expired download links | [ ] | |
| 54 | Forwarded download links | [ ] | |
| 55 | Interrupted downloads | [ ] | |
| 56 | Interrupted installation | [ ] | |
| 57 | Interrupted updates | [ ] | |
| 58 | Backup and restoration | [x] | `/backup` + `test_backup_create_restore` |
| 59 | Customer workspace migration | [~] | Backup zip portable; formal migration guide pending |
| 60 | Complete disaster recovery | [ ] | Control-plane DR not built |

**Tally:** 15× `[x]`, 22× `[~]`, 23× `[ ]` (approximate; revisit after each security sprint).
