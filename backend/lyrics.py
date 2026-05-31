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
    "rockney":     "Write in authentic Cockney style — use Cockney rhyming slang, reference East End London life, pubs, markets, football, family. Cheerful singalong verses with a big catchy pub chorus everyone can join in with. Think traditional London street culture.",
}

_KIDS_SONG_SYSTEM = """You are a warm, playful children's songwriter. Write fun, age-appropriate lyrics that children aged 3-8 will love.

Output ONLY valid JSON with this exact shape:
{{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}}

Song structure to use: {structure}

Rules:
- Simple, clear vocabulary — words a young child can understand
- Short, rhythmic lines with strong rhymes and repetition
- Fun, bouncy, sing-along energy — children should be able to join in easily
- Include repeated phrases or a call-and-response element children can memorise
- Themes: animals, adventure, friendship, colours, counting, nature, silliness, magic
- Upbeat and positive — no scary, sad, or adult themes
- Maximum 150 words total — short enough to hold a child's attention
- No markdown, no commentary. JSON only."""

_KIDS_STORY_SYSTEM = """You are a warm, imaginative children's storyteller. Write a short enchanting children's story.

Output ONLY valid JSON with this exact shape:
{
  "title": "Story Title Here",
  "lyrics": "First paragraph...\\n\\nSecond paragraph...\\n\\nThird paragraph..."
}

Rules:
- Write 3 to 4 natural prose paragraphs — NO song sections, NO [Verse] or [Chorus] labels
- Clear story arc: beginning (introduce the character and setting), middle (a gentle adventure or challenge), end (a warm happy resolution)
- Simple, vivid vocabulary that a young child can easily picture
- 220 to 300 words total — short enough to hold a young child's attention
- Warm, gentle excitement throughout — children should want to lean in and listen
- Always end with comfort, warmth and a smile
- No scary, violent, or adult themes whatsoever
- No markdown, no section labels, no commentary. JSON only."""

_KIDS_STORY_MULTI_VOICE_SYSTEM = """You are a warm, imaginative children's storyteller. Write a short enchanting children's story using two distinct voices: a narrator and a main character.

Output ONLY valid JSON with this exact shape:
{
  "title": "Story Title Here",
  "lyrics": "[NARRATOR] Once upon a time...\\n[CHARACTER] Wow, it's magical!\\n[NARRATOR] The adventure began..."
}

Speaker tag rules:
- EVERY sentence or paragraph must begin with [NARRATOR] or [CHARACTER] — no untagged text whatsoever
- [NARRATOR] = narration, scene-setting, description, transitions
- [CHARACTER] = the main character speaking, exclaiming, or reacting out loud
- Aim for 8 to 12 total segments, roughly half narrator and half character
- Character lines should feel spontaneous and expressive

Story rules:
- Clear arc: beginning, middle, end — warm happy resolution
- Simple, vivid vocabulary a young child can picture
- 220 to 300 words total
- Always end with comfort, warmth and a smile
- No scary, violent, or adult themes
- No markdown, no labels outside the tags, no commentary. JSON only."""

_KIDS_STORY_TWO_VOICE_SYSTEM = """You are a warm, imaginative children's storyteller. Write a short enchanting children's story using two distinct voices: a narrator and a child hero.

Output ONLY valid JSON with this exact shape:
{
  "title": "Story Title Here",
  "lyrics": "[NARRATOR] Once upon a time in a sunny meadow...\\n[HERO] Oh wow, a rainbow bridge!\\n[NARRATOR] The little hero ran towards it..."
}

Speaker tag rules:
- EVERY sentence or paragraph must begin with [NARRATOR] or [HERO] — no untagged text whatsoever
- [NARRATOR] = narration, scene-setting, description, transitions
- [HERO] = the child hero speaking, exclaiming, or reacting out loud
- Aim for 8 to 12 total segments, roughly half narrator and half hero
- Hero lines should feel wide-eyed, curious and spontaneous

Story rules:
- Clear arc: beginning (introduce hero and setting), middle (gentle adventure or challenge), end (warm happy resolution)
- Simple, vivid vocabulary a young child can easily picture
- 220 to 300 words total
- Warm, gentle excitement — children should want to lean in and listen
- Always end with comfort, warmth and a smile
- No scary, violent, or adult themes whatsoever
- No markdown, no labels outside the [NARRATOR]/[HERO] tags, no commentary. JSON only."""

_KIDS_STORY_THREE_VOICE_SYSTEM = """You are a warm, imaginative children's storyteller. Write a short enchanting children's story using three distinct voices: a narrator, a child hero, and an other character (like a dragon, villain, or magical creature).

Output ONLY valid JSON with this exact shape:
{
  "title": "Story Title Here",
  "lyrics": "[NARRATOR] Deep in the enchanted forest...\\n[HERO] I'm not scared!\\n[CHARACTER] ROAR! Who dares enter my forest?\\n[NARRATOR] The little hero stood tall..."
}

Speaker tag rules:
- EVERY sentence or paragraph must begin with [NARRATOR], [HERO], or [CHARACTER] — no untagged text whatsoever
- [NARRATOR] = narration, scene-setting, description, transitions
- [HERO] = the child hero speaking, exclaiming, or reacting out loud
- [CHARACTER] = the other character (dragon, villain, magical creature etc.) speaking
- Aim for 10 to 14 total segments; roughly half narrator, a quarter hero, a quarter character
- [HERO] lines: wide-eyed, curious and brave
- [CHARACTER] lines: dramatic, distinctive and memorable — this voice should be unmistakably different

Story rules:
- Clear arc: beginning (introduce hero and other character), middle (encounter and gentle challenge), end (resolution — the characters may even become friends)
- Simple, vivid vocabulary a young child can easily picture
- 250 to 320 words total
- Warm, exciting energy — children should lean forward when the character speaks
- Always end with comfort, warmth and a smile
- No genuinely scary or violent themes — keep the other character fun, not frightening
- No markdown, no labels outside the three tags, no commentary. JSON only."""

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
- If no song concept is provided, invent a compelling original concept for this genre yourself — be creative and surprising, pick a specific story, character, or situation that nobody would expect
- 200-400 words total.
- No markdown, no commentary. JSON only."""


_EXPLICIT_ADDENDUM = (
    "\n\nExplicit content is enabled. You may use strong language, profanity and adult themes "
    "authentically where it fits the genre. For grime, drill, hip-hop and street genres use "
    "authentic street language including swearing where it adds authenticity. Don't force it "
    "— only use explicit language where it genuinely fits the song."
)


_KIDS_LANGUAGE_MAP = {
    # European
    'french':     'French',
    'spanish':    'Spanish',
    'german':     'German',
    'italian':    'Italian',
    'portuguese': 'Portuguese',
    'russian':    'Russian',
    'polish':     'Polish',
    'dutch':      'Dutch',
    'swedish':    'Swedish',
    'norwegian':  'Norwegian',
    'danish':     'Danish',
    'greek':      'Greek',
    'romanian':   'Romanian',
    'ukrainian':  'Ukrainian',
    'hungarian':  'Hungarian',
    'czech':      'Czech',
    # Asian
    'korean':     'Korean',
    'japanese':   'Japanese',
    'mandarin':   'Mandarin Chinese',
    'hindi':      'Hindi',
    'thai':       'Thai',
    'tagalog':    'Tagalog (Filipino)',
    'indonesian': 'Bahasa Indonesia',
    'vietnamese': 'Vietnamese',
    'arabic':     'Arabic',
    'turkish':    'Turkish',
    # African & Caribbean
    'swahili':    'Swahili',
    'yoruba':     'Yoruba',
    'amharic':    'Amharic',
    'zulu':       'Zulu',
    'haitian':    'Haitian Creole',
    # Americas
    'brazilian':  'Brazilian Portuguese',
}

# Regular (non-kids) accents that should produce lyrics in a non-English language.
# Claude Sonnet is used automatically when this map has a match.
_REGULAR_LANGUAGE_MAP = {
    # European
    'german':              'German',
    'italian':             'Italian',
    'portuguese':          'Portuguese',
    'russian':             'Russian',
    'polish':              'Polish',
    'dutch':               'Dutch',
    'swedish':             'Swedish',
    'norwegian':           'Norwegian',
    'danish':              'Danish',
    'greek':               'Greek',
    'romanian':            'Romanian',
    'ukrainian':           'Ukrainian',
    'hungarian':           'Hungarian',
    'czech':               'Czech',
    # Asian
    'korean':              'Korean',
    'japanese':            'Japanese',
    'mandarin':            'Mandarin Chinese',
    'hindi':               'Hindi',
    'thai':                'Thai',
    'tagalog':             'Tagalog (Filipino)',
    'indonesian':          'Bahasa Indonesia',
    'vietnamese':          'Vietnamese',
    'arabic':              'Arabic',
    'turkish':             'Turkish',
    # African & Caribbean
    'swahili':             'Swahili',
    'yoruba':              'Yoruba',
    'amharic':             'Amharic',
    'zulu':                'Zulu',
    'haitian creole':      'Haitian Creole',
    # Americas
    'brazilian portuguese': 'Brazilian Portuguese',
}


def generate_lyrics(user_id: str, brief: str, db_path: pathlib.Path, explicit: bool = False, instrumental: bool = False, song_title: str | None = None, genres: list[str] | None = None, genre_b: str | None = None, blend_ratio: int | None = None, kids_story: bool = False, kids_mode: str = 'song', accent: str | None = None, story_language: str | None = None, character_voice: str | None = None, child_voice: str | None = None) -> dict:
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

    if kids_story:
        model = "claude-sonnet-4-6"
        if kids_mode == 'story':
            kids_prompt = brief.strip() if brief.strip() else "Write a fun, magical adventure story for young children."
            if character_voice and child_voice:
                system = _KIDS_STORY_THREE_VOICE_SYSTEM   # [NARRATOR]/[CHILD]/[CHARACTER]
            elif child_voice:
                system = _KIDS_STORY_TWO_VOICE_SYSTEM     # [NARRATOR]/[CHILD]
            elif character_voice:
                system = _KIDS_STORY_MULTI_VOICE_SYSTEM   # [NARRATOR]/[CHARACTER] (legacy 2-voice)
            else:
                system = _KIDS_STORY_SYSTEM
            _story_lang = _KIDS_LANGUAGE_MAP.get((story_language or 'english').lower())
            if _story_lang and (story_language or 'english').lower() != 'english':
                kids_prompt += (
                    f"\n\nIMPORTANT: Write the story ENTIRELY in {_story_lang}. "
                    f"Use natural, child-friendly {_story_lang} vocabulary and phrasing throughout. "
                    "Do not include any English text."
                )
        else:  # song mode
            structure = random.choice([
                "[Verse 1], [Chorus], [Verse 2], [Chorus], [Outro]",
                "[Intro], [Verse 1], [Chorus], [Verse 2], [Chorus]",
                "[Verse 1], [Chorus], [Verse 2], [Chorus], [Bridge], [Chorus]",
            ])
            system = _KIDS_SONG_SYSTEM.format(structure=structure)
            kids_prompt = brief.strip() if brief.strip() else (
                f"Genre: {', '.join(genres)}. " if genres else ""
            ) + "Write a fun, catchy children's song."
        logger.info(
            "generate_lyrics: kids_%s mode — calling %s user=%s brief=%r",
            kids_mode, model, user_id, brief[:200],
        )
        try:
            response = client.messages.create(
                model=model,
                max_tokens=800,
                temperature=1.0,
                system=system,
                messages=[{"role": "user", "content": kids_prompt}],
            )
        except Exception:
            logger.exception("generate_lyrics: kids_%s %s API call failed — user=%s", kids_mode, model, user_id)
            raise
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("generate_lyrics: kids_story JSON parse failed — raw=%r", raw[:500])
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
        return {"lyric_id": lyric_id, "lyrics": parsed["lyrics"], "title": final_title}

    structure = random.choice(_SONG_STRUCTURES)
    mood = random.choice(_MOODS)
    theme = random.choice(_THEMES)
    system = _LYRIC_SYSTEM_BASE.format(structure=structure, mood=mood)
    if explicit:
        system += _EXPLICIT_ADDENDUM

    # DJ-transition structure for genre blend songs
    fusion_prefix = ""
    dj_structure_override = None
    if genre_b and genres:
        genre_a = genres[0]
        dj_structure_override = (
            f"[Intro - {genre_a} style]\n"
            f"[Verse 1 - full {genre_a} energy]\n"
            f"[Transition - mixing in {genre_b}]\n"
            f"[Chorus - {genre_b} takes over]\n"
            f"[Verse 2 - back to {genre_a}]\n"
            f"[Bridge - genres collide]\n"
            f"[Outro - {genre_b} finish]"
        )
        fusion_prefix = (
            f"Write each section in a COMPLETELY DIFFERENT genre — "
            f"verse 1 must sound like pure {genre_a}, "
            f"chorus must sound like pure {genre_b}. "
            f"Do NOT mix them — SWITCH between them. "
            f"Like a DJ playing one track then cutting to another. "
            f"Verse sections: pure {genre_a} vocabulary, flow, slang and energy. "
            f"Chorus and bridge sections: pure {genre_b} vocabulary, flow, slang and energy. "
            "Hard cuts between sections — no crossfading, no blending.\n\n"
        )

    # Override structure when doing a DJ transition
    if dj_structure_override:
        structure = dj_structure_override

    # Build enriched user message with randomised creative directives
    if brief.strip():
        user_message = fusion_prefix + brief
    else:
        genre_hint = f"Genre: {', '.join(genres)}. " if genres else ""
        if genre_b:
            genre_hint = f"Genre mix: {genres[0]} × {genre_b} DJ transition. "
        user_message = fusion_prefix + f"{genre_hint}No concept specified — invent a compelling original song concept yourself."
    user_message += (
        f"\n\nTheme: {theme}. Song structure: {structure}. Mood: {mood}. "
        "Make this song completely unique and unlike anything generated before."
    )
    all_genres = (genres or []) + ([genre_b] if genre_b else [])
    if all_genres:
        vocab_lines = [
            f"Use authentic {g} vocabulary and slang: {GENRE_VOCABULARY[g]}"
            for g in all_genres
            if g in GENRE_VOCABULARY
        ]
        if vocab_lines:
            user_message += "\n" + " | ".join(vocab_lines)

    _lyric_language = _REGULAR_LANGUAGE_MAP.get((accent or '').lower())
    if _lyric_language:
        user_message += (
            f"\n\nIMPORTANT: Write the lyrics ENTIRELY in {_lyric_language} — not English. "
            f"Use authentic {_lyric_language} script, vocabulary and natural phrasing throughout. "
            f"Write every line in the native script of {_lyric_language} — no romanisation, no transliteration, no English."
        )
    model = "claude-sonnet-4-6" if (genre_b or _lyric_language) else "claude-haiku-4-5-20251001"
    logger.info(
        "generate_lyrics: calling %s — user=%s explicit=%s genre_b=%r blend_ratio=%r theme=%r mood=%r lyric_language=%r brief=%r",
        model, user_id, explicit, genre_b, blend_ratio, theme, mood, _lyric_language, brief[:200],
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=1.0,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        logger.exception("generate_lyrics: %s API call failed — user=%s brief=%r", model, user_id, brief[:200])
        raise

    raw = response.content[0].text.strip()
    logger.info("generate_lyrics: %s response received, length=%d, stop_reason=%s", model, len(raw), response.stop_reason)
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
