"""Signup access model (2026-07-17): email verification is no longer a gate.

Users can generate immediately; verification is still sent + tracked but only
softly nudged. Anti-bot moved entirely to signup-time (disposable-domain
blocklist + IP + device-fingerprint), so the blocklist must stay populated.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-signup-gate-tests")


def test_disposable_domains_still_blocked_including_web_library():
    import main

    bl = main._BLOCKED_EMAIL_DOMAINS
    # The specific one the user flagged, plus a spread of common disposables.
    for d in ["web-library.net", "mailinator.com", "guerrillamail.com",
              "1secmail.com", "getnada.com", "temp-mail.org"]:
        assert d in bl, f"{d} should be in the disposable blocklist"


def test_generate_endpoint_has_no_email_verification_gate():
    """Guard against re-introducing the hard wall. The generate endpoint's source
    must not raise a 403 based on email_verified."""
    import inspect
    import main

    src = inspect.getsource(main.songs_generate).lower()
    # The gate raised a 403 with this message — its absence proves the wall is gone.
    # (We check the block message, not the bare "email_verified" token, which still
    # legitimately appears in the explanatory comment.)
    assert "verify your email address before generating" not in src
    assert "email not verified" not in src  # the old log.warning marker
