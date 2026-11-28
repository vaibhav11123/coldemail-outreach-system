"""Campaign planner — HR CSV + academic queue. Does not rewrite sent columns on refresh."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from studio.paths import REPO_ROOT

HR_CSV = REPO_ROOT / "data" / "processed" / "cold_email_outreach_all_cleaned_ranked.csv"

# Technical ceiling awareness for legacy HR planner UI only.
# Academic outreach enforces studio.mail.quotas.DEFAULT_DAILY_LIMIT (20), not this number.
PERSONAL_GMAIL_CAP = 400
WORKSPACE_CAP = 2000
WORKSPACE_TRIAL_CAP = 500


def load_hr_dataframe(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or HR_CSV
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    for col in [
        "Sent_Status",
        "Sent_Timestamp",
        "FollowUp_1_Status",
        "FollowUp_1_Timestamp",
        "FollowUp_2_Status",
        "FollowUp_2_Timestamp",
        "scheduled_again_at",
    ]:
        if col not in df.columns:
            df[col] = "" if "Timestamp" in col or col == "scheduled_again_at" else "PENDING"
    return df


def _parse_dt(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(text).to_pydatetime()
    except Exception:
        return None


def classify_hr(df: pd.DataFrame, stage: str, now: datetime | None = None) -> dict[str, pd.DataFrame]:
    now = now or datetime.now()
    if df.empty:
        empty = df.copy()
        return {"due": empty, "too_early": empty, "missed": empty, "failed": empty}

    if stage == "INITIAL_SEND":
        due = df[df["Sent_Status"] == "PENDING"].copy()
        failed = df[df["Sent_Status"].isin(["FAILED_OTHER", "FAILED_REFUSED"])].copy()
        return {
            "due": due,
            "too_early": df.iloc[0:0].copy(),
            "missed": df.iloc[0:0].copy(),
            "failed": failed,
        }

    if stage == "FOLLOW_UP_1":
        base = df[
            (df["Sent_Status"] == "SENT_SUCCESS")
            & (~df["FollowUp_1_Status"].isin(["SENT_SUCCESS", "FAILED_REFUSED"]))
        ].copy()
        base["Sent_DT"] = base["Sent_Timestamp"].apply(_parse_dt)
        base["Sched_DT"] = base["scheduled_again_at"].apply(_parse_dt)
        due_rows, early_rows, missed_rows = [], [], []
        for idx, row in base.iterrows():
            anchor = row["Sched_DT"] or row["Sent_DT"]
            if anchor is None:
                continue
            days = (now - anchor).days
            # scheduled_again uses new anchor — due when days >= 0 within window or immediately if scheduled
            if row["Sched_DT"] is not None:
                if days >= 0:
                    due_rows.append(idx)
                else:
                    early_rows.append(idx)
                continue
            if 6 <= days <= 8:
                due_rows.append(idx)
            elif days < 6:
                early_rows.append(idx)
            else:
                missed_rows.append(idx)
        failed = df[df["FollowUp_1_Status"].isin(["FAILED_OTHER", "FAILED_REFUSED"])].copy()
        return {
            "due": base.loc[due_rows] if due_rows else base.iloc[0:0].copy(),
            "too_early": base.loc[early_rows] if early_rows else base.iloc[0:0].copy(),
            "missed": base.loc[missed_rows] if missed_rows else base.iloc[0:0].copy(),
            "failed": failed,
        }

    # FOLLOW_UP_2
    base = df[
        (df["Sent_Status"] == "SENT_SUCCESS")
        & (df["FollowUp_1_Status"] == "SENT_SUCCESS")
        & (~df["FollowUp_2_Status"].isin(["SENT_SUCCESS", "FAILED_REFUSED"]))
    ].copy()
    base["FU1_DT"] = base["FollowUp_1_Timestamp"].apply(_parse_dt)
    base["Sched_DT"] = base["scheduled_again_at"].apply(_parse_dt)
    due_rows, early_rows, missed_rows = [], [], []
    for idx, row in base.iterrows():
        anchor = row["Sched_DT"] or row["FU1_DT"]
        if anchor is None:
            continue
        days = (now - anchor).days
        if row["Sched_DT"] is not None:
            if days >= 0:
                due_rows.append(idx)
            else:
                early_rows.append(idx)
            continue
        if 6 <= days <= 8:
            due_rows.append(idx)
        elif days < 6:
            early_rows.append(idx)
        else:
            missed_rows.append(idx)
    failed = df[df["FollowUp_2_Status"].isin(["FAILED_OTHER", "FAILED_REFUSED"])].copy()
    return {
        "due": base.loc[due_rows] if due_rows else base.iloc[0:0].copy(),
        "too_early": base.loc[early_rows] if early_rows else base.iloc[0:0].copy(),
        "missed": base.loc[missed_rows] if missed_rows else base.iloc[0:0].copy(),
        "failed": failed,
    }


def sent_in_rolling_24h(df: pd.DataFrame, stage: str, now: datetime | None = None) -> int:
    now = now or datetime.now()
    if stage == "INITIAL_SEND":
        status_col, ts_col = "Sent_Status", "Sent_Timestamp"
    elif stage == "FOLLOW_UP_1":
        status_col, ts_col = "FollowUp_1_Status", "FollowUp_1_Timestamp"
    else:
        status_col, ts_col = "FollowUp_2_Status", "FollowUp_2_Timestamp"
    count = 0
    for _, row in df.iterrows():
        if row.get(status_col) != "SENT_SUCCESS":
            continue
        dt = _parse_dt(row.get(ts_col))
        if dt and now - dt <= timedelta(hours=24):
            count += 1
    return count


def schedule_again(csv_path: Path, index: int) -> None:
    """Write scheduled_again_at for a missed-window row. Does not send."""
    df = pd.read_csv(csv_path)
    if "scheduled_again_at" not in df.columns:
        df["scheduled_again_at"] = ""
    df.loc[index, "scheduled_again_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = str(csv_path) + ".tmp"
    df.to_csv(tmp, index=False)
    Path(tmp).replace(csv_path)


def preview_row(row: dict[str, Any]) -> dict[str, str]:
    name = str(row.get("Name") or "").strip()
    first = name.split()[0] if name else "Hiring"
    if not name or name.lower() in {"nan", "n/a"}:
        salutation = "Hiring Team"
    else:
        salutation = first
    company = str(row.get("Company") or "")
    return {
        "recipient": str(row.get("Email") or ""),
        "salutation": salutation,
        "subject": f"Interest in opportunities at {company}" if company else "Research interest",
        "company": company,
        "title": str(row.get("Title") or ""),
        "score": str(row.get("HiringScore") or ""),
    }


def academic_queue(conn) -> dict[str, list]:
    """Academic applications that are due for follow-up reminders only when armed."""
    rows = conn.execute(
        """
        SELECT a.*, d.recipient, d.subject, r.due_on, r.kind AS reminder_kind
        FROM application a
        LEFT JOIN draft d ON d.opportunity_id = a.opportunity_id
        LEFT JOIN reminder r ON r.application_id = a.id AND r.dismissed = 0
        WHERE a.state IN ('ready', 'submitted_by_me')
        """
    ).fetchall()
    due, early, failed = [], [], []
    today = datetime.now().date()
    for row in rows:
        item = dict(row)
        if row["reminder_kind"] == "follow_up" and row["due_on"]:
            try:
                due_on = datetime.strptime(row["due_on"][:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if due_on <= today:
                due.append(item)
            else:
                early.append(item)
    return {"due": due, "too_early": early, "missed": [], "failed": failed}
