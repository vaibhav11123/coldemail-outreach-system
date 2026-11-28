# System inventory — Academic Outreach Studio

Commit under test: see git HEAD at report generation time.

## Surfaces

| Surface | Path / module | Trust boundary |
| --- | --- | --- |
| Local FastAPI UI | `studio/app.py` | Loopback host + page token |
| SQLite WAL DB | `studio/db.py` | Local filesystem |
| Secrets store | `studio/secrets_store.py` | OS keychain / forced local file |
| Deterministic drafts | `studio/drafts.py` | Evidence allow-list |
| Send intents | `studio/mailer_studio.py` | Approval + unique content hash |
| BYOAI / handoff / Groq | `studio/ai/` | Untrusted model output |
| Connections hub | `studio/connections/` | Optional providers |
| Academic adapters | `studio/openalex.py`, `studio/academic/` | Network |
| Mail OAuth / SMTP | `studio/mail/` | OAuth + credentials |
| Hosted scaffolding | `/hosted` | **Not multi-tenant isolated yet** |
| Packaging scan | `studio/packaging_scan.py` | Build-time |
| Support bundle | `studio/support_bundle.py` | Must redact |

## External dependencies (runtime)

OpenAlex, Crossref, OpenCitations, ROR (via connections), Gmail OAuth, Outlook scaffold, SMTP, OpenRouter, Ollama, managed Groq (env), GitHub public API, Zotero local `:23119`.

## Explicitly unavailable / replaced

Semantic Scholar commercial API, unofficial Grok OAuth, Gemini CLI credential borrow, ChatGPT subscription-token bridge, Scholar scraping.
