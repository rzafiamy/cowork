"""
💬 Communication Tools
Implementations for SMTP, Telegram, Slack, and X (Twitter).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .utils import _env, _missing_key, _http_post

def smtp_send_email(recipient: str, subject: str, body: str) -> str:
    """Send an email via SMTP."""
    host = _env("SMTP_HOST")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    port = int(_env("SMTP_PORT") or 587)

    if not all([host, user, password]): return "❌ SMTP configuration missing."

    try:
        msg = MIMEMultipart()
        msg["From"], msg["To"], msg["Subject"] = user, recipient, subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return f"✅ Email sent to {recipient}."
    except Exception as e:
        return f"❌ Email failed: {e}"

def telegram_send_message(chat_id: str, text: str) -> str:
    """Send a message via Telegram Bot API."""
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

TOOLS = [
    {
        "category": "COMMUNICATION_TOOLS",
        "type": "function",
        "function": {
            "name": "smtp_send_email",
            "description": "Send an email via SMTP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
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
