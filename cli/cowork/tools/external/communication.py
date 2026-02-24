"""
💬 Communication Tools
Implementations for SMTP, Telegram, Slack, and X (Twitter).
"""

import mimetypes
import os
import re
import smtplib
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
from pathlib import Path
from typing import Optional
from .utils import _env, _missing_key, _http_post


# ── Attachment helper ─────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
_SLACK_CHANNEL_RE = re.compile(r"^(#[a-z0-9._\-]+|[CGD][A-Z0-9]{8,})$", re.IGNORECASE)
_TELEGRAM_CHAT_RE = re.compile(r"^(@[A-Za-z0-9_]{5,}|-?[0-9]{5,})$")
_PLACEHOLDER_TOKENS = (
    "example.com",
    "example.org",
    "test.com",
    "your-email",
    "recipient@email.com",
    "foo@bar",
    "john@doe",
)


def _has_placeholder(value: str) -> bool:
    v = (value or "").strip().lower()
    return any(tok in v for tok in _PLACEHOLDER_TOKENS)


def _require_non_empty(field: str, value: str) -> str | None:
    if not str(value or "").strip():
        return (
            f"❌ Missing `{field}`.\n"
            "Please ask the user for an explicit value before sending."
        )
    return None


def _validate_email_recipient(recipient: str) -> str | None:
    maybe_missing = _require_non_empty("recipient", recipient)
    if maybe_missing:
        return maybe_missing
    r = recipient.strip()
    if _has_placeholder(r):
        return (
            "❌ Recipient email looks like a placeholder.\n"
            "Please ask the user to confirm the exact recipient address."
        )
    if not _EMAIL_RE.match(r):
        return (
            f"❌ Invalid recipient email format: `{recipient}`.\n"
            "Please ask the user for a valid email address."
        )
    return None


def _validate_slack_channel(channel: str) -> str | None:
    maybe_missing = _require_non_empty("channel", channel)
    if maybe_missing:
        return maybe_missing
    c = channel.strip()
    if _has_placeholder(c):
        return (
            "❌ Slack channel looks like a placeholder.\n"
            "Please ask the user to confirm the exact channel name or ID."
        )
    if not _SLACK_CHANNEL_RE.match(c):
        return (
            f"❌ Invalid Slack channel format: `{channel}`.\n"
            "Use `#channel-name` or channel ID (`C...`, `G...`, `D...`). Ask the user to confirm."
        )
    return None


def _validate_telegram_chat_id(chat_id: str) -> str | None:
    maybe_missing = _require_non_empty("chat_id", chat_id)
    if maybe_missing:
        return maybe_missing
    c = chat_id.strip()
    if _has_placeholder(c):
        return (
            "❌ Telegram chat_id looks like a placeholder.\n"
            "Please ask the user to confirm the exact `@username` or numeric chat ID."
        )
    if not _TELEGRAM_CHAT_RE.match(c):
        return (
            f"❌ Invalid Telegram chat_id format: `{chat_id}`.\n"
            "Expected `@username` or numeric ID. Ask the user to confirm."
        )
    return None

def _attach_files(msg: MIMEMultipart, attachments: list[str]) -> list[str]:
    """
    Attach a list of file paths to a MIMEMultipart message.
    Returns a list of any errors encountered (missing/unreadable files).
    """
    errors = []
    for path_str in attachments:
        path = Path(path_str.strip()).expanduser()
        if not path.exists():
            errors.append(f"File not found: {path}")
            continue
        if not path.is_file():
            errors.append(f"Not a file: {path}")
            continue

        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            main_type, sub_type = mime_type.split("/", 1)
        else:
            main_type, sub_type = "application", "octet-stream"

        try:
            with open(path, "rb") as f:
                data = f.read()

            part = MIMEBase(main_type, sub_type)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=path.name,
            )
            msg.attach(part)
        except Exception as e:
            errors.append(f"Could not attach {path.name}: {e}")

    return errors


# ── Tool implementations ──────────────────────────────────────────────────────

def smtp_send_email(
    recipient: str,
    subject: str,
    body: str,
    attachments: Optional[list] = None,
    html: bool = False,
) -> str:
    """Send an email via SMTP, with optional file attachments."""
    err = _validate_email_recipient(recipient)
    if err:
        return err

    host = _env("SMTP_HOST")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    port = int(_env("SMTP_PORT") or 587)

    if not all([host, user, password]):
        return "❌ SMTP configuration missing (SMTP_HOST, SMTP_USER, SMTP_PASS required)."

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = user
        msg["To"] = recipient
        msg["Subject"] = subject

        # Body part
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
        msg.attach(body_part)

        # Attachments
        attach_errors = []
        if attachments:
            attach_errors = _attach_files(msg, attachments)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        result = f"✅ Email sent to {recipient}."
        if attachments:
            ok_count = len(attachments) - len(attach_errors)
            result += f" ({ok_count}/{len(attachments)} attachment(s) included)"
        if attach_errors:
            result += f"\n⚠️ Attachment warnings:\n" + "\n".join(f"  • {e}" for e in attach_errors)
        return result

    except Exception as e:
        return f"❌ Email failed: {e}"


def telegram_send_message(chat_id: str, text: str) -> str:
    """Send a message via Telegram Bot API."""
    err = _validate_telegram_chat_id(chat_id)
    if err:
        return err
    if not str(text or "").strip():
        return "❌ Missing Telegram message text. Please ask the user for message content."

    token = _env("TELEGRAM_BOT_TOKEN")
    if not token: return _missing_key("telegram_send_message", "TELEGRAM_BOT_TOKEN")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        data = _http_post(url, {"chat_id": chat_id, "text": text})
        if data.get("ok"): return f"✅ Telegram message sent."
        return f"❌ Telegram error: {data}"
    except Exception as e:
        return f"❌ Telegram failed: {e}"


def slack_send_message(channel: str, text: str) -> str:
    """Send a message to a Slack channel."""
    err = _validate_slack_channel(channel)
    if err:
        return err
    if not str(text or "").strip():
        return "❌ Missing Slack message text. Please ask the user for message content."

    token = _env("SLACK_BOT_TOKEN")
    if not token: return _missing_key("slack_send_message", "SLACK_BOT_TOKEN")

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        data = _http_post(url, {"channel": channel, "text": text}, headers=headers)
        if data.get("ok"): return f"✅ Slack message sent."
        return f"❌ Slack error: {data}"
    except Exception as e:
        return f"❌ Slack failed: {e}"


def twitter_post_tweet(text: str) -> str:
    """Post a tweet to X (Twitter)."""
    t = str(text or "").strip()
    if not t:
        return "❌ Missing tweet text. Please ask the user for message content."
    if len(t) > 280:
        return (
            f"❌ Tweet text is too long ({len(t)} chars > 280).\n"
            "Please ask the user to shorten it."
        )

    token = _env("TWITTER_BEARER_TOKEN")
    if not token: return _missing_key("twitter_post_tweet", "TWITTER_BEARER_TOKEN")

    url = "https://api.twitter.com/2/tweets"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        data = _http_post(url, {"text": text}, headers=headers)
        if "data" in data: return f"✅ Tweet posted. ID: {data['data']['id']}"
        return f"❌ Twitter error: {data}"
    except Exception as e:
        return f"❌ Twitter failed: {e}"


# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOLS = [
    {
        "category": "COMMUNICATION_TOOLS",
        "type": "function",
        "function": {
            "name": "smtp_send_email",
            "description": (
                "Send an email via SMTP. Supports plain text or HTML body and optional "
                "file attachments (pass absolute file paths or workspace artifact paths)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Recipient email address",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text or HTML)",
                    },
                    "attachments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of absolute file paths to attach. "
                            "Example: [\"/home/user/.cowork/workspace/my-session/artifacts/report.pdf\"]"
                        ),
                    },
                    "html": {
                        "type": "boolean",
                        "description": "Set to true if the body is HTML. Defaults to false (plain text).",
                    },
                },
                "required": ["recipient", "subject", "body"],
            },
        },
    },
    {
        "category": "COMMUNICATION_TOOLS",
        "type": "function",
        "function": {
            "name": "telegram_send_message",
            "description": "Send message via Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["chat_id", "text"],
            },
        },
    },
    {
        "category": "COMMUNICATION_TOOLS",
        "type": "function",
        "function": {
            "name": "slack_send_message",
            "description": "Send message via Slack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        },
    },
    {
        "category": "COMMUNICATION_TOOLS",
        "type": "function",
        "function": {
            "name": "twitter_post_tweet",
            "description": "Post a tweet to X (Twitter).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
]
