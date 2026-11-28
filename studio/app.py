"""Academic Outreach Studio — FastAPI + Jinja2 local app."""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from studio import db as dbmod
from studio.demo import seed_demo
from studio.drafts import (
    approve_draft,
    clear_approval_if_edited,
    content_hash,
    generate_draft,
    mailto_link,
    save_or_update_draft,
    to_eml,
)
from studio.faculty import collect_school, import_people, list_schools
from studio.fetch_url import extract_opportunity_suggestions, fetch_text
from studio.identity import flag_name_conflict, merge_researchers, undo_merge
from studio.jobs import enqueue, get_job, register_handler, start_worker
from studio.mail import (
    active_mail_summary,
    can_send_now,
    connect_institute,
    connect_manual_smtp,
    daily_limit as mail_daily_limit,
    disconnect_gmail,
    disconnect_institute,
    disconnect_outlook,
    discover_email_config,
    finish_gmail_oauth,
    finish_outlook_oauth,
    gmail_status,
    outlook_status,
    record_send,
    set_reply_consent,
    smtp_config_from_store,
    start_gmail_oauth,
    start_outlook_oauth,
)
from studio.mail.gmail import CLIENT_ID_SECRET as GOOGLE_CLIENT_ID_SECRET
from studio.mail.gmail import CLIENT_SECRET_SECRET as GOOGLE_CLIENT_SECRET_SECRET
from studio.mail.outlook import CLIENT_ID_SECRET as MICROSOFT_CLIENT_ID_SECRET
from studio.mailer_studio import create_intent, perform_send
from studio.matching import rebuild_shortlist
from studio.academic.crossref import lookup_doi
from studio.academic.opencitations import citations_for_doi
from studio.academic.orcid_local import lookup_orcid
from studio.ai.handoff import HANDOFF_TARGETS, build_handoff_prompt, import_handoff_body
from studio.bibliography import import_entries_as_facts, parse_bibliography
from studio.calendar_export import build_ics, events_from_tracker
from studio.connections import (
    connection_requirements,
    prefill_email_candidates,
    sections_for_ui,
    workspace_setup_steps,
)
from studio.github_import import (
    disconnect_github,
    fetch_public_repos,
    github_login,
    import_repos_as_facts,
    parse_github_login,
)
from studio.zotero_local import detect_zotero
from studio.openalex import request_api_key, save_pasted_key
from studio.paths import PACKAGE_ROOT, REPO_ROOT, app_data_dir, bundled_data_dir
from studio.planner import (
    PERSONAL_GMAIL_CAP,
    academic_queue,
    classify_hr,
    load_hr_dataframe,
    preview_row,
    schedule_again,
    sent_in_rolling_24h,
)
from studio.secrets_store import (
    delete_all_studio_secrets,
    delete_secret,
    get_secret,
    set_secret,
)
from studio.security import (
    new_page_token,
    require_localhost_host,
    require_page_token,
    set_page_token_cookie,
)
from studio.sheet_import import commit_import, read_tabular, suggest_mapping
from studio.summer_loader import load_summer_zip, seed_mini_bundled
from studio.ai.engine import rewrite_draft
from studio.ai.registry import (
    continue_without_ai,
    disconnect_provider,
    get_active_provider,
    get_provider,
    list_provider_cards,
    set_active_provider,
)
from studio.ai.types import EvidenceBoundRequest

TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))

def render(request: Request, name: str, **context):
    return TEMPLATES.TemplateResponse(request, name, context)

PAGE_TOKEN: str = new_page_token()
IMPORT_CACHE: dict[str, Any] = {}
FETCH_CACHE: dict[str, Any] = {}

OFFER_REFUND = (
    "If the app does not open or the licensed catalog fails to load, email support "
    "within 14 days for a refund. After refund, Studio entitlements are revoked. "
    "Dataset files already downloaded are contractual — see the individual licence."
)
SUPPORT_EMAIL = "support@academic-outreach.studio"

APPLICATION_STATES = [
    "drafted",
    "ready",
    "submitted_by_me",
    "replied",
    "interview",
    "rejected",
    "stopped",
]


def create_app(data_dir: Path | None = None) -> FastAPI:
    global PAGE_TOKEN
    if data_dir is not None:
        os.environ["STUDIO_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("STUDIO_FORCE_LOCAL_SECRETS", "1")
    PAGE_TOKEN = new_page_token()

    app = FastAPI(title="Academic Outreach Studio")
    app.mount("/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="static")

    conn = dbmod.connect()
    dbmod.migrate(conn)
    dbmod.recover_intents_on_startup(conn)
    dbmod.interrupt_running_jobs(conn)
    seed_demo(conn)
    _ensure_library(conn)
    conn.close()

    _register_jobs()
    start_worker()

    def _page_token_missing(request: Request) -> bool:
        return request.cookies.get("studio_page_token") != PAGE_TOKEN

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        if request.url.path.startswith("/static"):
            return await call_next(request)
        try:
            require_localhost_host(request)
        except Exception as exc:  # noqa: BLE001
            detail = getattr(exc, "detail", str(exc))
            return Response(str(detail), status_code=403)
        response = await call_next(request)
        if _page_token_missing(request):
            set_page_token_cookie(response, PAGE_TOKEN)
        return response

    def ctx(request: Request, nav: str = "", **extra: Any) -> dict:
        data = {
            "request": request,
            "nav": nav,
            "page_token": PAGE_TOKEN,
            "flash": request.query_params.get("flash"),
            "flash_error": request.query_params.get("err") == "1",
        }
        data.update(extra)
        return data

    def require_token(form_token: str | None) -> None:
        # Build a minimal request-like check against process token
        class _R:
            cookies = {"studio_page_token": PAGE_TOKEN}

        require_page_token(_R(), form_token)  # type: ignore[arg-type]

    from studio.dataset.reader_routes import build_reader_router
    from studio.licensing.api import build_licensing_router
    from studio.licensing.customer_routes import build_customer_licensing_router

    app.include_router(build_licensing_router())
    app.include_router(build_reader_router(ctx))
    app.include_router(
        build_customer_licensing_router(
            render=lambda request, name, **kw: TEMPLATES.TemplateResponse(
                request, name, ctx(request, **kw)
            ),
            require_token=require_token,
            support_email=SUPPORT_EMAIL,
            refund_copy=OFFER_REFUND,
        )
    )

    def get_conn():
        return dbmod.connect()

    def profile_ready(conn) -> bool:
        """Enough confirmed evidence to rank — project optional if coursework/skills exist."""
        interests = conn.execute(
            "SELECT COUNT(*) AS c FROM profile_fact WHERE kind='interest' AND confirmed=1"
        ).fetchone()["c"]
        projects = conn.execute(
            "SELECT COUNT(*) AS c FROM profile_fact WHERE kind='project' AND confirmed=1"
        ).fetchone()["c"]
        coursework = conn.execute(
            "SELECT COUNT(*) AS c FROM profile_fact WHERE kind='coursework' AND confirmed=1"
        ).fetchone()["c"]
        skills = conn.execute(
            "SELECT COUNT(*) AS c FROM profile_fact WHERE kind='skill' AND confirmed=1"
        ).fetchone()["c"]
        return interests > 0 and (projects > 0 or coursework > 0 or skills > 0)

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return RedirectResponse("/dashboard", status_code=302)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        from studio.campaign import build_campaign_snapshot

        conn = get_conn()
        try:
            snap = build_campaign_snapshot(conn, profile_ready=profile_ready(conn))
            return TEMPLATES.TemplateResponse(
                request,
                "dashboard.html",
                ctx(request, nav="dashboard", snap=snap),
            )
        finally:
            conn.close()

    # ---- S0 Offer ----
    @app.get("/offer", response_class=HTMLResponse)
    async def offer(request: Request):
        from studio.licensing.products import SKU, get_edition

        return TEMPLATES.TemplateResponse(
            request,
            "offer.html",
            ctx(
                request,
                nav="offer",
                dataset=get_edition(SKU.STANDARD_DATASET),
                studio=get_edition(SKU.ACADEMIC_STUDIO),
                refund=OFFER_REFUND,
                support=SUPPORT_EMAIL,
            ),
        )

    # ---- S1 Profile ----
    @app.get("/profile", response_class=HTMLResponse)
    async def profile_get(request: Request):
        conn = get_conn()
        try:
            applicant = conn.execute("SELECT * FROM applicant WHERE id=1").fetchone()
            facts = conn.execute(
                "SELECT * FROM profile_fact ORDER BY id DESC"
            ).fetchall()
            return TEMPLATES.TemplateResponse(request, "profile.html",
                ctx(
                    request,
                    nav="profile",
                    applicant=applicant,
                    facts=facts,
                    profile_ready=profile_ready(conn),
                ),
            )
        finally:
            conn.close()

    @app.post("/profile")
    async def profile_post(
        request: Request,
        page_token: str = Form(...),
        mode: str = Form("internship"),
        degree_level: str = Form("undergraduate"),
        degree_year: str = Form(""),
        countries: str = Form(""),
        funding_need: str = Form("no_preference"),
        dates_free: str = Form(""),
        github_url: str = Form(""),
        portfolio_url: str = Form(""),
        interest: str = Form(""),
        skill: str = Form(""),
        project: str = Form(""),
        cv: UploadFile | None = File(None),
    ):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE applicant SET mode=?, degree_level=?, degree_year=?, countries=?,
                    funding_need=?, dates_free=?, github_url=?, portfolio_url=?,
                    updated_at=datetime('now')
                WHERE id=1
                """,
                (
                    mode,
                    degree_level,
                    degree_year,
                    countries,
                    funding_need,
                    dates_free,
                    github_url,
                    portfolio_url,
                ),
            )
            for kind, body in (("interest", interest), ("skill", skill), ("project", project)):
                if body.strip():
                    conn.execute(
                        """
                        INSERT INTO profile_fact(kind, body, source, confirmed)
                        VALUES (?, ?, 'typed', 1)
                        """,
                        (kind, body.strip()),
                    )
            if cv is not None and cv.filename:
                raw = await cv.read()
                # Cap CV uploads (PDF/DOCX) to avoid unbounded memory use
                if len(raw) > 5_000_000:
                    return RedirectResponse(
                        "/profile?err=1&flash=CV%20too%20large%20(max%205MB)",
                        status_code=303,
                    )
                from studio.cv_import import parse_cv, persist_extracted_profile

                parsed = parse_cv(cv.filename, raw)
                persist_extracted_profile(conn, parsed.profile, confirmed=False)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        ready_now = False
        conn2 = get_conn()
        try:
            ready_now = profile_ready(conn2)
        finally:
            conn2.close()
        if ready_now:
            msg = "Profile%20saved"
        elif not (interest.strip() or skill.strip() or project.strip()):
            msg = "Nothing%20new%20to%20save.%20Add%20an%20interest%20or%20project."
        else:
            msg = "Saved.%20Confirm%20interest%20and%20project%20to%20unlock%20shortlist."
        return RedirectResponse(f"/profile?flash={msg}", status_code=303)

    @app.post("/profile/confirm/{fact_id}")
    async def profile_confirm(fact_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("UPDATE profile_fact SET confirmed=1 WHERE id=?", (fact_id,))
        finally:
            conn.close()
        return RedirectResponse("/profile", status_code=303)

    @app.post("/profile/reject/{fact_id}")
    async def profile_reject(fact_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("DELETE FROM profile_fact WHERE id=? AND confirmed=0", (fact_id,))
        finally:
            conn.close()
        return RedirectResponse("/profile", status_code=303)

    # ---- S2 Start ----
    @app.get("/start", response_class=HTMLResponse)
    async def start(request: Request):
        conn = get_conn()
        try:
            return TEMPLATES.TemplateResponse(request, "start.html",
                ctx(
                    request,
                    nav="start",
                    profile_ready=profile_ready(conn),
                    schools=list_schools(),
                ),
            )
        finally:
            conn.close()

    @app.get("/demo", response_class=HTMLResponse)
    async def demo_list(request: Request):
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT o.id, r.display_name AS name, a.institution, o.status
                FROM opportunity o
                JOIN researcher r ON r.id = o.researcher_id
                LEFT JOIN affiliation a ON a.researcher_id = r.id AND a.is_current = 1
                WHERE o.demo = 1
                """
            ).fetchall()
            return TEMPLATES.TemplateResponse(request, "demo.html",
                ctx(request, nav="start", items=rows),
            )
        finally:
            conn.close()

    @app.get("/library", response_class=HTMLResponse)
    async def library(request: Request, q: str = ""):
        return RedirectResponse(f"/directory?q={quote(q)}" if q else "/directory", status_code=302)

    @app.get("/directory", response_class=HTMLResponse)
    async def directory(
        request: Request,
        q: str = "",
        funding: str = "",
        status: str = "",
        university: str = "",
    ):
        """Complete faculty directory — FTS5 + hybrid semantic, works without AI."""
        from studio.search.hybrid import ensure_search_indexes, hybrid_search_researchers

        conn = get_conn()
        try:
            ensure_search_indexes(conn)
            hits = hybrid_search_researchers(
                conn,
                q,
                limit=100,
                funding=funding or None,
                status=status or None,
                university=university or None,
            )
            items = []
            for h in hits:
                items.append(
                    {
                        "opportunity_id": h.get("opportunity_id"),
                        "researcher_id": h.get("researcher_id"),
                        "name": h.get("display_name"),
                        "institution": h.get("institution"),
                        "funding": h.get("funding"),
                        "status": h.get("status"),
                        "paper_title": h.get("paper_title"),
                        "snippet": h.get("snippet") or "",
                        "rrf_score": h.get("rrf_score"),
                        "retrieval": h.get("retrieval"),
                    }
                )
            saved = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM saved_search ORDER BY created_at DESC LIMIT 20"
                )
            ]
            empty = "No match for that search." if q else "Directory is empty — load the Summer library."
            return TEMPLATES.TemplateResponse(
                request,
                "directory.html",
                ctx(
                    request,
                    nav="directory",
                    items=items,
                    q=q,
                    funding=funding,
                    status=status,
                    university=university,
                    empty_reason=empty,
                    total=len(items),
                    saved_searches=saved,
                ),
            )
        finally:
            conn.close()

    @app.post("/directory/save-search")
    async def directory_save_search(
        page_token: str = Form(...),
        name: str = Form(...),
        q: str = Form(""),
        funding: str = Form(""),
        status: str = Form(""),
        university: str = Form(""),
    ):
        require_token(page_token)
        label = (name or "").strip() or (q.strip()[:40] if q.strip() else "Saved search")
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO saved_search(name, query, funding, status, university)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    label,
                    q.strip(),
                    funding.strip() or None,
                    status.strip() or None,
                    university.strip() or None,
                ),
            )
        finally:
            conn.close()
        return RedirectResponse("/directory?flash=Search%20saved", status_code=303)

    @app.post("/directory/saved/{search_id}/delete")
    async def directory_delete_saved(search_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("DELETE FROM saved_search WHERE id=?", (search_id,))
        finally:
            conn.close()
        return RedirectResponse("/directory", status_code=303)

    @app.get("/compare", response_class=HTMLResponse)
    async def compare_faculty(request: Request):
        from studio.compare import comparison_rows

        ids_raw = request.query_params.get("ids", "")
        rid_params = request.query_params.getlist("rid")
        selected: list[int] = []
        for part in ids_raw.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                selected.append(int(part))
        for r in rid_params:
            if str(r).isdigit():
                selected.append(int(r))
        # unique preserve order
        seen: set[int] = set()
        selected_ids: list[int] = []
        for i in selected:
            if i not in seen:
                seen.add(i)
                selected_ids.append(i)

        conn = get_conn()
        try:
            facts = [dict(f) for f in conn.execute("SELECT * FROM profile_fact").fetchall()]
            rows = comparison_rows(conn, selected_ids, facts) if selected_ids else []
            shortlist_options = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT r.id AS researcher_id, r.display_name AS name,
                           a.institution AS institution
                    FROM shortlist_item s
                    JOIN opportunity o ON o.id = s.opportunity_id
                    JOIN researcher r ON r.id = o.researcher_id
                    LEFT JOIN affiliation a ON a.researcher_id = r.id AND a.is_current = 1
                    ORDER BY s.rank_score DESC
                    LIMIT 24
                    """
                )
            ]
            return TEMPLATES.TemplateResponse(
                request,
                "compare.html",
                ctx(
                    request,
                    nav="compare",
                    rows=rows,
                    ids_raw=",".join(str(i) for i in selected_ids),
                    selected_ids=selected_ids,
                    shortlist_options=shortlist_options,
                ),
            )
        finally:
            conn.close()

    @app.post("/add-person")
    async def add_person(
        page_token: str = Form(...),
        name: str = Form(...),
        affiliation: str = Form(""),
        email: str = Form(""),
    ):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "INSERT INTO researcher(display_name, email, origin) VALUES (?, ?, 'manual')",
                (name.strip(), email.strip() or None),
            )
            rid = cur.lastrowid
            conn.execute(
                "INSERT INTO researcher_id(researcher_id, source, external_id) VALUES (?, 'manual', ?)",
                (rid, f"manual:{name}|{affiliation}|{email}".lower()),
            )
            if affiliation.strip():
                conn.execute(
                    "INSERT INTO affiliation(researcher_id, institution, is_current) VALUES (?, ?, 1)",
                    (rid, affiliation.strip()),
                )
            ocur = conn.execute(
                """
                INSERT INTO opportunity(
                    researcher_id, kind, status, funding, eligibility, deadline,
                    apply_url, email_invited, checked_at, origin, demo, note
                ) VALUES (?, 'unknown', 'unknown', 'unknown', 'unknown', NULL, NULL,
                          'unknown', date('now'), 'manual', 0, NULL)
                """,
                (rid,),
            )
            flag_name_conflict(conn, name.strip(), rid)
            conn.execute("COMMIT")
            oid = ocur.lastrowid
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return RedirectResponse(f"/opportunity/{oid}", status_code=303)

    @app.post("/fetch-url")
    async def fetch_url_post(page_token: str = Form(...), url: str = Form("")):
        require_token(page_token)
        if not url.strip():
            return RedirectResponse(
                "/start?flash=Paste%20an%20http%20or%20https%20URL%20first&err=1",
                status_code=303,
            )
        try:
            final_url, html = fetch_text(url.strip())
        except Exception as exc:  # noqa: BLE001
            return RedirectResponse(
                f"/start?flash={quote(str(exc))}&err=1", status_code=303
            )
        suggestions = extract_opportunity_suggestions(html, final_url)
        fetch_id = secrets.token_hex(8)
        FETCH_CACHE[fetch_id] = {
            "url": final_url,
            "suggestions": suggestions,
            "html": html[:5000],
        }
        return RedirectResponse(f"/fetch-url/review/{fetch_id}", status_code=303)

    @app.get("/fetch-url/review/{fetch_id}", response_class=HTMLResponse)
    async def fetch_review(request: Request, fetch_id: str):
        data = FETCH_CACHE.get(fetch_id)
        if not data:
            return RedirectResponse("/start?flash=Fetch%20expired&err=1", status_code=303)
        return TEMPLATES.TemplateResponse(request, "fetch_confirm.html",
            ctx(
                request,
                nav="start",
                fetch_id=fetch_id,
                suggestions=data["suggestions"],
                name="",
                email="",
                error=None,
            ),
        )

    @app.post("/fetch-url/confirm")
    async def fetch_confirm(
        page_token: str = Form(...),
        fetch_id: str = Form(...),
        name: str = Form(...),
        email: str = Form(""),
        confirm: list[str] = Form(default=[]),
    ):
        require_token(page_token)
        data = FETCH_CACHE.get(fetch_id)
        if not data:
            return RedirectResponse("/start?flash=Fetch%20expired&err=1", status_code=303)
        fields = {
            "status": "unknown",
            "funding": "unknown",
            "eligibility": "unknown",
            "deadline": None,
            "apply_url": None,
            "email_invited": "unknown",
            "note": None,
        }
        notes = []
        for idx in confirm:
            try:
                s = data["suggestions"][int(idx)]
            except (ValueError, IndexError, KeyError):
                continue
            if s["field"] in fields and s["field"] != "deadline" and s["field"] != "apply_url":
                fields[s["field"]] = s["value"]
            elif s["field"] == "deadline":
                fields["deadline"] = s["value"]
            elif s["field"] == "apply_url":
                fields["apply_url"] = s["value"]
            notes.append(s.get("quote") or "")
        fields["note"] = "; ".join(n for n in notes if n) or None
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "INSERT INTO researcher(display_name, email, origin) VALUES (?, ?, 'url')",
                (name.strip(), email.strip() or None),
            )
            rid = cur.lastrowid
            conn.execute(
                "INSERT INTO researcher_id(researcher_id, source, external_id) VALUES (?, 'manual', ?)",
                (rid, f"url:{data['url']}|{name}".lower()),
            )
            ocur = conn.execute(
                """
                INSERT INTO opportunity(
                    researcher_id, kind, status, funding, eligibility, deadline,
                    apply_url, email_invited, checked_at, origin, demo, note
                ) VALUES (?, 'unknown', ?, ?, ?, ?, ?, ?, date('now'), 'url', 0, ?)
                """,
                (
                    rid,
                    fields["status"],
                    fields["funding"],
                    fields["eligibility"],
                    fields["deadline"],
                    fields["apply_url"],
                    fields["email_invited"],
                    fields["note"],
                ),
            )
            for idx in confirm:
                try:
                    s = data["suggestions"][int(idx)]
                except (ValueError, IndexError, KeyError):
                    continue
                conn.execute(
                    "INSERT INTO evidence(opportunity_id, quote, url) VALUES (?, ?, ?)",
                    (ocur.lastrowid, s.get("quote") or s["field"], s.get("url")),
                )
            conn.execute("COMMIT")
            oid = ocur.lastrowid
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        FETCH_CACHE.pop(fetch_id, None)
        return RedirectResponse(f"/opportunity/{oid}", status_code=303)

    @app.post("/import")
    async def import_preview(
        page_token: str = Form(...),
        file: UploadFile = File(...),
    ):
        require_token(page_token)
        raw = await file.read()
        try:
            headers, rows, warnings = read_tabular(file.filename or "upload.csv", raw)
        except Exception as exc:  # noqa: BLE001
            return RedirectResponse(
                f"/start?flash={quote(str(exc))}&err=1", status_code=303
            )
        import_id = secrets.token_hex(8)
        mapping = suggest_mapping(headers)
        IMPORT_CACHE[import_id] = {"headers": headers, "rows": rows, "mapping": mapping}
        # redirect to mapping page via temporary store — render directly
        return RedirectResponse(f"/import/map/{import_id}", status_code=303)

    @app.get("/import/map/{import_id}", response_class=HTMLResponse)
    async def import_map(request: Request, import_id: str):
        data = IMPORT_CACHE.get(import_id)
        if not data:
            return RedirectResponse("/start?flash=Import%20expired&err=1", status_code=303)
        preview = [
            {k: r.get(k) for k in data["headers"][:4]} for r in data["rows"][:5]
        ]
        return TEMPLATES.TemplateResponse(request, "import_map.html",
            ctx(
                request,
                nav="start",
                import_id=import_id,
                headers=data["headers"],
                mapping=data["mapping"],
                warnings=[],
                preview=preview,
            ),
        )

    @app.post("/import/confirm")
    async def import_confirm(
        page_token: str = Form(...),
        import_id: str = Form(...),
        name_col: str = Form(...),
        affiliation_col: str = Form(...),
        email_col: str = Form(""),
    ):
        require_token(page_token)
        data = IMPORT_CACHE.get(import_id)
        if not data:
            return RedirectResponse("/start?flash=Import%20expired&err=1", status_code=303)
        mapping = {
            "name": name_col,
            "affiliation": affiliation_col,
            "email": email_col or None,
        }
        conn = get_conn()
        try:
            count = commit_import(conn, data["rows"], mapping)
        except Exception as exc:  # noqa: BLE001
            conn.close()
            return RedirectResponse(
                f"/start?flash={quote(str(exc))}&err=1", status_code=303
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
        IMPORT_CACHE.pop(import_id, None)
        return RedirectResponse(
            f"/library?flash={quote(f'Imported {count} rows')}", status_code=303
        )

    @app.post("/faculty")
    async def faculty_collect(page_token: str = Form(...), school: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            job_id = enqueue(conn, "faculty", {"school_id": school})
        finally:
            conn.close()
        return RedirectResponse(f"/job/{job_id}", status_code=303)

    @app.post("/openalex/connect")
    async def openalex_connect(page_token: str = Form(...), email: str = Form(...)):
        require_token(page_token)
        try:
            data = request_api_key(email.strip())
            if data.get("http_status") == 201:
                msg = (
                    "OpenAlex sent an activation email. Click the link in your inbox, "
                    "then return to Academic Outreach Studio."
                )
            elif data.get("http_status") == 409:
                msg = (
                    "An OpenAlex key may already exist for this email. "
                    "Activate from the email link, or paste your key under Advanced on Openings."
                )
            else:
                msg = data.get("message") or f"OpenAlex status {data.get('http_status')}"
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
        return RedirectResponse(
            f"/connections?flash={quote(msg)}#openalex", status_code=303
        )

    @app.post("/openalex/paste")
    async def openalex_paste(page_token: str = Form(...), api_key: str = Form(...)):
        require_token(page_token)
        save_pasted_key(api_key)
        return RedirectResponse(
            "/connections?flash=OpenAlex%20key%20saved#openalex", status_code=303
        )

    # ---- Unified Connections ----
    def connections_page(
        request: Request,
        *,
        github_repos=None,
        crossref_result=None,
        citations_result=None,
        orcid_lookup=None,
        **extra,
    ):
        prefs = prefill_email_candidates()
        return ctx(
            request,
            nav="connections",
            sections=sections_for_ui(),
            setup_steps=workspace_setup_steps(),
            requirements=connection_requirements(),
            openalex_prefill=(prefs[0] if prefs else ""),
            github_login=github_login(),
            github_repos=github_repos or [],
            orcid_id=get_secret("orcid_id") or "",
            crossref_result=crossref_result,
            citations_result=citations_result,
            orcid_lookup=orcid_lookup,
            **extra,
        )

    @app.get("/connections", response_class=HTMLResponse)
    async def connections_get(request: Request):
        gh_repos = []
        login = github_login()
        if login and request.query_params.get("imported"):
            preview = fetch_public_repos(login, per_page=5)
            if preview.get("ok"):
                gh_repos = preview.get("repos") or []
        return TEMPLATES.TemplateResponse(
            request,
            "connections.html",
            connections_page(request, github_repos=gh_repos),
        )

    @app.post("/connections/github")
    async def connections_github(page_token: str = Form(...), github: str = Form("")):
        require_token(page_token)
        login = parse_github_login(github)
        if not login:
            return RedirectResponse(
                "/connections?err=1&flash=Enter%20a%20GitHub%20username%20or%20profile%20URL#github",
                status_code=303,
            )
        result = fetch_public_repos(login)
        if not result.get("ok"):
            return RedirectResponse(
                f"/connections?err=1&flash={quote(result.get('message') or 'Import failed')}#github",
                status_code=303,
            )
        conn = get_conn()
        try:
            n = import_repos_as_facts(conn, login, result.get("repos") or [])
        finally:
            conn.close()
        return RedirectResponse(
            f"/connections?imported=1&flash={quote(f'Imported {n} public projects for review')}#github",
            status_code=303,
        )

    @app.post("/connections/orcid")
    async def connections_orcid(
        request: Request, page_token: str = Form(...), orcid: str = Form("")
    ):
        require_token(page_token)
        raw = (orcid or "").strip()
        if not raw:
            delete_secret("orcid_id")
            return RedirectResponse(
                "/connections?flash=ORCID%20cleared#orcid", status_code=303
            )
        if "orcid.org/" in raw:
            raw = raw.rstrip("/").split("orcid.org/")[-1]
        set_secret("orcid_id", raw)
        looked = lookup_orcid(raw)
        return TEMPLATES.TemplateResponse(
            request,
            "connections.html",
            connections_page(
                request,
                orcid_lookup=looked,
                flash=(
                    f"ORCID saved · {looked.get('name') or raw}"
                    if looked.get("ok")
                    else f"ORCID saved as link · {looked.get('message') or ''}"
                ),
                flash_error=False,
            ),
        )

    @app.post("/connections/crossref")
    async def connections_crossref(
        request: Request, page_token: str = Form(...), doi: str = Form("")
    ):
        require_token(page_token)
        result = lookup_doi(doi)
        return TEMPLATES.TemplateResponse(
            request,
            "connections.html",
            connections_page(
                request,
                crossref_result=result,
                flash=result.get("title") if result.get("ok") else result.get("message"),
                flash_error=not result.get("ok"),
            ),
        )

    @app.post("/connections/citations")
    async def connections_citations(
        request: Request, page_token: str = Form(...), doi: str = Form("")
    ):
        require_token(page_token)
        result = citations_for_doi(doi)
        return TEMPLATES.TemplateResponse(
            request,
            "connections.html",
            connections_page(
                request,
                citations_result=result,
                flash="OpenCitations result" if result.get("ok") else result.get("message"),
                flash_error=not result.get("ok"),
            ),
        )

    @app.post("/connections/bibliography")
    async def connections_bibliography(
        page_token: str = Form(...),
        file: UploadFile = File(None),
    ):
        require_token(page_token)
        if file is None or not file.filename:
            return RedirectResponse(
                "/connections?err=1&flash=Choose%20a%20BibTeX%2C%20RIS%2C%20or%20CSV%20file#google_scholar",
                status_code=303,
            )
        blob = await file.read()
        if len(blob) > 2_000_000:
            return RedirectResponse(
                "/connections?err=1&flash=Bibliography%20too%20large%20(max%202MB)#google_scholar",
                status_code=303,
            )
        raw = blob.decode("utf-8", errors="replace")
        parsed = parse_bibliography(raw, file.filename or "")
        if not parsed.get("ok"):
            return RedirectResponse(
                f"/connections?err=1&flash={quote(parsed.get('message') or 'Parse failed')}#google_scholar",
                status_code=303,
            )
        conn = get_conn()
        try:
            n = import_entries_as_facts(
                conn, parsed.get("entries") or [], source="bibliography"
            )
        finally:
            conn.close()
        return RedirectResponse(
            f"/connections?flash={quote(f'Imported {n} publications for review on Profile')}#google_scholar",
            status_code=303,
        )

    @app.post("/connections/zotero-detect")
    async def connections_zotero_detect(page_token: str = Form(...)):
        require_token(page_token)
        det = detect_zotero()
        msg = det.get("message") or "Zotero check complete"
        err = "" if det.get("ok") else "1"
        return RedirectResponse(
            f"/connections?flash={quote(msg)}"
            + (f"&err={err}" if err else "")
            + "#zotero",
            status_code=303,
        )

    @app.get("/connections/calendar.ics")
    async def connections_calendar_ics():
        conn = get_conn()
        try:
            events = events_from_tracker(conn)
            if not events:
                # Always produce a usable calendar file with a sample follow-up window
                from datetime import datetime, timedelta

                events = [
                    {
                        "summary": "Follow-up with professor",
                        "description": "Review before sending. Add deadlines in Tracker to populate this calendar.",
                        "start": datetime.utcnow() + timedelta(days=8),
                    }
                ]
            body = build_ics(events)
        finally:
            conn.close()
        return Response(
            body,
            media_type="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=academic-outreach.ics"
            },
        )

    @app.get("/job/{job_id}", response_class=HTMLResponse)
    async def job_status(request: Request, job_id: int):
        conn = get_conn()
        try:
            job = get_job(conn, job_id)
            if not job:
                return RedirectResponse("/start?flash=Job%20not%20found&err=1", status_code=303)
            return TEMPLATES.TemplateResponse(request, "job.html",
                ctx(request, nav="start", job=job),
            )
        finally:
            conn.close()

    @app.post("/job/{job_id}/cancel")
    async def job_cancel(job_id: int, page_token: str = Form(...)):
        require_token(page_token)
        from studio.jobs import cancel_job

        conn = get_conn()
        try:
            cancel_job(conn, job_id)
        finally:
            conn.close()
        return RedirectResponse(f"/job/{job_id}", status_code=303)

    # ---- S3 Opportunity ----
    @app.get("/opportunity/{opp_id}", response_class=HTMLResponse)
    async def opportunity(request: Request, opp_id: int):
        conn = get_conn()
        try:
            opp = conn.execute("SELECT * FROM opportunity WHERE id=?", (opp_id,)).fetchone()
            if not opp:
                return RedirectResponse("/start?flash=Not%20found&err=1", status_code=303)
            researcher = conn.execute(
                "SELECT * FROM researcher WHERE id=?", (opp["researcher_id"],)
            ).fetchone()
            aff = conn.execute(
                "SELECT institution FROM affiliation WHERE researcher_id=? AND is_current=1",
                (opp["researcher_id"],),
            ).fetchone()
            pubs = conn.execute(
                "SELECT * FROM publication WHERE researcher_id=? ORDER BY year DESC",
                (opp["researcher_id"],),
            ).fetchall()
            short = conn.execute(
                "SELECT rank_explanation FROM shortlist_item WHERE opportunity_id=?",
                (opp_id,),
            ).fetchone()
            from studio.rank_payload import parse_rank_explanation

            reasons, intel = parse_rank_explanation(
                short["rank_explanation"] if short else None
            )
            expired = False
            if opp["deadline"]:
                try:
                    expired = date.fromisoformat(str(opp["deadline"])[:10]) < date.today()
                except ValueError:
                    expired = False
            return TEMPLATES.TemplateResponse(request, "opportunity.html",
                ctx(
                    request,
                    nav="start",
                    opp=opp,
                    researcher=researcher,
                    institution=(aff["institution"] if aff else "Unknown"),
                    publications=pubs,
                    reasons=reasons,
                    match_intel=intel,
                    expired=expired,
                ),
            )
        finally:
            conn.close()

    # ---- S4 Shortlist ----
    @app.get("/shortlist", response_class=HTMLResponse)
    async def shortlist(
        request: Request,
        hide_unknowns: str = "",
        country: str = "",
    ):
        conn = get_conn()
        try:
            if not profile_ready(conn):
                return TEMPLATES.TemplateResponse(request, "shortlist.html",
                    ctx(
                        request,
                        nav="shortlist",
                        items=[],
                        hide_unknowns=bool(hide_unknowns),
                        country=country,
                        empty_reason="Confirm at least one interest and one project first.",
                    ),
                )
            rows = conn.execute(
                """
                SELECT s.opportunity_id, s.rank_score, o.funding, o.eligibility,
                       o.deadline, o.email_invited, o.status,
                       r.display_name AS name, a.institution
                FROM shortlist_item s
                JOIN opportunity o ON o.id = s.opportunity_id
                JOIN researcher r ON r.id = o.researcher_id
                LEFT JOIN affiliation a ON a.researcher_id = r.id AND a.is_current = 1
                ORDER BY s.rank_score DESC
                """
            ).fetchall()
            items = []
            for r in rows:
                if hide_unknowns and (
                    r["funding"] == "unknown"
                    or r["eligibility"] == "unknown"
                    or r["status"] == "unknown"
                ):
                    continue
                if country and country.lower() not in (r["institution"] or "").lower():
                    continue
                if r["deadline"]:
                    try:
                        if date.fromisoformat(str(r["deadline"])[:10]) < date.today():
                            continue
                    except ValueError:
                        pass
                items.append(r)
            empty = "Filters removed everyone." if rows else "Rebuild ranking after confirming your profile."
            return TEMPLATES.TemplateResponse(request, "shortlist.html",
                ctx(
                    request,
                    nav="shortlist",
                    items=items,
                    hide_unknowns=bool(hide_unknowns),
                    country=country,
                    empty_reason=empty,
                ),
            )
        finally:
            conn.close()

    @app.post("/shortlist/rebuild")
    async def shortlist_rebuild(page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            if not profile_ready(conn):
                return RedirectResponse(
                    "/shortlist?err=1&flash=Confirm%20at%20least%20one%20interest%20and%20one%20project%20first",
                    status_code=303,
                )
            rebuild_shortlist(conn)
        finally:
            conn.close()
        return RedirectResponse("/shortlist?flash=Ranked", status_code=303)

    @app.post("/shortlist/add/{opp_id}")
    async def shortlist_add(opp_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            exists = conn.execute(
                "SELECT id FROM shortlist_item WHERE opportunity_id=?", (opp_id,)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO shortlist_item(opportunity_id, rank_score, rank_explanation) VALUES (?, 0, '[]')",
                    (opp_id,),
                )
        finally:
            conn.close()
        return RedirectResponse("/shortlist", status_code=303)

    # ---- S5 Draft ----
    @app.get("/drafts", response_class=HTMLResponse)
    async def drafts_list(request: Request):
        conn = get_conn()
        try:
            items = conn.execute("SELECT * FROM draft ORDER BY updated_at DESC").fetchall()
            return TEMPLATES.TemplateResponse(request, "drafts.html",
                ctx(request, nav="drafts", items=items),
            )
        finally:
            conn.close()

    @app.get("/draft/{opportunity_id}", response_class=HTMLResponse)
    async def draft_get(request: Request, opportunity_id: int):
        conn = get_conn()
        try:
            existing = conn.execute(
                "SELECT * FROM draft WHERE opportunity_id=?", (opportunity_id,)
            ).fetchone()
            opp = conn.execute(
                "SELECT * FROM opportunity WHERE id=?", (opportunity_id,)
            ).fetchone()
            if not opp:
                return RedirectResponse("/start?err=1&flash=Missing", status_code=303)
            researcher = conn.execute(
                "SELECT * FROM researcher WHERE id=?", (opp["researcher_id"],)
            ).fetchone()
            error = None
            if existing:
                draft = dict(existing)
            else:
                facts = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed=1"
                    )
                ]
                pubs = [
                    dict(p)
                    for p in conn.execute(
                        "SELECT title, year, url, abstract FROM publication WHERE researcher_id=?",
                        (opp["researcher_id"],),
                    )
                ]
                short = conn.execute(
                    "SELECT rank_explanation FROM shortlist_item WHERE opportunity_id=?",
                    (opportunity_id,),
                ).fetchone()
                from studio.rank_payload import parse_rank_explanation

                reasons, _intel = parse_rank_explanation(
                    short["rank_explanation"] if short else None
                )
                try:
                    generated = generate_draft(
                        researcher["display_name"] if researcher else "",
                        researcher["email"] if researcher and researcher["email"] else "",
                        facts,
                        pubs,
                        reasons,
                        opportunity=dict(opp),
                    )
                    did = save_or_update_draft(conn, opportunity_id, generated)
                    draft = dict(
                        conn.execute("SELECT * FROM draft WHERE id=?", (did,)).fetchone()
                    )
                except ValueError as exc:
                    error = str(exc)
                    draft = {
                        "id": 0,
                        "recipient": (researcher["email"] if researcher else "") or "",
                        "subject": "",
                        "body": "",
                        "content_hash": "",
                        "approved_hash": None,
                    }
            active = get_active_provider()
            ai_status = active.get_status() if active else None
            facts_h = [
                dict(r)
                for r in conn.execute(
                    "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed=1"
                )
            ]
            pubs_h = [
                dict(p)
                for p in conn.execute(
                    "SELECT title, url, abstract FROM publication WHERE researcher_id=?",
                    (opp["researcher_id"],),
                )
            ]
            evidence_h = [f["body"] for f in facts_h]
            evidence_h.extend([p.get("title") or "" for p in pubs_h])
            evidence_h.extend([p.get("url") or "" for p in pubs_h])
            handoff_req = EvidenceBoundRequest(
                recipient=draft.get("recipient") or "",
                subject=draft.get("subject") or "",
                body=draft.get("body") or "",
                evidence_snippets=evidence_h,
                citations=[
                    {
                        "applicant": next(
                            (f["body"] for f in facts_h if f["kind"] == "project"), ""
                        ),
                        "source": (
                            pubs_h[0].get("abstract") or pubs_h[0].get("title")
                            if pubs_h
                            else ""
                        ),
                        "url": (pubs_h[0].get("url") if pubs_h else ""),
                    }
                ],
            )
            handoff_prompt = build_handoff_prompt(handoff_req)
            from studio.drafting.evidence import build_evidence_graph
            from studio.drafting.quality import inspect_application_quality

            aff = conn.execute(
                "SELECT institution FROM affiliation WHERE researcher_id=? AND is_current=1",
                (opp["researcher_id"],),
            ).fetchone()
            ev_graph = build_evidence_graph(facts_h, pubs_h, [], opportunity=dict(opp))
            quality = inspect_application_quality(
                subject=draft.get("subject") or "",
                body=draft.get("body") or "",
                researcher_name=(researcher["display_name"] if researcher else "") or "",
                institution=(aff["institution"] if aff else None),
                evidence=ev_graph,
                opportunity=dict(opp),
            )
            return TEMPLATES.TemplateResponse(request, "draft.html",
                ctx(
                    request,
                    nav="drafts",
                    opportunity_id=opportunity_id,
                    draft=draft,
                    error=error,
                    quality=quality.to_dict(),
                    mailto=mailto_link(draft["recipient"], draft["subject"], draft["body"]),
                    ai_status=ai_status,
                    rewrite_note=request.query_params.get("rewrite"),
                    rewrite_error=request.query_params.get("rwerr") == "1",
                    handoff_targets=HANDOFF_TARGETS,
                    handoff_prompt=handoff_prompt,
                ),
            )
        finally:
            conn.close()

    @app.post("/draft/{opportunity_id}/handoff-import")
    async def draft_handoff_import(
        opportunity_id: int,
        page_token: str = Form(...),
        body: str = Form(""),
    ):
        require_token(page_token)
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM draft WHERE opportunity_id=?", (opportunity_id,)
            ).fetchone()
            if not row:
                return RedirectResponse(
                    f"/draft/{opportunity_id}?rewrite=No%20draft%20yet&rwerr=1",
                    status_code=303,
                )
            facts = [
                dict(r)
                for r in conn.execute(
                    "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed=1"
                )
            ]
            opp = conn.execute(
                "SELECT * FROM opportunity WHERE id=?", (opportunity_id,)
            ).fetchone()
            pubs = [
                dict(p)
                for p in conn.execute(
                    "SELECT title, url, abstract FROM publication WHERE researcher_id=?",
                    (opp["researcher_id"],),
                )
            ] if opp else []
            evidence = [f["body"] for f in facts]
            evidence.extend([p.get("title") or "" for p in pubs])
            evidence.extend([p.get("url") or "" for p in pubs])
            evidence.extend([p.get("abstract") or "" for p in pubs])
            req = EvidenceBoundRequest(
                recipient=row["recipient"],
                subject=row["subject"],
                body=row["body"],
                evidence_snippets=evidence,
                citations=[
                    {
                        "applicant": next(
                            (f["body"] for f in facts if f["kind"] == "project"), ""
                        ),
                        "source": (
                            pubs[0].get("abstract") or pubs[0].get("title") if pubs else ""
                        ),
                        "url": (pubs[0].get("url") if pubs else ""),
                    }
                ],
            )
            result = import_handoff_body(req, body)
            if result.ok and result.body:
                clear_approval_if_edited(
                    conn,
                    int(row["id"]),
                    row["recipient"],
                    result.subject or row["subject"],
                    result.body,
                )
                save_or_update_draft(
                    conn,
                    opportunity_id,
                    {
                        "recipient": row["recipient"],
                        "subject": result.subject or row["subject"],
                        "body": result.body,
                        "content_hash": content_hash(
                            row["recipient"],
                            result.subject or row["subject"],
                            result.body,
                        ),
                    },
                )
                note = "Imported from your AI and validated"
                err = ""
            else:
                note = result.error or "Import failed evidence checks"
                err = "1"
            return RedirectResponse(
                f"/draft/{opportunity_id}?rewrite={quote(note)}"
                + (f"&rwerr={err}" if err else ""),
                status_code=303,
            )
        finally:
            conn.close()

    @app.post("/draft/{opportunity_id}/rewrite")
    async def draft_rewrite(opportunity_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM draft WHERE opportunity_id=?", (opportunity_id,)
            ).fetchone()
            if not row:
                return RedirectResponse(
                    f"/draft/{opportunity_id}?rewrite=No%20draft%20yet&rwerr=1",
                    status_code=303,
                )
            facts = [
                dict(r)
                for r in conn.execute(
                    "SELECT kind, body, confirmed FROM profile_fact WHERE confirmed=1"
                )
            ]
            opp = conn.execute(
                "SELECT * FROM opportunity WHERE id=?", (opportunity_id,)
            ).fetchone()
            pubs = [
                dict(p)
                for p in conn.execute(
                    "SELECT title, url, abstract FROM publication WHERE researcher_id=?",
                    (opp["researcher_id"],),
                )
            ] if opp else []
            evidence = [f["body"] for f in facts]
            evidence.extend([p.get("title") or "" for p in pubs])
            evidence.extend([p.get("url") or "" for p in pubs])
            evidence.extend([p.get("abstract") or "" for p in pubs])
            citations = [
                {
                    "applicant": next((f["body"] for f in facts if f["kind"] == "project"), ""),
                    "source": (pubs[0].get("abstract") or pubs[0].get("title") if pubs else ""),
                    "url": (pubs[0].get("url") if pubs else ""),
                }
            ]
            req = EvidenceBoundRequest(
                recipient=row["recipient"],
                subject=row["subject"],
                body=row["body"],
                evidence_snippets=evidence,
                citations=citations,
            )
            result = rewrite_draft(req)
            if result.ok and result.body:
                clear_approval_if_edited(
                    conn, int(row["id"]), row["recipient"], result.subject or row["subject"], result.body
                )
            note = result.error or (
                f"Rewritten with {result.provider_id}"
                if not result.used_deterministic_fallback
                else "Kept built-in draft"
            )
            err = "1" if (result.rejected_claims or (result.error and result.used_deterministic_fallback and not result.ok)) else ""
            if result.rejected_claims:
                err = "1"
                note = result.rejected_claims[0]
            return RedirectResponse(
                f"/draft/{opportunity_id}?rewrite={quote(note)}"
                + (f"&rwerr={err}" if err else ""),
                status_code=303,
            )
        finally:
            conn.close()

    @app.post("/draft/{opportunity_id}")
    async def draft_post(
        opportunity_id: int,
        page_token: str = Form(...),
        recipient: str = Form(""),
        subject: str = Form(""),
        body: str = Form(""),
        action: str = Form("save"),
    ):
        require_token(page_token)
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT id FROM draft WHERE opportunity_id=?", (opportunity_id,)
            ).fetchone()
            if not row:
                h = content_hash(recipient, subject, body)
                did = save_or_update_draft(
                    conn,
                    opportunity_id,
                    {
                        "recipient": recipient,
                        "subject": subject,
                        "body": body,
                        "content_hash": h,
                    },
                )
            else:
                did = int(row["id"])
                clear_approval_if_edited(conn, did, recipient, subject, body)
            if action == "approve":
                try:
                    approve_draft(conn, did)
                    # ensure application row
                    app = conn.execute(
                        "SELECT id FROM application WHERE opportunity_id=?",
                        (opportunity_id,),
                    ).fetchone()
                    if not app:
                        conn.execute(
                            """
                            INSERT INTO application(opportunity_id, channel, state)
                            VALUES (?, 'email', 'ready')
                            """,
                            (opportunity_id,),
                        )
                    else:
                        conn.execute(
                            "UPDATE application SET state='ready', updated_at=datetime('now') WHERE id=?",
                            (app["id"],),
                        )
                except ValueError as exc:
                    return RedirectResponse(
                        f"/draft/{opportunity_id}?flash={quote(str(exc))}&err=1",
                        status_code=303,
                    )
        finally:
            conn.close()
        return RedirectResponse(f"/draft/{opportunity_id}?flash=Saved", status_code=303)

    @app.get("/draft/{draft_id}/eml")
    async def draft_eml(draft_id: int):
        conn = get_conn()
        try:
            # accept opportunity id or draft id
            row = conn.execute("SELECT * FROM draft WHERE id=?", (draft_id,)).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM draft WHERE opportunity_id=?", (draft_id,)
                ).fetchone()
            if not row:
                return Response("Not found", status_code=404)
            data = to_eml(row["recipient"], row["subject"], row["body"])
            return Response(
                data,
                media_type="message/rfc822",
                headers={"Content-Disposition": f'attachment; filename="draft-{row["id"]}.eml"'},
            )
        finally:
            conn.close()

    @app.post("/draft/{draft_id}/sent-by-me")
    async def draft_sent_by_me(draft_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM draft WHERE id=?", (draft_id,)).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM draft WHERE opportunity_id=?", (draft_id,)
                ).fetchone()
            if row:
                app = conn.execute(
                    "SELECT id FROM application WHERE opportunity_id=?",
                    (row["opportunity_id"],),
                ).fetchone()
                if app:
                    conn.execute(
                        "UPDATE application SET state='submitted_by_me', updated_at=datetime('now') WHERE id=?",
                        (app["id"],),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO application(opportunity_id, channel, state)
                        VALUES (?, 'email', 'submitted_by_me')
                        """,
                        (row["opportunity_id"],),
                    )
                oid = row["opportunity_id"]
            else:
                oid = draft_id
        finally:
            conn.close()
        return RedirectResponse(f"/draft/{oid}?flash=Marked%20sent", status_code=303)

    @app.post("/draft/{draft_id}/open-chat")
    async def draft_open_chat(
        draft_id: int, page_token: str = Form(...), provider: str = Form("chatgpt")
    ):
        require_token(page_token)
        urls = {
            "chatgpt": "https://chatgpt.com/",
            "claude": "https://claude.ai/",
            "gemini": "https://gemini.google.com/",
            "copilot": "https://github.com/copilot",
        }
        return RedirectResponse(urls.get(provider, "https://chatgpt.com/"), status_code=303)

    # ---- S6 Tracker ----
    @app.get("/tracker", response_class=HTMLResponse)
    async def tracker(request: Request):
        from studio.reminders import group_kanban, open_reminders, sync_deadline_reminders

        conn = get_conn()
        try:
            sync_deadline_reminders(conn)
            items = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT a.*, r.display_name AS name
                    FROM application a
                    JOIN opportunity o ON o.id = a.opportunity_id
                    JOIN researcher r ON r.id = o.researcher_id
                    ORDER BY a.updated_at DESC
                    """
                )
            ]
            return TEMPLATES.TemplateResponse(
                request,
                "tracker.html",
                ctx(
                    request,
                    nav="tracker",
                    items=items,
                    columns=group_kanban(items),
                    states=APPLICATION_STATES,
                    reminders=open_reminders(conn),
                ),
            )
        finally:
            conn.close()

    @app.get("/tracker/timeline", response_class=HTMLResponse)
    async def tracker_timeline(request: Request):
        conn = get_conn()
        try:
            items = conn.execute(
                """
                SELECT a.*, r.display_name AS name
                FROM application a
                JOIN opportunity o ON o.id = a.opportunity_id
                JOIN researcher r ON r.id = o.researcher_id
                ORDER BY a.updated_at DESC
                """
            ).fetchall()
            return TEMPLATES.TemplateResponse(
                request,
                "tracker_timeline.html",
                ctx(request, nav="tracker", items=items),
            )
        finally:
            conn.close()

    @app.post("/tracker/{app_id}/state")
    async def tracker_state(app_id: int, page_token: str = Form(...), state: str = Form(...)):
        require_token(page_token)
        if state not in APPLICATION_STATES:
            return RedirectResponse("/tracker?err=1&flash=Bad%20state", status_code=303)
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE application SET state=?, updated_at=datetime('now') WHERE id=?",
                (state, app_id),
            )
            from studio.reminders import sync_deadline_reminders

            sync_deadline_reminders(conn)
        finally:
            conn.close()
        return RedirectResponse("/tracker", status_code=303)

    @app.post("/tracker/{app_id}/notes")
    async def tracker_notes(app_id: int, page_token: str = Form(...), notes: str = Form("")):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE application SET notes=?, updated_at=datetime('now') WHERE id=?",
                (notes.strip() or None, app_id),
            )
        finally:
            conn.close()
        return RedirectResponse("/tracker", status_code=303)

    @app.post("/tracker/reminder/{rem_id}/dismiss")
    async def tracker_dismiss_reminder(rem_id: int, page_token: str = Form(...)):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute("UPDATE reminder SET dismissed=1 WHERE id=?", (rem_id,))
        finally:
            conn.close()
        return RedirectResponse("/tracker", status_code=303)

    @app.get("/tracker/export")
    async def tracker_export():
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT a.id, r.display_name, a.channel, a.state, a.deadline, a.link, a.notes
                FROM application a
                JOIN opportunity o ON o.id = a.opportunity_id
                JOIN researcher r ON r.id = o.researcher_id
                """
            ).fetchall()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "name", "channel", "state", "deadline", "link", "notes"])
            for r in rows:
                w.writerow(
                    [
                        r["id"],
                        r["display_name"],
                        r["channel"],
                        r["state"],
                        r["deadline"],
                        r["link"],
                        r["notes"],
                    ]
                )
            return Response(
                buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=applications.csv"},
            )
        finally:
            conn.close()

    @app.post("/tracker/delete-all")
    async def tracker_delete_all(page_token: str = Form(...), confirm: str = Form("")):
        require_token(page_token)
        if confirm.strip() != "DELETE":
            return RedirectResponse(
                "/tracker?err=1&flash=Type%20DELETE%20to%20confirm", status_code=303
            )
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM profile_fact")
            conn.execute("DELETE FROM draft")
            conn.execute("DELETE FROM application_file")
            conn.execute("DELETE FROM reminder")
            conn.execute("DELETE FROM application")
            conn.execute("DELETE FROM send_intent")
            conn.execute("DELETE FROM shortlist_item")
            conn.execute("DELETE FROM suppression")
            # user-imported people (not bundled)
            conn.execute(
                """
                DELETE FROM researcher WHERE origin IN ('import', 'manual', 'url', 'faculty')
                """
            )
            conn.execute(
                """
                UPDATE applicant SET degree_year=NULL, countries=NULL, dates_free=NULL,
                    github_url=NULL, portfolio_url=NULL, funding_need='no_preference',
                    mode='internship', updated_at=datetime('now')
                WHERE id=1
                """
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        # Personal credentials only — bundled library / demo / binaries preserved (FR-23)
        delete_all_studio_secrets()
        disconnect_github()
        return RedirectResponse(
            "/profile?flash=Personal%20records%20deleted.%20Bundled%20library%20kept.",
            status_code=303,
        )

    # ---- S7 Mail / Connect your email ----
    @app.get("/mail", response_class=HTMLResponse)
    async def mail_get(request: Request):
        conn = get_conn()
        try:
            drafts = conn.execute(
                """
                SELECT * FROM draft
                ORDER BY updated_at DESC
                LIMIT 20
                """
            ).fetchall()
            summary = active_mail_summary()
            smtp = {
                "host": get_secret("smtp_host") or "",
                "port": get_secret("smtp_port") or "465",
                "username": get_secret("smtp_username") or "",
                "sender": get_secret("smtp_sender") or "",
                "use_tls": get_secret("smtp_use_tls") == "1",
                "use_ssl": get_secret("smtp_use_ssl") == "1",
            }
            smtp_connected = bool(get_secret("smtp_host") and get_secret("smtp_sender"))
            ok_quota, quota_label = can_send_now()
            discover_email = (request.query_params.get("email") or "").strip()
            discovery = None
            suggested_username = ""
            if discover_email:
                # Registry + offline paths first; network ISPDB only when needed
                disc = discover_email_config(discover_email, allow_network=False)
                if disc.auth_method == "manual":
                    disc = discover_email_config(discover_email, allow_network=True)
                discovery = disc.as_dict()
                if disc.smtp:
                    suggested_username = disc.smtp.resolved_username(disc.email)
            return TEMPLATES.TemplateResponse(
                request,
                "mail.html",
                ctx(
                    request,
                    nav="mail",
                    drafts=drafts,
                    smtp=smtp,
                    smtp_connected=smtp_connected,
                    mailbox_ready=summary["mailbox_ready"],
                    mailbox_kind=summary["kind"],
                    gmail=summary["gmail"],
                    outlook=summary["outlook"],
                    institute=summary["institute"],
                    discover_email=discover_email,
                    discovery=discovery,
                    suggested_username=suggested_username,
                    quota_label=quota_label,
                    quota_ok=ok_quota,
                    daily_limit=mail_daily_limit(),
                    google_client_id=get_secret(GOOGLE_CLIENT_ID_SECRET) or "",
                    microsoft_client_id=get_secret(MICROSOFT_CLIENT_ID_SECRET) or "",
                ),
            )
        finally:
            conn.close()

    @app.post("/mail/discover")
    async def mail_discover(page_token: str = Form(...), email: str = Form("")):
        require_token(page_token)
        email = (email or "").strip()
        if not email:
            return RedirectResponse(
                "/mail?err=1&flash=Enter%20an%20email%20address",
                status_code=303,
            )
        return RedirectResponse(
            f"/mail?email={quote(email)}",
            status_code=303,
        )

    @app.post("/mail/connect/institute")
    async def mail_connect_institute(
        page_token: str = Form(...),
        email: str = Form(""),
        username: str = Form(""),
        password: str = Form(""),
    ):
        require_token(page_token)
        result = connect_institute(email, username, password, allow_network=True)
        if result.get("ok"):
            return RedirectResponse(
                f"/mail?flash={quote(result.get('message') or 'Connected')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/mail?email={quote(email)}&err=1&flash={quote(result.get('message') or 'Connect failed')}",
            status_code=303,
        )

    @app.post("/mail/disconnect/institute")
    async def mail_disconnect_institute(page_token: str = Form(...)):
        require_token(page_token)
        disconnect_institute()
        return RedirectResponse(
            "/mail?flash=Institutional%20email%20disconnected", status_code=303
        )

    @app.post("/mail/connect")
    async def mail_connect(
        page_token: str = Form(...),
        host: str = Form(""),
        port: str = Form("465"),
        username: str = Form(""),
        password: str = Form(""),
        sender: str = Form(""),
        use_tls: str = Form(""),
        use_ssl: str = Form(""),
    ):
        require_token(page_token)
        result = connect_manual_smtp(
            host=host,
            port=port,
            username=username,
            password=password,
            sender=sender,
            use_tls=bool(use_tls),
            use_ssl=bool(use_ssl) or (port.strip() == "465"),
        )
        if not result.get("ok"):
            return RedirectResponse(
                f"/mail?err=1&flash={quote(result.get('message') or 'Save failed')}",
                status_code=303,
            )
        return RedirectResponse("/mail?flash=Mailbox%20saved", status_code=303)

    @app.post("/mail/connect/gmail")
    async def mail_connect_gmail(page_token: str = Form(...)):
        require_token(page_token)
        port = os.environ.get("STUDIO_PORT", "8765")
        callback_base = f"http://127.0.0.1:{port}"
        result = start_gmail_oauth(callback_base)
        if result.get("ok") and result.get("redirect_url"):
            return RedirectResponse(result["redirect_url"], status_code=303)
        return RedirectResponse(
            f"/mail?err=1&flash={quote(result.get('message') or 'Gmail connect failed')}",
            status_code=303,
        )

    @app.post("/mail/connect/outlook")
    async def mail_connect_outlook(page_token: str = Form(...)):
        require_token(page_token)
        port = os.environ.get("STUDIO_PORT", "8765")
        callback_base = f"http://127.0.0.1:{port}"
        result = start_outlook_oauth(callback_base)
        if result.get("ok") and result.get("redirect_url"):
            return RedirectResponse(result["redirect_url"], status_code=303)
        return RedirectResponse(
            f"/mail?err=1&flash={quote(result.get('message') or 'Outlook connect failed')}",
            status_code=303,
        )

    @app.get("/mail/callback/gmail")
    async def mail_callback_gmail(code: str = "", state: str = "", error: str = ""):
        if error:
            return RedirectResponse(
                f"/mail?err=1&flash={quote(error)}", status_code=303
            )
        result = finish_gmail_oauth(code=code, state=state)
        if result.get("ok"):
            return RedirectResponse(
                f"/mail?flash={quote(result.get('message') or 'Gmail connected')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/mail?err=1&flash={quote(result.get('message') or 'Gmail connect failed')}",
            status_code=303,
        )

    @app.get("/mail/callback/outlook")
    async def mail_callback_outlook(code: str = "", state: str = "", error: str = ""):
        if error:
            return RedirectResponse(
                f"/mail?err=1&flash={quote(error)}", status_code=303
            )
        result = finish_outlook_oauth(code=code, state=state)
        if result.get("ok"):
            return RedirectResponse(
                f"/mail?flash={quote(result.get('message') or 'Outlook connected')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/mail?err=1&flash={quote(result.get('message') or 'Outlook connect failed')}",
            status_code=303,
        )

    @app.post("/mail/finish/gmail")
    async def mail_finish_gmail(
        page_token: str = Form(...),
        code: str = Form(""),
        state: str = Form(""),
    ):
        require_token(page_token)
        result = finish_gmail_oauth(code=code, state=state)
        if result.get("ok"):
            return RedirectResponse(
                f"/mail?flash={quote(result.get('message') or 'Gmail connected')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/mail?err=1&flash={quote(result.get('message') or 'Exchange failed')}",
            status_code=303,
        )

    @app.post("/mail/disconnect/gmail")
    async def mail_disconnect_gmail(page_token: str = Form(...)):
        require_token(page_token)
        disconnect_gmail()
        return RedirectResponse("/mail?flash=Gmail%20disconnected", status_code=303)

    @app.post("/mail/disconnect/outlook")
    async def mail_disconnect_outlook(page_token: str = Form(...)):
        require_token(page_token)
        disconnect_outlook()
        return RedirectResponse("/mail?flash=Outlook%20disconnected", status_code=303)

    @app.post("/mail/setup-later")
    async def mail_setup_later(page_token: str = Form(...)):
        require_token(page_token)
        return RedirectResponse(
            "/drafts?flash=You%20can%20connect%20email%20later%20from%20Mail",
            status_code=303,
        )

    @app.post("/mail/google-client")
    async def mail_google_client(
        page_token: str = Form(...),
        client_id: str = Form(""),
        client_secret: str = Form(""),
    ):
        require_token(page_token)
        if not client_id.strip():
            return RedirectResponse(
                "/mail?err=1&flash=Google%20client%20id%20required",
                status_code=303,
            )
        set_secret(GOOGLE_CLIENT_ID_SECRET, client_id.strip())
        if client_secret.strip():
            set_secret(GOOGLE_CLIENT_SECRET_SECRET, client_secret.strip())
        return RedirectResponse("/mail?flash=Google%20client%20saved", status_code=303)

    @app.post("/mail/microsoft-client")
    async def mail_microsoft_client(
        page_token: str = Form(...),
        client_id: str = Form(""),
    ):
        require_token(page_token)
        if not client_id.strip():
            return RedirectResponse(
                "/mail?err=1&flash=Microsoft%20client%20id%20required",
                status_code=303,
            )
        set_secret(MICROSOFT_CLIENT_ID_SECRET, client_id.strip())
        return RedirectResponse(
            "/mail?flash=Microsoft%20client%20saved", status_code=303
        )

    @app.post("/mail/daily-limit")
    async def mail_set_daily_limit(page_token: str = Form(...), limit: str = Form("")):
        require_token(page_token)
        raw = (limit or "").strip()
        if not raw.isdigit():
            return RedirectResponse(
                "/mail?err=1&flash=Limit%20must%20be%20a%20number",
                status_code=303,
            )
        n = max(1, min(100, int(raw)))
        set_secret("mail_daily_limit", str(n))
        return RedirectResponse(
            f"/mail?flash={quote(f'Daily limit set to {n}')}", status_code=303
        )

    @app.post("/mail/ai-key")
    async def mail_ai_key(page_token: str = Form(...)):
        require_token(page_token)
        return RedirectResponse("/ai", status_code=303)

    @app.post("/mail/ai-disconnect")
    async def mail_ai_disconnect(page_token: str = Form(...)):
        require_token(page_token)
        return RedirectResponse("/ai", status_code=303)

    # ---- BYOAI: Connect your AI ----
    @app.get("/ai", response_class=HTMLResponse)
    async def ai_connect(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "connect_ai.html",
            ctx(
                request,
                nav="ai",
                cards=list_provider_cards(),
                step_heading="Power up your research outreach",
            ),
        )

    @app.get("/ai/groq", response_class=HTMLResponse)
    async def ai_groq_assistant(request: Request):
        from studio.connections.groq import onboarding as groq_onboarding

        view = groq_onboarding.start_assistant(launch_browser=False)
        return TEMPLATES.TemplateResponse(
            request,
            "groq_connect.html",
            ctx(request, nav="ai", view=view),
        )

    @app.post("/ai/groq/launch")
    async def ai_groq_launch(page_token: str = Form(...)):
        require_token(page_token)
        from studio.connections.groq import onboarding as groq_onboarding

        groq_onboarding.start_assistant(launch_browser=True)
        return RedirectResponse("/ai/groq?flash=GroqCloud%20opened", status_code=303)

    @app.post("/ai/groq/finish")
    async def ai_groq_finish(
        page_token: str = Form(...),
        api_key: str = Form(""),
    ):
        require_token(page_token)
        from studio.connections.groq import onboarding as groq_onboarding

        ok, message, _view = groq_onboarding.complete_with_pasted_key(api_key)
        if ok:
            set_active_provider("groq")
            return RedirectResponse(
                f"/ai/groq?flash={quote(message)}", status_code=303
            )
        return RedirectResponse(
            f"/ai/groq?err=1&flash={quote(message)}", status_code=303
        )

    @app.post("/ai/groq/import-local")
    async def ai_groq_import_local(page_token: str = Form(...)):
        require_token(page_token)
        from studio.connections.groq import onboarding as groq_onboarding

        ok, message, _view = groq_onboarding.import_local_env_key_with_consent(
            consented=True
        )
        if ok:
            set_active_provider("groq")
            return RedirectResponse(
                f"/ai/groq?flash={quote(message)}", status_code=303
            )
        return RedirectResponse(
            f"/ai/groq?err=1&flash={quote(message)}", status_code=303
        )

    @app.post("/ai/groq/decline-local")
    async def ai_groq_decline_local(page_token: str = Form(...)):
        require_token(page_token)
        from studio.connections.groq import onboarding as groq_onboarding

        groq_onboarding.import_local_env_key_with_consent(consented=False)
        return RedirectResponse("/ai/groq", status_code=303)

    @app.post("/ai/groq/cancel")
    async def ai_groq_cancel(page_token: str = Form(...)):
        require_token(page_token)
        from studio.connections.groq import onboarding as groq_onboarding

        groq_onboarding.cancel_setup()
        return RedirectResponse(
            "/ai?flash=Groq%20setup%20cancelled", status_code=303
        )

    @app.post("/ai/groq/disconnect")
    async def ai_groq_disconnect(page_token: str = Form(...)):
        require_token(page_token)
        disconnect_provider("groq")
        return RedirectResponse("/ai?flash=Groq%20disconnected", status_code=303)

    @app.get("/ai/mcp", response_class=HTMLResponse)
    async def ai_mcp(request: Request):
        return TEMPLATES.TemplateResponse(
            request, "ai_mcp.html", ctx(request, nav="ai")
        )

    @app.post("/ai/continue-without")
    async def ai_continue_without(page_token: str = Form(...)):
        require_token(page_token)
        continue_without_ai()
        return RedirectResponse(
            "/drafts?flash=Continuing%20with%20built-in%20drafts", status_code=303
        )

    @app.post("/ai/connect/{provider_id}")
    async def ai_connect_provider(
        request: Request, provider_id: str, page_token: str = Form(...)
    ):
        require_token(page_token)
        if provider_id == "groq":
            return RedirectResponse("/ai/groq", status_code=303)
        headless = provider_id == "openrouter-headless"
        pid = "openrouter" if headless else provider_id
        p = get_provider(pid)
        if not p:
            return RedirectResponse("/ai?err=1&flash=Unknown%20provider", status_code=303)
        port = os.environ.get("STUDIO_PORT", "8765")
        callback_base = f"http://127.0.0.1:{port}"
        if headless:
            result = p.connect_headless_start()  # type: ignore[attr-defined]
        else:
            result = p.connect_start(callback_base)
        if result.redirect_url and result.ok and not result.needs_paste_code:
            return RedirectResponse(result.redirect_url, status_code=303)
        if not result.ok and result.redirect_url and not result.needs_paste_code:
            return RedirectResponse(
                f"/ai?err=1&flash={quote(result.message)}", status_code=303
            )
        extra = result.extra or {}
        return TEMPLATES.TemplateResponse(
            request,
            "ai_setup.html",
            ctx(
                request,
                nav="ai",
                provider=p,
                message=result.message,
                redirect_url=result.redirect_url,
                needs_paste=bool(result.needs_paste_code or not result.ok),
                paste_kind=extra.get("paste_kind", "code"),
                guided_title=extra.get("guided_title"),
                guided_steps=extra.get("guided_steps") or [],
                docs_url=extra.get("docs_url"),
            ),
        )

    @app.get("/ai/setup/{provider_id}", response_class=HTMLResponse)
    async def ai_setup_get(request: Request, provider_id: str):
        if provider_id == "groq":
            return RedirectResponse("/ai/groq", status_code=303)
        p = get_provider(provider_id)
        if not p:
            return RedirectResponse("/ai?err=1&flash=Unknown%20provider", status_code=303)
        started = p.connect_start("")
        extra = started.extra or {}
        return TEMPLATES.TemplateResponse(
            request,
            "ai_setup.html",
            ctx(
                request,
                nav="ai",
                provider=p,
                message=started.message or p.get_status().detail,
                redirect_url=started.redirect_url,
                needs_paste=True,
                paste_kind=extra.get("paste_kind", "api_key"),
                guided_title=extra.get("guided_title"),
                guided_steps=extra.get("guided_steps") or [],
                docs_url=extra.get("docs_url"),
            ),
        )

    @app.post("/ai/finish/{provider_id}")
    async def ai_finish_provider(
        provider_id: str,
        page_token: str = Form(...),
        code: str = Form(""),
        api_key: str = Form(""),
        base_url: str = Form(""),
        model: str = Form(""),
        state: str = Form(""),
    ):
        require_token(page_token)
        p = get_provider(provider_id)
        if not p:
            return RedirectResponse("/ai?err=1&flash=Unknown%20provider", status_code=303)
        result = p.connect_finish(
            code=code, api_key=api_key, base_url=base_url, model=model, state=state
        )
        if result.ok:
            set_active_provider(provider_id)
            return RedirectResponse(
                f"/ai?flash={quote(result.message)}", status_code=303
            )
        return RedirectResponse(
            f"/ai?err=1&flash={quote(result.message)}", status_code=303
        )

    @app.get("/ai/callback/{provider_id}")
    async def ai_oauth_callback(
        provider_id: str,
        code: str = "",
        state: str = "",
        error: str = "",
    ):
        if error:
            return RedirectResponse(
                f"/ai?err=1&flash={quote(error)}", status_code=303
            )
        p = get_provider(provider_id)
        if not p:
            return RedirectResponse("/ai?err=1&flash=Unknown%20provider", status_code=303)
        result = p.connect_finish(code=code, state=state)
        if result.ok:
            set_active_provider(provider_id)
            return RedirectResponse(
                f"/ai?flash={quote(result.message)}", status_code=303
            )
        return RedirectResponse(
            f"/ai?err=1&flash={quote(result.message)}", status_code=303
        )

    @app.post("/ai/disconnect/{provider_id}")
    async def ai_disconnect_provider(provider_id: str, page_token: str = Form(...)):
        require_token(page_token)
        disconnect_provider(provider_id)
        return RedirectResponse("/ai?flash=Disconnected", status_code=303)

    @app.post("/ai/activate/{provider_id}")
    async def ai_activate_provider(provider_id: str, page_token: str = Form(...)):
        require_token(page_token)
        p = get_provider(provider_id)
        if not p or not p.get_status().connected:
            return RedirectResponse(
                "/ai?err=1&flash=Connect%20this%20account%20first", status_code=303
            )
        set_active_provider(provider_id)
        return RedirectResponse("/ai?flash=Using%20this%20AI%20for%20rewrite", status_code=303)

    @app.post("/mail/reply-consent")
    async def mail_reply_consent(page_token: str = Form(...), consent: str = Form("")):
        require_token(page_token)
        result = set_reply_consent(bool(consent))
        return RedirectResponse(
            f"/mail?flash={quote(result.get('message') or 'Consent saved')}",
            status_code=303,
        )

    @app.post("/mail/send/{draft_id}")
    async def mail_send(draft_id: int, page_token: str = Form(...)):
        require_token(page_token)
        summary = active_mail_summary()
        if not summary["mailbox_ready"]:
            return RedirectResponse(
                "/mail?err=1&flash=No%20email%20connected.%20Enter%20your%20address%20or%20Continue%20with%20Google.",
                status_code=303,
            )
        ok_quota, quota_msg = can_send_now()
        if not ok_quota:
            return RedirectResponse(
                f"/mail?err=1&flash={quote(quota_msg)}", status_code=303
            )
        kind = summary["kind"]
        provider = "gmail" if kind == "gmail" else "smtp"
        conn = get_conn()
        try:
            draft = conn.execute("SELECT * FROM draft WHERE id=?", (draft_id,)).fetchone()
            if not draft:
                return RedirectResponse(
                    "/mail?err=1&flash=Draft%20missing", status_code=303
                )
            if draft["approved_hash"] != draft["content_hash"]:
                return RedirectResponse(
                    "/mail?err=1&flash=Draft%20is%20not%20approved.%20Approve%20the%20exact%20letter%20first.",
                    status_code=303,
                )
            try:
                intent_id = create_intent(
                    conn, draft_id, draft["content_hash"], provider
                )
            except ValueError as exc:
                return RedirectResponse(
                    f"/mail?err=1&flash={quote(str(exc))}", status_code=303
                )
            smtp_config = None
            if provider == "smtp":
                smtp_config = smtp_config_from_store()
                if not smtp_config:
                    return RedirectResponse(
                        "/mail?err=1&flash=SMTP%20settings%20missing",
                        status_code=303,
                    )
            try:
                perform_send(conn, intent_id, smtp_config)
                record_send()
            except Exception as exc:  # noqa: BLE001
                return RedirectResponse(
                    f"/mail?err=1&flash={quote(str(exc))}", status_code=303
                )
        finally:
            conn.close()
        return RedirectResponse("/mail?flash=Sent", status_code=303)

    # ---- S9 Planner ----
    @app.get("/planner", response_class=HTMLResponse)
    async def planner_get(
        request: Request, queue: str = "hr", stage: str = "FOLLOW_UP_1"
    ):
        conn = get_conn()
        try:
            cap = PERSONAL_GMAIL_CAP
            if queue == "hr":
                df = load_hr_dataframe()
                buckets = classify_hr(df, stage)
                used = sent_in_rolling_24h(df, stage)
                remaining = max(0, cap - used)

                def pack(frame, label_name="Name"):
                    out = []
                    for idx, row in frame.iterrows():
                        out.append(
                            {
                                "index": int(idx) if isinstance(idx, (int,)) else idx,
                                "name": str(row.get(label_name) or row.get("Email") or ""),
                                "company": str(row.get("Company") or ""),
                                "recipient": str(row.get("Email") or ""),
                                "error": str(row.get("Last_Error") or "")
                                if "Last_Error" in frame.columns
                                else "",
                            }
                        )
                    return out

                due = pack(buckets["due"])
                too_early = pack(buckets["too_early"])
                missed = pack(buckets["missed"])
                failed = pack(buckets["failed"])
                preview = None
                if not buckets["due"].empty:
                    preview = preview_row(buckets["due"].iloc[0].to_dict())
            else:
                buckets = academic_queue(conn)
                due = [
                    {
                        "name": r.get("recipient") or f"app-{r['id']}",
                        "recipient": r.get("recipient"),
                        "company": "",
                    }
                    for r in buckets["due"]
                ]
                too_early = [
                    {"name": r.get("recipient") or f"app-{r['id']}", "recipient": r.get("recipient"), "company": ""}
                    for r in buckets["too_early"]
                ]
                missed = []
                failed = []
                remaining = cap
                preview = None
                if due:
                    preview = {
                        "recipient": due[0].get("recipient") or "",
                        "salutation": "Professor",
                        "subject": "Follow-up",
                    }
            return TEMPLATES.TemplateResponse(request, "planner.html",
                ctx(
                    request,
                    nav="planner",
                    queue=queue,
                    stage=stage,
                    due=due,
                    too_early=too_early,
                    missed=missed,
                    failed=failed,
                    remaining=remaining,
                    cap=cap,
                    preview=preview,
                ),
            )
        finally:
            conn.close()

    @app.post("/planner/schedule-again")
    async def planner_schedule_again(page_token: str = Form(...), index: int = Form(...)):
        require_token(page_token)
        csv_path = REPO_ROOT / "data" / "processed" / "cold_email_outreach_all_cleaned_ranked.csv"
        if csv_path.exists():
            schedule_again(csv_path, index)
        return RedirectResponse("/planner?queue=hr&stage=FOLLOW_UP_1&flash=Scheduled", status_code=303)

    @app.post("/planner/run-hr")
    async def planner_run_hr(page_token: str = Form(...), stage: str = Form(...)):
        require_token(page_token)
        # Never auto-send HR from this environment
        return RedirectResponse(
            "/planner?err=1&flash=HR%20send%20disabled%20here", status_code=303
        )

    @app.post("/planner/run-academic")
    async def planner_run_academic(page_token: str = Form(...)):
        require_token(page_token)
        return RedirectResponse(
            "/planner?queue=academic&flash=No%20armed%20follow-ups%20or%20mailbox",
            status_code=303,
        )

    # ---- Backup / restore ----
    @app.get("/backup", response_class=HTMLResponse)
    async def backup_page(request: Request):
        workspace = app_data_dir()
        backup_dir = workspace / "backups"
        backups = []
        if backup_dir.is_dir():
            for p in sorted(backup_dir.glob("studio-backup-*.zip"), reverse=True)[:12]:
                backups.append(
                    {"name": p.name, "size_kb": max(1, p.stat().st_size // 1024)}
                )
        return TEMPLATES.TemplateResponse(
            request,
            "backup.html",
            ctx(request, nav="backup", backups=backups),
        )

    @app.post("/backup/create")
    async def backup_create(page_token: str = Form(...)):
        require_token(page_token)
        from studio.backup import create_backup

        path = create_backup(app_data_dir())
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/zip",
        )

    @app.get("/backup/download/{name}")
    async def backup_download(name: str):
        safe = Path(name).name
        if not safe.startswith("studio-backup-") or not safe.endswith(".zip"):
            return RedirectResponse("/backup?err=1&flash=Bad%20file", status_code=303)
        path = app_data_dir() / "backups" / safe
        if not path.is_file():
            return RedirectResponse("/backup?err=1&flash=Missing", status_code=303)
        return FileResponse(path, filename=safe, media_type="application/zip")

    @app.post("/backup/restore")
    async def backup_restore(
        page_token: str = Form(...),
        zip: UploadFile = File(...),
    ):
        require_token(page_token)
        from studio.backup import restore_backup

        workspace = app_data_dir()
        dest = workspace / "backups" / f"upload-{secrets.token_hex(6)}.zip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = await zip.read()
        if len(data) > 50_000_000:
            return RedirectResponse(
                "/backup?err=1&flash=Backup%20too%20large%20(max%2050MB)",
                status_code=303,
            )
        dest.write_bytes(data)
        try:
            restore_backup(dest, workspace)
        except Exception as exc:  # noqa: BLE001 — surface to flash
            return RedirectResponse(
                f"/backup?err=1&flash={quote(str(exc)[:80])}", status_code=303
            )
        return RedirectResponse("/backup?flash=Restored", status_code=303)

    # ---- S8 Return ----
    @app.get("/return", response_class=HTMLResponse)
    async def return_screen(request: Request):
        conn = get_conn()
        try:
            today = date.today()
            soon = today + timedelta(days=14)
            stale_before = (today - timedelta(days=30)).isoformat()
            deadlines = conn.execute(
                """
                SELECT o.id, r.display_name AS name, o.deadline
                FROM opportunity o
                JOIN researcher r ON r.id = o.researcher_id
                WHERE o.deadline IS NOT NULL
                  AND o.deadline >= ?
                  AND o.deadline <= ?
                ORDER BY o.deadline
                """,
                (today.isoformat(), soon.isoformat()),
            ).fetchall()
            stale = conn.execute(
                """
                SELECT o.id, r.display_name AS name, o.checked_at
                FROM opportunity o
                JOIN researcher r ON r.id = o.researcher_id
                WHERE o.checked_at IS NOT NULL AND o.checked_at < ?
                ORDER BY o.checked_at
                LIMIT 50
                """,
                (stale_before,),
            ).fetchall()
            profiles = conn.execute("SELECT * FROM profile_slot ORDER BY id").fetchall()
            if not profiles:
                profiles = [{"label": "Primary", "is_active": 1}]
            return TEMPLATES.TemplateResponse(request, "return.html",
                ctx(
                    request,
                    nav="return",
                    deadlines=deadlines,
                    stale=stale,
                    profiles=profiles,
                    alerts_on=get_secret("alerts_on") == "1",
                ),
            )
        finally:
            conn.close()

    @app.post("/return/alerts")
    async def return_alerts(page_token: str = Form(...), alerts: str = Form("")):
        require_token(page_token)
        set_secret("alerts_on", "1" if alerts else "0")
        return RedirectResponse("/return?flash=Alerts%20saved", status_code=303)

    @app.post("/return/add-profile")
    async def return_add_profile(page_token: str = Form(...), label: str = Form("")):
        require_token(page_token)
        if not label.strip():
            return RedirectResponse(
                "/return?err=1&flash=Profile%20label%20is%20required",
                status_code=303,
            )
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO profile_slot(label, applicant_mode, is_active) VALUES (?, 'internship', 0)",
                (label.strip(),),
            )
        finally:
            conn.close()
        return RedirectResponse("/return?flash=Profile%20added", status_code=303)

    # ---- Hosted edition ----
    @app.get("/hosted", response_class=HTMLResponse)
    async def hosted_get(request: Request):
        conn = get_conn()
        try:
            accounts = conn.execute("SELECT * FROM hosted_account ORDER BY id").fetchall()
            return TEMPLATES.TemplateResponse(request, "hosted.html",
                ctx(request, nav="", accounts=accounts),
            )
        finally:
            conn.close()

    @app.post("/hosted/create")
    async def hosted_create(
        page_token: str = Form(...),
        email: str = Form(...),
        display_name: str = Form(""),
    ):
        require_token(page_token)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO hosted_account(email, display_name) VALUES (?, ?)",
                (email.strip(), display_name.strip() or None),
            )
        except Exception as exc:  # noqa: BLE001
            conn.close()
            return RedirectResponse(
                f"/hosted?err=1&flash={quote(str(exc))}", status_code=303
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return RedirectResponse("/hosted?flash=Created", status_code=303)

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


def _ensure_library(conn) -> None:
    zip_candidates = [
        Path(os.environ.get("SUMMER_ZIP", "")),
        Path.home() / "Downloads" / "Summer-2027-research-data-20261122.zip",
        bundled_data_dir() / "Summer-2027-research-data-20261122.zip",
    ]
    for z in zip_candidates:
        if z and z.exists():
            try:
                load_summer_zip(conn, z)
                return
            except Exception:
                continue
    seed_mini_bundled(conn)


def _register_jobs() -> None:
    def faculty_handler(payload: dict, progress) -> Any:
        school_id = payload.get("school_id")
        progress(10)
        result = collect_school(school_id)
        progress(70)
        conn = dbmod.connect()
        try:
            if result["people"]:
                import_people(conn, school_id, result["people"])
            elif result.get("error"):
                raise RuntimeError(result["error"])
            progress(100)
            return {"count": len(result["people"]), "error": result.get("error")}
        finally:
            conn.close()

    register_handler("faculty", faculty_handler)

    def match_handler(payload: dict, progress) -> Any:
        progress(20)
        conn = dbmod.connect()
        try:
            n = rebuild_shortlist(conn)
            progress(100)
            return {"count": n}
        finally:
            conn.close()

    register_handler("match", match_handler)


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "studio.app:app",
        host="127.0.0.1",
        port=int(os.environ.get("STUDIO_PORT", "8765")),
        reload=False,
    )


if __name__ == "__main__":
    main()
