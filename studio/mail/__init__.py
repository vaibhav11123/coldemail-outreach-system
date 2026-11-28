"""Connect your email — universal discovery, Gmail/Outlook OAuth, institutional SMTP."""

from studio.mail.discovery import discover_email_config, discovery_preview, parse_email
from studio.mail.gmail import (
    GMAIL_SEND_SCOPES,
    disconnect_gmail,
    finish_gmail_oauth,
    gmail_status,
    refresh_access_token,
    send_via_gmail,
    set_reply_consent,
    start_gmail_oauth,
)
from studio.mail.institute import (
    active_mail_summary,
    connect_institute,
    connect_manual_smtp,
    disconnect_institute,
    institute_status,
    smtp_config_from_store,
)
from studio.mail.outlook import (
    disconnect_outlook,
    finish_outlook_oauth,
    outlook_status,
    start_outlook_oauth,
)
from studio.mail.quotas import (
    DEFAULT_DAILY_LIMIT,
    FOLLOW_UP_DAYS_MAX,
    FOLLOW_UP_DAYS_MIN,
    MAX_FOLLOW_UPS,
    can_send_now,
    daily_limit,
    record_send,
    sent_in_rolling_24h,
)

__all__ = [
    "GMAIL_SEND_SCOPES",
    "DEFAULT_DAILY_LIMIT",
    "FOLLOW_UP_DAYS_MAX",
    "FOLLOW_UP_DAYS_MIN",
    "MAX_FOLLOW_UPS",
    "active_mail_summary",
    "can_send_now",
    "connect_institute",
    "connect_manual_smtp",
    "daily_limit",
    "disconnect_gmail",
    "disconnect_institute",
    "disconnect_outlook",
    "discover_email_config",
    "discovery_preview",
    "finish_gmail_oauth",
    "finish_outlook_oauth",
    "gmail_status",
    "institute_status",
    "outlook_status",
    "parse_email",
    "record_send",
    "refresh_access_token",
    "send_via_gmail",
    "sent_in_rolling_24h",
    "set_reply_consent",
    "smtp_config_from_store",
    "start_gmail_oauth",
    "start_outlook_oauth",
]
