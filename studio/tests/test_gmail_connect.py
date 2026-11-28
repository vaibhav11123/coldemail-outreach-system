"""Connect your email — Gmail send-only OAuth, quotas, Outlook scaffold."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from studio.mail.gmail import (
    GMAIL_SEND_SCOPES,
    ACCESS_SECRET,
    EMAIL_SECRET,
    REFRESH_SECRET,
    VERIFIER_SECRET,
    disconnect_gmail,
    finish_gmail_oauth,
    gmail_status,
    send_via_gmail,
    start_gmail_oauth,
)
from studio.mail.quotas import (
    DEFAULT_DAILY_LIMIT,
    can_send_now,
    record_send,
    sent_in_rolling_24h,
)
from studio.mailer_studio import create_intent, perform_send
from studio.secrets_store import set_secret


def test_connect_email_screen_copy(client):
    r = client.get("/mail")
    assert r.status_code == 200
    assert "Connect your email" in r.text
    assert "Continue with Google" in r.text
    assert "Continue with Microsoft" in r.text
    assert "We never ask for your email password" in r.text
    assert "Set up later" in r.text
    # passwords / SMTP not above Advanced
    before_adv = r.text.split("Advanced email settings")[0]
    assert "app password" not in before_adv.lower()
    assert 'name="password"' not in before_adv
    assert "SMTP" not in before_adv


def test_gmail_scopes_are_send_only():
    joined = " ".join(GMAIL_SEND_SCOPES)
    assert "gmail.send" in joined
    assert "openid" in joined
    for forbidden in ("gmail.readonly", "gmail.compose", "gmail.modify", "gmail.metadata"):
        assert forbidden not in joined


def test_start_gmail_oauth_builds_pkce_url(client):
    set_secret("google_oauth_client_id", "test-desktop-client.apps.googleusercontent.com")
    result = start_gmail_oauth("http://127.0.0.1:8765")
    assert result["ok"] is True
    url = result["redirect_url"]
    assert "accounts.google.com" in url
    qs = parse_qs(urlparse(url).query)
    assert qs["response_type"] == ["code"]
    assert qs["code_challenge_method"] == ["S256"]
    assert "code_challenge" in qs
    scopes = qs["scope"][0]
    assert "gmail.send" in scopes
    assert "gmail.readonly" not in scopes
    assert qs["redirect_uri"][0].endswith("/mail/callback/gmail")


def test_start_gmail_without_client_id(client):
    disconnect_gmail()
    from studio.secrets_store import delete_secret

    delete_secret("google_oauth_client_id")
    r = client.post(
        "/mail/connect/gmail",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "err=1" in (r.headers.get("location") or "")


def test_finish_gmail_oauth_stores_tokens(client, monkeypatch):
    set_secret("google_oauth_client_id", "cid.apps.googleusercontent.com")
    set_secret(VERIFIER_SECRET, "verifier-xyz")
    set_secret("gmail_oauth_state", "state-abc")
    set_secret("gmail_redirect_uri", "http://127.0.0.1:8765/mail/callback/gmail")

    class TokenResp:
        status_code = 200

        def json(self):
            return {
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
                "scope": " ".join(GMAIL_SEND_SCOPES),
            }

    class UserResp:
        status_code = 200

        def json(self):
            return {"email": "student@gmail.com"}

    def fake_get(url, **kwargs):
        return UserResp()

    monkeypatch.setattr(
        "studio.mail.gmail.requests.post", lambda *a, **k: TokenResp()
    )
    monkeypatch.setattr("studio.mail.gmail.requests.get", fake_get)
    result = finish_gmail_oauth(code="authcode", state="state-abc")
    assert result["ok"] is True
    st = gmail_status()
    assert st["connected"] is True
    assert st["email"] == "student@gmail.com"
    assert st["permissions"] == "Send only"


def test_gmail_callback_route(client, monkeypatch):
    set_secret("google_oauth_client_id", "cid.apps.googleusercontent.com")
    set_secret(VERIFIER_SECRET, "v")
    set_secret("gmail_oauth_state", "s1")
    set_secret("gmail_redirect_uri", "http://127.0.0.1:8765/mail/callback/gmail")

    class TokenResp:
        status_code = 200

        def json(self):
            return {
                "access_token": "tok",
                "refresh_token": "ref",
                "expires_in": 3600,
            }

    class UserResp:
        status_code = 200

        def json(self):
            return {"email": "u@gmail.com"}

    monkeypatch.setattr(
        "studio.mail.gmail.requests.post", lambda *a, **k: TokenResp()
    )
    monkeypatch.setattr(
        "studio.mail.gmail.requests.get", lambda *a, **k: UserResp()
    )
    r = client.get(
        "/mail/callback/gmail?code=c&state=s1",
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "err=" not in (r.headers.get("location") or "")
    assert gmail_status()["connected"]


def test_send_via_gmail_posts_raw(monkeypatch):
    set_secret(ACCESS_SECRET, "tok")
    set_secret(EMAIL_SECRET, "me@gmail.com")
    set_secret("gmail_token_expiry", str(10**11))  # far future

    captured = {}

    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"id": "msg123", "threadId": "thr456"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["headers"] = kwargs.get("headers")
        return Resp()

    monkeypatch.setattr("studio.mail.gmail.requests.post", fake_post)
    out = send_via_gmail("prof@uni.edu", "Hello", "Body text")
    assert out["provider_message_id"] == "msg123"
    assert out["thread_id"] == "thr456"
    assert "messages/send" in captured["url"]
    assert "raw" in captured["json"]
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_perform_send_gmail_provider(data_dir, monkeypatch):
    from studio.db import connect, migrate
    from studio.drafts import content_hash, save_or_update_draft

    conn = connect(data_dir / "studio.sqlite")
    migrate(conn)
    conn.execute(
        "INSERT INTO researcher(display_name, email, origin) VALUES ('T','t@ex.edu','manual')"
    )
    rid = conn.execute("SELECT id FROM researcher ORDER BY id DESC LIMIT 1").fetchone()[
        "id"
    ]
    conn.execute(
        "INSERT INTO opportunity(researcher_id, origin) VALUES (?, 'manual')", (rid,)
    )
    oid = conn.execute("SELECT id FROM opportunity ORDER BY id DESC LIMIT 1").fetchone()[
        "id"
    ]
    body = "Hello"
    h = content_hash("t@ex.edu", "Hi", body)
    did = save_or_update_draft(
        conn,
        oid,
        {"recipient": "t@ex.edu", "subject": "Hi", "body": body, "content_hash": h},
    )
    conn.execute("UPDATE draft SET approved_hash=content_hash WHERE id=?", (did,))
    intent = create_intent(conn, did, h, "gmail")

    monkeypatch.setattr(
        "studio.mail.gmail.send_via_gmail",
        lambda **k: {"provider_message_id": "m1", "thread_id": "t1"},
    )
    assert perform_send(conn, intent, None) == "sent"
    row = conn.execute(
        "SELECT state, provider_message_id FROM send_intent WHERE id=?", (intent,)
    ).fetchone()
    assert row["state"] == "sent"
    assert "m1" in row["provider_message_id"]
    assert "t1" in row["provider_message_id"]
    conn.close()


def test_daily_quota_blocks_after_limit(client):
    disconnect_gmail()
    from studio.secrets_store import delete_secret

    delete_secret("mail_send_log_json")
    set_secret("mail_daily_limit", "2")
    assert can_send_now()[0] is True
    record_send()
    record_send()
    ok, msg = can_send_now()
    assert ok is False
    assert "2/2" in msg or "limit" in msg.lower()
    assert sent_in_rolling_24h() == 2
    assert DEFAULT_DAILY_LIMIT == 20


def test_setup_later_redirects_to_drafts(client):
    r = client.post(
        "/mail/setup-later",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "/drafts" in (r.headers.get("location") or "")


def test_outlook_scaffold_needs_client(client):
    from studio.secrets_store import delete_secret

    delete_secret("microsoft_oauth_client_id")
    r = client.post(
        "/mail/connect/outlook",
        data={"page_token": client.page_token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "err=1" in (r.headers.get("location") or "")


def test_connected_gmail_hides_password_prompt(client):
    set_secret(REFRESH_SECRET, "refresh")
    set_secret(EMAIL_SECRET, "student@gmail.com")
    r = client.get("/mail")
    assert "Connected" in r.text
    assert "student@gmail.com" in r.text
    assert "Send only" in r.text
    assert "Disconnect account" in r.text
    assert 'action="/mail/connect/gmail"' not in r.text
    assert 'action="/mail/disconnect/gmail"' in r.text
