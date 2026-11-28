"""Customer Excel workbook for the Global Research Dataset.

Sheets are created only when the packaged rows support them. Nothing here
invents funding, opportunity, country or research facts: every number is
calculated from the rows passed in, and unknowns stay labelled unknown.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from studio.status_labels import effective_opportunity_status, format_tri_state

CREATOR = "Academic Studio"
INK = "172B2A"
ACTION = "246B58"
SECONDARY = "63736E"
BORDER = "DCE5E2"
CANVAS = "F5F7F8"

SHEET_START = "Start Here"
SHEET_COVERAGE = "Coverage"
SHEET_FACULTY = "Faculty Directory"
SHEET_PUBLICATIONS = "Publications"
SHEET_SOURCES = "Sources"
SHEET_DICTIONARY = "Data Dictionary"
SHEET_QUALITY = "Quality Report"
SHEET_CHANGELOG = "Changelog"
SHEET_PROVENANCE = "Provenance"

SHEET_PURPOSE = {
    SHEET_START: "Counts, navigation and how to use this workbook",
    SHEET_COVERAGE: "Universities, research-area hints and completeness of the dataset",
    SHEET_FACULTY: "Every faculty record as a filterable Excel table",
    SHEET_PUBLICATIONS: "Representative papers linked to faculty (when packaged)",
    SHEET_SOURCES: "Unique application and paper URLs (when packaged)",
    SHEET_DICTIONARY: "What each column means and how blanks are written",
    SHEET_QUALITY: "Completeness, freshness, integrity checks and known limits",
    SHEET_CHANGELOG: "Packaging date and record count for this delivery",
}

# (field, workbook header, meaning, null convention)
COLUMN_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "export_id",
        "Export ID",
        "Surrogate id unique to your licensed delivery. Use it as the key across sheets and files.",
        "Always present.",
    ),
    (
        "canonical_id",
        "Catalog ID",
        "Stable internal id of the faculty record in the catalog (same in every delivery).",
        "Always present.",
    ),
    (
        "display_name",
        "Faculty name",
        "Faculty member display name as published by the source.",
        "Always present.",
    ),
    (
        "email",
        "Professional email",
        "Professional email when published by the source.",
        "Empty cell = no email recorded.",
    ),
    (
        "university",
        "University",
        "Current institutional affiliation when known.",
        "Empty cell = affiliation not recorded.",
    ),
    (
        "status",
        "Applications status (reported)",
        "Opening/recruiting status exactly as reported by the source at collection time.",
        "'Application status unconfirmed' = the source did not state a status.",
    ),
    (
        "effective_status",
        "Effective status at packaging date",
        "Reported status adjusted for the deadline: Expired when the deadline had passed on the packaging date.",
        "Computed from Deadline and packaging date; not a live status.",
    ),
    (
        "funding",
        "Funding",
        "Funding signal when present. A mention is not a guarantee of funding.",
        "'Funding unknown' = the source did not state funding. Never inferred.",
    ),
    (
        "eligibility",
        "Eligibility notes",
        "Eligibility notes when present (international eligibility labels or source text).",
        "'International eligibility unconfirmed' = not stated by the source.",
    ),
    (
        "deadline",
        "Application deadline",
        "Application deadline when present (ISO dates are shown as Excel dates; other text is kept as written).",
        "Empty cell = no deadline recorded.",
    ),
    (
        "apply_url",
        "Application / lab URL",
        "Official application or lab URL when present (clickable).",
        "Empty cell = no URL recorded.",
    ),
    (
        "email_invited",
        "Direct inquiries",
        "Whether the source indicates that email inquiries are welcome.",
        "'Contact preference unconfirmed' = not stated by the source.",
    ),
    (
        "note",
        "Opportunity note",
        "Free-text opportunity note from the source.",
        "Empty cell = no note recorded.",
    ),
    (
        "paper_title",
        "Representative paper",
        "Representative publication title when present. A paper is not an open opportunity.",
        "Empty cell = no paper packaged.",
    ),
    (
        "paper_year",
        "Paper year",
        "Publication year of the representative paper.",
        "Empty cell = unknown.",
    ),
    (
        "paper_url",
        "Paper URL",
        "Publication URL when present (clickable).",
        "Empty cell = no URL recorded.",
    ),
    (
        "paper_abstract",
        "Paper abstract (excerpt)",
        "Publication abstract excerpt when present.",
        "Empty cell = no abstract recorded.",
    ),
)

_UNKNOWN_TOKENS = {"", "unknown", "—", "-", "none", "n/a", "null"}
_TRI_TOKENS = {"stated-yes", "stated-no", "unknown", "yes", "no", "open", "closed"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_AREA_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Machine learning", ("machine learning", "deep learning", "neural network", "mixture-of-experts")),
    ("Natural language processing", ("language model", "natural language", "nlp", "translation")),
    ("Computer vision", ("computer vision", "image", "visual", "video")),
    ("Robotics and control", ("robot", "control", "autonomous")),
    ("Systems and architecture", ("systems", "inference", "accelerator", "scheduling", "compiler")),
    ("Security and privacy", ("security", "privacy", "cryptograph", "adversarial")),
    ("Human-computer interaction", ("human-computer", "interaction", "usability", "interface")),
    ("Data and databases", ("database", "data mining", "big data", "retrieval")),
    ("Bioinformatics and genomics", ("genom", "bioinformatic", "protein", "sequenc")),
    ("Neuroscience and health", ("neuro", "clinical", "medical", "health", "cancer")),
    ("Physics and quantum", ("quantum", "photon", "physics")),
    ("Materials and chemistry", ("material", "chemi", "catalys", "polymer")),
    ("Energy and climate", ("energy", "battery", "climate", "solar")),
    ("Mathematics and statistics", ("theorem", "statistic", "optimization", "algorithm")),
)


def default_title(packaged_on: date) -> str:
    return f"Global Research Dataset {packaged_on.year}"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_known(value: Any) -> bool:
    return _clean(value).lower() not in _UNKNOWN_TOKENS


def _is_http(url: str) -> bool:
    return url.lower().startswith(("http://", "https://"))


def _set(cell: Cell, value: Any) -> Cell:
    """Assign a value and keep untrusted text from becoming a formula."""
    cell.value = value
    if cell.data_type == "f":
        cell.data_type = "s"
    return cell


def _label(value: Any, kind: str) -> str:
    """Tri-state tokens become labels; free text is preserved verbatim."""
    raw = _clean(value)
    if raw.lower() in _TRI_TOKENS or raw == "":
        return format_tri_state(raw, kind=kind)
    return raw


def _parse_date(value: Any) -> date | None:
    text = _clean(value)
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _norm_university(value: Any) -> str:
    return " ".join(_clean(value).split())


def _header_style(ws: Worksheet, row: int, start_col: int, end_col: int) -> None:
    for col in range(start_col, end_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=ACTION)
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _title(ws: Worksheet, text: str, subtitle: str | None = None) -> None:
    ws["A1"].value = text
    ws["A1"].font = Font(bold=True, size=18, color=INK)
    if subtitle:
        ws["A2"].value = subtitle
        ws["A2"].font = Font(italic=True, color=SECONDARY)


def _section(ws: Worksheet, row: int, text: str) -> None:
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(bold=True, size=13, color=ACTION)


def _link_internal(cell: Cell, sheet: str, label: str | None = None) -> None:
    cell.value = label or sheet
    cell.hyperlink = Hyperlink(
        ref=cell.coordinate, location=f"'{sheet}'!A1", display=label or sheet
    )
    cell.font = Font(color="0563C1", underline="single")


def _link_external(cell: Cell, url: str) -> None:
    _set(cell, url)
    if _is_http(url):
        cell.hyperlink = url
        cell.font = Font(color="0563C1", underline="single")


def _widths(ws: Worksheet, widths: Iterable[int | float]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _add_table(ws: Worksheet, name: str, header_row: int, ncols: int, last_row: int) -> None:
    if last_row <= header_row:
        return
    ref = f"A{header_row}:{get_column_letter(ncols)}{last_row}"
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False
    )
    ws.add_table(table)
    ws.auto_filter.ref = None


def _back_link(ws: Worksheet, cell: str = "A2") -> None:
    _link_internal(ws[cell], SHEET_START, "← Back to Start Here")


def _percent(num: int, den: int) -> float | None:
    return (num / den) if den else None


def completeness(rows: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    n = len(rows)
    return {
        "Professional email present": (sum(1 for r in rows if _clean(r.get("email"))), n),
        "Funding stated by source": (sum(1 for r in rows if _is_known(r.get("funding"))), n),
        "Application status stated by source": (
            sum(1 for r in rows if _is_known(r.get("status"))),
            n,
        ),
        "Application deadline present": (
            sum(1 for r in rows if _clean(r.get("deadline"))),
            n,
        ),
        "Application / lab URL present": (
            sum(1 for r in rows if _clean(r.get("apply_url"))),
            n,
        ),
        "Representative paper present": (
            sum(1 for r in rows if _clean(r.get("paper_title"))),
            n,
        ),
    }


def university_counts(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for r in rows:
        name = _norm_university(r.get("university"))
        if not name:
            continue
        key = name.casefold()
        display.setdefault(key, name)
        counts[key] += 1
    return sorted(
        ((display[k], c) for k, c in counts.items()),
        key=lambda t: (-t[1], t[0].casefold()),
    )


def country_counts(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Only when rows carry an explicit country field. Never guessed from text."""
    counts: Counter[str] = Counter()
    for r in rows:
        country = " ".join(_clean(r.get("country")).split())
        if country:
            counts[country] += 1
    return sorted(counts.items(), key=lambda t: (-t[1], t[0].casefold()))


def research_area_hints(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Keyword hits in paper titles and notes; a hint, not a classification."""
    out: list[tuple[str, int]] = []
    texts = [f"{_clean(r.get('paper_title'))} {_clean(r.get('note'))}".lower() for r in rows]
    for area, words in _AREA_KEYWORDS:
        hits = sum(1 for t in texts if t.strip() and any(w in t for w in words))
        if hits:
            out.append((area, hits))
    out.sort(key=lambda t: (-t[1], t[0]))
    return out


def _unique_sources(rows: list[dict[str, Any]]) -> list[tuple[str, str, int, str]]:
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        for field, kind in (("apply_url", "Application / lab page"), ("paper_url", "Publication")):
            url = _clean(r.get(field))
            if not url:
                continue
            entry = seen.setdefault(
                url, {"kind": kind, "count": 0, "first": _clean(r.get("display_name"))}
            )
            entry["count"] += 1
    return sorted(
        ((u, e["kind"], e["count"], e["first"]) for u, e in seen.items()),
        key=lambda t: (t[1], t[0]),
    )


def _build_start(
    wb: Workbook,
    rows: list[dict[str, Any]],
    *,
    banner: str,
    packaged_on: date,
    title: str,
    present: list[str],
    sample_of: int | None,
) -> None:
    ws = wb.active
    ws.title = SHEET_START
    ws.sheet_properties.tabColor = ACTION
    _title(ws, title, banner)
    r = 4
    if sample_of is not None:
        _section(ws, r, "Sample notice")
        ws.cell(
            row=r + 1,
            column=1,
            value=(
                f"This is a sample of {len(rows)} of {sample_of} records. It is a preview, "
                "not the complete dataset."
            ),
        )
        r += 3
    _section(ws, r, "At a glance")
    pubs = sum(1 for x in rows if _clean(x.get("paper_title")))
    unis = len(university_counts(rows))
    stats: list[tuple[str, Any]] = [
        ("Faculty records", len(rows)),
        ("Universities", unis),
    ]
    countries = country_counts(rows)
    if countries:
        stats.append(("Countries", len(countries)))
    if pubs:
        stats.append(("Publications (representative papers)", pubs))
    stats.append(("Packaged on", packaged_on.isoformat()))
    for label, val in stats:
        r += 1
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=val).alignment = Alignment(horizontal="left")
    r += 2
    _section(ws, r, "Go to a sheet")
    for sheet in present:
        if sheet == SHEET_START:
            continue
        r += 1
        _link_internal(ws.cell(row=r, column=1), sheet)
        ws.cell(row=r, column=2, value=SHEET_PURPOSE.get(sheet, ""))
    r += 2
    _section(ws, r, "How to use this workbook")
    tips = (
        f"1. Open '{SHEET_FACULTY}' and use the filter arrows in the header row to narrow by university, status or funding.",
        "2. Click a header arrow, then Sort A to Z (or Z to A) to order the table.",
        "3. Use Ctrl+F to search names, universities and paper titles.",
        "4. Application / lab and paper URLs are clickable; open them to confirm details at the source.",
        f"5. Read '{SHEET_DICTIONARY}' for column meanings and '{SHEET_QUALITY}' for known limits.",
        "6. 'Unknown' means the source did not state a value. It never means No.",
        "7. Do not share this workbook; Export IDs identify your licensed delivery.",
    )
    for tip in tips:
        r += 1
        ws.cell(row=r, column=1, value=tip)
    _widths(ws, (38, 70))


def _build_coverage(
    wb: Workbook,
    rows: list[dict[str, Any]],
    *,
    sample_of: int | None,
) -> None:
    ws = wb.create_sheet(SHEET_COVERAGE)
    ws.sheet_properties.tabColor = ACTION
    _title(ws, "Coverage")
    _back_link(ws)
    r = 4
    if sample_of is not None:
        ws.cell(row=r, column=1, value=f"Sample coverage ({len(rows)} of {sample_of} records).")
        r += 2
    _section(ws, r, "Completeness (calculated from this delivery)")
    r += 1
    for col, h in enumerate(("Measure", "Records", "Of total", "Share"), start=1):
        ws.cell(row=r, column=col, value=h)
    _header_style(ws, r, 1, 4)
    for label, (num, den) in completeness(rows).items():
        r += 1
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=num)
        ws.cell(row=r, column=3, value=den)
        share = _percent(num, den)
        c = ws.cell(row=r, column=4, value=share)
        c.number_format = "0.0%"
    r += 2

    countries = country_counts(rows)
    if countries:
        _section(ws, r, "Countries")
        r += 1
        ws.cell(row=r, column=1, value="Country")
        ws.cell(row=r, column=2, value="Faculty records")
        _header_style(ws, r, 1, 2)
        for name, n in countries:
            r += 1
            _set(ws.cell(row=r, column=1), name)
            ws.cell(row=r, column=2, value=n)
        r += 2

    hints = research_area_hints(rows)
    if hints:
        _section(ws, r, "Research-area hints")
        r += 1
        ws.cell(
            row=r,
            column=1,
            value=(
                "Keyword matches on representative paper titles and notes. "
                "A hint, not a classification of each researcher."
            ),
        ).font = Font(italic=True, color=SECONDARY)
        r += 1
        ws.cell(row=r, column=1, value="Area hint")
        ws.cell(row=r, column=2, value="Faculty with a match")
        _header_style(ws, r, 1, 2)
        for name, n in hints:
            r += 1
            ws.cell(row=r, column=1, value=name)
            ws.cell(row=r, column=2, value=n)
        r += 2

    unis = university_counts(rows)
    if unis:
        _section(ws, r, f"Universities ({len(unis)})")
        r += 1
        ws.cell(row=r, column=1, value="University")
        ws.cell(row=r, column=2, value="Faculty records")
        _header_style(ws, r, 1, 2)
        for name, n in unis:
            r += 1
            _set(ws.cell(row=r, column=1), name)
            ws.cell(row=r, column=2, value=n)
    _widths(ws, (52, 24, 12, 10))


def _faculty_value(row: dict[str, Any], field: str, packaged_on: date) -> Any:
    if field == "effective_status":
        eff = effective_opportunity_status(
            status=_clean(row.get("status")) or None,
            deadline=_clean(row.get("deadline")) or None,
            today=packaged_on.isoformat(),
        )
        return eff["label"]
    raw = row.get(field)
    if field == "status":
        return _label(raw, "applications")
    if field == "funding":
        return _label(raw, "funding")
    if field == "eligibility":
        return _label(raw, "international")
    if field == "email_invited":
        return _label(raw, "email_invited")
    if field == "deadline":
        parsed = _parse_date(raw)
        if parsed and len(_clean(raw)) == 10:
            return parsed
        return _clean(raw) or None
    if field == "paper_year":
        text = _clean(raw)
        return int(text) if text.isdigit() else (text or None)
    text = _clean(raw)
    return text or None


def _build_faculty(
    wb: Workbook, rows: list[dict[str, Any]], *, banner: str, packaged_on: date
) -> None:
    ws = wb.create_sheet(SHEET_FACULTY)
    ws.sheet_properties.tabColor = ACTION
    ws["A1"].value = banner
    ws["A1"].font = Font(bold=True, color="0B4F6C")
    _back_link(ws)
    header_row = 3
    specs = COLUMN_SPECS
    for col, spec in enumerate(specs, start=1):
        ws.cell(row=header_row, column=col, value=spec[1])
    _header_style(ws, header_row, 1, len(specs))
    url_fields = {"apply_url", "paper_url"}
    for i, row in enumerate(rows, start=header_row + 1):
        for col, spec in enumerate(specs, start=1):
            field = spec[0]
            value = _faculty_value(row, field, packaged_on)
            cell = ws.cell(row=i, column=col)
            if field in url_fields and isinstance(value, str):
                _link_external(cell, value)
            else:
                _set(cell, value)
            if field == "deadline" and isinstance(value, date):
                cell.number_format = "yyyy-mm-dd"
    last = header_row + len(rows)
    _add_table(ws, "FacultyDirectory", header_row, len(specs), last)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    _widths(ws, (22, 26, 28, 28, 30, 30, 22, 28, 30, 18, 38, 30, 40, 44, 11, 38, 50))


def _build_publications(wb: Workbook, rows: list[dict[str, Any]]) -> bool:
    pubs = [r for r in rows if _clean(r.get("paper_title"))]
    if not pubs:
        return False
    ws = wb.create_sheet(SHEET_PUBLICATIONS)
    ws.sheet_properties.tabColor = SECONDARY
    _title(
        ws,
        "Publications",
        "One representative paper per faculty record, as packaged. A paper is not an open opportunity.",
    )
    _back_link(ws, "A3")
    header_row = 5
    headers = (
        "Export ID",
        "Faculty name",
        "University",
        "Paper title",
        "Year",
        "Paper URL",
        "Abstract (excerpt)",
    )
    for col, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col, value=h)
    _header_style(ws, header_row, 1, len(headers))
    for i, row in enumerate(pubs, start=header_row + 1):
        _set(ws.cell(row=i, column=1), _clean(row.get("export_id")) or None)
        _set(ws.cell(row=i, column=2), _clean(row.get("display_name")) or None)
        _set(ws.cell(row=i, column=3), _clean(row.get("university")) or None)
        _set(ws.cell(row=i, column=4), _clean(row.get("paper_title")))
        year = _clean(row.get("paper_year"))
        _set(ws.cell(row=i, column=5), int(year) if year.isdigit() else (year or None))
        url = _clean(row.get("paper_url"))
        if url:
            _link_external(ws.cell(row=i, column=6), url)
        _set(ws.cell(row=i, column=7), _clean(row.get("paper_abstract")) or None)
    _add_table(ws, "Publications", header_row, len(headers), header_row + len(pubs))
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    _widths(ws, (22, 26, 28, 56, 8, 40, 60))
    return True


def _build_sources(wb: Workbook, rows: list[dict[str, Any]]) -> bool:
    sources = _unique_sources(rows)
    if not sources:
        return False
    ws = wb.create_sheet(SHEET_SOURCES)
    ws.sheet_properties.tabColor = SECONDARY
    _title(ws, "Sources", "Unique URLs referenced by this dataset. Open them to verify at the source.")
    _back_link(ws, "A3")
    header_row = 5
    headers = ("Source type", "URL", "Records referencing it", "First faculty name")
    for col, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col, value=h)
    _header_style(ws, header_row, 1, len(headers))
    for i, (url, kind, count, first) in enumerate(sources, start=header_row + 1):
        ws.cell(row=i, column=1, value=kind)
        _link_external(ws.cell(row=i, column=2), url)
        ws.cell(row=i, column=3, value=count)
        _set(ws.cell(row=i, column=4), first or None)
    _add_table(ws, "Sources", header_row, len(headers), header_row + len(sources))
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    _widths(ws, (24, 70, 22, 30))
    return True


def _build_dictionary(wb: Workbook) -> None:
    ws = wb.create_sheet(SHEET_DICTIONARY)
    ws.sheet_properties.tabColor = SECONDARY
    _title(ws, "Data Dictionary")
    _back_link(ws)
    header_row = 4
    headers = ("Column in Faculty Directory", "Field in CSV / JSON / SQLite", "Meaning", "Null convention")
    for col, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col, value=h)
    _header_style(ws, header_row, 1, len(headers))
    for i, (field, header, meaning, null) in enumerate(COLUMN_SPECS, start=header_row + 1):
        ws.cell(row=i, column=1, value=header)
        ws.cell(
            row=i,
            column=2,
            value=field if field != "effective_status" else "(workbook only)",
        )
        ws.cell(row=i, column=3, value=meaning).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=i, column=4, value=null).alignment = Alignment(wrap_text=True, vertical="top")
    r = header_row + len(COLUMN_SPECS) + 2
    _section(ws, r, "Conventions")
    for line in (
        "Unknown means the source did not state a value. Unknown is never treated as No.",
        "Funding mentioned is not a funding guarantee; confirm with the lab.",
        "CSV, JSON and SQLite keep raw tokens (stated-yes, stated-no, unknown); this workbook shows readable labels.",
        "Factual fields are not altered for fingerprinting. Only Export ID values and row order are personalized.",
    ):
        r += 1
        ws.cell(row=r, column=1, value=line)
    _widths(ws, (34, 30, 80, 52))


def _build_quality(
    wb: Workbook,
    rows: list[dict[str, Any]],
    *,
    packaged_on: date,
    has_publications: bool,
) -> None:
    ws = wb.create_sheet(SHEET_QUALITY)
    ws.sheet_properties.tabColor = SECONDARY
    _title(ws, "Quality Report", f"Calculated from this delivery on {packaged_on.isoformat()}.")
    _back_link(ws, "A3")
    n = len(rows)
    r = 5

    def table(title: str, header: tuple[str, ...], data: list[tuple[Any, ...]], pct_col: int | None = None) -> None:
        nonlocal r
        _section(ws, r, title)
        r += 1
        for col, h in enumerate(header, start=1):
            ws.cell(row=r, column=col, value=h)
        _header_style(ws, r, 1, len(header))
        for rec in data:
            r += 1
            for col, v in enumerate(rec, start=1):
                c = _set(ws.cell(row=r, column=col), v)
                if pct_col is not None and col == pct_col:
                    c.number_format = "0.0%"
                    c.alignment = Alignment(horizontal="left")
        r += 2

    comp = [(k, a, b, _percent(a, b)) for k, (a, b) in completeness(rows).items()]
    table("Completeness", ("Measure", "Records", "Of total", "Share"), comp, pct_col=4)

    deadlines = [_parse_date(x.get("deadline")) for x in rows]
    parsed = [d for d in deadlines if d]
    expired = sum(1 for d in parsed if d < packaged_on)
    unparsed = sum(1 for x in rows if _clean(x.get("deadline")) and _parse_date(x.get("deadline")) is None)
    fresh: list[tuple[Any, ...]] = [
        ("Packaging date", packaged_on.isoformat()),
        ("Records with an ISO deadline", len(parsed)),
        ("Deadlines already past at packaging date", expired),
        ("Deadlines still upcoming at packaging date", len(parsed) - expired),
        ("Deadline text not in ISO date form", unparsed),
        ("Earliest deadline", min(parsed).isoformat() if parsed else "n/a"),
        ("Latest deadline", max(parsed).isoformat() if parsed else "n/a"),
    ]
    years = [int(y) for y in (_clean(x.get("paper_year")) for x in rows) if y.isdigit()]
    if years:
        recent = sum(1 for y in years if y >= packaged_on.year - 2)
        fresh.extend(
            [
                ("Oldest representative paper year", min(years)),
                ("Newest representative paper year", max(years)),
                (f"Papers from {packaged_on.year - 2} onward", recent),
            ]
        )
    table("Freshness", ("Measure", "Value"), fresh)

    emails = [_clean(x.get("email")).casefold() for x in rows if _clean(x.get("email"))]
    email_counts = Counter(emails)
    dup_emails = sum(1 for c in email_counts.values() if c > 1)
    bad_emails = sum(1 for e in emails if not _EMAIL_RE.match(e))
    ids = Counter(_clean(x.get("canonical_id")) for x in rows)
    dup_ids = sum(1 for k, c in ids.items() if k and c > 1)
    integrity = [
        ("Records", n),
        ("Email addresses shared by more than one record", dup_emails),
        ("Email values that do not look like an address", bad_emails),
        ("Catalog IDs that appear more than once", dup_ids),
    ]
    table("Integrity checks", ("Check", "Result"), integrity)

    limits = [
        "Each record carries at most one representative paper; this is not a full bibliography."
        if has_publications
        else "No papers were packaged in this delivery.",
        "Status, funding and eligibility are what the source stated at collection time; they are not live.",
        "Unknown means not stated by the source; it must not be read as No.",
        "No per-record verification date is stored in this edition, so freshness is limited to deadlines and paper years.",
        "Country is not a field in this edition; no country statistics are shown.",
        "Research-area hints on the Coverage sheet are keyword matches, not a taxonomy.",
    ]
    _section(ws, r, "Known limitations")
    for line in limits:
        r += 1
        ws.cell(row=r, column=1, value=line)
    _widths(ws, (62, 20, 14, 10))


def _build_changelog(wb: Workbook, *, packaged_on: date, record_count: int) -> None:
    ws = wb.create_sheet(SHEET_CHANGELOG)
    ws.sheet_properties.tabColor = SECONDARY
    _title(ws, "Changelog")
    _back_link(ws)
    header_row = 4
    headers = ("Delivery", "Packaging date", "Records", "Notes")
    for col, h in enumerate(headers, start=1):
        ws.cell(row=header_row, column=col, value=h)
    _header_style(ws, header_row, 1, len(headers))
    ws.cell(row=header_row + 1, column=1, value="This delivery")
    c = ws.cell(row=header_row + 1, column=2, value=packaged_on)
    c.number_format = "yyyy-mm-dd"
    c.alignment = Alignment(horizontal="left")
    ws.cell(row=header_row + 1, column=3, value=record_count)
    ws.cell(
        row=header_row + 1,
        column=4,
        value="Initial packaging for this licence. No earlier version history is recorded.",
    )
    _widths(ws, (22, 16, 12, 80))


def build_workbook(
    rows: list[dict[str, Any]],
    *,
    banner: str,
    provenance: dict[str, Any],
    packaged_on: date | None = None,
    title: str | None = None,
    sample_of: int | None = None,
) -> Workbook:
    packaged_on = packaged_on or date.today()
    title = title or default_title(packaged_on)
    wb = Workbook()

    has_pubs = any(_clean(r.get("paper_title")) for r in rows)
    has_sources = bool(_unique_sources(rows))
    present = [SHEET_START, SHEET_COVERAGE, SHEET_FACULTY]
    if has_pubs:
        present.append(SHEET_PUBLICATIONS)
    if has_sources:
        present.append(SHEET_SOURCES)
    present.extend([SHEET_DICTIONARY, SHEET_QUALITY, SHEET_CHANGELOG])

    _build_start(
        wb,
        rows,
        banner=banner,
        packaged_on=packaged_on,
        title=title,
        present=present,
        sample_of=sample_of,
    )
    _build_coverage(wb, rows, sample_of=sample_of)
    _build_faculty(wb, rows, banner=banner, packaged_on=packaged_on)
    if has_pubs:
        _build_publications(wb, rows)
    if has_sources:
        _build_sources(wb, rows)
    _build_dictionary(wb)
    _build_quality(wb, rows, packaged_on=packaged_on, has_publications=has_pubs)
    _build_changelog(wb, packaged_on=packaged_on, record_count=len(rows))

    props = wb.properties
    props.creator = CREATOR
    props.lastModifiedBy = CREATOR
    props.title = f"{title} (licensed delivery)" if sample_of is None else f"{title} (sample)"
    props.description = banner
    props.keywords = (
        f"license:{provenance.get('license_id')};customer:{provenance.get('customer_id')}"
    )

    prov = wb.create_sheet(SHEET_PROVENANCE)
    prov["A1"] = "Do not delete — delivery provenance"
    for i, (k, v) in enumerate(provenance.items(), start=3):
        prov.cell(row=i, column=1, value=k)
        prov.cell(row=i, column=2, value=str(v))
    prov.sheet_state = "hidden"
    wb.active = 0
    return wb


def save_workbook(path: Path, wb: Workbook) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def data_dictionary_text() -> str:
    lines = [
        "Global Research Dataset — data dictionary",
        "========================================",
        "",
        "CSV / JSON / SQLite field names are listed first; the Excel header is in brackets.",
        "",
    ]
    for field, header, meaning, null in COLUMN_SPECS:
        if field == "effective_status":
            lines.append(f"(workbook only) [{header}]")
        else:
            lines.append(f"{field} [{header}]")
        lines.append(f"    {meaning}")
        lines.append(f"    Blanks / unknowns: {null}")
        lines.append("")
    lines.extend(
        [
            "Unknown means the source did not state a value; it is never treated as No.",
            "CSV, JSON and SQLite keep raw tokens (stated-yes, stated-no, unknown);",
            "the Excel workbook shows readable labels.",
            "",
            "Factual fields are not altered for fingerprinting. Only export_id values and",
            "row ordering are personalized. Redistribution of this package is prohibited.",
            "",
        ]
    )
    return "\n".join(lines)
