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
