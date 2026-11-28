# Defect register (production qualification pass)

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| PQ-01 | High | After SMTP failure, `create_intent` returned the failed intent and `perform_send` refused (`Cannot send from state failed`), stranding retries | **Fixed** — failed intents reset to `pending` on explicit retry |
| PQ-02 | High | `mark_submitted` ignored rowcount; concurrent workers could both proceed to the provider | **Fixed** — atomic claim returns bool; `perform_send` aborts if unclaimed |
| PQ-03 | Medium | OpenAlex success path called `resp.json()` without guard → could crash UI on garbage payloads | **Fixed** — invalid JSON / non-object → controlled failure |
| PQ-04 | Medium | Support bundle redaction matched exact keys only (`password`), so `smtp_password` / `*_token` leaked into JSON dumps | **Fixed** — substring-sensitive key matching |
| PQ-05 | Medium | Evidence guard missed invented “confirmed funded openings” / GPA claims when a known URL was present | **Fixed** — funding/GPA heuristic in `has_uncited_claim` |
| PQ-06 | High (hosted) | `/hosted` creates account rows but all drafts/profile live in singleton applicant DB — INV-06 fails for commercial multi-tenant | **Open** — disable hosted claims until tenant isolation ships |
| PQ-07 | Release | No signed installer / clean Mac/Windows matrix evidence in this agent environment | **Open / BLOCKED** |
| PQ-08 | Release | No Mailpit live SMTP, real Gmail, Groq quality benchmark, or student usability study executed here | **Open / NOT RUN** |
