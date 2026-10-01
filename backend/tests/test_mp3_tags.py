"""Song MP3 metadata (2026-10-01): strip the provider's embedded tags and write
our own (artist "Zeus Beats", title = song title) — on every save, plus a
staged, backed-up clean-up of existing files (mp3_retag.py, Porick `mp3tags`).

Found in production: ~half of song MP3s carried
TXXX comment = "made with suno; created=…; id=<provider job id>".
No importlib.reload here — see the test-baseline note about db reloads.
"""
import os
import pathlib
import re
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-mp3-tag-tests")

from mutagen.id3 import ID3, TXXX, TSSE, TIT2  # noqa: E402

import audio_tags  # noqa: E402

BACKEND = pathlib.Path(__file__).parent.parent
AUDIO = b"\xff\xfb\x90\x64" + bytes(range(256)) * 900          # stand-in MPEG payload


def _provider_mp3(path, extra_v1=False):
    path.write_bytes(AUDIO + (b"TAG" + b"old v1 title".ljust(125, b"\x00") if extra_v1 else b""))
    tags = ID3()
    tags.add(TXXX(encoding=3, desc="comment", text="made with suno; created=2026-05-08T17:58:09Z; id=fed6c6ad"))
    tags.add(TSSE(encoding=3, text="Lavf60.16.100"))
    tags.add(TIT2(encoding=3, text="provider title"))
    tags.save(str(path), v2_version=4)
    return path


# ── audio_tags ───────────────────────────────────────────────────────────────

def test_retag_replaces_provider_tags_and_keeps_audio_identical(tmp_path):
    f = _provider_mp3(tmp_path / "1.mp3", extra_v1=True)
    before_audio = audio_tags.audio_digest(f)
    assert audio_tags.has_provider_mark(f)
    assert any(t.startswith("ID3v1=") for t in audio_tags.describe_tags(f))

    audio_tags.retag_mp3(f, "Mate Tax")

    assert sorted(audio_tags.describe_tags(f)) == ["TIT2=Mate Tax", "TPE1=Zeus Beats"]
    assert not audio_tags.has_provider_mark(f)
    assert b"suno" not in f.read_bytes().lower()
    assert audio_tags.audio_digest(f) == before_audio
    assert audio_tags.is_clean(f, "Mate Tax")


def test_retag_song_file_never_raises(tmp_path):
    assert audio_tags.retag_song_file(tmp_path / "missing.mp3", 1, tmp_path / "x.db") is False


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("MP3_BACKUP_DIR", str(tmp_path / "backup"))
    (tmp_path / "data").mkdir()
    (tmp_path / "songs").mkdir()
    import db
    path = db.get_db_path()
    db.init_user_tables(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO users (id, email, password_hash, created_at, updated_at) VALUES ('u1','a@b.c','x','now','now')")
    for vid, title in ((1, "First Song"), (2, "Second Song"), (3, None), (4, "Clean Already")):
        conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, 'u1', 'b', 'l', ?)", (vid, title))
        conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status) VALUES (?, ?, 'u1', 'p', 'complete')", (vid, vid))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status) VALUES (9, 1, 'u1', 'p', 'pending')")
    conn.commit()
    conn.close()
    songs = tmp_path / "songs"
    _provider_mp3(songs / "1.mp3")
    _provider_mp3(songs / "2.mp3")
    (songs / "3.mp3").write_bytes(AUDIO)                       # no tags at all
    (songs / "4.mp3").write_bytes(AUDIO)
    audio_tags.retag_mp3(songs / "4.mp3", "Clean Already")
    return {"db": path, "songs": songs, "backup": tmp_path / "backup"}


def test_song_title_uses_lyric_title_with_fallback(env):
    assert audio_tags.song_title(env["db"], 1) == "First Song"
    assert audio_tags.song_title(env["db"], 3) == audio_tags.FALLBACK_TITLE
    assert audio_tags.song_title(env["db"], 999) == audio_tags.FALLBACK_TITLE


# ── mp3_retag (the clean-up) ─────────────────────────────────────────────────

def _bytes(env):
    return {p.name: p.read_bytes() for p in env["songs"].iterdir()}


def test_dryrun_changes_nothing_and_counts_correctly(env):
    import mp3_retag
    before = _bytes(env)
    items = mp3_retag.plan(env["db"])
    s = mp3_retag.summary(items)
    assert [i["variant_id"] for i in items] == [1, 2, 3, 4]       # pending variant 9 ignored
    assert (s["files"], s["to_change"], s["provider_marked"], s["already_clean"], s["backed_up"]) == (4, 3, 2, 1, 0)
    assert s["enough_space"] is True
    assert _bytes(env) == before
    assert not env["backup"].exists()


def test_apply_refuses_files_without_a_verified_backup(env):
    import mp3_retag
    before = _bytes(env)
    r = mp3_retag.apply(mp3_retag.plan(env["db"]))
    assert r["retagged"] == [] and sorted(r["not_backed_up"]) == [1, 2, 3]
    assert _bytes(env) == before


def test_backup_then_apply_then_rerun_is_a_noop(env):
    import mp3_retag
    originals = _bytes(env)
    items = mp3_retag.plan(env["db"])
    b = mp3_retag.backup(items)
    assert b == {"copied": 3, "already_backed_up": 0}
    for vid in (1, 2, 3):
        assert (env["backup"] / f"{vid}.mp3").read_bytes() == originals[f"{vid}.mp3"]
    assert len((env["backup"] / "manifest.jsonl").read_text().splitlines()) == 3

    r = mp3_retag.apply(items)
    assert sorted(d["variant_id"] for d in r["retagged"]) == [1, 2, 3]
    assert r["skipped_clean"] == 1 and r["restored_after_failed_check"] == []
    assert audio_tags.is_clean(env["songs"] / "1.mp3", "First Song")
    assert audio_tags.is_clean(env["songs"] / "3.mp3", audio_tags.FALLBACK_TITLE)
    for vid in (1, 2, 3):
        assert audio_tags.audio_digest(env["songs"] / f"{vid}.mp3") == audio_tags.audio_digest(env["backup"] / f"{vid}.mp3")

    again = mp3_retag.apply(mp3_retag.plan(env["db"]))
    assert again["retagged"] == [] and again["skipped_clean"] == 4
    assert mp3_retag.backup(mp3_retag.plan(env["db"])) == {"copied": 0, "already_backed_up": 0}


def test_failed_verification_restores_the_original(env, monkeypatch):
    import mp3_retag
    items = mp3_retag.plan(env["db"])
    mp3_retag.backup(items)
    original = (env["songs"] / "1.mp3").read_bytes()

    def corrupting_retag(path, title):
        pathlib.Path(path).write_bytes(b"broken audio")
    monkeypatch.setattr(audio_tags, "retag_mp3", corrupting_retag)
    r = mp3_retag.apply([i for i in items if i["variant_id"] == 1])
    assert r["restored_after_failed_check"] == [1] and r["retagged"] == []
    assert (env["songs"] / "1.mp3").read_bytes() == original


def test_backup_refuses_when_disk_is_too_full(env, monkeypatch):
    import mp3_retag
    import shutil
    monkeypatch.setattr(shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(10, 10, 1000))
    with pytest.raises(RuntimeError, match="not enough disk space"):
        mp3_retag.backup(mp3_retag.plan(env["db"]))
    assert not any(env["backup"].glob("*.mp3")) if env["backup"].exists() else True


def test_restore_and_pick_test(env):
    import mp3_retag
    items = mp3_retag.plan(env["db"])
    assert [i["variant_id"] for i in mp3_retag.pick_test(items, 2)] == [1, 2]   # provider-marked first
    original = (env["songs"] / "2.mp3").read_bytes()
    mp3_retag.backup(items)
    mp3_retag.apply(items)
    assert mp3_retag.restore([2, 77]) == {"restored": [2], "no_backup": [77]}
    assert (env["songs"] / "2.mp3").read_bytes() == original


# ── Porick commands ──────────────────────────────────────────────────────────

def test_porick_dryrun_and_test_commands(env, monkeypatch):
    import telegram_admin as T
    monkeypatch.setattr(T, "_db_log_action", lambda *a, **k: None)
    before = _bytes(env)
    reply = T.parse_and_run("mp3tags dryrun", chat_id="c1")
    assert "DRY RUN" in reply and "Would change: 3" in reply
    assert _bytes(env) == before

    reply = T.parse_and_run("mp3tags test 2", chat_id="c1")
    assert "TEST on 2" in reply and "#1" in reply and "#2" in reply and "audio unchanged: ✅" in reply
    assert "mp3tags restore 1,2" in reply
    assert audio_tags.is_clean(env["songs"] / "1.mp3", "First Song")
    assert not audio_tags.is_clean(env["songs"] / "3.mp3", audio_tags.FALLBACK_TITLE)   # only 2 touched


def test_porick_run_all_refuses_until_backup_complete(env, monkeypatch):
    import telegram_admin as T
    import alerts
    import threading
    sent = []
    monkeypatch.setattr(T, "_db_log_action", lambda *a, **k: None)
    monkeypatch.setattr(alerts, "_send_telegram", lambda m: sent.append(m) or True)

    class Inline:
        def __init__(self, target, **kw): self.target = target
        def start(self): self.target()
    monkeypatch.setattr(threading, "Thread", Inline)
    before = _bytes(env)
    T.parse_and_run("mp3tags run all confirm", chat_id="c1")
    assert "backup incomplete" in sent[-1] and _bytes(env) == before

    T.parse_and_run("mp3tags backup", chat_id="c1")
    assert "MP3 backup done" in sent[-1]
    T.parse_and_run("mp3tags run all confirm", chat_id="c1")
    assert "MP3 retag done" in sent[-1] and "retagged 3" in sent[-1]
    assert all(audio_tags.is_clean(env["songs"] / f"{v}.mp3", audio_tags.song_title(env["db"], v)) for v in (1, 2, 3, 4))


# ── every save path retags ───────────────────────────────────────────────────

def test_every_song_mp3_save_site_retags():
    src = (BACKEND / "webhooks.py").read_text(encoding="utf-8")
    writes = len(re.findall(r'os\.path\.join\(STORAGE_PATH, f"\{\w+\}\.mp3"\)', src))
    hooks = src.count("audio_tags.retag_song_file(")
    assert writes == hooks == 5, (writes, hooks)
    # take 1 / take 2: tags are written AFTER the fade-out re-encode
    assert src.index("_apply_fade_out(local_path1") < src.index("retag_song_file(local_path1")
    assert src.index("_apply_fade_out(local_path2") < src.index("retag_song_file(local_path2")
    main_src = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "_audio_tags.retag_song_file(_sfx_out, _sfx_vid, db_path)" in main_src
