"""The AI-suggested reply is a convenience on top of the alert — never a dependency.

The alert is the load-bearing part: it is the only thing that tells the admin an
enquiry arrived. The draft is optional and regenerable. So every failure mode of
the model must degrade to "alert without a suggestion", never to a lost or delayed
notification.

Nothing here sends email. The draft is shown in Telegram for the admin to read,
edit and send deliberately with "reply <id> <message>". That manual step is also
what contains the prompt-injection risk of putting untrusted enquiry text through
a model.
"""
import os
import pathlib
import sys
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
# test_nothing_is_sent_automatically imports main to patch its mail sender.
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-suggestion-tests")

import alerts as _alerts

_ENQUIRY = dict(name="Ada", email="ada@example.com", subject="Booking",
                message="Can you score a short film?")


def _alert(suggestion, **over):
    fields = {**_ENQUIRY, **over}
    with patch.object(_alerts, "suggest_contact_reply", return_value=suggestion), \
         patch.object(_alerts, "send_admin_alert", return_value=True) as send:
        ok = _alerts.alert_contact_submission(
            fields["name"], fields["email"], fields["subject"], fields["message"], 7)
    return ok, (send.call_args.args[0] if send.call_args else "")


# ── The alert must survive every draft failure ───────────────────────────────

def test_alert_still_sends_when_the_draft_is_unavailable():
    ok, msg = _alert(None)
    assert ok is True
    assert "New contact form submission" in msg
    assert "Can you score a short film?" in msg
    assert "Suggested reply" not in msg


def test_a_raising_model_does_not_break_the_alert():
    """suggest_contact_reply swallows its own errors, but prove the alert survives
    even if that contract is broken."""
    with patch.object(_alerts, "suggest_contact_reply", side_effect=RuntimeError("model down")), \
         patch.object(_alerts, "send_admin_alert", return_value=True):
        try:
            _alerts.alert_contact_submission(**_ENQUIRY, submission_id=7)
        except Exception as exc:
            raise AssertionError(f"alert must not propagate a draft failure: {exc}")


def test_suggest_returns_none_rather_than_raising():
    with patch("anthropic.Anthropic", side_effect=RuntimeError("no api key")):
        assert _alerts.suggest_contact_reply("Ada", "Booking", "Hello?") is None


def test_suggest_skips_an_empty_enquiry_without_calling_the_model():
    with patch("anthropic.Anthropic") as client:
        assert _alerts.suggest_contact_reply("Ada", "Booking", "   ") is None
    client.assert_not_called()


# ── Layout: details first, suggestion last and clearly a draft ───────────────

def test_details_come_before_the_suggestion():
    _, msg = _alert("Happy to help — what length do you need?")
    assert msg.index("Can you score a short film?") < msg.index("Suggested reply"), \
        "the enquiry must be readable before the draft"


def test_the_suggestion_is_unmistakably_a_draft():
    _, msg = _alert("Happy to help — what length do you need?")
    assert "Suggested reply" in msg
    assert "nothing sent yet" in msg.lower()


def test_it_shows_the_command_needed_to_actually_send():
    _, msg = _alert("Happy to help.")
    assert "reply 7" in msg, "the admin needs the exact command, pre-filled with the id"


def test_nothing_is_sent_automatically():
    """The alert path must not touch the mail sender at all."""
    with patch.object(_alerts, "suggest_contact_reply", return_value="Drafted."), \
         patch.object(_alerts, "send_admin_alert", return_value=True), \
         patch("main._send_email") as mail:
        _alerts.alert_contact_submission(**_ENQUIRY, submission_id=7)
    mail.assert_not_called()


# ── HTML safety: one stray character must not lose the notification ──────────

def test_enquiry_html_is_escaped():
    """send_admin_alert posts with parse_mode=HTML, so an unescaped '<' makes
    Telegram reject the whole message and the notification is lost."""
    _, msg = _alert(None, message="Can you score a <film> & trailer?")
    assert "&lt;film&gt;" in msg and "&amp;" in msg
    assert "<film>" not in msg


def test_name_and_subject_are_escaped_too():
    _, msg = _alert(None, name="A<b>d</b>a", subject="R&D")
    assert "&lt;b&gt;" in msg and "R&amp;D" in msg


def test_a_draft_containing_markup_is_escaped():
    _, msg = _alert("Use <b>bold</b> & caps")
    assert "&lt;b&gt;bold&lt;/b&gt;" in msg and "&amp; caps" in msg


# ── Length: the enquiry is protected, the draft is expendable ────────────────

def test_long_enquiry_is_truncated_but_present():
    _, msg = _alert(None, message="x" * 5000)
    assert "truncated" in msg
    assert len(msg) < 4096, "Telegram would reject an over-long message"


def test_a_long_draft_cannot_push_the_message_over_the_limit():
    _, msg = _alert("y" * 5000, message="x" * 5000)
    assert len(msg) < 4096
    assert "truncated" in msg, "the enquiry must still be there"
