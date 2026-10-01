"""One-off clean-up of song MP3 metadata already on the volume (2026-10-01).

New songs are retagged as they are saved (audio_tags.retag_song_file). This
fixes the files saved before that existed, in owner-approved stages, driven
from Porick (telegram_admin.py, `mp3tags …`):

  dryrun        — changes nothing: how many files would change, how many carry
                  the provider's mark, bytes to back up vs free disk, examples
  test N        — back up N files (provider-marked first), retag them, and show
                  before/after tags and proof the audio is byte-identical
  backup        — copy every file that would change into the backup folder
  run all confirm — retag everything; refuses unless every file is backed up
  restore IDS   — copy files back from the backup

Safety:
  * a file is only ever retagged after its backup exists and its sha256
    matches the live file (re-backed-up if the file changed since);
  * after retagging, the audio payload hash must be unchanged and the tags must
    be exactly ours, otherwise the file is restored from backup immediately;
  * idempotent — already-clean files are skipped, re-running is a no-op;
  * backups are never deleted by this module.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import shutil
import threading
from datetime import datetime, timezone

import audio_tags

log = logging.getLogger("zeus.mp3_retag")

SPACE_MARGIN = 500 * 1024 * 1024        # keep at least 500 MB free after a backup
_RUN_LOCK = threading.Lock()             # one backup/run at a time


def storage_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("SONG_STORAGE_PATH", "/data/songs"))


def backup_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("MP3_BACKUP_DIR") or (storage_dir().parent / "backups" / "mp3-retag"))


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def plan(db_path) -> list[dict]:
    """Every completed song whose MP3 exists, with what its tags are now."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        ids = [r[0] for r in conn.execute("SELECT id FROM song_variants WHERE status = 'complete' ORDER BY id")]
    finally:
        conn.close()
    items = []
    for vid in ids:
        path = storage_dir() / f"{vid}.mp3"
        if not path.is_file():
            continue
        title = audio_tags.song_title(db_path, vid)
        tags = audio_tags.describe_tags(path)
        items.append({
            "variant_id": vid, "path": path, "title": title, "tags": tags,
            "provider_mark": any("suno" in t.lower() for t in tags),
            "clean": sorted(tags) == audio_tags.wanted_tags(title),
            "size": path.stat().st_size,
        })
    return items


def _backup_path(vid) -> pathlib.Path:
    return backup_dir() / f"{vid}.mp3"


def _backed_up(item) -> bool:
    b = _backup_path(item["variant_id"])
    return b.is_file() and _sha256(b) == _sha256(item["path"])


def summary(items) -> dict:
    todo = [i for i in items if not i["clean"]]
    need = [i for i in todo if not _backup_path(i["variant_id"]).is_file()]
    bdir = backup_dir()
    probe = bdir if bdir.exists() else storage_dir()
    free = shutil.disk_usage(probe).free
    return {
        "files": len(items),
        "to_change": len(todo),
        "provider_marked": sum(1 for i in items if i["provider_mark"]),
        "already_clean": len(items) - len(todo),
        "backed_up": len(todo) - len(need),
        "bytes_to_back_up": sum(i["size"] for i in need),
        "free_bytes": free,
        "enough_space": sum(i["size"] for i in need) + SPACE_MARGIN <= free,
        "backup_dir": str(bdir),
    }


def backup(items) -> dict:
    """Copy each not-yet-clean file into the backup folder (verified)."""
    todo = [i for i in items if not i["clean"]]
    s = summary(items)
    if not s["enough_space"]:
        raise RuntimeError(
            f"not enough disk space: need {s['bytes_to_back_up'] // 2**20} MB + 500 MB margin, "
            f"free {s['free_bytes'] // 2**20} MB — nothing was copied")
    bdir = backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    with open(bdir / "manifest.jsonl", "a", encoding="utf-8") as manifest:
        for item in todo:
            dest = _backup_path(item["variant_id"])
            if dest.is_file() and _sha256(dest) == _sha256(item["path"]):
                skipped += 1
                continue
            tmp = dest.with_suffix(".mp3.part")
            shutil.copy2(item["path"], tmp)
            if _sha256(tmp) != _sha256(item["path"]):
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"backup verify failed for {item['variant_id']} — stopped")
            os.replace(tmp, dest)
            manifest.write(json.dumps({
                "variant_id": item["variant_id"], "sha256": _sha256(dest), "size": item["size"],
                "tags_before": item["tags"], "backed_up_at": datetime.now(timezone.utc).isoformat(),
            }) + "\n")
            copied += 1
    return {"copied": copied, "already_backed_up": skipped}


def apply(items) -> dict:
    """Retag files that are backed up; verify; restore any that fail."""
    done, skipped_clean, not_backed_up, restored = [], 0, [], []
    for item in items:
        if item["clean"]:
            skipped_clean += 1
            continue
        if not _backed_up(item):
            not_backed_up.append(item["variant_id"])
            continue
        before_audio = audio_tags.audio_digest(item["path"])
        try:
            audio_tags.retag_mp3(item["path"], item["title"])
            ok = (audio_tags.audio_digest(item["path"]) == before_audio
                  and audio_tags.is_clean(item["path"], item["title"]))
        except Exception:
            log.exception("mp3_retag: retag failed variant_id=%s", item["variant_id"])
            ok = False
        if not ok:
            shutil.copy2(_backup_path(item["variant_id"]), item["path"])
            restored.append(item["variant_id"])
            continue
        done.append({"variant_id": item["variant_id"], "title": item["title"],
                     "before": item["tags"], "after": audio_tags.describe_tags(item["path"]),
                     "audio_unchanged": True})
    return {"retagged": done, "skipped_clean": skipped_clean,
            "not_backed_up": not_backed_up, "restored_after_failed_check": restored}


def restore(variant_ids) -> dict:
    back, missing = [], []
    for vid in variant_ids:
        src = _backup_path(vid)
        if not src.is_file():
            missing.append(vid)
            continue
        shutil.copy2(src, storage_dir() / f"{vid}.mp3")
        back.append(vid)
    return {"restored": back, "no_backup": missing}


def pick_test(items, n: int) -> list[dict]:
    todo = [i for i in items if not i["clean"]]
    marked = [i for i in todo if i["provider_mark"]]
    rest = [i for i in todo if not i["provider_mark"]]
    return (marked + rest)[:n]


def run_locked(fn, *args):
    """Run fn under the module lock; raises RuntimeError if a job is running."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("another mp3tags backup/run is already in progress")
    try:
        return fn(*args)
    finally:
        _RUN_LOCK.release()
