"""Universal email discovery + institutional SMTP connect."""

from __future__ import annotations

from studio.mail.discovery import discover_email_config, parse_email
from studio.mail.institute import (
    connect_institute,
    disconnect_institute,
    institute_status,
    smtp_config_from_store,
)
from studio.mail.registry import lookup_domain
from studio.mailer_studio import send_via_smtp


def test_parse_email():
    assert parse_email("Student@IITD.AC.IN") == ("student@iitd.ac.in", "iitd.ac.in")
    assert parse_email("not-an-email") is None


def test_iit_delhi_registry_and_dept_suffix():
    hit = lookup_domain("ee.iitd.ac.in")
    assert hit is not None
    suffix, cfg = hit
    assert suffix == "iitd.ac.in"
    assert cfg["institution"] == "IIT Delhi"
    assert cfg["smtp"].host == "smtp.iitd.ac.in"
    assert cfg["smtp"].port == 465
    assert cfg["imap"].host == "mailstore.iitd.ac.in"
    assert cfg["imap"].port == 993


def test_discover_iit_delhi_offline():
    disc = discover_email_config("student@ee.iitd.ac.in", allow_network=False)
    assert disc.auth_method == "password"
    assert disc.institution == "IIT Delhi"
    assert disc.smtp.host == "smtp.iitd.ac.in"
    assert disc.source == "verified_registry"
    assert "Institutional" in disc.detail or "IIT Delhi" in disc.detail


def test_discover_iitm_and_iitk():
    m = discover_email_config("a@iitm.ac.in", allow_network=False)
    assert m.institution == "IIT Madras"
    assert m.imap.host == "web.zmail.iitm.ac.in"
    k = discover_email_config("b@iitk.ac.in", allow_network=False)
    assert k.institution == "IIT Kanpur"
    assert k.smtp.host == "mmtp.iitk.ac.in"


def test_discover_gmail_oauth_path():
    disc = discover_email_config("me@gmail.com", allow_network=False)
    assert disc.auth_method == "oauth_google"
    assert disc.smtp is None


def test_discover_unknown_manual():
    disc = discover_email_config("x@unlikely-uni-xyz.example", allow_network=False)
    assert disc.auth_method == "manual"


def test_mail_discover_iitd_ui(client):
    r = client.post(
        "/mail/discover",
        data={"page_token": client.page_token, "email": "student@iitd.ac.in"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get("location") or ""
    assert "email=" in loc
    r2 = client.get(loc)
    assert r2.status_code == 200
    assert "Institutional mail configuration detected" in r2.text or "IIT Delhi" in r2.text
    assert "Connect institute email" in r2.text
    assert "Institute login ID" in r2.text
    assert "smtp.iitd.ac.in" in r2.text
    assert "mailstore.iitd.ac.in" in r2.text
    # No password jargon above Advanced for the address step alone — form has institute password after discover
    assert "Institute mail password" in r2.text


def test_mail_discover_gmail_shows_oauth(client):
    r = client.get("/mail?email=me@gmail.com")
    assert r.status_code == 200
    assert "Continue with Google" in r.text
    assert "Connect institute email" not in r.text


def test_connect_institute_refuses_unreachable(monkeypatch):
    monkeypatch.setattr(
        "studio.mail.discovery.verify_endpoints",
        lambda *a, **k: False,
    )
    disconnect_institute()
    result = connect_institute(
        "student@iitd.ac.in",
        "student",
        "secret",
        allow_network=False,
    )
    assert result["ok"] is False
    assert "Credentials were not saved" in result["message"]
    assert institute_status()["connected"] is False


def test_connect_institute_saves_when_reachable(monkeypatch):
    monkeypatch.setattr(
        "studio.mail.discovery.verify_endpoints",
        lambda *a, **k: True,
    )
    disconnect_institute()
    result = connect_institute(
        "student@iitd.ac.in",
        "student",
        "secret",
        allow_network=False,
    )
    assert result["ok"] is True
    st = institute_status()
    assert st["connected"] is True
    assert st["email"] == "student@iitd.ac.in"
    assert st["institution"] == "IIT Delhi"
    cfg = smtp_config_from_store()
    assert cfg is not None
    assert cfg["host"] == "smtp.iitd.ac.in"
    assert cfg["port"] == 465
    assert cfg["use_ssl"] is True
    assert cfg["username"] == "student"
    disconnect_institute()


def test_connect_institute_http(client, monkeypatch):
    monkeypatch.setattr(
        "studio.mail.discovery.verify_endpoints",
        lambda *a, **k: True,
    )
    r = client.post(
        "/mail/connect/institute",
        data={
            "page_token": client.page_token,
            "email": "ada@iitd.ac.in",
            "username": "ada",
            "password": "not-a-real-password",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "err=" not in (r.headers.get("location") or "")
    r2 = client.get("/mail")
    assert "Connected" in r2.text
    assert "ada@iitd.ac.in" in r2.text
    assert "IIT Delhi" in r2.text


def test_smtp_ssl_path_used_for_465(monkeypatch):
    calls = {}

    class FakeSMTP_SSL:
        def __init__(self, host, port, timeout=30):
            calls["ssl"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, u, p):
            calls["login"] = (u, p)

        def send_message(self, msg):
            calls["sent"] = True

    monkeypatch.setattr("studio.mailer_studio.smtplib.SMTP_SSL", FakeSMTP_SSL)
    send_via_smtp(
        host="smtp.iitd.ac.in",
        port=465,
        username="u",
        password="p",
        sender="u@iitd.ac.in",
        recipient="p@ex.edu",
        subject="Hi",
        body="Body",
        use_ssl=True,
    )
    assert calls["ssl"] == ("smtp.iitd.ac.in", 465)
    assert calls["sent"] is True


def test_address_first_screen(client):
    r = client.get("/mail")
    assert r.status_code == 200
    assert "Use your personal or university email" in r.text
    assert 'name="email"' in r.text
    assert "Set up later" in r.text
