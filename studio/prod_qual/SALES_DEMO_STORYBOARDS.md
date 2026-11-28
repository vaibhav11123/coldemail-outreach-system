# Sales demo storyboards

Docs only. These storyboards describe clips to record later from a real package and the production UI. Nothing here has been recorded.

Rules for every clip: show real catalog data (redact personal data that is not already public faculty information), never a six-row demo list, never invented numbers. Any figure on screen must come from the workbook's own Coverage or Quality Report sheet.

The long QA recordings (`demo_detailed_tour.mp4`, `demo_supplemental_tracker_reader.mp4`) stay internal. They are for engineering and audit review and are not used for marketing, listings or support.

---

## 1. Dataset video — 45 to 60 seconds

Goal: a buyer understands what the file contains, how complete it is, and that it opens in Excel with nothing to install.

Recorded from: a real `GlobalResearch.xlsx` (or the sample workbook) opened in Excel, 16:9, 1080p.

| Time | Screen | On-screen text / voice-over | Notes |
| --- | --- | --- | --- |
| 0:00–0:05 | Marketplace cover, then cut to the open workbook | "Global Research Dataset: faculty, universities and papers in one workbook." | Cover is the dataset, not Studio |
| 0:05–0:15 | **Start Here** sheet | Title and year, faculty / university / publication counts, the sheet links | Click one navigation link to jump to Coverage |
| 0:15–0:25 | **Coverage** sheet | Completeness table (email, funding stated, deadline present) and the universities list | Read the figures exactly as shown; say "stated by the source", not "available" |
| 0:25–0:38 | **Faculty Directory** | Use the filter arrow on University; type a name in Ctrl+F; open one record's application link | Show frozen header while scrolling; show a readable status label such as "Applications open" |
| 0:38–0:46 | **Data Dictionary** then **Quality Report** | "Unknown means the source did not state it." Point at known limitations | Honesty beat: it builds trust |
| 0:46–0:54 | Folder view of the package | `GlobalResearch.xlsx`, CSV, JSON, SQLite, `START_HERE.txt`, licence | Do not show customer-specific export IDs of a real buyer |
| 0:54–1:00 | Purchase page | Price, "Get the dataset", "View sample" | End card only; no countdown or claims about outcomes |

Do not claim: admission odds, guaranteed funding, rankings that are not documented on the Coverage sheet, or live status ("as reported by the source at collection time").

## 2. Studio video — 60 to 90 seconds

Goal: show the research workflow from catalog to a validated draft and a tracked application, on the production build.

Recorded from: the production Studio build with the real purchased catalog active. No demo workspace banner, no developer tools.

| Time | Screen | On-screen text / voice-over | Notes |
| --- | --- | --- | --- |
| 0:00–0:08 | Launch Studio, Overview | "Academic Studio opens your purchased catalog on your own computer." | Show the real faculty count |
| 0:08–0:22 | **Faculty library** | Search, filter by university, open a faculty profile | Full-width table, `N of M` count visible |
| 0:22–0:32 | **My profile** | Drop a CV, review what was extracted | Use a sample CV with no real personal data |
| 0:32–0:44 | **Research matches** and a faculty detail page | Match explanation, human status labels, official application link | If an opening is expired, show the Expired state |
| 0:44–0:54 | **Compare faculty** | Pick two researchers from the library | No internal IDs on screen |
| 0:54–1:10 | **Draft editor** | Built-in draft, evidence beside the letter, quality checks pass; show a failing claim being blocked and fixed | Offline draft; no AI required. Approve locks the text |
| 1:10–1:20 | **Applications** | Move a card, add a note, open the timeline | Make clear nothing is sent automatically |
| 1:20–1:30 | Price and licence | One personal licence, offline catalog | End card |

Do not show: the HR planner, hosted accounts, API keys, OAuth client IDs, the Connections page, or any real mailbox.

## 3. Recording hygiene checklist

- [ ] Record the production build, not a dev server: no `localhost` port in the address bar, no debug banner.
- [ ] Clean workspace: a dedicated demo OS user and browser profile, no bookmarks bar, no extensions, no devtools, no other windows or notifications visible.
- [ ] 16:9, 1920x1080, 30 fps, system UI scale 100%. Text must stay readable after the marketplace compresses the video; zoom the app to 110–125% if table text is under 13px on a phone-sized preview.
- [ ] Real catalog scale and real data. Do not record the six-row demo set. Redact any personal data beyond public faculty details (your own email, tokens, licence IDs, customer IDs).
- [ ] No dead scroll: script each scroll, keep the mouse moving with purpose, cut waits on loading.
- [ ] No secrets on screen: licence file paths, `.aslic` contents, `.env`, API keys, device IDs.
- [ ] Every number spoken or shown is read off the workbook or app at recording time. Re-record if the data changes.
- [ ] Do not imply outcomes (acceptance, funding, replies) and do not show a real email being sent.
- [ ] Captions on, burned in or as a sidecar file, so the clip works muted.
- [ ] Open the final file on a phone and at 50% size before publishing.
- [ ] Keep the raw recording and the script in the internal archive; ship only the edited clip.

## 4. Long QA videos stay internal

The 14-minute tour and the 3-minute tracker/reader recording show demo data, developer-facing screens and known defects. They are kept for audit and regression review only. Do not upload them to marketplace listings, the website or support articles. Listing assets are the short clips above, a real-workbook screenshot gallery, a Studio screenshot gallery and the 8–15 minute tutorial, all made from the production UI.
