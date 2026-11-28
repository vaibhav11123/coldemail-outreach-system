# Groq Connect Assistant

User-authorized BYOG onboarding. Minimizes credential friction without inventing OAuth.

## Layout

| Module | Role |
| --- | --- |
| `connection_state.py` | Phase machine (idle → import → validate → connected / errors) |
| `browser_launcher.py` | Opens official `console.groq.com` only |
| `credential_import.py` | Explicit paste + consented `GROQ_API_KEY` detection |
| `credential_validator.py` | Official models API validation |
| `model_discovery.py` | Prefer GPT-OSS / Llama for letter polish |
| `keychain.py` | OS keychain / local secrets persistence |
| `quota_manager.py` | 429 / revoked / unavailable signals |
| `onboarding.py` | Orchestrates the assistant UI |

## Allowed

- Launch official GroqCloud keys page
- Explicit paste of a key the student copied
- Import of local `GROQ_API_KEY` **after** consent
- Validate via documented Groq API
- Store in OS keychain

## Forbidden

- Reading Groq session cookies
- Scraping or automating the dashboard
- Undocumented account-management endpoints
- Claiming this flow is OAuth
- Using `STUDIO_GROQ_API_KEY` as a shared product proxy

## Parallel path

`Connect instant AI` → OpenRouter OAuth PKCE (documented one-touch). Uses the student’s OpenRouter allowance.
