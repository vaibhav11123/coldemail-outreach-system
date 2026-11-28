"""Mail intents against local SMTP; planner missed-window; HR CSV untouched."""

from __future__ import annotations

import hashlib
import socket
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from studio.db import connect, migrate, recover_intents_on_startup
from studio.drafts import content_hash, save_or_update_draft
from studio.mailer_studio import create_intent, mark_submitted, perform_send
from studio.planner import classify_hr, preview_row, schedule_again


class _TinySMTP:
    """Minimal SMTP sink for Python 3.12+ (smtpd removed)."""

    def __init__(self, host: str, port: int):
        self.messages: list[dict] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self._sock.listen(5)
        self._sock.settimeout(0.5)
        self._stop = False
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.sendall(b"220 localhost\r\n")
                data_mode = False
                buf = b""
                mailfrom = ""
                rcpttos: list[str] = []
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    if data_mode:
                        if b"\r\n.\r\n" in buf:
                            payload = buf.split(b"\r\n.\r\n", 1)[0]
                            self.messages.append(
                                {"from": mailfrom, "to": rcpttos, "data": payload}
                            )
                            conn.sendall(b"250 OK\r\n")
                            data_mode = False
                            buf = b""
                        continue
                    while b"\r\n" in buf:
                        line, buf = buf.split(b"\r\n", 1)
                        cmd = line.decode("utf-8", errors="replace").upper()
                        if cmd.startswith("EHLO") or cmd.startswith("HELO"):
                            conn.sendall(b"250 localhost\r\n")
                        elif cmd.startswith("MAIL"):
                            mailfrom = line.decode()
                            conn.sendall(b"250 OK\r\n")
                        elif cmd.startswith("RCPT"):
                            rcpttos.append(line.decode())
                            conn.sendall(b"250 OK\r\n")
                        elif cmd.startswith("DATA"):
                            conn.sendall(b"354 End data\r\n")
                            data_mode = True
                            break
                        elif cmd.startswith("QUIT"):
                            conn.sendall(b"221 Bye\r\n")
                            return
                        else:
                            conn.sendall(b"250 OK\r\n")

    def close(self) -> None:
        self._stop = True
        try:
            self._sock.close()
        except OSError:
            pass


@pytest.fixture()
def smtp_sink():
    server = _TinySMTP("127.0.0.1", 0)
    yield server, server.port
    server.close()


def _approved_draft(conn):
    conn.execute("INSERT INTO researcher(display_name, email, origin) VALUES ('T','t@ex.edu','manual')")
    rid = conn.execute("SELECT id FROM researcher ORDER BY id DESC LIMIT 1").fetchone()["id"]
    conn.execute(
        "INSERT INTO opportunity(researcher_id, origin) VALUES (?, 'manual')", (rid,)
    )
    oid = conn.execute("SELECT id FROM opportunity ORDER BY id DESC LIMIT 1").fetchone()["id"]
    body = "Hello"
    h = content_hash("t@ex.edu", "Hi", body)
    did = save_or_update_draft(
        conn, oid, {"recipient": "t@ex.edu", "subject": "Hi", "body": body, "content_hash": h}
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    return did, h


def test_local_smtp_one_message(data_dir, smtp_sink):
    server, port = smtp_sink
    conn = connect(data_dir / "studio.sqlite")
    migrate(conn)
    did, h = _approved_draft(conn)
    intent = create_intent(conn, did, h, "smtp")
    perform_send(
        conn,
        intent,
        {
            "host": "127.0.0.1",
            "port": port,
            "username": "",
            "password": "",
            "sender": "studio@localhost",
            "use_tls": False,
        },
    )
    for _ in range(40):
        if server.messages:
            break
        time.sleep(0.05)
    assert len(server.messages) == 1
    st = conn.execute("SELECT state FROM send_intent WHERE id=?", (intent,)).fetchone()["state"]
    assert st == "sent"
    conn.close()


def test_kill_submitted_unknown_delivery(data_dir):
    conn = connect(data_dir / "studio.sqlite")
    migrate(conn)
    did, h = _approved_draft(conn)
    intent = create_intent(conn, did, h, "smtp")
    mark_submitted(conn, intent)
    n = recover_intents_on_startup(conn)
    assert n == 1
    st = conn.execute("SELECT state FROM send_intent WHERE id=?", (intent,)).fetchone()["state"]
    assert st == "unknown_delivery"
    # second click / perform_send refuses
    with pytest.raises(ValueError):
        perform_send(
            conn,
            intent,
            {"host": "127.0.0.1", "port": 1, "sender": "a@b.c", "use_tls": False},
        )
    conn.close()


def test_planner_missed_window_not_due():
    now = datetime(2026, 11, 28)
    df = pd.DataFrame(
        [
            {
                "Name": "Late",
                "Email": "late@ex.com",
                "Company": "Co",
                "Title": "Intern",
                "HiringScore": 0.9,
                "Sent_Status": "SENT_SUCCESS",
                "Sent_Timestamp": (now - timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S"),
                "FollowUp_1_Status": "PENDING",
                "FollowUp_1_Timestamp": "",
                "FollowUp_2_Status": "PENDING",
                "FollowUp_2_Timestamp": "",
                "scheduled_again_at": "",
            },
            {
                "Name": "Due",
                "Email": "due@ex.com",
                "Company": "Co",
                "Title": "Intern",
                "HiringScore": 0.8,
                "Sent_Status": "SENT_SUCCESS",
                "Sent_Timestamp": (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
                "FollowUp_1_Status": "PENDING",
                "FollowUp_1_Timestamp": "",
                "FollowUp_2_Status": "PENDING",
                "FollowUp_2_Timestamp": "",
                "scheduled_again_at": "",
            },
        ]
    )
    buckets = classify_hr(df, "FOLLOW_UP_1", now=now)
    assert len(buckets["missed"]) == 1
    assert buckets["missed"].iloc[0]["Email"] == "late@ex.com"
    assert len(buckets["due"]) == 1
    assert buckets["due"].iloc[0]["Email"] == "due@ex.com"
    # missed not in due
    assert "late@ex.com" not in set(buckets["due"]["Email"])


def test_schedule_again_flag(tmp_path):
    path = tmp_path / "hr.csv"
    df = pd.DataFrame(
        [
            {
                "Name": "Late",
                "Email": "late@ex.com",
                "Sent_Status": "SENT_SUCCESS",
                "Sent_Timestamp": "2026-11-01 10:00:00",
                "FollowUp_1_Status": "PENDING",
            }
        ]
    )
    df.to_csv(path, index=False)
    schedule_again(path, 0)
    again = pd.read_csv(path)
    assert str(again.loc[0, "scheduled_again_at"]).strip() != ""


def test_preview_hiring_team_when_name_empty():
    p = preview_row({"Name": "", "Email": "hr@co.com", "Company": "Acme", "Title": "", "HiringScore": ""})
    assert p["salutation"] == "Hiring Team"


def test_hr_csv_sent_status_unchanged_after_planner_refresh(client, monkeypatch):
    monkeypatch.setenv("STUDIO_ENABLE_HR_PLANNER", "1")
    csv_path = Path("data/processed/cold_email_outreach_all_cleaned_ranked.csv")
    if not csv_path.exists():
        pytest.skip("HR CSV not present")
    before = csv_path.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    r = client.get("/planner?queue=hr&stage=FOLLOW_UP_1")
    assert r.status_code == 200
    assert "Missed" in r.text or "Due" in r.text
    after = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert after == digest


def test_filters_scheduled_again_accepted():
    from outreach.filters import filter_recipients_by_stage

    now = datetime(2026, 11, 28)
    df = pd.DataFrame(
        [
            {
                "Sent_Status": "SENT_SUCCESS",
                "Sent_Timestamp": (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
                "FollowUp_1_Status": "PENDING",
                "FollowUp_1_Timestamp": "",
                "FollowUp_2_Status": "PENDING",
                "FollowUp_2_Timestamp": "",
                "scheduled_again_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
    )
    out = filter_recipients_by_stage(df, stage="FOLLOW_UP_1", now=now)
    assert len(out) == 1
