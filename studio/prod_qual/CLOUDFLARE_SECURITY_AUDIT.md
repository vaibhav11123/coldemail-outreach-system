# Cloudflare security-audit skill — run log

Installed: `npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit`  
Skill path: `.agents/skills/security-audit` (local agent install; not required for product customers)

## Run-2 (2026-11-28)

| Field | Value |
| --- | --- |
| Profile | `standard` scoped to `studio/` (partial) |
| Output | `~/security-audit-skill/coldemail-outreach-system/run-2` |
| Status | **incomplete** — `partial_hunting_parent_verified_remediation` |
| Validators | `findings.json` PASS (11); `coverage-ledger.json` PASS (14 units) |
| Independent pen-test gate | **Not satisfied** — full hunter-wave matrix and fresh verifier pool incomplete |

### Confirmed defects remediated in-tree

- Backup restore ZipSlip (`studio/backup.py`)
- Forensic zip `extractall` ZipSlip (`studio/dataset/forensic.py`)
- `aslic_basename` path traversal and `package_dir` confinement (`studio/licensing/api.py`)
- DEK cache cleared on revoke (`studio/licensing/dek_cache.py`, `secrets_store.py`)
- Reader page-token `compare_digest` (`studio/dataset/reader_routes.py`)
- Custom AI `base_url` SSRF via `resolve_and_validate` (`studio/ai/providers/custom.py`)
- Upload size caps: CV 5MB, backup restore 50MB, bibliography 2MB (`studio/app.py`)

### Still needs validation / product decision

- Licensing JSON API trusts Host allowlist without page token (localhost peer model)
- Offline `.aslic` residual validity after revoke until TTL
- Signed installers and hardware-backed device binding

### Honesty

This run produced actionable remediations and schema-valid findings. It is **not** a release-gate penetration test. Resume remaining deferred ledger units before claiming full `standard` coverage.

## Run-1 (2026-11-28)

| Field | Value |
| --- | --- |
| Profile | `quick` scoped to `studio/` |
| Output | `~/security-audit-skill/coldemail-outreach-system/run-1` |
| Status | **incomplete** — follow-up queue deferred Phases 2–6 |
| Independent pen-test gate | **Not satisfied** |

### Spot-check finding → fix

Optional webhook secret previously allowed unauthenticated payment/revoke when `STUDIO_LICENSING_WEBHOOK_SECRET` was unset. Fixed to **fail closed** in `studio/licensing/api.py`. Re-checked in run-2 → **rejected** as fixed.

### Alternatives considered (guidance only)

| Skill | Notes |
| --- | --- |
| Cloudflare security-audit | Multi-phase, adversarial verification, machine-readable findings — selected |
| Trail of Bits skills | Strong with CodeQL/Semgrep + PoC tests — useful companion later |
| Anthropic /security-review | Read-only PR focus |
| Sentry / PostHog skills | Exploitability / reproducer-oriented |
