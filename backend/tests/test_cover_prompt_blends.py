"""Cover prompt for blended genres.

A blend is stored as genre_tag "first__second" (songs.py, main.py). The cover
lookup used to try only the whole tag, so every blend fell through to the
generic default prompt. A blend should get the FIRST genre's prompt.
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

import webhooks  # noqa: E402

P = webhooks.GENRE_COVER_PROMPTS
DEFAULT = webhooks._DEFAULT_COVER_PROMPT


def test_single_genre_uses_its_own_prompt():
    assert webhooks.cover_prompt_for("country") == P["country"]


def test_blend_uses_the_first_genres_prompt():
    assert webhooks.cover_prompt_for("bluessoul__country") == P["bluessoul"]
    assert webhooks.cover_prompt_for("country__bluessoul") == P["country"]


def test_blend_with_unknown_first_genre_falls_back_to_the_second():
    assert webhooks.cover_prompt_for("notagenre__country") == P["country"]


def test_unknown_and_empty_tags_get_the_default():
    assert webhooks.cover_prompt_for("notagenre") == DEFAULT
    assert webhooks.cover_prompt_for("nope__alsonope") == DEFAULT
    assert webhooks.cover_prompt_for("") == DEFAULT
    assert webhooks.cover_prompt_for(None) == DEFAULT


def test_flux_cover_uses_the_blend_aware_lookup(monkeypatch, tmp_path):
    """End to end through _generate_flux_cover: the prompt sent to Flux for a
    blend is the first genre's, not the generic default."""
    import image_generator
    sent = {}

    def fake_submit(prompt, ratio):
        sent["prompt"] = prompt
        raise RuntimeError("stop after capturing the prompt")   # cover fails soft -> None

    monkeypatch.setattr(image_generator, "submit_image_generation", fake_submit)
    assert webhooks._generate_flux_cover(1, "bluessoul__country", title="t") is None
    assert sent["prompt"] == P["bluessoul"]

