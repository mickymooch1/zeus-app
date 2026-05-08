import json
import pathlib

from anthropic import Anthropic

import db

LYRIC_SYSTEM_PROMPT = """You are a professional songwriter. Generate ORIGINAL song lyrics based on the user's brief.

Output ONLY valid JSON with this exact shape:
{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}

Use these structural tags exactly: [Verse 1], [Chorus], [Verse 2], [Bridge], [Outro].

Hard rules:
- Never reproduce or imitate copyrighted song lyrics. Do not write "in the style of [named artist]" — write original work.
- 3-4 verses + chorus, 200-400 words total.
- No markdown, no commentary. JSON only."""


def generate_lyrics(user_id: str, brief: str, db_path: pathlib.Path) -> dict:
    client = Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=LYRIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": brief}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    conn = db._conn(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
            (user_id, brief, parsed["lyrics"], parsed["title"]),
        )
        lyric_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {
        "lyric_id": lyric_id,
        "lyrics": parsed["lyrics"],
        "title": parsed["title"],
    }
