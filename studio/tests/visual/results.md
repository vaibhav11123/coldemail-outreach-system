# Academic Outreach Studio — visual browser protocol results

- URL opened: **http://127.0.0.1:8765/offer** (Chrome, real browser, driven through the desktop GUI)
- Date: 2026-11-28
- Screenshots: `/opt/cursor/artifacts/visual/` (59 PNG files; names start with the screen id `sN_` and the pass `main` / `empty` / `failure`)
- Viewports: Chrome page zoom was used to emulate widths on a 1920-px display. 150% is about 1280 CSS px, 500% is about 384 CSS px (about 390), 100% is 1920 CSS px.
- Colours (from `studio/static/*.css`): background #FFFBEB, primary (brown button) #92400E, stated (green) #065F46, ring #92400E.
  Contrast on #FFFBEB: brown 6.84:1, green 7.41:1. White text on the brown button is 7.09:1. All pass WCAG AA.

## Summary

Each screen has three passes (main / empty / failure). PASS means the control worked and the result words appeared.
PASS* means it worked but there is a defect or rough edge listed under Findings.
Of 30 passes, 21 are PASS, 7 are PASS* and 0 are hard FAIL. 2 are N/A (S0 empty and S5 empty). Every control a student would click worked.

| Screen | Route | Main | Empty | Failure | Evidence (files under /opt/cursor/artifacts/visual/) |
|---|---|---|---|---|---|
| S0 Offer | /offer | PASS | N/A | PASS | s0_main_before_click, s0_main_after_click_profile, s0_main_offer_1280, s0_failure_wrong_host_0000. Offer lists the included items, price, refund and support. There is no send button. Wrong Host returns 403 "Host not allowed". |
| S1 Profile | /profile | PASS | PASS | PASS* | s1_empty_before_blocked_message, s1_main_filled_before_save, s1_main_after_save_flash_Saved, s1_main_facts_Confirmed, s1_failure_empty_blocked_shortlist_message, s1_failure_save_empty_flash_Saved (see F7) |
| S2 Start | /start | PASS | PASS* | PASS | s2_main_start_page_before, s2_main_demo_list_Demo_Stated_Unknown, s2_main_library_list, s2_empty_library_nonsense_no_match, s2_empty_fetch_blank_url_raw_json_422 (F1), s2_failure_secret_url_typed, s2_failure_blocked_destination_error (SSRF block message shown) |
| S3 Opening card | /opportunity/N | PASS | PASS | PASS* | s3_main_alpha_card_stated_1280 (Stated / Unknown), s3_main_alpha_why_it_fits_after_profile, s3_failure_gamma_unknown_funding, s3_empty_beta_stated_closed_no_deadline, s3_main_delta_expired_deadline (F4) |
| S4 Shortlist | /shortlist | PASS | PASS | PASS* | s4_empty_shortlist_blocked, s4_main_shortlist_before_rebuild, s4_main_after_rebuild_flash_Ranked, s4_failure_hide_unknowns_filter, s4_failure_rebuild_with_empty_profile_flash_Ranked (F5, F8) |
| S5 Draft | /draft/1 | PASS | N/A (no draft yet; see S6 empty) | PASS* | s5_main_draft_alpha_body_with_citation, s5_main_draft_restored_cited_not_approved, s5_failure_uncited_body_saved_no_warning, s5_failure_uncited_body_approved_no_check (F3) |
| S6 Tracker | /tracker | PASS | PASS | PASS | s6_empty_tracker, s6_main_tracker_after_draft_ready, s6_failure_delete_wrong_confirm_error. Delete-all with a wrong confirm shows an error and deletes nothing. |
| S7 Mail | /mail | PASS | PASS | PASS* | s7_empty_mail_no_mailbox_connected, s7_empty_no_mailbox, s7_main_save_smtp_127_mailbox_saved (F6), s7_main_send_approved_draft_list_with_mailbox, s7_failure_unapproved_draft_not_offered_no_approved_drafts, s7_failure_send_without_approval_error_not_approved (F9), s7_failure_empty_sender_raw_json_422 (F1) |
| S8 Return | /return | PASS | PASS | PASS* | s8_empty_return_deadlines_none_stale_none, s8_empty_return_none, s8_main_alerts_enabled_saved, s8_failure_empty_profile_label_raw_json_422 (F1) |
| S9 Planner | /planner | PASS | PASS | PASS | s9_main_planner_hr_due_early_missed (Due / Too early / Missed), s9_empty_failed_none_send_disabled (Failed: none), s9_failure_send_hr_disabled_not_allowed_cursor (not-allowed cursor on a disabled send) |

## Responsive (1280-wide and 390-wide) and focus ring

| Check | Result | Evidence |
|---|---|---|
| Offer at 1280 | PASS. Layout is fine and nothing overflows. | s0_viewport1280_offer_zoom150 |
| Offer at 1280, Tab to the primary button | PASS. Each Tab stop (nav links, the mailto link, "Continue to profile") has a visible 2-px brown outline with an offset. The primary button shows the ring. | s0_viewport1280_offer_focus_ring_primary_button, s0_focus_ring_button_1280 |
| Offer at 390 | PASS. The nav wraps to two rows, there is no horizontal scrolling, and the text reflows. | s0_viewport390_offer_top_nav_wraps_zoom500 |
| Offer at 390, focus ring on the primary button | PASS. The ring is a white inner line plus a brown outer line, clearly visible on the brown button. | s0_viewport390_offer_focus_ring_primary_button |
| Opening card at 1280 | PASS | s3_main_alpha_card_stated_1280 |
| Opening card at 390 | PASS. Green "Stated open", "Stated" and "Stated eligible" are readable on the cream/white card. | s3_viewport390_opening_alpha_header_zoom500, s3_viewport390_opening_alpha_green_stated_facts_zoom500 |
| Draft at 1280 / 100% | PASS. Brown Save button, outlined "Approve this exact letter" and the other actions all read well. | s5_main_draft_alpha_body_with_citation, s5_viewport1920_draft_zoom100_brown_buttons |
| Draft at 390 | PASS. The body wraps, and the paper URL citation and the profile project line are visible. The Subject input clips its text (it scrolls inside the input, which is acceptable). | s5_viewport390_draft_recipient_subject_zoom500, s5_viewport390_draft_body_with_citation_zoom500 |
| Brown button (#92400E) and green Stated (#065F46) on #FFFBEB | PASS. Colours match the CSS tokens, and contrast is at least 6.8:1. | All the screenshots above |

## Findings for the parent to fix (none blocks a student; ordered by importance)

- **F1. Raw JSON 422 on empty required fields.** Three forms return FastAPI JSON validation errors instead of a friendly page or flash:
  - `/start` fetch form with a blank URL.
  - `/mail/connect` with an empty From address.
  - `/return/add-profile` with an empty label.
  Suggested fix: make those Form fields default to `""` and validate in the handler, then redirect with `?err=1&flash=<sentence>`.
  Evidence: s2_empty_fetch_blank_url_raw_json_422, s7_failure_empty_sender_raw_json_422, s8_failure_empty_profile_label_raw_json_422.
- **F2. Terse, lowercase error flashes.** The mail guards show "not approved" and "no mailbox". They should be full sentences, for example "This draft is not approved. Approve the exact letter first." and "Connect a mailbox under Mail first." Evidence: s7_failure_send_without_approval_error_not_approved.
  - The UI correctly hides unapproved drafts ("No approved drafts.").
  - The server guard was verified: a direct POST redirects to `/mail?err=1&flash=not approved`. I never sent any mail.
- **F3. An uncited research sentence is accepted and approvable.** Editing the draft body to add a sentence with no citation saves with no warning, and "Approve this exact letter" still works. This contradicts the on-page rule "Every research sentence must cite your confirmed profile or a sourced paper." Evidence: s5_failure_uncited_body_saved_no_warning, s5_failure_uncited_body_approved_no_check. I restored the cited body afterwards.
- **F4. Contradictory facts on the Expired card.** Delta shows "Applications: Stated open" next to an Expired deadline. Show a warning or downgrade the status. Evidence: s3_main_delta_expired_deadline.
- **F5. Raw tokens on the shortlist.** Fact cells show the strings "stated-no" and "unknown" instead of the styled green Stated / Unknown labels used on opening cards. Evidence: s4_main_after_rebuild_flash_Ranked.
- **F6. Flash banner is shown twice** on /mail after saving the mailbox. Evidence: s7_main_save_smtp_127_mailbox_saved.
- **F7 and F8. Misleading flash on a no-op.** Saving an empty profile flashes "Saved" (s1_failure_save_empty_flash_Saved), and rebuilding the shortlist with an empty profile flashes "Ranked" (s4_failure_rebuild_with_empty_profile_flash_Ranked). In both cases the page still says the profile is not confirmed or the shortlist is blocked. Consider flashing "Nothing to save" or "Confirm your profile first".
- **F9. Checkbox layout oddity.** On /shortlist (hide unknowns), /mail and /return (alerts) the checkbox is centered and its label sits below it. Evidence: s4_failure_hide_unknowns_filter, s8_main_alerts_enabled_saved.
- **F10. Page-token forms and curl.** POSTs from curl need the `studio_page_token` cookie plus the hidden `page_token` (scrape it from the HTML). This is working as designed, but the test docs should say so.

## What worked as intended

- Host allowlist: a wrong Host header returns 403 "Host not allowed". The offer page loads only on 127.0.0.1.
- SSRF: pasting http://127.0.0.1/secret into the fetch form shows the blocked-destination error.
- The profile save shows Confirmed. The empty profile shows the blocked-shortlist reason.
- Demo labelling, Stated and Unknown facts, and the Expired deadline all render with the correct words.
- Delete-all with a confirm other than DELETE shows an error. The Planner shows Due / Too early / Missed / Failed for the HR queue, and its disabled send button shows a not-allowed cursor.

## State left in the app DB

Profile confirmed (GPU scheduling / CUDA / the MoE project). Draft 1 has its cited body and is Not approved. The mailbox is 127.0.0.1:1025 from student@127.0.0.1. Return alerts are ON. No mail was sent.

---

# Re-test of the previously defective paths (fixed build)

- Date: 2026-11-28 01:13–01:19 UTC. URL base: http://127.0.0.1:8765. Screenshots are in `/opt/cursor/artifacts/visual/*_fixed.png`.
- **Server note:** at the start of the re-test the app process (pid 6317, started 00:53) predated the fixes in `app.py` (modified 01:12). The first blank-URL test still returned raw JSON 422, and that screenshot is kept as `s2_fetch_blank_url_raw_json_before_restart_STALE_SERVER_fixed.png`. I restarted uvicorn with the same environment (`STUDIO_DATA_DIR=/tmp/studio-visual`, `STUDIO_FORCE_LOCAL_SECRETS=1`, port 8765, tmux session `studio-server`) and re-ran everything on the restarted server. The data was kept.

**Result: 8 PASS, 0 FAIL (item 6 re-tested and fixed; see the update below).**

| # | Check | Result | Evidence and observed words |
|---|---|---|---|
| 1 | Blank URL on /start fetch form gives an HTML flash, not raw JSON | **PASS** | `s2_fetch_blank_url_html_flash_fixed.png`. A red banner on /start reads "Paste an http or https URL first". |
| 2 | Empty From on /mail/connect gives an HTML flash | **PASS** | `s7_mail_empty_from_flash_required_fixed.png`. A red banner on /mail reads "Host and From address are required", and the form is redisplayed. |
| 3 | Empty profile label on /return gives an HTML flash | **PASS** | `s8_return_empty_profile_label_flash_required_fixed.png`. A red banner reads "Profile label is required". |
| 4a | Mail page shows the unapproved draft with a disabled Send and a "Not approved." sentence | **PASS** | `s7_mail_unapproved_draft_disabled_send_not_approved_checkbox_fixed.png`. Under "Send an approved draft" it lists the demo.alpha@example.edu draft, a greyed-out disabled Send, and "Not approved." |
| 4b | No double flash banner after saving the mailbox | **PASS** | `s7_mail_save_mailbox_single_flash_fixed.png`. There is one top banner ("Mailbox saved"). The persistent in-card status line "Mailbox settings saved" is separate status text and is also shown on the empty-From error page. If a single message is wanted, consider hiding that line when a flash is present (cosmetic). |
| 5 | Shortlist shows "Unknown" / "Stated" words, not raw tokens | **PASS** | `s4_shortlist_unknown_stated_words_checkbox_left_fixed.png`. Rows read "Funding: Unknown", "Funding: Stated" (green) and "Funding: Stated no". No `stated-no` token is shown. |
| 6 | Draft: an uncited claim ("I researched quantum underwater basket weaving.", no URL) should make Approve fail with an error flash | **PASS** (re-test 01:19 UTC; the first run FAILED, see the update below) | `s5_draft_uncited_claim_APPROVED_not_blocked_FAIL_fixed.png`. After Save and "Approve this exact letter" the page shows green "Approved" and no error flash. The draft was approved with the claim in its body. The server HTML also contains `<p class="stated">Approved</p>`. See the root cause below. |
| 7 | Expired Delta card still shows Expired, with a muted planning note | **PASS** | `s3_delta_expired_with_planning_note_fixed.png`. "Deadline: ~~2026-11-18~~ Expired", followed by a muted note: "The check date still records what the source said; the deadline is past, so treat this opening as expired for planning." |
| 8 | Checkbox labels left-aligned beside the checkbox on shortlist, mail and return | **PASS** | Shortlist ("Hide unknowns"): `s4_shortlist_unknown_stated_words_checkbox_left_fixed.png`. Mail ("Use STARTTLS" and "Allow reply detection"): `s7_mail_empty_from_flash_required_fixed.png`, `s7_mail_unapproved_draft_disabled_send_not_approved_checkbox_fixed.png`. Return ("Enable deadline and stale alerts"): `s8_return_checkbox_label_left_aligned_fixed.png`. In every case the label sits to the right of the checkbox on the same line. |

## Item 6 root cause (for the parent to fix)

In `studio/drafts.py`, `approve_draft()` builds the evidence list as
`allowed = [row["body"], row["subject"]]` and then adds the publications. The draft **body itself is part of the evidence**, so `has_uncited_claim()` finds every token of the new claim ("quantum", "underwater", "basket", "weaving") in `allowed_lower` and never flags it. Any "I researched …" sentence passes because it is checked against itself.

- Fix: build `allowed` only from the confirmed profile fields (interests, skills, project text), the publication title, url and abstract, and the opportunity facts. Do not include the body, and probably not the subject either.
- Consider a second guard: any sentence that starts with "I researched/studied/worked on/published" must overlap a profile or paper token.
- The error text should come back as a flash, for example `/draft/N?flash=Uncited%20claim%20in%20draft&err=1`. The redirect for `ValueError` already exists in `app.py` (about line 921), so only the evidence list needs fixing. A clearer sentence than "Uncited claim in draft" is also worth considering.
- Mail's Send guard already uses a full sentence ("Draft is not approved. Approve the exact letter first.", `app.py` about line 1240), which looks good, but it was not exercised again in this run.

## State after the re-test

The draft body was restored to the original cited text and saved. It is back to "Not approved." (I deleted the quantum sentence by retyping the body.) The mailbox is saved (127.0.0.1:1025, from student@127.0.0.1) and the profile is still confirmed. Alerts are still ON. No mail was sent. The uvicorn server runs in tmux session `studio-server`.


## Update: item 6 re-test after the `approve_draft` fix (01:19 UTC) — PASS

- Steps: Demo Lab Alpha draft (/draft/1), appended "I researched quantum underwater basket weaving." with no URL, Save, then "Approve this exact letter".
- Observed: a **red error flash** reads "Uncited claim in draft. Remove it or cite a sourced sentence." The URL is `/draft/1?flash=Uncited claim in draft. Remove it or cite a sourced sentence.&err=1`. The status line still reads "Not approved. Editing recipient, subject, or body clears approval." There is no green Approved state.
- Screenshot: `/opt/cursor/artifacts/visual/s5_uncited_blocked_fixed.png`
- The previous failing run is kept as `s5_draft_uncited_claim_APPROVED_not_blocked_FAIL_fixed.png`.
- After the test I restored the cited body (see the note in the final report).

## BYOAI Connect AI

Run: 2026-11-28 01:28–01:33 UTC against http://127.0.0.1:8765/ai. Screenshots are `/opt/cursor/artifacts/visual/byoai_*.png`.

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1a | Page title and h1 read "Connect your AI" | PASS | `byoai_01_main_top_1280.png` (tab title "Connect your AI — Academic Outreach Studio") |
| 1b | "Connect free AI" is the prominent button | PASS | Filled brown primary button inside an accented Free AI card, above the paid-subscription cards. Screenshots 01 and 08 |
| 1c | "Continue without AI" is present | PASS | Secondary button below the provider cards. `byoai_02_collapsed_advanced_continue_1280.png` |
| 1d | Advanced settings is collapsed by default | PASS | `<details class="sheet">` has no `open` attribute. Screenshot 02 |
| 2 | No raw "API key" jargon above the Advanced fold | PASS | In the HTML, "API key" first appears at the `<summary>Advanced settings</summary>` line. Nothing above it. The only mention in the collapsed summary area is the muted line inside the details block. |
| 3 | Continue without AI lands on drafts with a flash | PASS | `/drafts?flash=Continuing with built-in drafts`, neutral banner "Continuing with built-in drafts". `byoai_03_continue_without_ai_drafts_flash.png` |
| 4 | Expanded Advanced shows Gemini, Claude, Grok and custom fields | PASS | Gemini API key + Save; Claude and Grok API key fields; Custom AI provider (base URL, optional key, model id); OpenRouter code paste. Screenshots 04 and 05. The Claude block was confirmed in the HTML and sits between the two screenshots. |
| 5 | Connect free AI navigates toward openrouter.ai | PASS | Network is reachable. Browser landed on `openrouter.ai/sign-up?redirect_url=…callback_url=http://127.0.0.1:8765/ai/callback/openrouter&code_challenge=…` (PKCE). `byoai_06_connect_free_ai_openrouter_signup.png` |
| 6 | Snapshots at 1280 and about 390 | PASS | 1280: screenshots 01–06. About 390: Chrome zoom 500% on a 1920 px screen gives a ~384 px viewport, `byoai_07_narrow_390_top.png` and `byoai_08_narrow_390_connect_free_ai.png`. The nav wraps, the title and Free AI card fit, and there is no horizontal scroll. |

Totals: 8 of 8 checks PASS, 0 FAIL.

Notes:
- Items 1–4 and 6 hold for the page as rendered. The "Powered by OpenRouter" line appears twice in the Free AI card (once before the button, once as the sign-in note). This is redundant but not a defect for this checklist.
- The "Advanced settings" summary shows no visible disclosure triangle in Chrome. It is still clickable and expands.
- After step 5 the browser was left on openrouter.ai and then returned to /ai. No credentials were entered and the zoom was reset to 100%.
