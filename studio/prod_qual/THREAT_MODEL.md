# Threat model (desktop + future hosted)

## Assets

Student CV / profile facts, mail credentials and OAuth tokens, AI API keys, drafts, application tracker, inference quota/spend, bundled research library.

## Actors

Curious local process, malicious webpage content (SSRF/prompt injection), careless student (double-send), hostile API client on LAN, future co-tenant on hosted, compromised dependency.

## Top risks (ordered)

1. Duplicate or unapproved email send
2. Credential leakage / cross-customer data
3. AI-approved false academic claims
4. Data loss on crash/upgrade
5. Incorrect opportunity status (funding/eligibility)
6. Auth / provider failure UX that strands the user
7. Install/usability friction
8. Uncontrolled inference spend

## Mitigations present

- Host allowlist + page tokens (`studio/security.py`)
- SSRF IP blocking on fetch
- Send intent state machine + unique content hash + atomic claim
- Evidence-bound approval / rewrite validation
- Personal delete preserves bundled library
- Startup recovery: `submitted` → `unknown_delivery` (no auto-resend)

## Open gaps (release-blocking for commercial hosted)

- Hosted multi-tenant row-level isolation not implemented (INV-06)
- No signed installers / clean-machine matrix in this environment
- No production Sentry / provider health dashboard yet
- Playwright browser E2E, k6 soak, OWASP ZAP, full mutmut: not run here
- Payment / entitlement flows: not implemented
