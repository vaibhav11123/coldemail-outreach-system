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
- [ ] Research relationship graph
- [ ] Research trajectory analysis

## 03 — Research preparation · 1/6 verified

- [~] Publication reading workspace (reader + opportunity pubs; not a full paper workspace)
- [ ] Research knowledge base
- [ ] Skill gap analysis
- [ ] Research roadmap generation
- [ ] Research proposal builder
- [ ] Interview preparation

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
- [ ] Complete customer documentation

## 07 — Security and delivery · 4/10 verified

- [x] Shared licensing implementation (Ed25519, X25519 DEK, SQLCipher, fingerprints, manifests)
- [~] Production issuer and protected keys (dev issuer local; production ops incomplete)
- [~] Payment and entitlement lifecycle (webhook + store; live payment provider incomplete)
- [x] Device replacement and revocation APIs
- [x] Dataset fingerprinting + signed manifests
- [x] Encrypted catalog (`.asdb` / `.aspkg`)
- [ ] Signed Windows and macOS installers
- [ ] Secure software updates
- [x] Backup and recovery (`/backup`)
- [~] Piracy monitoring (scaffold CLI)

## 08 — Production qualification · 2/10 verified

- [x] Unit and integration testing (studio/tests; non-live suite green)
- [~] End-to-end customer journeys (partial automated coverage)
- [ ] Adversarial AI testing (full)
- [ ] Security penetration testing
- [~] Fault injection and crash recovery (some INV tests)
- [ ] Performance benchmarking
- [ ] Cross-platform installation testing
- [~] Data integrity verification (packaging + fingerprint tests)
- [ ] Real-user usability testing
- [ ] Release qualification report (NOT READY until above close)

---

## Engineering principles (locked)

- Build for completeness — no deliberately crippled SKUs
- Build for ownership — purchased product is complete
- Build for independence — no mandatory vendor AI credits
- Build for reliability, security, extensibility, quality
- Build before selling — demand validation is not a gate
- One purchase · one individual licence · protection included

## Finished means

A nontechnical student can purchase, install, import a CV, discover researchers, understand their work, prepare credible applications, contact them, and manage the process without operator assistance — with every advertised feature working and known limitations documented.
