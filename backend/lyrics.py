import json
import pathlib
import random

from anthropic import Anthropic

import db

_SONG_STRUCTURES = [
    "[Verse 1], [Chorus], [Verse 2], [Chorus], [Bridge], [Outro]",
    "[Intro], [Verse 1], [Chorus], [Verse 2], [Chorus], [Outro]",
    "[Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Pre-Chorus], [Chorus], [Bridge], [Outro]",
    "[Verse 1], [Verse 2], [Bridge], [Chorus], [Outro]",
    "[Intro], [Verse 1], [Chorus], [Verse 2], [Bridge], [Chorus], [Outro]",
]

_MOODS = ["uplifting", "melancholic", "aggressive", "romantic", "nostalgic", "euphoric", "defiant", "playful"]

_LYRIC_SYSTEM_BASE = """You are a professional songwriter. Generate ORIGINAL song lyrics based on the user's brief.

Output ONLY valid JSON with this exact shape:
{{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}}

Song structure to use: {structure}

Emotional angle: {mood} — let this feeling drive every line.

Hard rules:
- Never reproduce or imitate copyrighted song lyrics. Do not write "in the style of [named artist]" — write original work.
- 200-400 words total.
- Make this song unique and different from typical songs in this genre. Surprise the listener.
- No markdown, no commentary. JSON only."""


_EXPLICIT_ADDENDUM = (
    "\n\nThis is an explicit track. Include strong language, profanity, and adult themes "
    "authentically. Do not self-censor — write the lyrics as a real explicit song would be written."
)


def generate_lyrics(user_id: str, brief: str, db_path: pathlib.Path, explicit: bool = False, instrumental: bool = False, song_title: str | None = None) -> dict:
    if instrumental:
        title = song_title or "Instrumental"
        conn = db._conn(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
                (user_id, brief, "[Instrumental]", title),
            )
            lyric_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        return {"lyric_id": lyric_id, "lyrics": "[Instrumental]", "title": title}

    client = Anthropic()

    structure = random.choice(_SONG_STRUCTURES)
    mood = random.choice(_MOODS)
    system = _LYRIC_SYSTEM_BASE.format(structure=structure, mood=mood)
    if explicit:
        system += _EXPLICIT_ADDENDUM

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=1.0,
        system=system,
        messages=[{"role": "user", "content": brief}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    final_title = song_title or parsed["title"]

    conn = db._conn(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
            (user_id, brief, parsed["lyrics"], final_title),
        )
        lyric_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {
        "lyric_id": lyric_id,
        "lyrics": parsed["lyrics"],
        "title": final_title,
    }
