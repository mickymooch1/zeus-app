"""Automatic fade-out: every song should end with an 8s exponential fade instead
of cutting off dead. Measured against 8 real production songs — all were at or
near full volume until the final 1-3 seconds, one dropped to near-total digital
silence in the last 0.75s. Locked in after listening to 4s/6s/8s/10s comparisons
on the three most abrupt real songs (1551, 1553, 1608) — 8s was the one that
sounded natural.

Best-effort by design: a fade is cosmetic. If ffmpeg is missing, times out, or
errors, the song must still be delivered unfaded rather than fail — same
log-first, never-raise shape as alerts.py and _maybe_extend_short_song.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("JWT_SECRET", "test-secret-for-fade-tests")

import webhooks  # noqa: E402

_SRC = (pathlib.Path(__file__).parent.parent / "webhooks.py").read_text(encoding="utf-8")


class _FakeCompleted:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def test_locked_in_at_8_seconds_exponential():
    """The value picked after listening to 4/6/8/10s comparisons — regressing this
    silently would undo that decision without anyone noticing."""
    assert webhooks._FADE_SECONDS == 8


def test_skips_fade_when_song_shorter_than_fade_length(monkeypatch):
    """A file shorter than the fade itself must be left alone, not mangled."""
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or _FakeCompleted())
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 5.0)

    webhooks._apply_fade_out("irrelevant.mp3", variant_id=1, fallback_duration=5)

    assert calls == [], "ffmpeg must not be invoked for a song shorter than the fade"


def test_happy_path_invokes_ffmpeg_with_expected_filter_and_replaces_file(monkeypatch, tmp_path):
    """Duration 150s, 8s fade -> afade should start at 142s. The temp output must
    be swapped into place over the original on success."""
    target = tmp_path / "42.mp3"
    target.write_bytes(b"original-audio-bytes")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        # ffmpeg's real behaviour: write the -y ... output path (last arg)
        pathlib.Path(cmd[-1]).write_bytes(b"faded-audio-bytes")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 150.0)

    webhooks._apply_fade_out(str(target), variant_id=42, fallback_duration=150)

    cmd = captured["cmd"]
    assert "ffmpeg" in cmd[0].lower() or cmd[0] == "ffmpeg"
    af_index = cmd.index("-af")
    af_value = cmd[af_index + 1]
    assert af_value == "afade=t=out:st=142.0:d=8:curve=exp", af_value
    # tmp file replaced the original in place — no leftover .fade.tmp, and the
    # file at the original path now holds the faded bytes.
    assert target.read_bytes() == b"faded-audio-bytes"
    assert not (tmp_path / "42.mp3.fade.tmp").exists()


def test_ffmpeg_failure_never_raises_and_leaves_original_file_untouched(monkeypatch, tmp_path):
    """The core reliability guarantee: a fade failure must never block delivery."""
    target = tmp_path / "43.mp3"
    target.write_bytes(b"original-audio-bytes")

    def failing_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr=b"ffmpeg exploded")

    monkeypatch.setattr(subprocess, "run", failing_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 150.0)

    webhooks._apply_fade_out(str(target), variant_id=43, fallback_duration=150)  # must not raise

    assert target.read_bytes() == b"original-audio-bytes", "original must survive a fade failure"
    assert not (tmp_path / "43.mp3.fade.tmp").exists(), "no leftover partial temp file"


def test_ffmpeg_failure_logs_stderr_and_stdout(monkeypatch, tmp_path, caplog):
    """The gap that made the real production failure hard to diagnose: the log
    only ever showed the exit code, never ffmpeg's own error message."""
    target = tmp_path / "45.mp3"
    target.write_bytes(b"original-audio-bytes")

    def failing_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            234, cmd, output=b"some stdout noise", stderr=b"Unknown encoder 'libmp3lame'",
        )

    monkeypatch.setattr(subprocess, "run", failing_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 150.0)

    with caplog.at_level("ERROR", logger="zeus.webhooks"):
        webhooks._apply_fade_out(str(target), variant_id=45, fallback_duration=150)

    logged = "\n".join(r.message for r in caplog.records)
    assert "Unknown encoder 'libmp3lame'" in logged
    assert "234" in logged


def test_ffmpeg_failure_pages_admin(monkeypatch, tmp_path):
    """The failure was invisible to the team (found by ear, not by monitoring) —
    a real ffmpeg failure must page like every other alert_* in this system."""
    import alerts

    target = tmp_path / "46.mp3"
    target.write_bytes(b"original-audio-bytes")
    calls = []
    monkeypatch.setattr(alerts, "alert_fade_out_failed", lambda variant_id, detail: calls.append((variant_id, detail)))

    def failing_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(234, cmd, stderr=b"Unknown encoder 'libmp3lame'")

    monkeypatch.setattr(subprocess, "run", failing_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 150.0)

    webhooks._apply_fade_out(str(target), variant_id=46, fallback_duration=150)

    assert len(calls) == 1
    assert calls[0][0] == 46
    assert "libmp3lame" in calls[0][1]


def test_no_admin_page_on_successful_fade(monkeypatch, tmp_path):
    import alerts

    target = tmp_path / "47.mp3"
    target.write_bytes(b"original-audio-bytes")
    calls = []
    monkeypatch.setattr(alerts, "alert_fade_out_failed", lambda *a, **k: calls.append((a, k)))

    def fake_run(cmd, **kwargs):
        pathlib.Path(cmd[-1]).write_bytes(b"faded-audio-bytes")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: 150.0)

    webhooks._apply_fade_out(str(target), variant_id=47, fallback_duration=150)

    assert calls == []


def test_probe_failure_falls_back_to_caller_supplied_duration(monkeypatch, tmp_path):
    """A probe hiccup must not skip the fade outright — fall back to the
    Apiframe-reported duration rather than losing the fade for no reason."""
    target = tmp_path / "44.mp3"
    target.write_bytes(b"original-audio-bytes")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        pathlib.Path(cmd[-1]).write_bytes(b"faded-audio-bytes")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(webhooks, "_probe_duration_seconds", lambda p: None)

    webhooks._apply_fade_out(str(target), variant_id=44, fallback_duration=100)

    af_value = captured["cmd"][captured["cmd"].index("-af") + 1]
    assert af_value == "afade=t=out:st=92:d=8:curve=exp", af_value


def test_both_takes_call_apply_fade_out():
    """Take 1 and take 2 must both be faded — the shelved auto-extend feature only
    ever touched take 1 and left take 2 unfaded/unextended; do not repeat that gap."""
    assert _SRC.count("_apply_fade_out(") >= 2, \
        "expected a call for take 1 and a call for take 2"


def test_fade_applied_before_status_marked_complete_for_take_1():
    """Must run before the file is treated as final, so nothing downstream
    (stems, video mux, the DB write) can ever see the unfaded version."""
    take1_section = _SRC.split("permanent_url1 = f\"{PUBLIC_BASE_URL}", 1)[0]
    assert "_apply_fade_out(" in take1_section[-800:], \
        "fade for take 1 must be applied immediately before permanent_url1 is set"


def test_fade_applied_before_status_marked_complete_for_take_2():
    take2_section = _SRC.split("permanent_url2 = f\"{PUBLIC_BASE_URL}", 1)[0]
    assert "_apply_fade_out(" in take2_section[-800:], \
        "fade for take 2 must be applied immediately before permanent_url2 is set"
