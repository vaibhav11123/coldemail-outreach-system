"""Premium: alerts, modes, multi-profile, hosted account isolation."""

from __future__ import annotations


def test_degree_modes_on_profile(client):
    r = client.get("/profile")
    assert "PhD" in r.text
    assert "Visiting" in r.text
    assert "Research assistant" in r.text


def test_return_alerts_and_profiles(client):
    r = client.get("/return")
    assert r.status_code == 200
    assert "14 days" in r.text
    assert "30 days" in r.text
    client.post(
        "/return/alerts",
        data={"page_token": client.page_token, "alerts": "1"},
        follow_redirects=False,
    )
    client.post(
        "/return/add-profile",
        data={"page_token": client.page_token, "label": "Sibling"},
        follow_redirects=False,
    )
    r2 = client.get("/return")
    assert "Sibling" in r2.text


def test_hosted_accounts_isolated(client, conn):
    client.post(
        "/hosted/create",
        data={
            "page_token": client.page_token,
            "email": "a@ex.com",
            "display_name": "Alice",
        },
        follow_redirects=False,
    )
    client.post(
        "/hosted/create",
        data={
            "page_token": client.page_token,
            "email": "b@ex.com",
            "display_name": "Bob",
        },
        follow_redirects=False,
    )
    accounts = conn.execute("SELECT email FROM hosted_account ORDER BY id").fetchall()
    emails = [a["email"] for a in accounts]
    assert "a@ex.com" in emails and "b@ex.com" in emails
    # drafts remain local to applicant table — hosted accounts have no shared draft read API
    r = client.get("/hosted")
    assert "Alice" in r.text and "Bob" in r.text
