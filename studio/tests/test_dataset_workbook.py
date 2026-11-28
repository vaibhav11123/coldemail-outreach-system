"""Excel packaging: Start Here / Faculty Directory workbook and sample pack."""

from __future__ import annotations

import csv
import os
from datetime import date

import pytest
from openpyxl import load_workbook

os.environ["STUDIO_FORCE_LOCAL_SECRETS"] = "1"

from studio.dataset.fingerprint import FingerprintContext
from studio.dataset.package_standard import package_standard_dataset, write_xlsx
from studio.dataset.sample_pack import select_sample_records, write_sample_pack
from studio.licensing.crypto import IssuerKeys
from studio.packaging_scan import scan_package_dir

TODAY = date(2026, 6, 1)


def _row(i: int, **kw):
    base = {
        "export_id": f"EX-{i:03d}",
        "canonical_id": f"cid-{i}",
        "display_name": f"Person {i}",
        "email": f"p{i}@uni{i % 3}.edu",
        "university": f"University {i % 3}",
        "status": "stated-yes",
        "funding": "unknown",
        "eligibility": "unknown",
        "deadline": "2099-01-01",
        "apply_url": f"https://example.edu/apply/{i}",
        "email_invited": "stated-yes",
        "note": "Open",
        "paper_title": f"Deep learning for topic {i}",
        "paper_year": 2024,
        "paper_url": f"https://example.edu/paper/{i}",
        "paper_abstract": "An abstract.",
    }
    base.update(kw)
    return base


@pytest.fixture()
def rows():
    return [_row(i) for i in range(1, 9)]


def _write(tmp_path, rows, **kw):
    path = tmp_path / "wb.xlsx"
    write_xlsx(
        path,
        rows,
        "Licensed to customer c1",
        {"license_id": "lic1", "customer_id": "c1"},
        packaged_on=TODAY,
        **kw,
    )
    return load_workbook(path)


def test_write_xlsx_has_start_here_and_faculty_directory(tmp_path, rows):
    wb = _write(tmp_path, rows)
    assert wb.sheetnames[:3] == ["Start Here", "Coverage", "Faculty Directory"]
    for name in (
        "Publications",
        "Sources",
        "Data Dictionary",
        "Quality Report",
        "Changelog",
        "Provenance",
    ):
        assert name in wb.sheetnames
    assert wb["Provenance"].sheet_state == "hidden"
    assert wb.active.title == "Start Here"
    assert wb.properties.creator == "Academic Studio"

    start = wb["Start Here"]
    assert start["A1"].value == "Global Research Dataset 2026"
    cells = {c.value: start.cell(row=c.row, column=2).value for c in start["A"] if c.value}
    assert cells["Faculty records"] == 8
    assert cells["Publications (representative papers)"] == 8
    links = [c.hyperlink.location for c in start["A"] if c.hyperlink and c.hyperlink.location]
    assert "'Faculty Directory'!A1" in links
    assert "'Coverage'!A1" in links


def test_faculty_directory_table_freeze_and_readable_headers(tmp_path, rows):
    wb = _write(tmp_path, rows)
    ws = wb["Faculty Directory"]
    assert ws.freeze_panes == "A4"
    assert list(ws.tables) == ["FacultyDirectory"]
    assert ws.tables["FacultyDirectory"].ref.endswith(f"{3 + len(rows)}")
    headers = [c.value for c in ws[3] if c.value]
    assert headers[0] == "Export ID"
    assert "Faculty name" in headers
    assert "stated-yes" not in {c.value for c in ws[4]}
    by_header = {h: i + 1 for i, h in enumerate(headers)}
    assert ws.cell(row=4, column=by_header["Applications status (reported)"]).value == "Applications open"
    assert ws.cell(row=4, column=by_header["Funding"]).value == "Funding unknown"
    assert ws.cell(row=4, column=by_header["Effective status at packaging date"]).value == "Open"
    url_cell = ws.cell(row=4, column=by_header["Application / lab URL"])
    assert url_cell.hyperlink is not None
    assert url_cell.hyperlink.target.startswith("https://example.edu/apply/")


def test_expired_deadline_shows_effective_expired(tmp_path):
    wb = _write(tmp_path, [_row(1, deadline="2020-01-01")])
    ws = wb["Faculty Directory"]
    headers = {c.value: c.column for c in ws[3]}
    assert ws.cell(row=4, column=headers["Effective status at packaging date"]).value == "Expired"
    assert ws.cell(row=4, column=headers["Applications status (reported)"]).value == "Applications open"


def test_no_publications_or_sources_when_data_absent(tmp_path):
    bare = [
        _row(1, paper_title=None, paper_year=None, paper_url=None, paper_abstract=None, apply_url=None),
    ]
    wb = _write(tmp_path, bare)
    assert "Publications" not in wb.sheetnames
    assert "Sources" not in wb.sheetnames
    assert "Faculty Directory" in wb.sheetnames
    labels = [c.value for c in wb["Start Here"]["A"] if c.value]
    assert "Publications (representative papers)" not in labels


def test_country_sheet_content_not_fabricated(tmp_path, rows):
    wb = _write(tmp_path, rows)
    texts = [c.value for row in wb["Coverage"].iter_rows() for c in row if isinstance(c.value, str)]
    assert not any(t == "Countries" for t in texts)
    with_country = [dict(r, country="Canada") for r in rows]
    wb2 = _write(tmp_path, with_country)
    texts2 = [c.value for row in wb2["Coverage"].iter_rows() for c in row if isinstance(c.value, str)]
    assert "Countries" in texts2 and "Canada" in texts2


def test_coverage_completeness_calculated(tmp_path):
    data = [
        _row(1, email="a@x.edu", funding="stated-yes"),
        _row(2, email=None, funding="unknown", deadline=None),
    ]
    wb = _write(tmp_path, data)
    ws = wb["Coverage"]
    found = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] in ("Professional email present", "Funding stated by source", "Application deadline present"):
            found[row[0]] = (row[1], row[2], row[3])
    assert found["Professional email present"] == (1, 2, 0.5)
    assert found["Funding stated by source"] == (1, 2, 0.5)
    assert found["Application deadline present"] == (1, 2, 0.5)


def test_formula_like_text_stays_text(tmp_path):
    wb = _write(tmp_path, [_row(1, display_name="=HYPERLINK(\"http://evil\",\"x\")")])
    cell = wb["Faculty Directory"].cell(row=4, column=3)
    assert cell.data_type != "f"


def test_package_standard_workbook_alias_and_start_here_doc(tmp_path):
    issuer = IssuerKeys.generate()
    ctx = FingerprintContext("cust", "salt", "lic")
    out = tmp_path / "pkg"
    package_standard_dataset(
        records=[{k: v for k, v in _row(i).items() if k != "export_id"} for i in range(1, 6)],
        out_dir=out,
        ctx=ctx,
        issuer=issuer,
        packaged_on=TODAY,
    )
    assert (out / "GlobalResearch.xlsx").exists()
    assert (out / "GlobalResearch.xlsx").read_bytes() == (out / "faculty_catalog.xlsx").read_bytes()
    wb = load_workbook(out / "GlobalResearch.xlsx")
    assert wb.sheetnames[0] == "Start Here"
    assert "Faculty Directory" in wb.sheetnames
    start_txt = (out / "START_HERE.txt").read_text(encoding="utf-8")
    for name in ("Start Here", "Coverage", "Faculty Directory", "Data Dictionary", "Quality Report", "Changelog"):
        assert name in start_txt
    scan_package_dir(out)


def test_sample_pack_is_subset_unfingerprinted(tmp_path):
    records = [{k: v for k, v in _row(i).items() if k != "export_id"} for i in range(1, 41)]
    records[0]["email"] = None  # incomplete rows are skipped while enough complete ones exist
    result = write_sample_pack(records, tmp_path / "sample", n=22, packaged_on=TODAY)
    assert result["sample_records"] == 22
    assert result["total_records"] == 40
    wb = load_workbook(tmp_path / "sample" / "GlobalResearch_SAMPLE.xlsx")
    assert wb.sheetnames[0] == "Start Here"
    ws = wb["Faculty Directory"]
    names = [ws.cell(row=r, column=3).value for r in range(4, 4 + 22)]
    assert "Person 1" not in names
    assert names[0] == "Person 2"
    assert ws.cell(row=4, column=1).value == "SAMPLE-001"
    with (tmp_path / "sample" / "GlobalResearch_SAMPLE.csv").open(encoding="utf-8") as f:
        next(f)
        got = list(csv.DictReader(f))
    assert len(got) == 22
    assert all(r["canonical_id"].startswith("SAMPLE-") for r in got)
    scan_package_dir(tmp_path / "sample")


def test_sample_pack_never_exceeds_available_and_redacts(tmp_path):
    records = [{k: v for k, v in _row(i).items() if k != "export_id"} for i in range(1, 4)]
    assert len(select_sample_records(records, 25)) == 3
    write_sample_pack(records, tmp_path / "s", n=25, packaged_on=TODAY, redact_emails=True)
    with (tmp_path / "s" / "GlobalResearch_SAMPLE.csv").open(encoding="utf-8") as f:
        next(f)
        row = next(csv.DictReader(f))
    assert "***@" in row["email"]
