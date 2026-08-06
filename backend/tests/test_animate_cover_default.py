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


def test_web_no_longer_requests_animation_at_all():
    """Superseded 2026-08-06: animated covers were removed entirely, so the web
    client stopped sending the field. The backend default staying False is what
    now guarantees no animation is ever requested."""
    src = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "animate_cover" not in src, "web should no longer mention animate_cover"


# ── Animated covers removed entirely (2026-08-06) ────────────────────────────

def test_no_kling_call_survives_anywhere_in_the_backend():
    """~90% of fal.ai spend. Nothing may start that pipeline again."""
    backend = pathlib.Path(__file__).parent.parent
    for f in backend.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "target=_kling_pipeline" not in src, f"Kling thread started in {f.name}"
        assert "def _kling_pipeline" not in src, f"Kling pipeline redefined in {f.name}"


def test_the_manual_generate_video_endpoint_is_gone():
    """It commissioned the same ~$1.40 clip by another route."""
    src = (pathlib.Path(__file__).parent.parent / "main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/songs/variants/{variant_id}/generate-video")' not in src


def test_premium_credits_survive_for_stem_separation():
    """Animations are gone but premium credits are NOT — they are the currency for
    stems, and removing them would leave stems with no top-up route."""
    src = (pathlib.Path(__file__).parent.parent / "main.py").read_text(encoding="utf-8")
    assert "check_and_deduct_premium_credit" in src, "stems must still spend premium credits"
    import billing
    assert billing.PREMIUM_PACKS, "there must still be a way to buy premium credits"
    for pack in billing.PREMIUM_PACKS.values():
        assert "animation" not in pack["label"].lower(), f"stale label: {pack['label']}"


def test_pack_keys_are_unchanged_so_stripe_keeps_working():
    """Labels changed; keys must not — Stripe price IDs and the crediting webhook
    are keyed on them, so renaming would strand in-flight payments."""
    import billing
    assert set(billing.PREMIUM_PACKS) == {"animation_pack_5", "animation_pack_15"}


def test_no_user_facing_copy_still_sells_animation():
    root = pathlib.Path(__file__).parent.parent.parent / "web-beats" / "src"
    import json
    for loc in (root / "locales").glob("*.json"):
        blob = json.dumps(json.loads(loc.read_text(encoding="utf-8")), ensure_ascii=False).lower()
        # "kling" as a substring also matches German "klingt" (= sounds), which is
        # legitimate copy — match the brand name instead.
        assert "kling ai" not in blob, f"{loc.name} still mentions Kling AI"
        assert "kling-video" not in blob, f"{loc.name} still references the Kling model"
        assert "animatedcover" not in blob, f"{loc.name} still has the toggle strings"
    for page in ("LandingPage.jsx", "PricingPage.jsx", "TutorialPage.jsx"):
        txt = (root / "pages" / page).read_text(encoding="utf-8")
        assert "Kling" not in txt, f"{page} still mentions Kling"
        assert "HD Video Animation" not in txt, f"{page} still advertises animation"
