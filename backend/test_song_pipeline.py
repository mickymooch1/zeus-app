"""
One-off pipeline smoke test.
Set these in your environment before running — do NOT hardcode values here:
  ANTHROPIC_API_KEY, APIFRAME_API_KEY, SONG_WEBHOOK_URL, SONG_STORAGE_PATH, SONG_PUBLIC_BASE_URL
"""
import os
import sys

# Fail fast if required keys are missing
for _key in ("ANTHROPIC_API_KEY", "APIFRAME_API_KEY", "SONG_WEBHOOK_URL"):
    if not os.environ.get(_key):
        print(f"ERROR: {_key} is not set. Aborting.")
        sys.exit(1)

import db
import lyrics as lyrics_mod
import songs as songs_mod
from song_genres import GENRE_PRESETS

db_path = db.get_db_path()
print(f"DB              : {db_path}")
print(f"SONG_WEBHOOK_URL: {os.environ['SONG_WEBHOOK_URL']}")
print(f"SONG_STORAGE_PATH: {os.environ.get('SONG_STORAGE_PATH', '/data/songs  (default)')}")

# ── Step 1: resolve admin user ────────────────────────────────────────────────
ADMIN_EMAIL = "dominic.rowle@yahoo.com"
user = db.get_user_by_email(db_path, ADMIN_EMAIL)
if user:
    user_id = user["id"]
    print(f"User found: {user_id} ({ADMIN_EMAIL})")
else:
    # Production account lives in Railway — use a stable placeholder for local runs
    user_id = "local-admin-dominic"
    print(f"User not in local DB — using placeholder id: {user_id}")

# ── Step 2: grant 10 song credits ─────────────────────────────────────────────
db.upsert_song_credits(db_path, user_id, balance=10, monthly_allowance=10)
credits = db.get_song_credits(db_path, user_id)
print(f"Credits after grant: balance={credits['balance']}  allowance={credits['monthly_allowance']}")

# ── Step 3: generate lyrics ───────────────────────────────────────────────────
print("\nCalling GenerateLyrics …")
result = lyrics_mod.generate_lyrics(
    user_id,
    "30-second jingle for a Manchester coffee shop, Friday vibes",
    db_path,
)
lyric_id = result["lyric_id"]
print(f"  Title   : {result['title']}")
print(f"  lyric_id: {lyric_id}")
print(f"  Lyrics  :\n{result['lyrics'][:300]}…")

# ── Step 4: submit song variant ───────────────────────────────────────────────
print("\nCalling GenerateSongVariant (pop) …")
variant = songs_mod.generate_song_variant(
    user_id=user_id,
    lyric_id=lyric_id,
    style_prompt=GENRE_PRESETS["pop"],
    genre_tag="pop",
    db_path=db_path,
)
print(f"  variant_id       : {variant['variant_id']}")
print(f"  status           : {variant['status']}")

# Print the task_id that Apiframe returned (stored on the row)
import sqlite3
conn = sqlite3.connect(str(db_path))
row = conn.execute(
    "SELECT provider_job_id, webhook_secret FROM song_variants WHERE id = ?",
    (variant["variant_id"],),
).fetchone()
conn.close()
print(f"  provider_job_id  : {row[0]}")
print(f"  webhook_secret   : {row[1][:12]}…")

credits_after = db.get_song_credits(db_path, user_id)
print(f"\nCredits remaining: {credits_after['balance']} (deducted 1)")

print("\nNow wait 60 seconds and check the database —")
print("  variants for lyric_id", lyric_id, "should flip to 'complete' with mp3_url populated.")
print("  Run: SELECT id, status, take_number, mp3_url FROM song_variants WHERE lyric_id =", lyric_id, ";")
