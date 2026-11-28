# Bring Your Own AI (BYOAI)

Students connect an existing subscription, free allowance, API account, or local model. The product never pays for their inference.

## Customer journey

1. **Connect free AI** — OpenRouter OAuth PKCE. No key copy. Free models (quota applies) or their credits.
2. **Already have a subscription?** — ChatGPT (pending commercial approval), GitHub Copilot (device login; terms check), Hugging Face (`inference-api`).
3. **Continue without AI** — deterministic evidence-bound draft.
4. **Advanced** — Gemini AI Studio key, Claude API key, Grok API key (OAuth not commercially confirmed), custom OpenAI-compatible endpoint, Ollama detect.

## Architecture

One rewrite engine (`studio/ai/engine.py`) + interchangeable providers. Every AI response is validated; uncited claims fall back to the deterministic draft.

## MCP (reverse BYOAI)

`studio/ai/mcp_server.py` lists tools so eligible AI clients can call our professor database without us holding inference credentials.

## Commercial blockers tracked in UI copy

- ChatGPT: Nov 4 2026 Sign-in terms for paid apps.
- Copilot: confirm research-letter use is permitted.
- Claude Platform OAuth: beta; does not spend Pro/Max.
- Grok browser OAuth: promising open-source reports; not enabled for one-click until xAI permits redistribution.
