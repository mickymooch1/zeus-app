"""Voice-clone quality settings and honest expectations (2026-08-10).

A user's clone "sounded nothing like" them. Investigation ruled out every
mechanical cause — ElevenLabs' own record of the sample showed it arrived
intact (1,004,453 bytes, duration_secs 63.84, decoded cleanly), the correct
IVC endpoint was used, and the narration path really did use the clone
(`story narration: using cloned voice_id=...`).

What remained was Instant Voice Cloning's own ceiling, which ElevenLabs concede
"may struggle with unique accents". Four renders at different settings were
compared by ear and none matched, so the settings below are applied because they
are objectively better for any clone — NOT because they rescue a hard voice.

The UI copy exists to set that expectation before someone records.
"""
import inspect
import pathlib
import sys
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-voice-quality-tests")

SETTINGS = (pathlib.Path(__file__).parent.parent.parent
            / "web-beats" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")


def _generate_src():
    import main
    return inspect.getsource(main.songs_generate)


def test_cloned_voice_gets_speaker_boost():
    """It exists specifically to boost similarity to the original speaker, and we
    were never sending it."""
    assert '"use_speaker_boost": True' in _generate_src()


def test_cloned_voice_uses_lower_stability_than_stock():
    """High stability yields "a monotonous voice with limited emotion" — it
    flattens the cadence that makes a voice recognisable."""
    src = _generate_src()
    assert '"stability": 0.4' in src, "clone should use lower stability"
    assert '"stability": 0.75' in src, "stock narrators should keep their tuning"


def test_the_clone_settings_only_apply_to_the_clone():
    """Stock narrator voices are already tuned; changing them was not the goal."""
    src = _generate_src()
    assert "_is_cloned_narrator" in src
    assert "if _is_cloned_narrator:" in src


def test_upload_is_not_mislabelled_as_mp3():
    """Browser recordings are WebM/Opus. The filename used to claim .mp3 for
    every upload, which contradicted the bytes."""
    import main
    src = inspect.getsource(main.clone_voice)
    assert '"voice_sample.mp3", audio_bytes' not in src, "hardcoded mp3 filename is back"
    assert "_upload_name" in src and "_upload_type" in src


def test_ui_enforces_a_real_minimum_length():
    """The old gate was 20,000 bytes — a few seconds — while the text asked for
    1-3 minutes, so a hopeless sample could be submitted with no warning."""
    assert "MIN_SECONDS = 30" in SETTINGS
    assert "blob.size < 20000" not in SETTINGS, "the meaningless byte gate is back"


def test_ui_caps_the_recording():
    """Past roughly two minutes extra audio does not improve the clone."""
    assert "MAX_SECONDS = 150" in SETTINGS
    # the timer must actually stop the recording at the cap, not just colour a hint
    assert "if (elapsedRef.current >= MAX_SECONDS) stopRecording();" in SETTINGS


def test_ui_sets_honest_expectations_before_recording():
    """A clone of a distinctive voice may simply not be close. Say so up front
    rather than letting someone discover it after recording."""
    low = SETTINGS.lower()
    assert "inspired by" in low, "should not imply an exact copy"
    assert "accent" in low, "should mention accents being harder"
    assert "quiet" in low, "should give recording guidance"
