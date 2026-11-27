# Agent notes

## Cursor Cloud specific instructions

- Run Python from the project venv: `.venv/bin/python` and `.venv/bin/pip`. The install step creates `.venv` from `requirements.txt`. Activating the venv does not persist across a new cloud boot.
- Do not create or commit a `.env` file. Credentials are injected as environment variables. The campaign reads `SENDER_EMAIL` and `SENDER_PASSWORD`. LinkedIn scraping reads `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`.
- Do not run `python -m outreach.campaign` or the LinkedIn scrapers unless the user explicitly asks to send or scrape. Test mode still sends real email when credentials are present.
- Faculty directory collection is Ruby (`faculty-scraper/scripts/`). Profile enrichment and the campaign engine are Python.
- The master lead file is `data/processed/cold_email_outreach_all_cleaned_ranked.csv`. Treat it as campaign state. Do not rewrite sent-status columns unless the user asks.
