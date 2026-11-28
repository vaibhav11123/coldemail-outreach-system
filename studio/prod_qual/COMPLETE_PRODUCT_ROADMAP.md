# Complete product roadmap (reconciled)

**Direction:** Build the complete commercial-grade workstation before sales focus. Two sold SKUs only; licence included in purchase price; retain the full protection stack.

**Provisional pricing**

| Product | SKU | Price | Licence |
| --- | --- | --- | --- |
| Global Research Dataset | `standard_dataset` | $14.99 | Perpetual individual, included |
| Academic Studio | `academic_studio` | $39.99 | Perpetual individual, 2 devices, included |

`protected_dataset` = internal encrypted packaging alias (not sold).

Legend: `[x]` verified in repo · `[~]` partial / scaffold · `[ ]` not built

**Verified tally (this reconciliation):** 28/63 items fully or substantially verified; many remaining items are advanced modules or production ops.

---

## 01 — Data intelligence · 3/6 verified

- [x] Complete faculty profile schema + Summer/demo loaders (`summer_loader`, opportunity/researcher tables)
- [~] Normalize the complete publication database (schema + OpenAlex/Crossref hooks; full 1,021 audit pending Summer zip in-env)
- [~] Verify institutional rankings and source provenance (source fields present; ranking audit incomplete)
- [ ] Build research taxonomy
- [ ] Implement data freshness and update engine
- [x] Support importing additional researchers (`/add-person`, sheet/URL/faculty import paths)

## 02 — Research discovery · 5/7 verified

- [x] Hybrid semantic and keyword search (`studio/search/` FTS5 + RRF)
- [x] Natural-language faculty discovery (directory hybrid query)
- [x] Advanced filtering and saved searches (`/directory` filters + `saved_search`)
- [x] CV-to-faculty matching (`cv_import`, `matching`, `match_intel`)
- [x] Faculty comparison workspace (`/compare`, `studio/compare.py`)
- [ ] Research relationship graph — **tracked; not demand-blocked**
- [ ] Research trajectory analysis — **tracked; not demand-blocked**

## 03 — Research preparation · 1/6 verified

- [~] Publication reading workspace (reader + opportunity pubs; not a full paper workspace)
- [ ] Research knowledge base — **tracked; not demand-blocked**
- [ ] Skill gap analysis — **tracked; not demand-blocked**
- [ ] Research roadmap generation — **tracked; not demand-blocked**
- [ ] Research proposal builder — **tracked; not demand-blocked**
- [ ] Interview preparation — **tracked; not demand-blocked**

## 04 — Application intelligence · 6/8 verified

- [x] Evidence graph and retrieval (`studio/drafting/` evidence binding)
- [x] Application strategy engine (`drafting/strategy.py`)
- [x] Constrained AI composition + handoff validation
- [x] Multiple writing strategies and tones
- [x] Claim-level verification / quality inspector (`drafting/quality.py`)
- [x] Revision history and approval integrity (draft approve hash)
- [x] Deterministic offline fallback (composer without AI)
- [~] Full adversarial AI test suite (prod_qual INV present; AcademicDraftBench pending)

## 05 — Correspondence and management · 6/8 verified

- [x] Email provider integrations (Gmail/Outlook/SMTP scaffolds)
- [x] Attachment management (`application_file`)
- [x] Reliable approved sending + intent ledger
- [x] Duplicate-send prevention (`send_intent` unique content hash)
- [~] Reply tracking (state machine; inbox sync incomplete)
- [x] Follow-up preparation (reminder writer for submitted apps)
- [x] Application Kanban and timeline (`/tracker`, `/tracker/timeline`)
- [x] Deadline management (deadline field + reminders)

## 06 — Customer experience · 5/8 verified

- [x] CV-first onboarding (PDF/DOCX/TXT import)
- [x] Campaign dashboard redesign (`/dashboard` what-to-do-next)
- [x] Contextual AI connection setup (Connections + Groq Connect)
- [~] Guided first-use experience (step rail; fuller tour pending)
- [~] Universal search and keyboard navigation (directory HTMX; global cmd-K pending)
- [x] Helpful empty states (directory/tracker/dashboard)
- [~] Accessibility and responsive layouts (improved; audit incomplete)
- [ ] Complete customer documentation — **tracked; real usability polish not demand-blocked**

## 07 — Security and delivery · 6/10 verified

- [x] Shared licensing implementation (Ed25519, X25519 DEK, SQLCipher, fingerprints, manifests)
- [~] Production issuer vault (`issuer_vault` + `STUDIO_ISSUER_MODE=production`); live ops still owner-held
- [~] Payment lifecycle (idempotent webhook + events log + fulfil); live merchant still required
- [x] Device replacement and revocation APIs
- [x] Dataset fingerprinting + signed manifests
- [x] Encrypted catalog (`.asdb` / `.aspkg`)
- [ ] Signed Windows and macOS OS installers — **tracked; needs Store/Apple credentials**
- [~] Secure software updates (app-level signed manifests shipped; OS trust UX open)
- [x] Backup and recovery (`/backup`)
- [~] Piracy monitoring (local + allowlisted live URL crawl CLI)

## 08 — Production qualification · 2/10 verified

- [x] Unit and integration testing (studio/tests; non-live suite green)
- [~] End-to-end customer journeys (partial automated coverage)
- [ ] Adversarial AI testing (full)
- [~] Security penetration testing — Cloudflare run-2 incomplete; **not** a release gate
- [~] Fault injection and crash recovery (some INV tests)
- [ ] Performance benchmarking
- [ ] Cross-platform installation testing
- [~] Data integrity verification (packaging + fingerprint tests)
- [ ] Real-user usability testing
- [ ] Release qualification report (NOT READY until above close)

---

## Commercial operating model (locked)

- ₹0 upfront / ₹0 mandatory monthly infrastructure — `ZERO_COST_COMMERCIAL.md`
- Prefer MoR / payment links; eliminate Gumroad/Payhip/Lemon Squeezy as primary — `COMMERCIAL_DISTRIBUTION.md`
- Manual fulfilment first: `python -m studio.dataset fulfil --verified-payment`
- Purchase lifecycle + failure matrix: `PURCHASE_LIFECYCLE.md`
- Graphical activation: `/activate` (+ offline request / `issue-licence`)
- No Keygen subscription; optional Cloudflare Workers later
- Biggest commercial blocker: merchant product-category approval (not engineering)
- Installer binaries still unbuilt (PyInstaller specs only) — do not claim shippable EXE/DMG yet

## Engineering principles (locked)

- Build for completeness — no deliberately crippled SKUs
- Build for ownership — purchased product is complete
- Build for independence — no mandatory vendor AI credits
- Build for reliability, security, extensibility, quality
- Build a sophisticated product, not a sophisticated payment system
- One purchase · one individual licence · protection included

## Finished means

A nontechnical student can purchase, install, import a CV, discover researchers, understand their work, prepare credible applications, contact them, and manage the process without operator assistance — with every advertised feature working and known limitations documented.

## Explicitly unfinished (tracked — not demand-blocked)

These remain open product workstreams; shipping commercial Option A fulfilment does **not** wait on them:

| Item | Tracker |
| --- | --- |
| Research relationship graph | §02 |
| Trajectory / skill-gap engines | §02–§03 |
| Proposal / interview prep | §03 |
| Production issuer ops + live payments | §07 + `PAYMENT_LIFECYCLE_OPS.md` |
| OS-signed installers / notarization | §07 + `packaging/SIGNING.md` |
| Release-gate penetration test | §08 + `CLOUDFLARE_SECURITY_AUDIT.md` |
| Real-user usability testing | §08 |
