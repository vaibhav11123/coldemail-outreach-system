# Academic Outreach Studio

Local FastAPI + Jinja2 app for academic research-internship outreach.

```bash
.venv/bin/python -m studio
# or
.venv/bin/uvicorn studio.app:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/offer`. The app rejects non-localhost Host headers.

```bash
STUDIO_FORCE_LOCAL_SECRETS=1 .venv/bin/python -m pytest studio/tests -m "not live"
.venv/bin/python -m studio.benchmarks.run_metrics
bash studio/packaging/build_installers.sh
```

Data lives in `STUDIO_DATA_DIR` or `~/.academic-outreach-studio/studio.sqlite`.
Do not run `python -m outreach.campaign` from this package.

## Dataset editions & licensing

Shared stack in `studio/licensing/` + `studio/dataset/` (see `studio/dataset/README.md` and `studio/prod_qual/PROTECTION_ROADMAP.md`):

- **Standard Dataset** — fingerprinted CSV/Excel/JSON (full facts; unique export IDs)
- **Protected Dataset** — SQLCipher `ResearchCatalog.asdb` + device-bound `CustomerLicense.aslic`
- **Academic Studio** — same encrypted catalog under a software licence

```bash
.venv/bin/python -m studio.dataset editions
.venv/bin/python -m studio.dataset package-protected --out /tmp/prot --customer c1 --email c1@example.com --activate
.venv/bin/python -m studio.dataset read --package /tmp/prot --query Ada
```
