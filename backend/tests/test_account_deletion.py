"""Admin panel "Delete account" + file cleanup (account_deletion.py, 2026-09-29).

Row deletion is the existing db.delete_user_account engine (see
test_delete_user_account.py); these cover what was added around it: the
preview, the rails (admin / self / active subscription refused; Stripe
purchases and QR codes need an explicit acknowledgement; typed email must
match), removal of the user's files on the volume (never outside the storage
roots, never a file another account still references), the admin_action_log
entry, the two admin endpoints, and Porick's delete_user now removing files.
"""
import json
import os
import pathlib
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-account-deletion-tests")

STORES = ("songs", "avatars", "videos", "images", "stories", "clips")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fresh DB + tmp storage roots; `ad` is account_deletion with default_roots
    pointed at the tmp roots so nothing can reach the real /data."""
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir()
    # No importlib.reload anywhere in this file: db.get_db_path() reads
    # ZEUS_DATA_DIR on every call, and reloading db replaces
    # db.get_db_path_dep — which broke other files' dependency_overrides
    # (the test_ai_hub* suites failed when run after this one).
    import db as _db
    db_path = _db.get_db_path()
    _db.init_user_tables(db_path)
    roots = {s: tmp_path / "vol" / s for s in STORES}
    for r in roots.values():
        r.mkdir(parents=True)
    import account_deletion as ad
    monkeypatch.setattr(ad, "default_roots", lambda: roots)
    return {"db": _db, "ad": ad, "path": db_path, "roots": roots, "tmp": tmp_path}


def _sql(path, q, args=()):
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(q, args)
        conn.commit()
        return cur.fetchall()
    finally:
        conn.close()


def _user(path, uid, email, is_admin=0, status=None, plan=None, memorial=0):
    _sql(path, "INSERT INTO users (id, email, password_hash, is_admin, subscription_status, subscription_plan, "
               "memorial_credits_available, created_at, updated_at) VALUES (?, ?, 'x', ?, ?, ?, ?, 'now', 'now')",
         (uid, email, is_admin, status, plan, memorial))


def _file(roots, store, name, data=b"x" * 10):
    p = roots[store] / name
    p.write_bytes(data)
    return p


def _seed_target(e, qr=0, stripe=False):
    """u1 with a memorial song (id 7) and its files, a photo, a clip upload, credits."""
    path, roots = e["path"], e["roots"]
    _user(path, "u1", "target@example.com", memorial=1)
    _sql(path, "INSERT INTO lyrics (id, user_id, brief, lyrics_text) VALUES (1, 'u1', 'b', 'l')")
    _sql(path, "INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, mp3_url, occasion, qr_generated) "
               "VALUES (7, 1, 'u1', 'p', 'complete', 'https://zeusbeats.com/files/songs/7.mp3', 'memorial', ?)", (qr,))
    _sql(path, "INSERT INTO song_variant_photos (variant_id, filename) VALUES (7, 'photo1.jpg')")
    _sql(path, "INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES ('u1', 4, 0)")
    e["db"].record_credit_grant(path, "u1", "target@example.com", "song", 5,
                                "stripe" if stripe else "signup", "pi_123" if stripe else None)
    _sql(path, "INSERT INTO clips (user_id, song_id, media_type, media_url, clip_start_time, clip_duration, created_at) "
               "VALUES ('u1', 7, 'video', '/files/clips/own.mp4', 0, 15, 'now')")
    return {
        "mp3": _file(roots, "songs", "7.mp3"), "mp4": _file(roots, "videos", "7.mp4"),
        "portrait": _file(roots, "avatars", "7_portrait.jpg"), "photo": _file(roots, "songs", "photo1.jpg"),
        "clip": _file(roots, "clips", "own.mp4"),
    }


def _log_rows(path):
    try:
        return _sql(path, "SELECT chat_id, action, summary FROM admin_action_log")
    except sqlite3.OperationalError:  # table only exists once something has been logged
        return []


# ── preview ──────────────────────────────────────────────────────────────────

def test_preview_shows_what_would_be_deleted_and_changes_nothing(env):
    files = _seed_target(env)
    p = env["ad"].build_preview(env["path"], "u1")
    assert p["email"] == "target@example.com"
    assert (p["songs"], p["song_credits"], p["memorial_credits"], p["memorial_pages"]) == (1, 4, 1, 1)
    assert p["ledger_rows"] == 1 and p["stripe_purchases"] == 0 and p["qr_codes"] == 0
    assert p["files"] == 5 and p["file_bytes"] == 50
    assert p["blockers"] == [] and p["warnings"] == []
    assert all(f.exists() for f in files.values())
    assert _sql(env["path"], "SELECT COUNT(*) FROM users WHERE id='u1'")[0][0] == 1


def test_preview_unknown_user_is_none(env):
    assert env["ad"].build_preview(env["path"], "nope") is None


def test_preview_blocks_admin_accounts(env):
    _user(env["path"], "a1", "admin@example.com", is_admin=1)
    p = env["ad"].build_preview(env["path"], "a1")
    assert any("admin" in b for b in p["blockers"])


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_preview_blocks_active_subscriptions(env, status):
    _user(env["path"], "u2", "sub@example.com", status=status, plan="music_pro")
    p = env["ad"].build_preview(env["path"], "u2")
    assert any("Cancel it in Stripe first" in b for b in p["blockers"])


def test_preview_cancelled_subscription_is_not_blocked(env):
    _user(env["path"], "u2", "old@example.com", status="cancelled", plan="music_pro")
    assert env["ad"].build_preview(env["path"], "u2")["blockers"] == []


def test_preview_warns_on_stripe_purchase_and_qr(env):
    _seed_target(env, qr=1, stripe=True)
    p = env["ad"].build_preview(env["path"], "u1")
    assert p["stripe_purchases"] == 1 and p["qr_codes"] == 1
    assert len(p["warnings"]) == 2 and p["blockers"] == []


# ── rails ────────────────────────────────────────────────────────────────────

ADMIN = {"id": "a1", "email": "admin@example.com"}


def _delete(env, uid="u1", confirm="target@example.com", ack=False, actor=ADMIN):
    return env["ad"].delete_from_admin_panel(env["path"], uid, actor=actor, confirm_email=confirm,
                                             acknowledge_warnings=ack)


def _still_there(env, uid="u1"):
    return _sql(env["path"], "SELECT COUNT(*) FROM users WHERE id=?", (uid,))[0][0] == 1


def test_mismatched_typed_email_refuses_and_changes_nothing(env):
    files = _seed_target(env)
    with pytest.raises(env["ad"].DeletionRefused, match="doesn't match"):
        _delete(env, confirm="someone@else.com")
    assert _still_there(env) and all(f.exists() for f in files.values()) and _log_rows(env["path"]) == []


def test_admin_target_refused(env):
    _user(env["path"], "a2", "other-admin@example.com", is_admin=1)
    with pytest.raises(env["ad"].DeletionRefused, match="admin"):
        _delete(env, uid="a2", confirm="other-admin@example.com")
    assert _still_there(env, "a2")


def test_self_delete_refused(env):
    _user(env["path"], "a1", "admin@example.com", is_admin=1)
    with pytest.raises(env["ad"].DeletionRefused, match="your own account"):
        _delete(env, uid="a1", confirm="admin@example.com")
    assert _still_there(env, "a1")


def test_active_subscription_refused(env):
    _user(env["path"], "u2", "sub@example.com", status="active", plan="music_pro")
    with pytest.raises(env["ad"].DeletionRefused, match="Stripe"):
        _delete(env, uid="u2", confirm="sub@example.com", ack=True)
    assert _still_there(env, "u2")


def test_warnings_require_acknowledgement(env):
    files = _seed_target(env, qr=1, stripe=True)
    with pytest.raises(env["ad"].DeletionRefused, match="I understand"):
        _delete(env)
    assert _still_there(env) and all(f.exists() for f in files.values())
    result = _delete(env, ack=True)
    assert result["deleted"]["users"] == 1
    summary = json.loads(_log_rows(env["path"])[0][2])
    assert len(summary["warnings_acknowledged"]) == 2


# ── delete + files ───────────────────────────────────────────────────────────

def test_delete_removes_rows_files_and_logs(env):
    files = _seed_target(env)
    other = _file(env["roots"], "songs", "99.mp3")          # unrelated user's file
    result = _delete(env)

    assert not _still_there(env)
    for t in ("song_variants", "lyrics", "song_credits", "credit_ledger", "clips", "song_variant_photos"):
        assert _sql(env["path"], f"SELECT COUNT(*) FROM {t}")[0][0] == 0, t
    assert not any(f.exists() for f in files.values())
    assert other.exists()
    assert sorted(result["files"]["removed"]) == sorted(
        ["songs/7.mp3", "videos/7.mp4", "avatars/7_portrait.jpg", "songs/photo1.jpg", "clips/own.mp4"])
    assert result["files"]["bytes_freed"] == 50 and result["files"]["failed"] == []

    (chat_id, action, summary), = _log_rows(env["path"])
    s = json.loads(summary)
    assert chat_id == "web:admin@example.com" and action == "admin_delete_user"
    assert s["email"] == "target@example.com" and s["user_id"] == "u1"
    assert s["files_removed"] == 5 and s["rows"]["users"] == 1 and s["deleted_at"]


def test_file_still_referenced_by_another_account_is_kept(env):
    _seed_target(env)
    shared = _file(env["roots"], "clips", "shared.mp4")
    _sql(env["path"], "INSERT INTO clips (user_id, song_id, media_type, media_url, clip_start_time, clip_duration, created_at) "
                      "VALUES ('u1', 7, 'video', '/files/clips/shared.mp4', 0, 15, 'now')")
    _user(env["path"], "u9", "other@example.com")
    _sql(env["path"], "INSERT INTO clips (user_id, song_id, media_type, media_url, clip_start_time, clip_duration, created_at) "
                      "VALUES ('u9', 1, 'video', 'https://zeusbeats.com/files/clips/shared.mp4', 0, 15, 'now')")
    result = _delete(env)
    assert shared.exists()
    assert "clips/shared.mp4" in result["files"]["shared"]


def test_nothing_outside_the_storage_roots_is_ever_touched(env):
    ad, roots = env["ad"], env["roots"]
    outside = env["tmp"] / "vol" / "secret.txt"
    outside.write_text("keep me")
    assert ad._resolve(roots, "songs", "../secret.txt") is None
    assert ad._resolve(roots, "songs", "..") is None
    assert ad._resolve(roots, "nope", "7.mp3") is None
    report = ad.remove_files(env["path"], {("songs", "../secret.txt"), ("songs", "missing.mp3")}, roots)
    assert outside.exists()
    assert report["removed"] == [] and len(report["missing"]) == 2


# ── endpoints ────────────────────────────────────────────────────────────────

@pytest.fixture
def api(env):
    import main as _main
    from fastapi.testclient import TestClient
    _user(env["path"], "a1", "admin@example.com", is_admin=1)
    _user(env["path"], "n1", "normal@example.com")
    tok = lambda uid, email: {"Authorization": f"Bearer {_main.auth.create_token(uid, email, is_admin=False)}"}
    return {"c": TestClient(_main.app), "admin": tok("a1", "admin@example.com"),
            "normal": tok("n1", "normal@example.com")}


def test_endpoints_are_admin_only(env, api):
    _seed_target(env)
    c = api["c"]
    assert c.get("/admin/users/u1/delete-preview", headers=api["normal"]).status_code == 403
    r = c.request("DELETE", "/admin/users/u1", json={"confirm_email": "target@example.com"}, headers=api["normal"])
    assert r.status_code == 403 and _still_there(env)


def test_endpoint_preview_then_delete(env, api):
    files = _seed_target(env)
    c = api["c"]
    p = c.get("/admin/users/u1/delete-preview", headers=api["admin"]).json()
    assert p["email"] == "target@example.com" and p["files"] == 5
    bad = c.request("DELETE", "/admin/users/u1", json={"confirm_email": "wrong@example.com"}, headers=api["admin"])
    assert bad.status_code == 409 and _still_there(env)
    ok = c.request("DELETE", "/admin/users/u1", json={"confirm_email": "TARGET@example.com"}, headers=api["admin"])
    assert ok.status_code == 200, ok.text
    assert not _still_there(env) and not any(f.exists() for f in files.values())


def test_endpoint_preview_flags_self(env, api):
    p = api["c"].get("/admin/users/a1/delete-preview", headers=api["admin"]).json()
    assert any("your own account" in b for b in p["blockers"])


# ── Porick delete_user now removes files too ─────────────────────────────────

def test_porick_confirm_removes_files_and_logs(env):
    files = _seed_target(env)
    import telegram_admin as T
    reply = T._cmd_confirm_delete_user("target@example.com")
    assert reply.startswith("✅") and "files removed: 5" in reply
    assert not any(f.exists() for f in files.values())
    (chat_id, action, _summary), = _log_rows(env["path"])
    assert (chat_id, action) == ("porick", "admin_delete_user")
