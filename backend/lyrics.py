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

_LYRIC_SYSTEM_BASE = """You are an elite songwriter with the range of a Pulitzer Prize poet and the instincts of a hit-making producer. Write original, surprising, emotionally vivid song lyrics. Avoid clichés at all costs.

Output ONLY valid JSON with this exact shape:
{{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}}

Song structure to use: {structure}

Emotional angle: {mood} — let this feeling drive every line.

Rules:
- Never reproduce or imitate copyrighted song lyrics. Write entirely original work.
- Never use these overused phrases: "in the night", "feel the beat", "lose control", "dance floor", "let it go", "fire inside", "heart on fire", "rise up", "chase your dreams"
- Use unexpected metaphors, vivid imagery, and specific details instead of generic emotion
- Vary the song structure — not every song needs verse/chorus/verse/chorus. Try: spoken word intro, bridge breakdowns, pre-chorus hooks, double choruses, outros that evolve
- Match the vocabulary and tone precisely to the genre — blues lyrics sound nothing like K-pop, grime sounds nothing like classical
- For MC-style genres (grime, jungle, D&B, drill, niche) write in fast-paced bars with internal rhyme schemes
- For soul/blues write with raw emotional specificity — reference real places, real feelings, real moments
- Give the song a genuine narrative arc — something should change or be revealed by the end
- Surprise the listener with at least one lyric they wouldn't expect
- 200-400 words total.
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
        model="claude-haiku-4-5-20251001",
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


def store_custom_lyrics(user_id: str, brief: str, lyrics_text: str, db_path: pathlib.Path, song_title: str | None = None) -> dict:
    """Store user-supplied lyrics directly without calling Claude."""
    title = song_title or "Custom Song"
    conn = db._conn(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
            (user_id, brief or "Custom lyrics", lyrics_text, title),
        )
        lyric_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return {"lyric_id": lyric_id, "lyrics": lyrics_text, "title": title}
