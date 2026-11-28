"""Launch the official GroqCloud dashboard in the system browser.

Never automates the dashboard, never reads cookies, never drives undocumented APIs.
"""

from __future__ import annotations

import webbrowser

CONSOLE_KEYS_URL = "https://console.groq.com/keys"
CONSOLE_HOME_URL = "https://console.groq.com/"
DOCS_URL = "https://console.groq.com/docs/quickstart"


def official_keys_url() -> str:
    return CONSOLE_KEYS_URL


def official_docs_url() -> str:
    return DOCS_URL


def launch_official_dashboard(*, prefer_keys_page: bool = True) -> dict:
    """Open Groq's official console. Returns status for the assistant UI."""
    import os

    url = CONSOLE_KEYS_URL if prefer_keys_page else CONSOLE_HOME_URL
    opened = False
    error = ""
    # Skip real browser popups under pytest / headless CI
    if os.environ.get("STUDIO_NO_BROWSER") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
        return {
            "ok": True,
            "url": url,
            "opened_in_browser": False,
            "error": "",
            "note": (
                "Only the official GroqCloud site is opened. "
                "We do not automate the page or read your Groq session."
            ),
        }
    try:
        opened = bool(webbrowser.open(url, new=2))
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    return {
        "ok": True,  # even if webbrowser fails, we still expose the URL for a manual click
        "url": url,
        "opened_in_browser": opened,
        "error": error,
        "note": (
            "Only the official GroqCloud site is opened. "
            "We do not automate the page or read your Groq session."
        ),
    }
