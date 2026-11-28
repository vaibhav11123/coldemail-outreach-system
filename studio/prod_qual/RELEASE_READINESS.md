# Commercial release readiness report

**Product:** Academic Outreach Studio  
**Branch:** `cursor/academic-outreach-studio-9e6a`  
**Verdict: NOT commercially ready (0/15 checklist items fully evidenced)**

This environment executed adversarial automated qualification against the current codebase. Passing unit/integration counts alone are insufficient for sale.

## Checklist (15)

| # | Gate | Status | Notes |
| --- | --- | --- | --- |
| 1 | Core functionality | PARTIAL | FR suite + 167 non-live tests PASS; live providers mostly mocked |
| 2 | Installation | NOT RUN | No signed clean-machine binaries here |
| 3 | Security | PARTIAL | Host/CSRF/SSRF/redaction/gitleaks/pip-audit PASS; ZAP/semgrep NOT RUN |
| 4 | Email safety | PARTIAL | Invariant suite PASS with Mailpit NOT RUN; concurrency claim fixed |
| 5 | AI accuracy | PARTIAL | Curated adversarial cases PASS; 500-case + human review NOT RUN |
| 6 | Data integrity | PARTIAL | Intent recovery + backup smoke PASS; SIGKILL matrix NOT RUN |
| 7 | Privacy / isolation | FAIL | Hosted multi-tenant isolation missing (PQ-06) |
| 8 | Connections live | NOT RUN | Real OAuth/SMTP/Groq accounts not exercised this pass |
| 9 | Performance | PARTIAL | 10k search smoke PASS; k6 normal/stress/soak NOT RUN |
| 10 | Endurance 24h | NOT RUN | |
| 11 | Usability study | NOT RUN | Human-only |
| 12 | Commercial payments | N/A | Not implemented |
| 13 | Licensing of assets | PARTIAL | ORCID CC0 / OpenCitations CC0 documented; full counsel review open |
| 14 | Support diagnostics | PARTIAL | Redaction fixed; production monitoring not built |
| 15 | Rollback of release binary | NOT RUN | |

## Commands executed (this environment)

```bash
.venv/bin/python -m pytest studio/tests -m "not live" -q
# → 167 passed, 3 deselected

.venv/bin/python -m pytest studio/tests/prod_qual -q
# → included in full run

bash studio/prod_qual/run_scans.sh /opt/cursor/artifacts/prod_qual
# → pip-audit PASS (0 vulns), gitleaks PASS

.venv/bin/python studio/prod_qual/mutation_smoke.py
# → PASS (structural; full mutmut NOT RUN)
```

## Defects fixed this pass

PQ-01, PQ-02, PQ-03, PQ-04, PQ-05 (see `DEFECT_REGISTER.md`).

## What must remain blocked from customer claims

- “Commercially ready” / “production verified” for any live OAuth, Groq quality, or hosted multi-user isolation
- Unsigned installer download pages for Mac/Windows
- Payment or refund guarantees

## Recommended next engineering package

1. Tenant-scoped schema before enabling `/hosted` for paying users  
2. Mailpit + Playwright E2E-03/04/09  
3. AI eval set (≥500) + independent human sample  
4. k6 smoke against a staging host + 24h soak  
5. Signed PyInstaller/MSI/DMG clean-room installs  
6. Full mutmut on `mailer_studio.py` / `drafts.py` / `security.py`
