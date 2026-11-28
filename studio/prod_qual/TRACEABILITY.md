# Requirement → test traceability (production qualification)

| ID | Requirement / invariant | Automated evidence | Status |
| --- | --- | --- | --- |
| INV-01 | No unapproved send | `test_inv_email_safety.py` | PASS |
| INV-02 | No auto-resend unknown_delivery | `test_inv_email_safety.py` | PASS |
| INV-03 | No duplicate provider submit | concurrent claim + 100× create | PASS |
| INV-04 | No unsupported claims approved | hallucination/injection + Hypothesis | PASS |
| INV-05 | Unknown funding not presented as funded | classify + UI string | PASS |
| INV-06 | Cross-tenant isolation | documents scaffolding gap | FAIL (hosted not isolated) |
| INV-07 | Credential redaction / SSRF | support bundle + SSRF tests | PASS |
| INV-08 | Delete personal keeps bundled | delete-all E2E | PASS |
| INV-09 | Crash recovery of intents | reconnect + backup | PASS |
| INV-10 | No silent paid AI failover | deterministic fallback | PASS |
| INV-11 | Offline core with APIs down | full outage mock | PASS |
| INV-12 | Host / CSRF / OAuth state | ASVS-style unit tests | PASS |
| INV-13 | Edit clears approval | email safety | PASS |
| INV-14 | Suppression blocks send | email safety | PASS |
| INV-15 | Failed send explicit retry | email safety | PASS |
| FR-1..25 | Product FR suite | `test_fr_nfr.py` | PASS (existing) |
| E2E-01/02/11/12 | HTTP journeys | `test_e2e_journeys_http.py` | PASS |
| E2E-03..10,13..18 | Real mail/AI/install/pay | — | NOT RUN / BLOCKED |
| Scale 10k | Synthetic library search | `test_scale_and_chaos.py` | PASS |
| Supply chain | pip-audit, gitleaks | `run_scans.sh` | PASS |
| Mutation | Critical guard presence | `mutation_smoke.py` | PASS (partial; mutmut NOT RUN) |
| Load/soak | k6 scripts present | `k6/smoke.js` | NOT RUN (no k6 target env) |
| Playwright | Real browser | — | NOT RUN |
| OWASP ZAP | Dynamic scan | — | NOT RUN |
| Usability | 20–30 students | — | NOT RUN (human) |
| Payments | Checkout/entitlement | — | N/A (not built) |
