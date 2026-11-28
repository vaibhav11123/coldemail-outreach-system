# Customer-experience remediation tracker

Source: customer audit of `demo_detailed_tour.mp4` (14:41) and `demo_supplemental_tracker_reader.mp4` (3:05). Ratings in that audit are simulated-buyer judgments, not a live study. Neither recording opened `GlobalResearch.xlsx` in Excel, so workbook items need proof against a real package, not only the Studio UI.

Locked approach: fix contracts and presentation of existing functionality. Do not add relationship-graph, trajectory or interview-prep modules. Do not weaken cryptographic checks. Do not invent catalog rows to fill Excel tabs.

**Progress: 46 / 80** (checked = implemented in this branch and verified in code or by a test; partial work stays unchecked and says what is left).

How to use: tick an item only when the behaviour exists in the tree and you can point at the file or test. If something is only partly done, leave it unchecked and note the gap.

---

## Block 1 — P0 critical functionality and security (8 / 10)

- [x] 1. Licence issuer mismatch recovery. `.aslic` is verified against the issuer key embedded in the purchased package (or `STUDIO_TRUSTED_ISSUER_PUBLIC`), not the operator `issuer_keys()`. Customer text and stable codes `AS-LIC-ISSUER-MISMATCH`, `AS-LIC-EXPIRED`, `AS-LIC-SIGNATURE`, `AS-LIC-DEVICE` (`studio/dataset/reader_routes.py`). Covered by `test_reader_trusts_package_issuer_not_operator`. The graphical picker and auto-locate are tracked in Block 7, item 6.
- [x] 2. Historical HR contacts excluded from customer releases. `/planner` and the HR queue are gated by `STUDIO_ENABLE_HR_PLANNER` (default off, `studio/app.py`); Planner is hidden from the nav when gated; `studio/packaging_scan.py` denies `cold_email_outreach*` files, `dev_issuer*`, `issuer_vault*`, the delivery ledger and payment events. HR planner tests set the gate (`test_mail_planner.py`).
- [x] 3. Genuinely non-sending test mail. Transport modes `preview`, `simulation`, `send_test`, `production` (`studio/mailer_studio.py`, `STUDIO_MAIL_MODE`). Planner copy states simulation never sends; `test_mail_mode_simulation_never_hits_smtp` and `test_planner_copy_never_claims_test_mode_sends` cover the contract.
- [x] 4. Sending limits reconciled. Academic default stays `DEFAULT_DAILY_LIMIT = 20` (`studio/mail/quotas.py`); the 400 HR cap is applied only when the HR planner gate is on (`studio/app.py`).
- [x] 5. Deterministic draft and validator share one contract. Hard evidence violations (`has_hard_evidence_violation`, `studio/drafts.py`) are split from soft warnings; the offline template no longer fails the invented-token check (`studio/drafting/quality.py`, `studio/drafting/fallback.py`).
- [x] 6. Approve and send enforce hard failures. `approve_draft` raises on `hard_fail` (`studio/drafts.py`); covered by `test_INV04_approve_draft_blocks_invented_url` and `test_draft_blocks_approve_on_hard_fail`.
- [x] 7. Expired effective status. `effective_opportunity_status` separates reported from effective status and demotes expired openings (`studio/status_labels.py`, `studio/templates/opportunity.html`). Single **Prepare application** CTA verified in `test_opportunity_open_has_single_primary_prepare`.
- [x] 8. Qualify AI and email Connect states. Gmail/Outlook show **Not available in this release** unless packaged OAuth client IDs exist (`mail.html`, `gmail_oauth_ready` / `outlook_oauth_ready`). AI cards already gate unavailable providers. Remaining vocabulary gaps (device-unavailable / connection-issue wording) are polish only.
- [x] 9. Private data kept out of releases. `scan_package_dir` rejects HR CSVs, operator DBs, secrets, `dev_issuer.json`, `.env` and `.pem` files (`studio/packaging_scan.py`; `test_packaging_scan_rejects_hr_csv`, `test_packaging_scan_rejects_issuer_secret`).
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

## Block 3 — P1 visual system (8 / 10)

- [x] 1. One customer-facing name, **Academic Studio** (dataset: Global Research Dataset). Page titles across base, offer, dashboard, profile, start, directory, opportunity, drafts, tracker, connections, activate, backup, return, connect_ai, mail, hosted and fetch_confirm use Academic Studio (no remaining "Academic Outreach Studio" titles).
- [x] 2. Solid canvas `#F5F7F8` replaces the misty gradient (`--canvas` / `--paper` in `studio/static/studio.css`; no misty gradient remains).
- [x] 3. Full-width workspace shell (`main.layout-workspace` up to 1400px) on directory, tracker, compare, reader and dashboard; split and focus layouts for draft/opportunity and activate (`test_layout_classes_per_page`).
- [x] 4. Design tokens applied: surface `#FFFFFF`, ink `#172B2A`, action `#246B58` (`--sea`), border `#DCE5E2` (`--line`), secondary `#63736E` (`--muted-text`).
- [x] 5. Layouts A (workspace), B (split pane) and C (focused/narrow) applied via `layout-workspace`, `layout-split` and `layout-focus` on the screens that need them.
- [ ] 6. Controls 36–40px high, 6–8px radius, one icon set. Gap: radius is 6px, but primary buttons are 44px high and there is no shared icon set (text-only controls).
- [x] 7. Typography: Fraunces for major headings, Sora for UI (`base.html` font link; `--font-display` / `--font-body`); body 16px, table/meta copy ~13–14px.
- [x] 8. Meaningful empty states (dashboard first-run vs returning, drafts, tracker) with a next action; Delete is not on the Applications board (`test_tracker_has_no_inline_delete`).
- [x] 9. Shared status-label helper `studio/status_labels.py` (`format_tri_state`, `effective_opportunity_status`, `format_application_state`, `format_deadline`, `last_verified_label`) with unit tests in `test_status_labels.py`. Adoption on catalog surfaces is tracked in Block 4, item 10.
- [ ] 10. Visible keyboard focus and WCAG 2.2 AA contrast (4.5:1 text) checked on the main screens. Gap: `:focus-visible` rings ship in CSS; contrast has not been audited with a formal AA pass on the main screens.

## Block 4 — P1 discovery (5 / 10)

- [x] 1. Catalog-first Start page: purchased / Summer library dominant, imports secondary, persistent demo banner (`studio/templates/start.html`).
- [ ] 2. One Faculty Library: Directory and Reader unified with source filters All / Purchased / Imports / Shortlisted. Gap: `/directory` and `/reader` remain separate surfaces without those source filters.
- [ ] 3. Full-width table toolbar: search, country/university/research-area/funding/recruitment filters. Gap: directory toolbar has search, university, funding and recruiting; country and research-area filters are missing.
- [ ] 4. Sortable headers and `N of M` count; "hybrid retrieval" hidden behind a tooltip. Gap: directory shows `N of M` and inline "keyword + semantic match"; column headers are not sortable and there is no hybrid-retrieval tooltip.
- [ ] 5. Row selection with batch shortlist and compare. Gap: compare checkboxes and selection tray exist (`test_directory_has_compare_checkboxes_and_tri_state`); batch shortlist is not implemented.
- [x] 6. Compare without comma-separated internal IDs (selection tray from the library / shortlist pickers; `test_compare_accepts_compare_ids`).
- [x] 7. Faculty-led opportunity page with papers beside the opening; one **Prepare application** button (expired openings demote to "Prepare application anyway"; `test_opportunity_expired_demotes_prepare`).
- [x] 8. Match scores explained; missing evidence separated from weak fit; scores not inflated (compatibility index + why/gaps + disclaimer on shortlist and opportunity; `match_intel.py`).
- [ ] 9. Recommended researchers kept separate from My shortlist; rebuilding recommendations never wipes the shortlist. Gap: Recommended / All saved views exist, but `rebuild_shortlist` still `DELETE`s every `shortlist_item` and reinserts all openings.
- [x] 10. Human status labels on every catalog surface. Directory, reader, shortlist, compare, opportunity, demo and tracker use `tri_state` / `app_state` / deadline helpers (no raw `stated-*` in row bodies).

## Block 5 — P1 onboarding and drafting (8 / 10)

- [x] 1. Profile onboarding is a single **1 of 3** (CV, confirm, preferences) (`studio/templates/profile.html`; `test_profile_single_progress`).
- [x] 2. CV drag-and-drop is primary; **Skip for now** goes to browsing the full library (`href="/directory"`).
- [ ] 3. Field UX: goal examples, degree select, graduation year, searchable countries, funding-need enum, interest chips, project cards. Gap: goal, degree, year and funding-need selects exist; countries are a plain text field; interests/projects are free-text, not chips/cards.
- [x] 4. Natural deterministic letter prose: subject, greeting, first-person projects tied to the faculty's research, signature, without field-label leakage (`studio/drafting/fallback.py` cleans leaked labels).
- [x] 5. Evidence inspector beside the letter (split pane), with hard failures separated from soft warnings in the UI (`draft.html` Must fix / Worth improving; `test_draft_blocks_approve_on_hard_fail`).
- [ ] 6. Claim recovery: the specific unsupported sentence and its source issue are shown, with repair or removal offered. Gap: quality panel names the check, not the sentence; no repair/remove actions.
- [x] 7. AI handoff wizard: select service, copy or open, paste, inspect claims, accept; handoff distinguished from a connected subscription (`draft.html` details + `handoff-import`).
- [x] 8. AI rewrite is validated before it replaces the accepted draft (`validate_rewrite` / rejected claims on `/draft/.../rewrite` and handoff import).
- [x] 9. Editing a draft clears its approval and approval locks the exact content hash (`approved_hash` reset on save, `content_hash` compared on approve, `studio/drafts.py`).
- [x] 10. Drafts library shows researcher, institution, subject, modified date and validation/approval state, with an empty state that links to the shortlist and library (`drafts.html`; `test_drafts_empty_state_links`).

## Block 6 — P1 applications and tracking (5 / 10)

- [ ] 1. Full-width Kanban with summary cards. Gap: full-width Kanban ships (`layout-workspace` + `.kanban`); no summary cards above the board.
- [ ] 2. Status and notes edited in a detail panel, not mini-forms on every card. Gap: each card still has inline state and notes forms (`tracker.html`).
- [x] 3. Application state labels from `format_application_state` shown in the tracker (database enums unchanged; `test_tracker_uses_human_states`).
- [ ] 4. Keyboard-accessible column moves. Gap: moves use a select + Move button only; no keyboard column shortcuts.
- [ ] 5. Timeline with human dates, event types and links back to the application. Gap: human dates and state labels exist; no event-type taxonomy or links back to a specific application.
- [x] 6. Applied or submitted never implies an email was sent; manual and sent are distinct (`submitted_by_me` → "Submitted manually"; draft "I sent this" path).
- [x] 7. Delete workspace moved to Settings, Privacy (`connections.html#privacy`; `test_tracker_has_no_inline_delete`).
- [ ] 8. Export clarity: tracker, shortlist, faculty dataset and complete workspace are named and described separately. Gap: Privacy offers applications CSV and Backup only; shortlist / faculty dataset exports are not named separately.
- [x] 9. Reminders and return copy written for customers (no internal "retention hook" wording; `test_return_has_no_retention_language`).
- [x] 10. Dashboard next actions: first-run versus returning states, drafts, deadlines and shortlist previews (`dashboard.html` first-run / returning branches + action list).

## Block 7 — P1 integrations and settings (4 / 10)

- [x] 1. Task-grouped Settings (Email, Artificial intelligence, Research sources, Academic profile, Documents) with chip nav; Settings is the primary entry in More (`connections.html`, `sections_for_ui`).
- [ ] 2. Developer terms hidden from customer copy (OAuth client IDs, "Reverse integration", "CC0 snapshot", "Register public OAuth app"). Gap: ORCID/OpenCitations still say CC0; mail Advanced still exposes OAuth client ID fields.
- [x] 3. Groq guided setup keeps the 4-step assistant and hides scraping/cookie details from the primary path (`groq_connect.html`).
- [ ] 4. Email setup: provider detection, Set up later, and Gmail/Microsoft only when production OAuth is packaged. Gap: discovery and Set up later exist; Gmail/Microsoft Connect buttons remain always available.
- [x] 5. `.eml` fallback for sending (offline export is exercised by `test_E2E02_offline_eml_export`).
- [ ] 6. Graphical catalog package picker and auto-locate of the installed catalog. Gap: configured-package auto-locate exists (`_default_package_dir`); path is still a text field, not a graphical picker.
- [ ] 7. Licence recovery screen reached from the catalog error, with Recover purchase and expandable technical details. Gap: issuer-mismatch recovery copy and Help links exist on Activate; no dedicated Recover-purchase CTA with expandable stable codes from the Reader error state.
- [ ] 8. Backup page: contents summary, last backup date, restore preview and confirm, schema/version check; device private keys never restored as a licence transfer. Gap: summary, last backup and confirm exist (`test_backup_summary_and_restore_confirmation`); no restore contents preview or schema/version check UI (secrets are excluded from the zip).
- [x] 9. Hosted account UI is hidden unless `STUDIO_SHOW_HOSTED=1` (`studio/app.py`, `studio/templates/base.html`; `test_planner_and_hosted_hidden_by_default`).
- [ ] 10. Multi-profile copy states that profiles are personas under one individual licence. Gap: return Profiles copy explains separate people you help; it does not state the one-individual-licence constraint.

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
- [ ] 9. 8–15 minute tutorial and feature comparison table. Gap: `FEATURE_COMPARISON.md` exists; the tutorial recording does not.
- [ ] 10. Install and recovery docs plus a usability walkthrough against the acceptance tests below. Gap: `INSTALL_AND_RECOVERY.md` exists; the acceptance walkthrough has not been run.

---

## Customer acceptance tests

The original audit's acceptance table is not stored in this repository. The tasks below are derived from the remediation plan's verification phase and the flows the audit followed. Targets are goals for a first-time buyer, not measured SLAs. "Automated" lists what already guards the behaviour; the manual column stays open until someone runs the walkthrough on a production build.

| # | Customer task | Goal | Automated guard | Manual result |
| --- | --- | --- | --- | --- |
| 1 | Open the purchased catalog after activating a licence, even when the local operator issuer differs | Catalog opens first try; on failure a plain-language recovery screen with a stable code | `test_reader_trusts_package_issuer_not_operator`; mismatched-issuer UI recovery still manual | Not run |
| 2 | Find the dataset workbook and learn what is inside | `Start Here` is the first sheet; sheets are linked and described within one minute | `test_dataset_workbook.py` | Not run |
| 3 | Filter the faculty directory by university and see how many match | Filter in Excel table, or in Studio with an `N of M` count | Workbook table test; Studio shows `N of M` (`directory.html` / `reader.html`) | Not run |
| 4 | Judge how complete the data is before buying | Coverage and Quality Report show percentages calculated from the data | `test_coverage_completeness_calculated` | Not run |
| 5 | Preview the product without paying | 20–25 record sample (xlsx + csv) available for the listing | `test_sample_pack_is_subset_unfingerprinted` | Not run |
| 6 | Read an opportunity whose deadline has passed | Shown as Expired; no prominent Prepare action; historical evidence kept | `test_opportunity_expired_demotes_prepare` | Not run |
| 7 | Compare two researchers | Pick from the library; no internal IDs typed or shown | `test_directory_has_compare_checkboxes_and_tri_state`, `test_compare_accepts_compare_ids` | Not run |
| 8 | Prepare a first draft from a faculty page | Built-in draft passes mandatory checks without AI | Draft quality tests; INV04 | Not run |
| 9 | Edit an approved draft | Approval clears and the edit is revalidated | `studio/drafts.py` behaviour; no dedicated test yet | Not run |
| 10 | Try to approve a draft containing an invented claim | Approval blocked with the unsupported sentence named | `test_INV04_approve_draft_blocks_invented_url`; UI blocks approve (`test_draft_blocks_approve_on_hard_fail`) | Not run |
| 11 | Move an application across the tracker and add a note | Detail panel edits; timeline shows a human-readable event | Human state labels covered; detail panel / event links still open | Not run |
| 12 | Send a test email safely | Preview or Simulation never contacts a mail provider | `test_mail_mode_simulation_never_hits_smtp` | Not run |
| 13 | Check that nothing from the seller's own outreach ships | Staged customer folder contains no HR CSV, operator DB or issuer key | `scan_package_dir` tests | Not run |
| 14 | Find the licence and recover a purchase | Licence page and Recover purchase reachable in two clicks | Activation page tests | Not run |
| 15 | Back up and restore the workspace | Restore shows a preview and asks to confirm | Confirm covered (`test_backup_summary_and_restore_confirmation`); contents preview still open | Not run |
