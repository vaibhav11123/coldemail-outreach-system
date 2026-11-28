# Customer-experience remediation tracker

Source: customer audit of `demo_detailed_tour.mp4` (14:41) and `demo_supplemental_tracker_reader.mp4` (3:05). Ratings in that audit are simulated-buyer judgments, not a live study. Neither recording opened `GlobalResearch.xlsx` in Excel, so workbook items need proof against a real package, not only the Studio UI.

Locked approach: fix contracts and presentation of existing functionality. Do not add relationship-graph, trajectory or interview-prep modules. Do not weaken cryptographic checks. Do not invent catalog rows to fill Excel tabs.

**Progress: 20 / 80** (checked = implemented in this branch and verified in code or by a test; partial work stays unchecked and says what is left).

How to use: tick an item only when the behaviour exists in the tree and you can point at the file or test. If something is only partly done, leave it unchecked and note the gap.

---

## Block 1 — P0 critical functionality and security (8 / 10)

- [x] 1. Licence issuer mismatch recovery. `.aslic` is verified against the issuer key embedded in the purchased package (or `STUDIO_TRUSTED_ISSUER_PUBLIC`), not the operator `issuer_keys()`. Customer text and stable codes `AS-LIC-ISSUER-MISMATCH`, `AS-LIC-EXPIRED`, `AS-LIC-SIGNATURE`, `AS-LIC-DEVICE` (`studio/dataset/reader_routes.py`). The graphical picker and auto-locate are tracked in Block 7, item 6.
- [x] 2. Historical HR contacts excluded from customer releases. `/planner` and the HR queue are gated by `STUDIO_ENABLE_HR_PLANNER` (default off, `studio/app.py`); Planner is hidden from the nav when gated; `studio/packaging_scan.py` denies `cold_email_outreach*` files, `dev_issuer*`, `issuer_vault*`, the delivery ledger and payment events. Tests that exercise the HR queue must set the gate (`test_hr_csv_sent_status_unchanged_after_planner_refresh` does not yet and fails against the current tree).
- [x] 3. Genuinely non-sending test mail. Transport modes `preview`, `simulation`, `send_test`, `production` (`studio/mailer_studio.py`, `STUDIO_MAIL_MODE`). Open: `studio/templates/planner.html` still says "Test mode still sends real mail" (page is gated off for customers); no dedicated mode test yet.
- [x] 4. Sending limits reconciled. Academic default stays `DEFAULT_DAILY_LIMIT = 20` (`studio/mail/quotas.py`); the 400 HR cap is applied only when the HR planner gate is on (`studio/app.py`).
- [x] 5. Deterministic draft and validator share one contract. Hard evidence violations (`has_hard_evidence_violation`, `studio/drafts.py`) are split from soft warnings; the offline template no longer fails the invented-token check (`studio/drafting/quality.py`, `studio/drafting/fallback.py`).
- [x] 6. Approve and send enforce hard failures. `approve_draft` raises on `hard_fail` (`studio/drafts.py`); covered by `test_INV04_approve_draft_blocks_invented_url`.
- [x] 7. Expired effective status. `effective_opportunity_status` separates reported from effective status and demotes expired openings (`studio/status_labels.py`, `studio/templates/opportunity.html`). The single Prepare CTA is tracked in Block 4, item 7.
- [ ] 8. Qualify AI and email Connect states. No Connect button for integrations a buyer cannot complete (Gmail/Outlook until production OAuth ships; ChatGPT/Copilot until eligibility is finished). States: Connect/Connected, Set up, Unavailable on this device, Not available in this release, Open external AI, Connection issue.
- [x] 9. Private data kept out of releases. `scan_package_dir` rejects HR CSVs, operator DBs, secrets, `dev_issuer.json`, `.env` and `.pem` files (`studio/packaging_scan.py`; `test_packaging_scan_rejects_issuer_secret`).
- [ ] 10. Purchase-to-catalog smoke test. Fulfil, package, activate, then browse the Faculty Library offline with no AI; documented and automated end to end.

## Block 2 — P0 dataset commercial readiness (6 / 10)

- [ ] 1. Inspect the real master catalog against what is packaged (field coverage, row counts, duplicates). The cold-email master lead file is campaign state and is never packaged.
- [ ] 2. Prove field parity across Excel, CSV, JSON and SQLite for the same delivery (a test that diffs factual fields after label mapping).
- [ ] 3. Verify ranking claims and ranking year against a documented source; remove or qualify any claim that cannot be verified on the offer page and in Coverage.
- [x] 4. Workbook opens on **Start Here** (title and year, counts, navigation hyperlinks, how-to) and has a **Coverage** sheet (universities, research-area hints, completeness percentages calculated from the data). `studio/dataset/workbook.py`; `test_dataset_workbook.py`.
- [x] 5. **Faculty Directory** is a native Excel table with filters, frozen header, readable column names, readable status/funding labels via `format_tri_state`, `Export ID` kept, clickable URLs, ISO dates as Excel dates.
- [x] 6. **Publications** and **Sources** sheets appear only when paper titles or URLs exist; no funding or opportunity sheets are fabricated. Country statistics appear only when a `country` field exists.
- [x] 7. **Data Dictionary**, **Quality Report** (completeness, freshness, integrity, known limits) and **Changelog** (packaging date and record count stub). Hidden **Provenance** sheet kept; creator metadata is "Academic Studio".
- [x] 8. 20–25 record redistributable sample pack (`studio/dataset/sample_pack.py`, CLI `sample-pack`): unmodified catalog rows, ordinal Export IDs, no customer fingerprint, optional email masking.
- [x] 9. `START_HERE.txt` and `Data_Dictionary.txt` list the workbook sheets and match the workbook column names; `GlobalResearch.xlsx` alias retained.
- [ ] 10. Open a real package's `GlobalResearch.xlsx` in Excel and LibreOffice (tables, links, freeze panes, hidden sheet) and keep the screenshots as demo proof. Not done: no spreadsheet application was available when the workbook was written; it was validated with openpyxl and by inspecting the table XML.

## Block 3 — P1 visual system (1 / 10)

- [ ] 1. One customer-facing name, **Academic Studio** (dataset: Global Research Dataset). Page titles in `hosted.html`, `connect_ai.html` and `fetch_confirm.html` still say "Academic Outreach Studio".
- [ ] 2. Solid canvas `#F5F7F8` replaces the misty gradient.
- [ ] 3. Full-width workspace shell (the 980px `main` cap lifted for workspace pages).
- [ ] 4. Design tokens applied: surface `#FFFFFF`, ink `#172B2A`, action `#246B58`, border `#DCE5E2`, secondary `#63736E`.
- [ ] 5. Layouts A (workspace), B (split pane) and C (focused/narrow) applied to the screens that need them.
- [ ] 6. Controls 36–40px high, 6–8px radius, one icon set.
- [ ] 7. Typography: Fraunces for major headings, Sora for UI; body 14–16px, table 13–14px.
- [ ] 8. Meaningful empty states (dashboard, drafts, tracker) with a next action; Delete is not the dominant action.
- [x] 9. Shared status-label helper `studio/status_labels.py` (`format_tri_state`, `effective_opportunity_status`, `format_application_state`, `format_deadline`, `last_verified_label`) with unit tests in `test_status_labels.py`. Adoption on every surface is tracked in Block 4, item 10.
- [ ] 10. Visible keyboard focus and WCAG 2.2 AA contrast (4.5:1 text) checked on the main screens.

## Block 4 — P1 discovery (0 / 10)

- [ ] 1. Catalog-first Start page: purchased library dominant, imports secondary, persistent demo banner.
- [ ] 2. One Faculty Library: Directory and Reader unified with source filters All / Purchased / Imports / Shortlisted.
- [ ] 3. Full-width table toolbar: search, country/university/research-area/funding/recruitment filters.
- [ ] 4. Sortable headers and `N of M` count; "hybrid retrieval" hidden behind a tooltip.
- [ ] 5. Row selection with batch shortlist and compare.
- [ ] 6. Compare without comma-separated internal IDs (selection tray from the library).
- [ ] 7. Faculty profile as parent, opportunities and papers as children; one **Prepare application** button (the opportunity page still shows both "Write letter" and "Prepare draft").
- [ ] 8. Match scores explained; missing evidence separated from weak fit; scores not inflated.
- [ ] 9. Recommended researchers kept separate from My shortlist; rebuilding recommendations never wipes the shortlist.
- [ ] 10. Human status labels on every catalog surface. Directory, shortlist, compare, opportunity and demo templates use the helper; Reader, tracker and dashboard still show raw tokens or dashes.

## Block 5 — P1 onboarding and drafting (1 / 10)

- [ ] 1. Profile onboarding is a single **1 of 3** (CV, experience, preferences).
- [ ] 2. CV drag-and-drop is primary; **Skip for now** goes to browsing the full library.
- [ ] 3. Field UX: goal examples, degree select, graduation year, searchable countries, funding-need enum, interest chips, project cards.
- [ ] 4. Natural deterministic letter prose: subject, greeting, first-person projects tied to the faculty's research, signature, without field-label leakage or uncited achievements.
- [ ] 5. Evidence inspector beside the letter (split pane), with hard failures separated from soft warnings in the UI.
- [ ] 6. Claim recovery: the specific unsupported sentence and its source issue are shown, with repair or removal offered.
- [ ] 7. AI handoff wizard: select service, copy or open, paste, inspect claims, accept; handoff distinguished from a connected subscription.
- [ ] 8. AI rewrite is validated before it replaces the accepted draft.
- [x] 9. Editing a draft clears its approval and approval locks the exact content hash (`approved_hash` reset on save, `content_hash` compared on approve, `studio/drafts.py`).
- [ ] 10. Drafts library shows researcher, institution, subject, modified date and validation/approval state, with an empty state that links to the shortlist and library.

## Block 6 — P1 applications and tracking (0 / 10)

- [ ] 1. Full-width Kanban with summary cards.
- [ ] 2. Status and notes edited in a detail panel, not mini-forms on every card.
- [ ] 3. Application state labels from `format_application_state` shown in the tracker (database enums unchanged).
- [ ] 4. Keyboard-accessible column moves.
- [ ] 5. Timeline with human dates, event types and links back to the application.
- [ ] 6. Applied or submitted never implies an email was sent; manual and sent are distinct.
- [ ] 7. Delete workspace moved to Settings, Privacy.
- [ ] 8. Export clarity: tracker, shortlist, faculty dataset and complete workspace are named and described separately.
- [ ] 9. Reminders and return copy written for customers (no internal "retention hook" wording).
- [ ] 10. Dashboard next actions: first-run versus returning states, drafts, deadlines and shortlist previews.

## Block 7 — P1 integrations and settings (2 / 10)

- [ ] 1. Task-grouped Settings (Email, Writing assistant, Research, Profile, Library, Advanced); the large Connections page is no longer the primary entry.
- [ ] 2. Developer terms hidden from customer copy (OAuth client IDs, "Reverse integration", "CC0 snapshot", "Register public OAuth app").
- [ ] 3. Groq guided setup keeps the 4-step assistant and hides scraping/cookie details from the primary path.
- [ ] 4. Email setup: provider detection, Set up later, and Gmail/Microsoft only when production OAuth is packaged.
- [x] 5. `.eml` fallback for sending (offline export is exercised by `test_E2E02_offline_eml_export`).
- [ ] 6. Graphical catalog package picker and auto-locate of the installed catalog.
- [ ] 7. Licence recovery screen reached from the catalog error, with Recover purchase and expandable technical details.
- [ ] 8. Backup page: contents summary, last backup date, restore preview and confirm, schema/version check; device private keys never restored as a licence transfer.
- [x] 9. Hosted account UI is hidden unless `STUDIO_SHOW_HOSTED=1` (`studio/app.py`, `studio/templates/base.html`).
- [ ] 10. Multi-profile copy states that profiles are personas under one individual licence.

## Block 8 — P1 sales demonstrations (2 / 10)

Long QA recordings stay internal. See `SALES_DEMO_STORYBOARDS.md`.

- [ ] 1. Production-UI recording hygiene applied to every shipped clip (checklist in the storyboards file).
- [ ] 2. Marketplace cover led by the dataset with real workbook imagery.
- [ ] 3. Workbook gallery (Start Here, Coverage, Faculty Directory, Data Dictionary) from a real package.
- [ ] 4. Studio gallery from the production UI with real data.
- [x] 5. 45–60 second dataset video storyboard written.
- [x] 6. 60–90 second Studio video storyboard written.
- [ ] 7. Dataset sales video recorded from the real workbook.
- [ ] 8. Studio sales video recorded from the production UI.
- [ ] 9. 8–15 minute tutorial and feature comparison table.
- [ ] 10. Install and recovery docs plus a usability walkthrough against the acceptance tests below.

---

## Customer acceptance tests

The original audit's acceptance table is not stored in this repository. The tasks below are derived from the remediation plan's verification phase and the flows the audit followed. Targets are goals for a first-time buyer, not measured SLAs. "Automated" lists what already guards the behaviour; the manual column stays open until someone runs the walkthrough on a production build.

| # | Customer task | Goal | Automated guard | Manual result |
| --- | --- | --- | --- | --- |
| 1 | Open the purchased catalog after activating a licence, even when the local operator issuer differs | Catalog opens first try; on failure a plain-language recovery screen with a stable code | `test_reader_ui_with_package` (matching issuer); mismatched-issuer test not yet written | Not run |
| 2 | Find the dataset workbook and learn what is inside | `Start Here` is the first sheet; sheets are linked and described within one minute | `test_dataset_workbook.py` | Not run |
| 3 | Filter the faculty directory by university and see how many match | Filter in Excel table, or in Studio with an `N of M` count | Workbook table test; Studio count not yet tested | Not run |
| 4 | Judge how complete the data is before buying | Coverage and Quality Report show percentages calculated from the data | `test_coverage_completeness_calculated` | Not run |
| 5 | Preview the product without paying | 20–25 record sample (xlsx + csv) available for the listing | `test_sample_pack_is_subset_unfingerprinted` | Not run |
| 6 | Read an opportunity whose deadline has passed | Shown as Expired; no prominent Prepare action; historical evidence kept | `test_status_labels.py` (helper); UI test not yet written | Not run |
| 7 | Compare two researchers | Pick from the library; no internal IDs typed or shown | None yet | Not run |
| 8 | Prepare a first draft from a faculty page | Built-in draft passes mandatory checks without AI | Draft quality tests; INV04 | Not run |
| 9 | Edit an approved draft | Approval clears and the edit is revalidated | `studio/drafts.py` behaviour; no dedicated test yet | Not run |
| 10 | Try to approve a draft containing an invented claim | Approval blocked with the unsupported sentence named | `test_INV04_approve_draft_blocks_invented_url` | Not run |
| 11 | Move an application across the tracker and add a note | Detail panel edits; timeline shows a human-readable event | None yet | Not run |
| 12 | Send a test email safely | Preview or Simulation never contacts a mail provider | Mode helper in `mailer_studio.py`; no dedicated test yet | Not run |
| 13 | Check that nothing from the seller's own outreach ships | Staged customer folder contains no HR CSV, operator DB or issuer key | `scan_package_dir` tests | Not run |
| 14 | Find the licence and recover a purchase | Licence page and Recover purchase reachable in two clicks | Activation page tests | Not run |
| 15 | Back up and restore the workspace | Restore shows a preview and asks to confirm | None yet | Not run |
