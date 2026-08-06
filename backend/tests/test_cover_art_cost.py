"""Cover art: genre-tailored Flux artwork, with Suno's as the fallback.

History, because this flipped twice and the reasoning matters:

  Originally  Flux ran unconditionally and overwrote Suno's free artwork.
  2026-08-06  Flipped to Suno-first while hunting fal.ai costs.
  2026-08-06  Flipped back — Suno's generic art was noticeably less matched to
              the genre, and Flux is only ~$0.025 an image. The real cost problem
              was Kling video at ~$1.40 a clip, which is removed and must stay
              removed.

So Flux runs on every take, and Suno's already-downloaded cover remains as the
fallback if Flux fails. A song is never left with no artwork.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("JWT_SECRET", "test-secret-for-cover-tests")

_SRC = (pathlib.Path(__file__).parent.parent / "webhooks.py").read_text(encoding="utf-8")


# ── Flux runs, and is genre-aware ────────────────────────────────────────────

def test_flux_runs_for_both_takes():
    assert _SRC.count("_generate_flux_cover(") >= 2, "both takes should get Flux artwork"
    assert "using Suno artwork (free) — skipping Flux" not in _SRC, \
        "the Suno-first behaviour was reverted — this marker should be gone"


def test_cover_prompts_are_genre_specific():
    """The whole reason Flux came back: Suno's art wasn't tailored to the genre."""
    import webhooks
    assert len(webhooks.GENRE_COVER_PROMPTS) > 50, "genre-specific prompts are the point"
    for genre in ("grime", "opera", "country", "jungle"):
        assert genre in webhooks.GENRE_COVER_PROMPTS, f"no cover prompt for {genre}"
    # and they must actually differ from one another
    assert webhooks.GENRE_COVER_PROMPTS["grime"] != webhooks.GENRE_COVER_PROMPTS["opera"]


def test_a_default_prompt_exists_for_unknown_genres():
    import webhooks
    assert webhooks._DEFAULT_COVER_PROMPT
    assert webhooks.GENRE_COVER_PROMPTS.get("not_a_real_genre") is None


# ── Suno's artwork is the fallback, so a song always has a cover ─────────────

def test_suno_art_is_kept_when_flux_fails():
    assert "keeping Suno's cover art" in _SRC
    assert _SRC.count("keeping Suno's cover art") == 2, "both takes need the fallback"


def test_suno_art_is_still_downloaded_first():
    """It has to be fetched before Flux runs, or there is nothing to fall back to."""
    assert "downloading take 1 cover art" in _SRC
    assert "downloading take 2 cover art" in _SRC


def test_the_no_art_at_all_case_is_logged():
    assert "no Flux and no Suno artwork" in _SRC


# ── Kling must stay gone — that was the real cost ────────────────────────────

def test_no_kling_invocation_returns():
    """~$1.40 a clip and ~90% of fal.ai spend. Restoring Flux must not drag Kling
    back in with it."""
    assert "target=_kling_pipeline" not in _SRC
    assert "def _kling_pipeline" not in _SRC


def test_webhooks_module_still_imports():
    import webhooks
    assert hasattr(webhooks, "_generate_flux_cover")


def test_every_selectable_genre_has_its_own_cover_prompt():
    """Guards the gap this file caught: opera and scat shipped without cover
    prompts and silently fell back to the generic default — the exact untailored
    artwork the Flux restore exists to avoid. Any new genre must bring one."""
    import webhooks
    from song_genres import GENRE_PRESETS

    # Instrumental/ambience genres deliberately share broader artwork.
    exempt = {
        "naturesounds", "whalesong", "cracklingfire", "thunderstorm", "oceanwaves",
        "forest", "nightsounds", "healingfrequency", "meditation", "ambient",
    }
    missing = sorted(
        g for g in GENRE_PRESETS
        if g not in webhooks.GENRE_COVER_PROMPTS and g not in exempt
    )
    assert not missing, f"genres with no cover prompt: {missing}"
