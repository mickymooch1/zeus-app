"""Animated covers must default OFF (2026-08-06).

Kling video is the most expensive thing in the stack. A 5-second Kling v2 Master
clip is ~$1.40 and BOTH takes animate, so an animated song is ~$2.80 — against
~$0.025 for a Flux cover image. In one 12-hour production window, 2 Kling clips
cost roughly 8x the 14 Flux images generated alongside them.

SongsGenerateRequest.animate_cover previously defaulted to True, so any client
that merely omitted the field opted its users into that spend. The iOS app did
exactly that: its generate payload sent brief, genres, instrumental,
intermittent_vocals and platform — no animate_cover — so every iOS song would
have requested ~$2.80 of animation nobody asked for.

The principle: a missing field must fail CHEAP, not expensive.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-animate-default-tests")

_ROOT = pathlib.Path(__file__).parent.parent.parent


def test_animate_cover_defaults_to_off():
    """The whole point: omitting the field must not spend money."""
    import main
    field = main.SongsGenerateRequest.model_fields["animate_cover"]
    assert field.default is False, "a missing animate_cover must not opt the user into Kling"


def test_a_request_without_the_field_does_not_animate():
    import main
    body = main.SongsGenerateRequest(brief="a song", genres=["pop"])
    assert body.animate_cover is False


def test_it_can_still_be_turned_on_explicitly():
    """Paid users who want animation must still get it."""
    import main
    body = main.SongsGenerateRequest(brief="a song", genres=["pop"], animate_cover=True)
    assert body.animate_cover is True


def test_ios_sends_animate_cover_explicitly():
    """Belt and braces — iOS must not depend on the backend default."""
    src = (_ROOT / "zeus-beats-ios" / "src" / "screens"
           / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert "animate_cover:" in src, "iOS must state its intent, not rely on a default"
    assert "animate_cover:       false" in src or "animate_cover: false" in src


def test_web_still_sends_its_own_choice_on_every_path():
    """Flipping the default must not silently disable animation for web users who
    turned it ON — all three request bodies (kids, roast, standard) send it."""
    src = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert src.count("animate_cover: animateCover") == 3, (
        "expected all three web request bodies to send animate_cover explicitly"
    )
