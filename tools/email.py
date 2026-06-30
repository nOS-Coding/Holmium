"""Email tools using stdlib-only imaplib and smtplib."""

import email
import imaplib
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from tools.registry import register_tool

_SECRETS_PATH = "/etc/holmium/secrets.env"


def _load_config() -> Dict[str, str]:
    config: Dict[str, str] = {}
    if not os.path.isfile(_SECRETS_PATH):
        return config
    with open(_SECRETS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                config[key.strip()] = val.strip().strip("'\"")
    return config


def _get_imap() -> Optional[imaplib.IMAP4_SSL]:
    cfg = _load_config()
    host = cfg.get("imap_host", "")
    port = int(cfg.get("imap_port", "993"))
    user = cfg.get("email_address", "")
    password = cfg.get("email_password", "")
    if not all([host, user, password]):
        return None
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)
    conn.select("INBOX")
    return conn


def _decode_header_str(val: str) -> str:
    parts = decode_header(val)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _fetch_email_data(conn: imaplib.IMAP4_SSL, num: bytes) -> Dict[str, Any]:
    status, msg_data = conn.fetch(num, "(RFC822)")
    if status != "OK":
        return {}
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    message_id = msg.get("Message-ID", "").strip("<>")
    subject = _decode_header_str(msg.get("Subject", "(No Subject)"))
    from_ = _decode_header_str(msg.get("From", ""))
    date_str = msg.get("Date", "")

    body_preview = ""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    body_preview = body[:200]
                break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")
            body_preview = body[:200]

    return {
        "message_id": message_id,
        "subject": subject,
        "from": from_,
        "date": date_str,
        "body_preview": body_preview,
        "body": body,
    }


@register_tool(
    "email_fetch_inbox",
    "Fetch the most recent emails from the inbox.",
    params_schema={
        "type": "object",
        "properties": {
            "n": {
                "type": "integer",
                "description": "Number of recent emails to fetch (default 10)",
                "default": 10,
            },
        },
        "required": [],
    },
)
def email_fetch_inbox(n: int = 10) -> List[Dict[str, Any]]:
    """Fetch the last N emails from the inbox."""
    try:
        conn = _get_imap()
        if conn is None:
            return [{"error": "Email not configured — check /etc/holmium/secrets.env"}]

        status, numbers = conn.search(None, "ALL")
        if status != "OK":
            return []

        ids = numbers[0].split()
        selected = ids[-n:] if len(ids) >= n else ids

        results = []
        for num in selected:
            data = _fetch_email_data(conn, num)
            if data:
                results.append(data)

        conn.logout()
        return results
    except Exception as e:
        return [{"error": str(e)}]


@register_tool(
    "email_read",
    "Read the full body of an email by its message ID.",
    params_schema={
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Message-ID of the email to read",
            },
        },
        "required": ["message_id"],
    },
)
def email_read(message_id: str) -> str:
    """Fetch the full body of an email by Message-ID."""
    try:
        conn = _get_imap()
        if conn is None:
            return "Email not configured"

        status, numbers = conn.search(None, "ALL")
        if status != "OK":
            return "No emails found"

        for num in numbers[0].split():
            data = _fetch_email_data(conn, num)
            if data.get("message_id") == message_id:
                conn.logout()
                return data.get("body", "(No body)")

        conn.logout()
        return "Email not found"
    except Exception as e:
        return f"Error: {e}"


@register_tool(
    "email_send",
    "Send an email via SMTP.",
    params_schema={
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body text",
            },
        },
        "required": ["to", "subject", "body"],
    },
)
def email_send(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email via SMTP with TLS."""
    try:
        cfg = _load_config()
        host = cfg.get("smtp_host", "")
        port = int(cfg.get("smtp_port", "587"))
        user = cfg.get("email_address", "")
        password = cfg.get("email_password", "")

        if not all([host, user, password]):
            return False

        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return True
    except Exception:
        return False


@register_tool(
    "email_search",
    "Search emails by query using IMAP SEARCH.",
    params_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (searches FROM, SUBJECT, BODY)",
            },
        },
        "required": ["query"],
    },
)
def email_search(query: str) -> List[Dict[str, Any]]:
    """Search emails using IMAP SEARCH."""
    try:
        conn = _get_imap()
        if conn is None:
            return [{"error": "Email not configured"}]

        status, numbers = conn.search(None, f'ALL HEADER Subject "{query}"')
        if status != "OK":
            return []

        ids = numbers[0].split()[-20:] if numbers[0] else []

        results = []
        for num in ids:
            data = _fetch_email_data(conn, num)
            if data:
                results.append(data)

        conn.logout()
        return results
    except Exception as e:
        return [{"error": str(e)}]


@register_tool(
    "email_reply",
    "Reply to an email, preserving the thread.",
    params_schema={
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Message-ID of the email to reply to",
            },
            "body": {
                "type": "string",
                "description": "Reply body text",
            },
        },
        "required": ["message_id", "body"],
    },
)
def email_reply(message_id: str, body: str) -> bool:
    """Reply to an email by its Message-ID."""
    try:
        cfg = _load_config()
        host = cfg.get("smtp_host", "")
        port = int(cfg.get("smtp_port", "587"))
        user = cfg.get("email_address", "")
        password = cfg.get("email_password", "")

        if not all([host, user, password]):
            return False

        conn = _get_imap()
        if conn is None:
            return False

        original = None
        status, numbers = conn.search(None, "ALL")
        if status == "OK":
            for num in numbers[0].split():
                data = _fetch_email_data(conn, num)
                if data.get("message_id") == message_id:
                    original = data
                    break
        conn.logout()

        if not original:
            return False

        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = original["from"]
        msg["Subject"] = f"Re: {original['subject']}"
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id
        msg.set_content(body)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return True
    except Exception:
        return False


@register_tool(
    "email_delete",
    "Delete (trash) an email by its message ID.",
    params_schema={
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Message-ID of the email to delete",
            },
        },
        "required": ["message_id"],
    },
)
def email_delete(message_id: str) -> bool:
    """Move an email to trash by Message-ID."""
    try:
        conn = _get_imap()
        if conn is None:
            return False

        status, numbers = conn.search(None, "ALL")
        if status != "OK":
            return False

        for num in numbers[0].split():
            status, msg_data = conn.fetch(num, "(BODY.PEEK[HEADER.FIELDS (Message-ID)])")
            if status != "OK":
                continue
            raw = msg_data[0][1].decode("utf-8", errors="replace")
            if message_id in raw:
                conn.copy(num, "[Gmail]/Trash")
                conn.store(num, "+FLAGS", "\\Deleted")
                conn.expunge()
                conn.logout()
                return True

        conn.logout()
        return False
    except Exception:
        return False
