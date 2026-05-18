import json
import logging
import pathlib
import random

from anthropic import Anthropic

import db

logger = logging.getLogger("zeus.lyrics")

_SONG_STRUCTURES = [
    "[Verse 1], [Chorus], [Verse 2], [Chorus], [Bridge], [Outro]",
    "[Intro], [Verse 1], [Chorus], [Verse 2], [Chorus], [Outro]",
    "[Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Pre-Chorus], [Chorus], [Bridge], [Outro]",
    "[Verse 1], [Verse 2], [Bridge], [Chorus], [Outro]",
    "[Intro], [Verse 1], [Chorus], [Verse 2], [Bridge], [Chorus], [Outro]",
    "verse-chorus-verse-chorus-bridge-chorus",
    "intro-verse-pre-chorus-chorus-verse-chorus-outro",
    "verse-verse-chorus-verse-chorus-bridge-chorus",
    "hook-verse-hook-verse-hook-bridge-hook",
    "spoken intro-verse-chorus-verse-chorus-outro",
]

_MOODS = [
    "uplifting", "melancholic", "aggressive", "romantic", "nostalgic", "euphoric", "defiant", "playful",
    "dark and gritty", "euphoric and uplifting", "melancholic and reflective",
    "aggressive and intense", "smooth and sensual", "raw and emotional",
    "energetic and hype", "calm and introspective", "bittersweet",
]

_THEMES = [
    "redemption", "betrayal", "nostalgia", "ambition", "heartbreak",
    "freedom", "struggle", "celebration", "loneliness", "revenge",
    "hope", "loss", "success", "street life", "love found", "love lost",
    "identity", "home", "money", "loyalty", "family", "the come up",
]

GENRE_VOCABULARY: dict[str, str] = {
    "grime":       "mandem, road, ends, bare, peng, wasteman, dutty, link, P's",
    "afrobeats":   "omo, wahala, jollof, Lagos, naija, vibez, soro soke",
    "reggae":      "Jah, Babylon, irie, riddim, roots, natty, Zion",
    "soul":        "testify, church, gospel, amen, spirit, move me, feel it",
    "hiphop":      "hustle, grind, stack, flex, drip, plug, bag, real talk",
    "jungle":      "rewind, selector, massive, jungle fever, dark and lovely",
    "niche":       "proper job, mint, banging, Sheffield, lass, lad, mental",
    "drumandbass": "amen break, rewind, selector, massive, liquid, dark, rollers",
    "ukdrill":     "opps, trap, 150, sliders, smoke, woadie, on site, bits",
    "afroswing":   "gyallis, ting, wavey, plug, buss, wul, oshun, agege",
    "amapiano":    "yano, log drum, piano, South Africa, umlando, siyathandana",
    "rastadub":    "Jah Rastafari, Babylon system, roots and culture, fire burn, ital",
    "bluessoul":   "low down dirty shame, crossroads, testify, mojo, 12-bar",
    "rnb":         "vibe, situationship, soft life, real love, body, drip, finesse",
    "ukgarage":    "rewind, two-step, selector, garage ting, bare, mandem, swerve",
    "bassline":    "banger, rave, proper, dark, filthy, Sheffield, bounce, wobble",
}

_LYRIC_SYSTEM_BASE = """You are the most creative songwriter alive. Your job is to write lyrics that genuinely surprise people.

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
- Every song must have a unique concept or angle — never write a generic love song or party anthem
- Open with a line that immediately grabs attention — shocking, poetic, funny, or deeply specific
- Use vivid specific details — real places, textures, smells, moments — not vague emotions
- Every chorus must have one line that's so good it gets stuck in your head immediately
- Vary song structures constantly — try spoken word sections, double time flows, call and response, narrative verses
- Match vocabulary precisely to the genre and culture — grime bars sound nothing like country ballads
- For urban genres write with authentic street vocabulary and cultural references
- For soul/blues write with raw emotional truth and storytelling
- Include at least one unexpected twist, metaphor or image that nobody would predict
- The song should feel like it could only have been written for THIS genre, NOT generic
- Never use filler lines — every line must earn its place
- Aim to write something that could genuinely be a hit
- Give the song a genuine narrative arc — something should change or be revealed by the end
- 200-400 words total.
- No markdown, no commentary. JSON only."""


_EXPLICIT_ADDENDUM = (
    "\n\nExplicit content is enabled. You may use strong language, profanity and adult themes "
    "authentically where it fits the genre. For grime, drill, hip-hop and street genres use "
    "authentic street language including swearing where it adds authenticity. Don't force it "
    "— only use explicit language where it genuinely fits the song."
)


def generate_lyrics(user_id: str, brief: str, db_path: pathlib.Path, explicit: bool = False, instrumental: bool = False, song_title: str | None = None, genres: list[str] | None = None) -> dict:
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
    theme = random.choice(_THEMES)
    system = _LYRIC_SYSTEM_BASE.format(structure=structure, mood=mood)
    if explicit:
        system += _EXPLICIT_ADDENDUM

    # Build enriched user message with randomised creative directives
    user_message = brief
    user_message += (
        f"\n\nTheme: {theme}. Song structure: {structure}. Mood: {mood}. "
        "Make this song completely unique and unlike anything generated before."
    )
    if genres:
        vocab_lines = [
            f"Use authentic {g} vocabulary and slang: {GENRE_VOCABULARY[g]}"
            for g in genres
            if g in GENRE_VOCABULARY
        ]
        if vocab_lines:
            user_message += "\n" + " | ".join(vocab_lines)

    logger.info(
        "generate_lyrics: calling Haiku — user=%s explicit=%s theme=%r mood=%r brief=%r",
        user_id, explicit, theme, mood, brief[:200],
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            temperature=1.0,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        logger.exception("generate_lyrics: Haiku API call failed — user=%s brief=%r", user_id, brief[:200])
        raise

    raw = response.content[0].text.strip()
    logger.info("generate_lyrics: Haiku response received, length=%d, stop_reason=%s", len(raw), response.stop_reason)
    logger.debug("generate_lyrics: raw response: %s", raw[:500])

    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("generate_lyrics: JSON parse failed — raw=%r", raw[:500])
        raise

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
