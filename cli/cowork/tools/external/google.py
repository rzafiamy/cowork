"""
📅 Google Productivity Tools
Implementations for Google Calendar, Drive, and Gmail.
"""

import time
from pathlib import Path
from .utils import _env

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

def _get_google_creds(scopes: list[str]):
    if not GOOGLE_LIBS_AVAILABLE: return None, "❌ Google libs missing."
    token_path = Path.home() / ".cowork" / "google_token.json"
    creds_path = Path.home() / ".cowork" / "google_credentials.json"
    creds = None
    if token_path.exists(): creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if not creds_path.exists(): return None, "❌ Google credentials missing."
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f: f.write(creds.to_json())
    return creds, None

def google_calendar_events(max_results: int = 10) -> str:
    """List upcoming Google Calendar events."""
    creds, err = _get_google_creds(["https://www.googleapis.com/auth/calendar.readonly"])
    if err: return err
    try:
        service = build("calendar", "v3", credentials=creds)
        res = service.events().list(calendarId="primary", timeMin=time.strftime("%Y-%m-%dT%H:%M:%SZ"), maxResults=max_results, singleEvents=True, orderBy="startTime").execute()
        events = res.get("items", [])
        lines = ["📅 **Google Calendar Events**\n"]
        for e in events: lines.append(f"- **{e['summary']}** ({e['start'].get('dateTime', e['start'].get('date'))})")
        return "\n".join(lines)
    except Exception as e: return f"❌ Calendar error: {e}"

def google_drive_search(query: str) -> str:
    """Search for files in Google Drive."""
    creds, err = _get_google_creds(["https://www.googleapis.com/auth/drive.readonly"])
    if err: return err
    try:
        service = build("drive", "v3", credentials=creds)
        res = service.files().list(q=f"name contains '{query}'", pageSize=5).execute()
        files = res.get("files", [])
        lines = ["📂 **Google Drive Results**\n"]
        for f in files: lines.append(f"- {f['name']} (ID: {f['id']})")
        return "\n".join(lines)
    except Exception as e: return f"❌ Drive error: {e}"

def google_calendar_create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
) -> str:
    creds, err = _get_google_creds(["https://www.googleapis.com/auth/calendar"])
    if err: return err
    try:
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary, "location": location, "description": description,
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"},
        }
        event = service.events().insert(calendarId="primary", body=event).execute()
        return f"✅ Event created: {event.get('htmlLink')}"
    except Exception as e: return f"❌ Calendar error: {e}"

def google_drive_upload_text(filename: str, content: str, mime_type: str = "text/plain") -> str:
    creds, err = _get_google_creds(["https://www.googleapis.com/auth/drive.file"])
    if err: return err
    try:
        from googleapiclient.http import MediaInMemoryUpload
        service = build("drive", "v3", credentials=creds)
        file_metadata = {"name": filename}
        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=mime_type)
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        return f"✅ File uploaded to Drive. ID: {file.get('id')}"
    except Exception as e: return f"❌ Drive upload error: {e}"

def gmail_send_email(recipient: str, subject: str, body: str) -> str:
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    creds, err = _get_google_creds(["https://www.googleapis.com/auth/gmail.send"])
    if err: return err
    try:
        service = build("gmail", "v1", credentials=creds)
        message = MIMEMultipart()
        message["to"], message["subject"] = recipient, subject
        message.attach(MIMEText(body))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"✅ Email sent via Gmail to {recipient}."
    except Exception as e: return f"❌ Gmail error: {e}"

TOOLS = [
    {
        "category": "GOOGLE_TOOLS",
        "type": "function",
        "function": {
            "name": "google_calendar_events",
            "description": "List upcoming Google Calendar events.",
            "parameters": {
                "type": "object",
                "properties": {"max_results": {"type": "integer"}},
                "required": [],
            },
        },
    },
    {
        "category": "GOOGLE_TOOLS",
        "type": "function",
        "function": {
            "name": "google_calendar_create_event",
            "description": "Create an event in Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start_time": {"type": "string", "description": "ISO format, e.g. 2024-12-25T09:00:00Z"},
                    "end_time": {"type": "string"},
                },
                "required": ["summary", "start_time", "end_time"],
            },
        },
    },
    {
        "category": "GOOGLE_TOOLS",
        "type": "function",
        "function": {
            "name": "google_drive_search",
            "description": "Search for files in Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "category": "GOOGLE_TOOLS",
        "type": "function",
        "function": {
            "name": "google_drive_upload_text",
            "description": "Upload a text file to Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "category": "GOOGLE_TOOLS",
        "type": "function",
        "function": {
            "name": "gmail_send_email",
            "description": "Send an email via Gmail API.",
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
]
