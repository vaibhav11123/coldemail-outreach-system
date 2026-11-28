# Product intelligence roadmap (functional, not cosmetic)

Principle: keep FastAPI + Jinja; add HTMX/search/CV/drafting intelligence incrementally.

## Shipped this iteration

- [x] Faculty directory `/directory` — SQLite FTS5 + hybrid RRF (BoW embeddings; FastEmbed optional)
- [x] Research Match Intelligence — component scores + why/gaps; not acceptance probability
- [x] CV-first import — PDF/DOCX/TXT via pypdf + python-docx → unconfirmed editable facts
- [x] Evidence-grounded drafting package (`studio/drafting/`) — strategy engine, deterministic composer, quality inspector
- [x] Profile gate allows coursework/skills without a confirmed project
- [x] HTMX progressive search on directory (CDN)

## Next (still open)

- [ ] Tabulator spreadsheet directory + Tailwind/Preline design system (subset)
- [ ] Tiptap letter editor
- [ ] Precompute FastEmbed vectors into distributed dataset packages
- [ ] AcademicDraftBench (300 cases) + blinded human eval
- [ ] Application kanban + reminder writers
- [ ] Faculty comparison workspace
- [ ] Campaign planner homepage (“what should I do next?”)
- [ ] Real student 90-second CV→match usability study

## Do not rebuild

Deterministic fallback, approval hashes, send intents, BYOAI credentials, licensing/fingerprinting stack already shipped.
