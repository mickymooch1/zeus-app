"""Porick "reply <id> <message>" — answering a contact form submission by email.

The ordering rule this file exists to protect: SEND FIRST, THEN MARK REPLIED.
Marking first would leave a row reading as answered when nobody received anything
— the same silent-failure shape that made the contact form drop enquiries for
however long the Gmail credentials had been rejected.

Mail goes through main._send_email, which routes to Resend when RESEND_API_KEY is
set. That matters: the raw-SMTP paths elsewhere in the codebase are currently
failing with Gmail 535, so a reply built on those would look sent and never
arrive.
"""
import os
import pathlib
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-contact-reply-tests")

import db as _db
import telegram_admin as _ta


def _fresh_db_with_submission(**over):
    path = pathlib.Path(tempfile.mkdtemp()) / "reply.db"
    _db.init_user_tables(path)
    fields = dict(name="Ada Lovelace", email="ada@example.com",
                  subject="Booking enquiry", message="Can you score a short film?")
    fields.update(over)
    sid = _db.save_contact_submission(path, **fields)
    return path, sid


def _reply(path, sid, message="Thanks for getting in touch!", sent=True):
    with patch.object(_db, "get_db_path", return_value=path), \
         patch("main._send_email", return_value=sent) as send:
        out = _ta._cmd_reply_to_contact(sid, message)
    return out, send


# ── Happy path ───────────────────────────────────────────────────────────────

def test_sends_the_email_and_confirms_with_name_and_address():
    path, sid = _fresh_db_with_submission()
    out, send = _reply(path, sid)
    send.assert_called_once()
    to, subject, html, text = send.call_args.args
    assert to == "ada@example.com"
    assert subject == "Re: Booking enquiry"
    assert "Thanks for getting in touch!" in text
    assert "Ada Lovelace" in out and "ada@example.com" in out
    assert out.startswith("✅ Reply sent to")


def test_marks_the_submission_replied():
    path, sid = _fresh_db_with_submission()
    _reply(path, sid, "Here is how it works.")
    row = _db.get_contact_submission(path, sid)
    assert row["replied_at"]
    assert row["reply_text"] == "Here is how it works."


def test_message_is_sent_verbatim():
    """It goes to a real person — the bot must not paraphrase it."""
    path, sid = _fresh_db_with_submission()
    msg = "Yes — £40 for a 2 minute cue, 3 day turnaround. Fine to use commercially."
    _, send = _reply(path, sid, msg)
    assert msg in send.call_args.args[3]


# ── The failure branches the command has to state clearly ────────────────────

def test_unknown_submission_id_says_so():
    path, _ = _fresh_db_with_submission()
    out, send = _reply(path, 9999)
    assert "No contact submission" in out and "9999" in out
    send.assert_not_called()


def test_non_numeric_id_says_so():
    path, _ = _fresh_db_with_submission()
    out, send = _reply(path, "banana")
    assert "not a valid submission id" in out
    send.assert_not_called()


def test_already_replied_is_refused():
    path, sid = _fresh_db_with_submission()
    _reply(path, sid, "First answer.")
    out, send = _reply(path, sid, "Second answer.")
    assert "already" in out.lower()
    send.assert_not_called(), "must not email the same person twice"


def test_empty_message_is_refused():
    path, sid = _fresh_db_with_submission()
    out, send = _reply(path, sid, "   ")
    assert "No reply text" in out
    send.assert_not_called()


def test_submission_without_a_usable_email_is_refused():
    path, sid = _fresh_db_with_submission(email="not-an-email")
    out, send = _reply(path, sid)
    assert "no usable email" in out.lower()
    send.assert_not_called()


# ── The ordering guarantee ───────────────────────────────────────────────────

def test_a_failed_send_leaves_the_submission_repliable():
    """The whole reason send happens before the DB write."""
    path, sid = _fresh_db_with_submission()
    out, _ = _reply(path, sid, "This will not send.", sent=False)
    assert "NOT sent" in out
    row = _db.get_contact_submission(path, sid)
    assert row["replied_at"] is None, "a failed send must not mark the enquiry answered"


def test_a_raising_sender_is_reported_not_swallowed():
    path, sid = _fresh_db_with_submission()
    with patch.object(_db, "get_db_path", return_value=path), \
         patch("main._send_email", side_effect=RuntimeError("provider down")):
        out = _ta._cmd_reply_to_contact(sid, "hello")
    assert "Could not send" in out and "provider down" in out
    assert _db.get_contact_submission(path, sid)["replied_at"] is None


def test_reply_routes_through_send_email_not_raw_smtp():
    """Raw SMTP is failing with Gmail 535; _send_email prefers Resend."""
    import inspect
    src = inspect.getsource(_ta._cmd_reply_to_contact)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "_send_email" in code
    assert "smtplib" not in code and "SMTP_PASSWORD" not in code
