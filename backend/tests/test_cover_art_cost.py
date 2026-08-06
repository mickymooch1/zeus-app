"""Cover art: use Suno's free artwork, pay Flux only as a fallback (2026-08-06).

Suno ships artwork with every take at no cost, and the webhook already downloads
and stores it. Flux then ran UNCONDITIONALLY and overwrote it — paying ~$0.025 an
image to replace one we had been given for free, twice per song.

Flux is now a fallback for when Suno's artwork is missing or its download failed,
so a song is never left with no cover.

Also pinned here: Kling must animate whatever cover the variant actually has.
Its gate used to key on the Flux result specifically, which would have silently
disabled animation for everyone the moment Flux stopped running.
"""
import inspect
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("JWT_SECRET", "test-secret-for-cover-tests")

_SRC = (pathlib.Path(__file__).parent.parent / "webhooks.py").read_text(encoding="utf-8")


def test_flux_is_never_called_unconditionally():
    """The regression: an unguarded _generate_flux_cover call is the bug."""
    for line in _SRC.splitlines():
        stripped = line.strip()
        if stripped.startswith("flux_cover1 =") or stripped.startswith("flux_cover2 ="):
            indent = len(line) - len(line.lstrip())
            assert indent >= 8, (
                f"Flux call looks unguarded (indent {indent}): {stripped[:60]}"
            )


def test_suno_artwork_short_circuits_flux():
    assert "using Suno artwork (free) — skipping Flux" in _SRC
    assert _SRC.count("using Suno artwork (free) — skipping Flux") == 2, \
        "both take 1 and take 2 must skip Flux when Suno supplied artwork"


def test_flux_still_runs_when_suno_art_is_missing():
    """A song must never end up with no cover at all."""
    assert "(no Suno artwork)" in _SRC
    assert _SRC.count("(no Suno artwork)") == 2


def test_kling_gates_on_the_actual_cover_not_the_flux_result():
    """If this regressed to flux_cover*, animation would silently stop for
    everyone, since Flux no longer runs on the normal path."""
    assert "elif not flux_cover1:" not in _SRC
    assert "elif not flux_cover2:" not in _SRC
    assert "elif not permanent_image_url1:" in _SRC
    assert "elif not permanent_image_url2:" in _SRC


def test_kling_is_handed_the_actual_cover_url():
    assert "args=(variant_id, permanent_image_url1, local_path1" in _SRC
    assert "args=(take2_variant_id, permanent_image_url2, local_path2" in _SRC
    assert "flux_cover1, local_path1" not in _SRC
    assert "flux_cover2, local_path2" not in _SRC


def test_no_undefined_flux_variable_can_leak_out_of_the_fallback():
    """flux_cover* is now only bound inside the else branch — nothing outside it
    may reference the name, or a normal song would raise NameError mid-webhook."""
    for name in ("flux_cover1", "flux_cover2"):
        for m in re.finditer(rf"^(\s*)(.*\b{name}\b.*)$", _SRC, re.MULTILINE):
            indent, line = len(m.group(1)), m.group(2).strip()
            assert indent >= 8, f"{name} referenced at indent {indent}: {line[:70]}"


def test_webhooks_module_still_imports():
    import webhooks
    assert hasattr(webhooks, "_generate_flux_cover")
