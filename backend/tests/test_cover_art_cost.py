"""Cover art: genre-tailored Flux artwork, with Suno's as the fallback.

History, because this flipped twice and the reasoning matters:

  Originally  Flux ran unconditionally and overwrote Suno's free artwork.
  2026-08-06  Flipped to Suno-first while hunting fal.ai costs.
  2026-08-06  Flipped back — Suno's generic art was noticeably less matched to
              the genre, and Flux is only ~$0.025 an image. The real cost problem
              was Kling video at ~$1.40 a clip, which is removed and must stay
              removed.
  2026-08-19  Split per take. Measured spend showed 2 paid Flux images per song
              (one per variant), while Suno's free cover for take 2 was being
              downloaded and then immediately overwritten. Take 1 keeps bespoke
              genre-tailored Flux art; take 2 ships Suno's. Halves cover spend
              and the genre-matching argument above still holds for take 1.

So: take 1 = Flux, with Suno's download as its fallback. Take 2 = Suno, with
Flux as ITS fallback. Both directions are covered, so neither take can be left
without artwork — which is what these tests pin down.
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

def test_take_1_gets_flux_unconditionally():
    """Take 1 is the one that must be genre-tailored — that is why Flux exists here."""
    assert "Starting Flux cover art for variant_id=%d genre=%s" in _SRC
    assert _SRC.count("_generate_flux_cover(") >= 2, "take 1 plus the take-2 fallback"


def test_take_2_uses_sunos_free_art_and_does_not_pay_for_flux():
    """The cost fix: take 2 must not call Flux when Suno already sent a cover."""
    assert "using Suno artwork %s (no Flux call)" in _SRC, \
        "take 2 should ship Suno's cover without paying fal.ai"
    # The take-2 Flux call must sit on the no-Suno-artwork branch, not run before it.
    take2 = _SRC.split("Take 2 keeps Suno's own cover", 1)[1][:1500]
    assert "if permanent_image_url2:" in take2, "take 2 must branch on Suno art being present"
    assert take2.index("if permanent_image_url2:") < take2.index("_generate_flux_cover("), \
        "Flux must only be reached on the else branch (no Suno art)"


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

def test_take_1_falls_back_to_suno_when_flux_fails():
    """Take 1's direction of the fallback: paid art fails, free art still ships."""
    assert "keeping Suno's cover art" in _SRC


def test_take_2_falls_back_to_flux_when_suno_sent_no_art():
    """Take 2's direction: no free art, so pay for one image rather than ship blank."""
    assert "Take 2 has no Suno artwork — falling back to Flux" in _SRC
    assert "(take2, Flux fallback)" in _SRC


def test_suno_art_is_still_downloaded_first():
    """It has to be fetched before Flux runs, or there is nothing to fall back to."""
    assert "downloading take 1 cover art" in _SRC
    assert "downloading take 2 cover art" in _SRC


def test_neither_take_can_end_up_blank():
    """Every path through both takes ends in artwork, or logs loudly that it did not."""
    assert "no Flux and no Suno artwork" in _SRC                          # take 1 exhausted
    assert "no Suno artwork and Flux failed" in _SRC                      # take 2 exhausted


def test_take_2_cover_gets_the_title_overlay():
    """Take 2 now ships Suno's raw download, which has no burned-in title unless we
    add one — without this the two takes of the same song look inconsistent."""
    assert "_add_text_overlay(_take2_cover_path" in _SRC
    # and it must be guarded, so a font/PIL failure costs the text, not the cover
    overlay_ctx = _SRC.split("_add_text_overlay(_take2_cover_path", 1)[0][-300:]
    assert "try:" in overlay_ctx, "overlay call must be wrapped in try/except"


# ── Kling must stay gone — that was the real cost ────────────────────────────

def test_no_kling_invocation_returns():
    """~$1.40 a clip and ~90% of fal.ai spend. Restoring Flux must not drag Kling
    back in with it."""
    assert "target=_kling_pipeline" not in _SRC
    assert "def _kling_pipeline" not in _SRC


def test_nothing_can_reach_kling_by_any_route():
    """Removed entirely 2026-08-20. The animated-cover pipeline went on 2026-08-06,
    but generate_video_art() survived in image_generator and stayed reachable through
    the zeus_agent GenerateVideoArt tool — a $1.40 clip was still one prompt away.
    This asserts the whole surface is gone, not just the pipeline."""
    import pathlib
    backend = pathlib.Path(__file__).parent.parent

    for fname in ("image_generator.py", "zeus_agent.py", "webhooks.py", "main.py", "songs.py"):
        src = (backend / fname).read_text(encoding="utf-8")
        # Strip comment lines: the removal notes deliberately name Kling.
        code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
        assert "queue.fal.run/fal-ai/kling" not in code, f"{fname} can still reach Kling"
        assert "def generate_video_art" not in code, f"{fname} still defines generate_video_art"
        assert "generate_video_art(" not in code, f"{fname} still calls generate_video_art"

    agent = (backend / "zeus_agent.py").read_text(encoding="utf-8")
    assert '"name": "GenerateVideoArt"' not in agent, "the video tool is still offered to the model"
    assert '"GenerateVideoArt"' not in agent.split("# GenerateVideoArt removed")[-1], \
        "a GenerateVideoArt handler branch still exists"


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
