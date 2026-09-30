"""Full account deletion: database rows AND the user's files on the volume.

Built 2026-09-29 for the admin panel's "Delete account" button, and shared
with Porick's `delete_user EMAIL confirm`. The database side is NOT
reimplemented here — it is db.delete_user_account (one transaction, dynamic
table discovery, prove-clean-before-commit, refuses admins). This module adds
what that engine never did: removing the files that belonged to the account
(song MP3s, videos, portraits, memorial/song photos, story audio, avatar and
clip uploads), plus the admin-panel preview, the safety rails and the log.

File removal is deliberately conservative:
  * candidates come ONLY from this user's own rows (captured before the
    delete) — never a directory glob;
  * a candidate must resolve to a file directly inside one of the known
    per-user storage roots (the shared caches — language lessons, voice
    previews, Porick audio — are not roots and are never touched);
  * after the delete commits, a candidate still referenced by ANY remaining
    row (e.g. a remix clip reusing another user's media) is kept, not removed.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import sqlite3
from datetime import datetime, timezone

import db

_log = logging.getLogger("zeus.account_deletion")

# Subscription states in which Stripe is still billing (or about to). Deleting
# the account would NOT cancel the Stripe subscription, so these are refused —
# cancel in Stripe first.
ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing", "past_due"})

_STORES = ("songs", "avatars", "videos", "images", "stories", "clips")
_FILE_URL_RE = re.compile(r"/(?:api/)?files/(" + "|".join(_STORES) + r")/([A-Za-z0-9._-]+)")


class DeletionRefused(Exception):
    """The account must not be deleted through this path (reason in str())."""


def default_roots() -> dict[str, pathlib.Path]:
    """Per-user storage roots, matching the /files/<store> mounts in main.py."""
    return {
        "songs":   pathlib.Path(os.environ.get("SONG_STORAGE_PATH", "/data/songs")),
        "avatars": pathlib.Path("/data/avatars"),
        "videos":  pathlib.Path("/data/videos"),
        "images":  pathlib.Path("/data/images"),
        "stories": pathlib.Path("/data/stories"),
        "clips":   pathlib.Path(os.environ.get("CLIP_STORAGE_PATH", "/data/clips")),
    }


# ── file discovery ───────────────────────────────────────────────────────────

def _refs_in(value) -> set[tuple[str, str]]:
    if not isinstance(value, str) or "files/" not in value:
        return set()
    return {(m.group(1), m.group(2)) for m in _FILE_URL_RE.finditer(value)}


def collect_file_refs(preview: dict) -> set[tuple[str, str]]:
    """(store, filename) pairs belonging to the user in a db.preview_user_deletion
    result: every /files/<store>/<name> URL in any of their rows, plus the
    names the app derives from a song variant's id, plus photo filenames."""
    rows = [preview["user"]] if preview.get("user") else []
    for group in (preview.get("rows") or {}, preview.get("orphans") or {}):
        for table_rows in group.values():
            rows.extend(table_rows)

    refs: set[tuple[str, str]] = set()
    for row in rows:
        for value in row.values():
            refs |= _refs_in(value)

    for v in (preview.get("rows") or {}).get("song_variants", []):
        vid = v["id"]
        refs |= {("songs", f"{vid}.mp3"), ("videos", f"{vid}.mp4"), ("avatars", f"{vid}_portrait.jpg")}
    for p in (preview.get("orphans") or {}).get("song_variant_photos", []):
        refs.add(("songs", p["filename"]))
    return refs


def _resolve(roots: dict[str, pathlib.Path], store: str, name: str) -> pathlib.Path | None:
    """The file path for (store, name), only if it sits directly inside that root."""
    root = roots.get(store)
    if root is None or not name or name in (".", "..") or "/" in name or "\\" in name:
        return None
    try:
        root_r = root.resolve()
        path = (root / name).resolve()
    except (OSError, ValueError):
        return None
    return path if path.parent == root_r else None


def _still_referenced(db_path: pathlib.Path, candidates: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Candidates that some REMAINING row still points at — one pass over every
    text column in the database (plus bare photo filenames)."""
    if not candidates:
        return set()
    names = {name for _store, name in candidates}
    found: set[tuple[str, str]] = set()
    conn = sqlite3.connect(str(db_path))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")
                    if (r[2] or "").upper() in ("", "TEXT") or "CHAR" in (r[2] or "").upper()]
            if not cols:
                continue
            for row in conn.execute(f"SELECT {', '.join(cols)} FROM {t}"):
                for value in row:
                    if isinstance(value, str) and "files/" in value:
                        found |= {ref for ref in _refs_in(value) if ref in candidates}
        photo_names = sorted(names)
        for i in range(0, len(photo_names), 500):
            chunk = photo_names[i:i + 500]
            for (fn,) in conn.execute(
                f"SELECT filename FROM song_variant_photos WHERE filename IN ({','.join('?' * len(chunk))})", chunk
            ):
                if ("songs", fn) in candidates:
                    found.add(("songs", fn))
    except sqlite3.OperationalError:
        pass  # song_variant_photos absent in a stripped-down schema — nothing to add
    finally:
        conn.close()
    return found


def remove_files(db_path: pathlib.Path, refs: set[tuple[str, str]],
                 roots: dict[str, pathlib.Path] | None = None) -> dict:
    """Remove the user's files AFTER their rows are gone. Returns what happened
    to each candidate; a failure is reported, never swallowed."""
    roots = roots or default_roots()
    shared = _still_referenced(db_path, refs)
    report = {"removed": [], "missing": [], "shared": [], "failed": [], "bytes_freed": 0}
    for store, name in sorted(refs):
        label = f"{store}/{name}"
        if (store, name) in shared:
            report["shared"].append(label)
            continue
        path = _resolve(roots, store, name)
        if path is None or not path.is_file():
            report["missing"].append(label)
            continue
        try:
            size = path.stat().st_size
            path.unlink()
            report["removed"].append(label)
            report["bytes_freed"] += size
        except OSError as exc:
            report["failed"].append(f"{label}: {exc}")
    return report


def _existing_files(refs: set[tuple[str, str]], roots: dict[str, pathlib.Path]) -> tuple[int, int]:
    count = size = 0
    for store, name in refs:
        path = _resolve(roots, store, name)
        if path is not None and path.is_file():
            count += 1
            size += path.stat().st_size
    return count, size


# ── preview (admin panel) ────────────────────────────────────────────────────

def build_preview(db_path: pathlib.Path, user_id: str,
                  roots: dict[str, pathlib.Path] | None = None) -> dict | None:
    """Everything the confirmation dialog shows. Changes nothing. None if no
    such user. `blockers` make deletion impossible; `warnings` need an explicit
    "I understand" acknowledgement."""
    roots = roots or default_roots()
    target = db.get_user_by_id(db_path, user_id)
    if not target:
        return None

    blockers: list[str] = []
    if target.get("is_admin"):
        blockers.append("This is an admin account — admin accounts can't be deleted here.")
        preview = {"user": target, "rows": {}, "orphans": {}}
    else:
        preview = db.preview_user_deletion(db_path, target["email"])

    status = (target.get("subscription_status") or "").lower()
    if status in ACTIVE_SUBSCRIPTION_STATUSES:
        blockers.append(
            f"Subscription is {status} ({target.get('subscription_plan') or 'unknown plan'}). "
            "Cancel it in Stripe first — deleting the account would not stop the billing."
        )

    rows = preview["rows"]
    variants = rows.get("song_variants", [])
    ledger = rows.get("credit_ledger", [])
    stripe_ledger = [r for r in ledger if r.get("stripe_payment_id")]
    qr_count = sum(1 for v in variants if v.get("qr_generated"))
    memorial_pages = sum(1 for v in variants if v.get("occasion") == "memorial")
    credits = (rows.get("song_credits") or [{}])[0]

    warnings: list[str] = []
    if stripe_ledger:
        warnings.append(f"Has {len(stripe_ledger)} past Stripe purchase(s) in the credit ledger.")
    if qr_count:
        warnings.append(
            f"{qr_count} song(s) have a generated QR code — it may be printed or engraved "
            "somewhere and will stop working."
        )

    file_count, file_bytes = _existing_files(collect_file_refs(preview), roots)
    return {
        "user_id": target["id"],
        "email": target["email"],
        "name": target.get("name"),
        "created_at": target.get("created_at"),
        "is_admin": bool(target.get("is_admin")),
        "subscription_plan": target.get("subscription_plan") or "free",
        "subscription_status": target.get("subscription_status") or "free",
        "songs": len(variants),
        "song_credits": credits.get("balance", 0) or 0,
        "memorial_credits": target.get("memorial_credits_available", 0) or 0,
        "ledger_rows": len(ledger),
        "stripe_purchases": len(stripe_ledger),
        "memorial_pages": memorial_pages,
        "qr_codes": qr_count,
        "files": file_count,
        "file_bytes": file_bytes,
        "tables": {t: len(r) for t, r in {**rows, **preview["orphans"]}.items()},
        "blockers": blockers,
        "warnings": warnings,
    }


# ── delete ───────────────────────────────────────────────────────────────────

def delete_account_and_files(db_path: pathlib.Path, email: str,
                             roots: dict[str, pathlib.Path] | None = None) -> dict:
    """db.delete_user_account + file cleanup. Raises exactly what the engine
    raises (ValueError / db.AdminAccountProtectedError / RuntimeError) with
    nothing deleted — files are only touched after the rows are committed.
    Applies no rails of its own; callers decide (see delete_from_admin_panel)."""
    preview = db.preview_user_deletion(db_path, email)
    refs = collect_file_refs(preview) if preview.get("user") else set()
    result = db.delete_user_account(db_path, email)
    result["files"] = remove_files(db_path, refs, roots)
    return result


def delete_from_admin_panel(db_path: pathlib.Path, user_id: str, *, actor: dict,
                            confirm_email: str, acknowledge_warnings: bool,
                            roots: dict[str, pathlib.Path] | None = None) -> dict:
    """The admin panel's delete, with its rails. Raises DeletionRefused (nothing
    deleted) unless every check passes; logs every successful deletion."""
    if user_id == actor.get("id"):
        raise DeletionRefused("You can't delete your own account here.")
    preview = build_preview(db_path, user_id, roots)
    if preview is None:
        raise DeletionRefused("User not found.")
    if (confirm_email or "").strip().lower() != preview["email"].lower():
        raise DeletionRefused("The typed email doesn't match this account.")
    if preview["blockers"]:
        raise DeletionRefused(" ".join(preview["blockers"]))
    if preview["warnings"] and not acknowledge_warnings:
        raise DeletionRefused("This account has warnings — tick “I understand” to continue.")

    result = delete_account_and_files(db_path, preview["email"], roots)
    try:
        log_deletion(db_path, source=f"web:{actor.get('email')}", result=result,
                     acknowledged=preview["warnings"] if acknowledge_warnings else [])
        result["logged"] = True
    except Exception as exc:  # the delete already committed — report, don't pretend it failed
        _log.error("admin_delete_user: admin_action_log write failed for %s: %s", result["email"], exc)
        result["logged"] = False
    return result


def log_deletion(db_path: pathlib.Path, *, source: str, result: dict, acknowledged: list[str]) -> None:
    """One admin_action_log row per deletion: who, when, what was removed."""
    files = result.get("files") or {}
    summary = json.dumps({
        "email": result["email"],
        "user_id": result["user_id"],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "rows": result["deleted"],
        "files_removed": len(files.get("removed", [])),
        "bytes_freed": files.get("bytes_freed", 0),
        "files_missing": len(files.get("missing", [])),
        "files_shared_kept": files.get("shared", []),
        "files_failed": files.get("failed", []),
        "warnings_acknowledged": acknowledged,
    }, ensure_ascii=False)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS admin_action_log (
                            id       INTEGER PRIMARY KEY AUTOINCREMENT,
                            chat_id  TEXT NOT NULL,
                            action   TEXT NOT NULL,
                            summary  TEXT NOT NULL,
                            created_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        conn.execute("INSERT INTO admin_action_log (chat_id, action, summary) VALUES (?, ?, ?)",
                     (source, "admin_delete_user", summary))
        conn.commit()
    finally:
        conn.close()
