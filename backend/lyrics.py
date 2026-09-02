import json
import logging
import pathlib
import random
import re

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

# Genre-specific mood/theme directives appended to the user prompt — overrides the random mood
# for genres where the required emotional register is non-negotiable.
GENRE_MOOD_DIRECTIVES: dict[str, str] = {
    "christmas":  "\n\nIMPORTANT MOOD: Write a joyful, warm, cheerful Christmas song — uplifting and festive, NEVER sad or dark. Themes: joy, family, snow, giving, togetherness, celebration, carol singing. Major key feel, upbeat and merry. Every line should feel warm and positive.",
    "gospel":     "\n\nIMPORTANT MOOD: Write with powerful uplifting gospel spirit — testifying, praising, hopeful, joyful. Church energy, call and response. Never dark or despairing.",
    "meditation": "\n\nIMPORTANT MOOD: Write peaceful, deeply calming, reflective lyrics — serene and tranquil. No aggression, no darkness, no urgency. Themes: stillness, breath, inner peace, letting go.",
    # Scat is sung in vocables, not words. Without this the lyric writer produces
    # ordinary lyrics and Suno sings them straight, which is vocal jazz, not scat.
    "scat":       "\n\nIMPORTANT — THIS IS SCAT SINGING: the vocal is WORDLESS improvisation, not lyrics. Write almost entirely in scat vocables — doo, bop, shoo, be, dee, wah, ba, dat, skee, doo-bee-doo-bop, shoo-be-doo-wah, ba-da-ba-dat — phrased like an improvising horn solo, with rhythmic swing and playful runs. A short repeated real-word hook (a few words at most) is fine as an anchor, but the verses must be vocables. Vary the syllables constantly rather than repeating one pattern; use longer flowing runs in the solo sections and punchier phrases over the swing hits.",
    "ukstreetsoul": "\n\nIMPORTANT — BRITISH CONTEXT: This is UK street soul, a distinctly British genre. Set the song in the UK (London or Manchester). Write with British cultural references throughout: pounds not dollars, British place names and slang, British spelling, UK urban life. Intimate, melancholic, late-night emotional storytelling. NEVER use American settings, references or vocabulary.",
}

GENRE_VOCABULARY: dict[str, str] = {
    "grime":       "mandem, road, ends, bare, peng, wasteman, dutty, link, P's",
    "afrobeats":   "omo, wahala, jollof, Lagos, naija, vibez, soro soke",
    "reggae":      "Jah, Babylon, irie, riddim, roots, natty, Zion",
    "soul":        "testify, church, gospel, amen, spirit, move me, feel it",
    "hiphop":      "hustle, grind, stack, flex, drip, plug, bag, real talk",
    "jungle":      "rewind, selector, massive, jungle fever, dark and lovely",
    # No city names here — this list is injected verbatim into the lyric prompt
    # as "Use authentic niche vocabulary and slang: ...", so any place name in it
    # is a direct instruction to Claude to sing that place name. The Yorkshire
    # dialect words carry the regional flavour without naming anywhere.
    "niche":       "proper job, mint, banging, lass, lad, mental, belter, sound",
    "drumandbass": "amen break, rewind, selector, massive, liquid, dark, rollers",
    "ukdrill":     "opps, trap, 150, sliders, smoke, woadie, on site, bits",
    "afroswing":   "gyallis, ting, wavey, plug, buss, wul, oshun, agege",
    "amapiano":    "yano, log drum, piano, South Africa, umlando, siyathandana",
    "rastadub":    "Jah Rastafari, Babylon system, roots and culture, fire burn, ital",
    "bluessoul":   "low down dirty shame, crossroads, testify, mojo, 12-bar",
    "rnb":         "vibe, situationship, soft life, real love, body, drip, finesse",
    "ukgarage":    "rewind, two-step, selector, garage ting, bare, mandem, swerve",
    "bassline":    "banger, rave, proper, dark, filthy, bounce, wobble, skanking",
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

_ROAST_SYSTEM = """You are the sharpest, funniest comedy songwriter alive — like a best man speech crossed with a roast. Your job is to write genuinely funny, warm, affectionate songs that take the mick out of someone.

Output ONLY valid JSON with this exact shape:
{{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}}

Song structure to use: {structure}

Rules:
- Write a genuinely funny, playful song — the kind of banter you'd hear between close mates
- Make it cheeky and affectionate, NOT cruel, nasty, or discriminatory
- Never include anything genuinely hurtful, discriminatory, racist, sexist, or harmful
- Use specific details from what you've been told about the person — generic jokes are lazy
- Include at least one killer line that will make everyone in the room howl
- The chorus should be a memorable punchline or catchphrase everyone will remember
- Think best man speech energy — roasting with love, embarrassing but affectionate
- Use playful exaggeration, gentle mockery of habits and quirks, funny observations
- The song should make the subject laugh while being slightly embarrassed
- 180-300 words total
- No markdown, no commentary. JSON only."""

_ROAST_VIBE_MODIFIERS: dict[str, str] = {
    "gentle":   "Tone: gentle friendly banter — warm and affectionate teasing between close mates. Light-hearted and kind. The kind of thing you'd say straight to their face with a grin.",
    "roast":    "Tone: proper roast — bold, cheeky, really going for it, pulling no punches on the funny stuff. More savage but still affectionate. Classic comedy roast energy.",
    "birthday": "Tone: classic birthday piss-take — embarrassing stories, teasing about their age, legendary moments everyone remembers. Celebratory but totally taking the mick. Big crowd singalong energy.",
    "staghen":  "Tone: stag/hen do banter — raucous, celebratory, sharing the most embarrassing stories to send them off in style. Big group energy, everyone's in on it, celebrating the end of their freedom.",
}

_ROAST_EXPLICIT_ADDENDUM = """
Explicit mode is ON — you can use swearing and adult language for comedic effect.
Make it a proper savage roast with cheeky swearing like a real best man's speech or a comedy roast night.
Swearing is fine for comedic emphasis (bloody, piss-take, shit, bastard, bloody hell, sod off, etc).
Use comedic swearing for a savage roast but NEVER use racial slurs, hate speech, or genuinely discriminatory language. Keep it cheeky banter, not bigotry.
Still keep it playful banter between mates — funny not genuinely cruel.
"""

_ROAST_CLEAN_ADDENDUM = """
Keep it clean — no swearing. Family-friendly banter and jokes.
Use comedic roast humour without any profanity. Still cheeky and funny, just clean.
NEVER use racial slurs, hate speech, or genuinely discriminatory language.
"""

_ROAST_EXPLICIT_SYSTEM = """You are the sharpest, funniest comedy songwriter alive — like a savage best man speech crossed with a comedy roast night. Your job is to write genuinely funny, sweary songs that take the absolute piss out of someone with love.

Explicit mode is ON. The user has specifically enabled adult language — you MUST use proper swearing for comedic effect.
Use words like: shit, fuck, bastard, twat, dickhead, tosser, bellend, piss-take, bollocks — for comedic emphasis.
Write like a genuine comedy roast: brutal, funny, sweary banter between close mates. The kind of speech that gets gasps and laughing at the same time.
Keep it funny not genuinely cruel. NEVER use racial slurs, hate speech, or discriminatory language ever.

Output ONLY valid JSON with this exact shape:
{{
  "title": "Song Title Here",
  "lyrics": "[Verse 1]\\nLine one...\\n[Chorus]\\nLine one..."
}}

Song structure to use: {structure}

Rules:
- USE actual swear words — do not censor them with asterisks or replace with mild alternatives
- Write a genuinely savage, funny roast — the kind of banter you'd hear at a comedy roast night
- Make it cheeky and affectionate, NOT cruel, nasty, or discriminatory
- Never use racial slurs, hate speech, or anything genuinely discriminatory
- Use specific details from what you've been told about the person — generic jokes are lazy
- Include at least one killer sweary punchline that will make everyone howl
- The chorus should be a memorable, quotable roast line — probably sweary
- Think best man speech energy — roasting with love, embarrassing but hilarious
- 180-300 words total
- No markdown, no commentary. JSON only."""

# Racial slur filter — strips slurs before lyrics reach Suno or the DB.
# Pattern uses word boundaries to avoid false positives on unrelated words.
_SLUR_PATTERN = re.compile(
    r'\b('
    r'n[i1!][g9][g9][ae3]r[s]?|n[i1!][g9][g9][ae3]|n[i1!][g9][g9][ae3]r|'
    r'f[a@]g[s]?|f[a@]gg[o0]t[s]?|'
    r'ch[i1][nk][k]?[s]?|'
    r'sp[i1][ck][k]?[s]?|'
    r'k[i1]k[e3][s]?|'
    r'w[e3]tb[a@]ck[s]?|'
    r'tr[a@]nn[yi1][e3]?[s]?|'
    r'r[e3]t[a@]rd[s]?|'
    r'c[o0][o0]n[s]?|'
    r'g[o0][o0]k[s]?|'
    r'cr[a@]ck[e3]r[s]?|'
    r'j[i1]g[a@]b[o0][o0][s]?|'
    r'p[a@]ki[s]?|'
    r'b[e3][a@]n[e3]r[s]?|'
    r's[a@]mb[o0][s]?|'
    r'c[a@]r[a@]b[o0][o0][s]?'
    r')',
    re.IGNORECASE,
)


def _strip_slurs(text: str) -> str:
    """Replace any racial slurs in generated lyrics with ****."""
    return _SLUR_PATTERN.sub('****', text)


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


_SECTION_TAG_LINE_RE = re.compile(r'^\s*\[[^\]]*\]\s*$')
_LEADING_TAG_RE = re.compile(r'^\[[^\]]*\]\s*')


def _extract_hook(lyrics_text: str, max_lines: int = 2) -> list[str]:
    """Pull a short hook (<= max_lines) out of a full lyric sheet.

    Prefers the lines under a [Chorus]/[Hook] section; falls back to the first
    content lines anywhere. Section-tag-only lines are skipped.
    """
    lines = [l.strip() for l in (lyrics_text or "").splitlines()]

    def _content_lines(seq: list[str]) -> list[str]:
        out: list[str] = []
        for l in seq:
            if not l or _SECTION_TAG_LINE_RE.match(l):
                continue
            l = _LEADING_TAG_RE.sub('', l).strip()  # drop inline "[Chorus] words"
            if l:
                out.append(l)
            if len(out) >= max_lines:
                break
        return out

    # 1) Prefer a chorus/hook section.
    collecting = False
    chorus_seq: list[str] = []
    for l in lines:
        m = re.match(r'^\[([^\]]*)\]', l)
        if m:
            tag = m.group(1).lower()
            if 'chorus' in tag or 'hook' in tag:
                collecting = True
            elif collecting:
                break  # next section ends the hook
            continue
        if collecting and l:
            chorus_seq.append(l)
    hook = _content_lines(chorus_seq)
    if hook:
        return hook[:max_lines]

    # 2) Fallback: first content lines anywhere.
    return _content_lines(lines)[:max_lines]


# Genre-aware instrumental scaffolding for intermittent-vocals mode. Each genre
# gets section tags matching its natural energy and arrangement (jungle → amen
# breaks, deep house → grooves/breakdowns, tech house → drops/builds). The hook
# appears THREE times and sparse ad-libs ("oohs", "yeah, uh, come on") sit under
# the instrumental sections — enough vocal content spread across the track that
# Suno renders a full 2.5-3 minutes instead of giving up and cutting it short
# (~30s) on near-empty instrumental tags. Still mostly instrumental — just not so
# sparse that the renderer bails. {hook} is replaced with the extracted hook lines.
INTERMITTENT_STRUCTURES = {
    'bassline': '[Intro - Instrumental]\n[Build]\n[Drop - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Instrumental break]\n(oohs and ahs)\n[Build]\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)\n[Extended outro - Instrumental]',
    'jungle': '[Intro - Instrumental]\n[Amen break - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Jungle break]\n(oohs and ahs)\n[Hook]\n{hook}\n[/Hook]\n[Reese bass drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)',
    'techhouse': '[Intro - Instrumental]\n[Groove - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Breakdown - Instrumental]\n(oohs and ahs)\n[Build - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Extended outro - Instrumental]\n(sparse ad-libs fading)',
    'house': '[Intro - Instrumental]\n[Verse - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Break - Instrumental]\n(oohs and ahs)\n[Build - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)',
    'deephouse': '[Intro - Instrumental]\n[Groove - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Breakdown - Instrumental]\n(oohs and ahs)\n[Hook]\n{hook}\n[/Hook]\n[Instrumental groove]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Extended outro - Instrumental]\n(sparse ad-libs fading)',
    'drumnbass': '[Intro - Instrumental]\n[Amen break]\n[Hook]\n{hook}\n[/Hook]\n[Jungle break - Instrumental]\n(oohs and ahs)\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)',
    'ukgarage': '[Intro - Instrumental]\n[2-step groove - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Break - Instrumental]\n(oohs and ahs)\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)',
    'purebassline': '[Intro - Instrumental]\n[4x4 build]\n[Drop - Instrumental]\n[Hook]\n{hook}\n[/Hook]\n[Instrumental break]\n(oohs and ahs)\n[Build]\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Extended outro - Instrumental]\n(sparse ad-libs fading)',
    # Default for all other genres
    'default': '[Intro - Instrumental]\n[Instrumental verse]\n[Hook]\n{hook}\n[/Hook]\n[Instrumental break]\n(oohs and ahs)\n[Instrumental verse]\n[Hook]\n{hook}\n[/Hook]\n[Drop - Instrumental]\n(yeah, uh, come on)\n[Hook]\n{hook}\n[/Hook]\n[Outro - Instrumental]\n(sparse ad-libs fading)\n[Extended outro - Instrumental]',
}

# GENRE_PRESETS stores a few of these genres under differently-spelled keys.
# Map the real genre tag the app passes us onto the structure entry above.
_INTERMITTENT_GENRE_ALIASES = {
    'drumandbass': 'drumnbass',
    'dnb': 'drumnbass',
    'technhouse': 'techhouse',     # GENRE_PRESETS stores tech house under this typo'd key
    'tech_house': 'techhouse',
    'deeprotbassline': 'bassline',
}


# Intermittent sheets were too thin to fill a track: a 2-line hook repeated 3x is
# ~520 characters of material for a 2.5-3 minute render, and completed songs
# averaged 114s against a 150s target. Suno renders what it is given, so it ran out
# and stopped. Two levers, both applied below:
#   * _HOOK_LINES 2 -> 4  — twice the sung material in each hook block
#   * _INTERMITTENT_EXTENSION — a fourth hook plus more instrumental scaffolding
# The instrumental:vocal balance is roughly preserved, because the extension adds
# instrumental sections alongside the extra hook rather than just more singing.
_HOOK_LINES = 4

_INTERMITTENT_EXTENSION = (
    "[Instrumental break]\n"
    "(oohs and ahs)\n"
    "[Hook]\n{hook}\n[/Hook]\n"
    "[Instrumental section]"
)


def _extend_structure(template: str) -> str:
    """Add one more hook and instrumental material just before the outro.

    Applied uniformly rather than editing all nine templates by hand, so each
    genre's hand-tuned opening (Amen break, 2-step groove, 4x4 build...) is left
    exactly as it was and only the tail grows.
    """
    lines = template.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("[Outro") or line.startswith("[Extended outro"):
            return "\n".join(lines[:i] + _INTERMITTENT_EXTENSION.split("\n") + lines[i:])
    # No outro tag (shouldn't happen with the shipped templates) — append instead,
    # so a future template without one still gets the extra material.
    return template + "\n" + _INTERMITTENT_EXTENSION


def build_intermittent_hook(lyrics_text: str, genre: str | None = None) -> str:
    """Reduce a full lyric sheet to a tiny sung hook surrounded by genre-aware
    instrumental section tags, so Suno spends most of the track on instrumentals.

    The lyrics passed to Suno in custom mode are sung in full, so the only
    reliable way to get sparse/intermittent vocals is to hand it almost nothing
    to sing. The instrumental scaffolding is selected per genre (see
    INTERMITTENT_STRUCTURES) so the section tags match each genre's natural
    energy and arrangement and Suno renders a full 2.5-3 minute track rather than
    ending early on the short hook.
    """
    hook = _extract_hook(lyrics_text, max_lines=_HOOK_LINES)
    hook_block = "\n".join(hook) if hook else "oh-oh-oh"
    key = (genre or "").strip().lower()
    key = _INTERMITTENT_GENRE_ALIASES.get(key, key)
    template = _extend_structure(INTERMITTENT_STRUCTURES.get(key, INTERMITTENT_STRUCTURES["default"]))
    # Hook lines could theoretically contain braces — use replace, not str.format.
    return template.replace("{hook}", hook_block)


def _apply_rapidfire_section_tags(lyrics_text: str) -> str:
    """For Rapid Fire Rap: rewrite section headers into bracketed performance tags
    so Suno delivers fast, rhythmic verses instead of mumbling through. These tags
    live INSIDE the lyrics text (the style box stays plain descriptors).
    [Verse]/[Verse 1]/[Verse 2: ...] → [Verse: Rhythmic, fast flow];
    [Chorus]/[Hook] → [Chorus: Aggressive hook]."""
    text = re.sub(r"\[\s*verse[^\]]*\]", "[Verse: Rhythmic, fast flow, breakneck speed]", lyrics_text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s*(?:chorus|hook)[^\]]*\]", "[Chorus: Aggressive hook]", text, flags=re.IGNORECASE)
    return text


# ── Title generation ─────────────────────────────────────────────────────────

_TITLE_MODEL = "claude-haiku-4-5-20251001"

_TITLE_SYSTEM = """You name songs. Given a song's lyrics, genre and brief, return ONE title.

Rules:
- 2 to 5 words. Short and memorable beats clever and long.
- It must fit THIS genre's world. A grime track and an opera aria should not
  sound like they were named by the same person.
- Pull an actual image, phrase or hook from the lyrics where you can — a title
  that echoes a line people will remember is far better than an abstract mood word.
- Never reuse the title of a real, existing song. Invent something original.
- No quotation marks, no punctuation at the end, no explanation, no markdown.
- Title Case.

Return ONLY the title text. Nothing else."""


def generate_song_title(
    lyrics_text: str | None,
    brief: str | None = None,
    genres: list[str] | None = None,
    fallback: str = "Untitled",
) -> str:
    """Name a song with Haiku, from its lyrics, genre and brief.

    Added 2026-08-05. Previously titles were an afterthought: the lyric prompt
    asked for a "title" field with no guidance at all among its 18 rules about
    lyrics, and two paths had no AI title whatsoever — every instrumental was
    called "Instrumental" and every custom-lyrics song "Custom Song".

    Never raises and never returns empty: on any failure the caller's existing
    title stands, because a mediocre title must never cost someone their song.
    """
    genre_str = ", ".join(genres or []) or "unspecified"
    body = (lyrics_text or "").strip()
    if not body and not (brief or "").strip():
        return fallback

    parts = [f"Genre: {genre_str}"]
    if (brief or "").strip():
        parts.append(f"Brief: {brief.strip()[:300]}")
    if body:
        parts.append(f"Lyrics:\n{body[:2000]}")
    else:
        parts.append("This is an instrumental — there are no lyrics. "
                     "Name it from the genre and brief.")

    try:
        resp = Anthropic().messages.create(
            model=_TITLE_MODEL,
            max_tokens=32,
            system=_TITLE_SYSTEM,
            messages=[{"role": "user", "content": "\n\n".join(parts)}],
        )
        title = (resp.content[0].text or "").strip()
    except Exception:
        logger.exception("generate_song_title: Haiku call failed — keeping %r", fallback)
        return fallback

    # Haiku occasionally wraps it or adds a trailing full stop despite the rules.
    title = title.strip().strip('"').strip("'").strip()
    title = title.split("\n")[0].strip().rstrip(".")
    if not title or len(title) > 60:
        logger.warning("generate_song_title: unusable title %r — keeping %r", title[:80], fallback)
        return fallback
    logger.info("generate_song_title: genre=%r title=%r", genre_str, title)
    return title


def generate_lyrics(user_id: str, brief: str, db_path: pathlib.Path, explicit: bool = False, instrumental: bool = False, song_title: str | None = None, genres: list[str] | None = None, genre_b: str | None = None, blend_ratio: int | None = None, kids_story: bool = False, kids_mode: str = 'song', accent: str | None = None, story_language: str | None = None, character_voice: str | None = None, child_voice: str | None = None, lyrics_language: str | None = None, roast_mode: bool = False, roast_name: str | None = None, roast_details: str | None = None, roast_vibe: str | None = None, bilingual_mode: bool = False, intermittent_vocals: bool = False, inspired_by_theme: str | None = None) -> dict:
    _need_translation = False  # initialised here so all code paths have a value
    if instrumental:
        # Was literally "Instrumental" for every instrumental ever made.
        title = song_title or generate_song_title(
            None, brief=brief, genres=genres, fallback="Instrumental")
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

    if roast_mode and roast_name:
        logger.info("Roast mode: explicit=%s roast_name=%r vibe=%r", explicit, roast_name, roast_vibe)
        structure = random.choice(_SONG_STRUCTURES)
        system = (_ROAST_EXPLICIT_SYSTEM if explicit else _ROAST_SYSTEM).format(structure=structure)
        vibe_modifier = _ROAST_VIBE_MODIFIERS.get(roast_vibe or 'gentle', _ROAST_VIBE_MODIFIERS['gentle'])
        user_message = (
            f"Write a funny roast song about {roast_name}.\n"
            f"About them: {(roast_details.strip() if roast_details else 'No details provided — invent generic funny stuff based on the name alone')}\n\n"
            f"{vibe_modifier}\n\n"
            "Make it genuinely funny — use specific details, not vague generic jokes. "
            "The song should make the subject laugh while cringing slightly."
        )
        if genres:
            user_message += f"\n\nGenre: {', '.join(genres)} — match the musical style, vocabulary and flow to this genre."
        if explicit:
            user_message += _ROAST_EXPLICIT_ADDENDUM
        else:
            user_message += _ROAST_CLEAN_ADDENDUM
        model = "claude-sonnet-4-6"
        logger.info(
            "generate_lyrics: roast mode — %s user=%s name=%r vibe=%r genres=%r explicit=%s",
            model, user_id, roast_name, roast_vibe, genres, explicit,
        )
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1200,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception:
            logger.exception("generate_lyrics: roast %s API call failed — user=%s", model, user_id)
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
            logger.exception("generate_lyrics: roast JSON parse failed — raw=%r", raw[:500])
            raise
        final_title = song_title or parsed["title"]
        safe_lyrics = _strip_slurs(parsed["lyrics"])
        logger.info("generate_lyrics: roast output — explicit=%s title=%r lyrics=%r", explicit, final_title, safe_lyrics[:500])
        conn = db._conn(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
                (user_id, brief, safe_lyrics, final_title),
            )
            lyric_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        return {"lyric_id": lyric_id, "lyrics": safe_lyrics, "title": final_title}

    if kids_story:
        model = "claude-sonnet-4-6"
        if kids_mode == 'story':
            kids_prompt = brief.strip() if brief.strip() else "Write a fun, magical adventure story for young children."
            _story_lang = _KIDS_LANGUAGE_MAP.get((story_language or 'english').lower())
            _is_single_voice = not (character_voice or child_voice)
            _is_foreign_lang = bool(_story_lang and (story_language or 'english').lower() != 'english')
            _bilingual = bilingual_mode and _is_foreign_lang
            _need_translation = _is_foreign_lang and not _bilingual
            logger.info(
                "generate_lyrics: kids_story language=%r mapped=%r foreign=%s single_voice=%s need_segments=%s bilingual=%s",
                story_language, _story_lang, _is_foreign_lang, _is_single_voice, _need_translation, _bilingual,
            )

            if _bilingual:
                # ── BILINGUAL PATH — one Claude call, returns early ─────────────────
                _bl_has_hero = bool(child_voice)
                _bl_has_char = bool(character_voice)
                if _bl_has_hero or _bl_has_char:
                    _bl_speakers = ["NARRATOR"] + (["HERO"] if _bl_has_hero else []) + (["CHARACTER"] if _bl_has_char else [])
                    _bl_speaker_str = ", ".join(_bl_speakers)
                    _bl_hero_rule = "\n- HERO: the child hero speaking or reacting" if _bl_has_hero else ""
                    _bl_char_rule = "\n- CHARACTER: the other character (creature, villain etc.) speaking" if _bl_has_char else ""
                    _bl_second_spk = _bl_speakers[1] if len(_bl_speakers) > 1 else "NARRATOR"
                    system = (
                        f"You are a warm, imaginative children's storyteller. Write a short enchanting bilingual "
                        f"children's story in {_story_lang} and English, using multiple voices.\n\n"
                        f"Output ONLY valid JSON with this exact shape:\n"
                        f'{{\n  "title": "Story Title Here",\n  "lines": [\n'
                        f'    {{"speaker": "NARRATOR", "foreign": "Sentence in {_story_lang}.", "english": "English translation."}},\n'
                        f'    {{"speaker": "{_bl_second_spk}", "foreign": "Exclamation!", "english": "English!"}}\n'
                        f'  ]\n}}\n\n'
                        f"Speaker rules:\n"
                        f"- EVERY line must have a speaker: {_bl_speaker_str}\n"
                        f"- NARRATOR: narration, scene-setting, transitions{_bl_hero_rule}{_bl_char_rule}\n"
                        f"- Aim for 14 to 18 lines; roughly half NARRATOR, rest split between voices\n\n"
                        f"Story rules:\n"
                        f"- Each line in both {_story_lang} (foreign) and English (english)\n"
                        f"- Short, clear sentences — one idea per line, ideal for speaking aloud\n"
                        f"- Clear arc: beginning (characters and setting), middle (gentle challenge), end (warm happy resolution)\n"
                        f"- Simple vocabulary a young child can picture; always end warmly\n"
                        f"- No scary or violent themes. No markdown, no commentary. JSON only."
                    )
                else:
                    system = (
                        f"You are a warm, imaginative children's storyteller. Write a short enchanting bilingual "
                        f"children's story in {_story_lang} and English.\n\n"
                        f"Output ONLY valid JSON with this exact shape:\n"
                        f'{{\n  "title": "Story Title Here",\n  "lines": [\n'
                        f'    {{"foreign": "Sentence in {_story_lang}.", "english": "English translation."}},\n'
                        f'    {{"foreign": "Another sentence.", "english": "Another translation."}}\n'
                        f'  ]\n}}\n\n'
                        f"Rules:\n"
                        f"- Write 14 to 18 lines — short, speakable sentences ideal for a child to hear\n"
                        f"- Each line: the sentence in {_story_lang} (foreign) and its English translation (english)\n"
                        f"- One idea per line; keep sentences short and simple\n"
                        f"- Clear arc: beginning (character and setting), middle (gentle adventure), end (warm happy resolution)\n"
                        f"- Simple, vivid vocabulary a young child can picture; always end warmly\n"
                        f"- No scary or violent themes. No markdown, no commentary. JSON only."
                    )
                try:
                    _bl_resp = client.messages.create(
                        model=model, max_tokens=2000,
                        system=system,
                        messages=[{"role": "user", "content": kids_prompt}],
                    )
                except Exception:
                    logger.exception("generate_lyrics: bilingual %s API call failed — user=%s", model, user_id)
                    raise
                _bl_raw = _bl_resp.content[0].text.strip()
                if _bl_raw.startswith("```"):
                    _bl_raw = _bl_raw.split("```", 2)[1]
                    if _bl_raw.startswith("json"):
                        _bl_raw = _bl_raw[4:]
                    _bl_raw = _bl_raw.strip()
                try:
                    _bl_parsed = json.loads(_bl_raw)
                except json.JSONDecodeError:
                    logger.exception("generate_lyrics: bilingual JSON parse failed — raw=%r", _bl_raw[:500])
                    raise
                _bilingual_lines = _bl_parsed.get("lines") or []
                final_title = song_title or _bl_parsed.get("title") or "Bilingual Story"
                _foreign_lyrics = "\n".join(ln.get("foreign", "") for ln in _bilingual_lines if ln.get("foreign"))
                conn = db._conn(db_path)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO lyrics (user_id, brief, lyrics_text, title, kids_story) VALUES (?, ?, ?, ?, 1)",
                        (user_id, brief, _foreign_lyrics or "bilingual", final_title),
                    )
                    lyric_id = cur.lastrowid
                    conn.commit()
                finally:
                    conn.close()
                logger.info(
                    "generate_lyrics: bilingual story ok — %d lines user=%s lyric_id=%s",
                    len(_bilingual_lines), user_id, lyric_id,
                )
                return {"lyric_id": lyric_id, "lyrics": _foreign_lyrics, "title": final_title, "bilingual_lines": _bilingual_lines}

            # ── NON-BILINGUAL: select system prompt ──────────────────────────────
            if character_voice and child_voice:
                system = _KIDS_STORY_THREE_VOICE_SYSTEM   # [NARRATOR]/[CHILD]/[CHARACTER]
            elif child_voice:
                system = _KIDS_STORY_TWO_VOICE_SYSTEM     # [NARRATOR]/[CHILD]
            elif character_voice:
                system = _KIDS_STORY_MULTI_VOICE_SYSTEM   # [NARRATOR]/[CHARACTER] (legacy 2-voice)
            else:
                system = _KIDS_STORY_SYSTEM
            if _is_foreign_lang:
                # Instruct Claude to write the story in the target language only.
                # Translations are fetched in a separate second call so neither call gets truncated.
                kids_prompt += (
                    f"\n\nIMPORTANT: Write the story ENTIRELY in {_story_lang}. "
                    f"Use natural, child-friendly {_story_lang} vocabulary and phrasing throughout. "
                    "Do not include any English text in the 'lyrics' field.\n\n"
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

        # ── Call 1: Generate the story / song ─────────────────────────────────
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1500,
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
            raise  # bubbles up as 500; no DB insert has happened so no credit charged

        final_title = song_title or parsed["title"]

        # ── Call 2 (foreign stories only): Translate utterances for subtitles ──
        # Done as a separate call so the story JSON never gets truncated by token limits.
        segments = None
        if _need_translation:
            try:
                _trans_prompt = (
                    f"Here is a children's story in {_story_lang}:\n\n"
                    f"{parsed['lyrics']}\n\n"
                    "Return ONLY a JSON object with a single \"segments\" key. "
                    "The value is an array with one entry per utterance or sentence, in story order. "
                    "Each entry: \"text\" (the utterance exactly as it appears in the story, "
                    "without any [SPEAKER] tag prefix) and \"english\" (the English translation). "
                    "Cover every utterance. No other keys.\n"
                    "Example: {\"segments\": [{\"text\": \"Il était une fois une licorne.\", "
                    "\"english\": \"Once upon a time there was a unicorn.\"}]}"
                )
                _trans_resp = client.messages.create(
                    model=model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": _trans_prompt}],
                )
                _trans_raw = _trans_resp.content[0].text.strip()
                if _trans_raw.startswith("```"):
                    _trans_raw = _trans_raw.split("```", 2)[1]
                    if _trans_raw.startswith("json"):
                        _trans_raw = _trans_raw[4:]
                    _trans_raw = _trans_raw.strip()
                _trans_parsed = json.loads(_trans_raw)
                segments = _trans_parsed.get("segments") or None
                logger.info(
                    "generate_lyrics: translation call ok — %d segments user=%s",
                    len(segments or []), user_id,
                )
            except Exception:
                logger.warning(
                    "generate_lyrics: translation call failed — story will have no subtitles user=%s",
                    user_id, exc_info=True,
                )
                segments = None  # story still works, just no subtitles

        conn = db._conn(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO lyrics (user_id, brief, lyrics_text, title, kids_story) VALUES (?, ?, ?, ?, 1)",
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
            "segments": segments,
        }

    structure = random.choice(_SONG_STRUCTURES)
    mood = random.choice(_MOODS)
    # When the user picked an "Inspired By" reference, the song must be ABOUT the
    # same kind of subject as that reference. Previously the reference only shaped
    # the Suno style string and the lyrics got a random theme from _THEMES, so an
    # inspired-by song matched the sound but not the story.
    theme = (inspired_by_theme or "").strip() or random.choice(_THEMES)
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
    if (inspired_by_theme or "").strip():
        # Stated explicitly because a one-word slot ("Theme: betrayal") is easy to
        # gloss over, whereas the reference's actual subject is the whole point.
        user_message += (
            f"\n\nSUBJECT MATTER (most important): this song must be ABOUT the following — "
            f"{inspired_by_theme.strip()}\n"
            "Write ORIGINAL lyrics telling your own version of that kind of story, with the "
            "same emotional sentiment and point of view. Do not copy any existing lyrics, and "
            "do not name any real artist, song or place. If a brief was also given above, keep "
            "its details but make the subject matter above the emotional core of the song."
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
        for g in all_genres:
            if g in GENRE_MOOD_DIRECTIVES:
                user_message += GENRE_MOOD_DIRECTIVES[g]

    _lyric_language = lyrics_language or _REGULAR_LANGUAGE_MAP.get((accent or '').lower())
    if _lyric_language:
        user_message += (
            f"\n\nIMPORTANT: Write the lyrics ENTIRELY in {_lyric_language} — not English. "
            f"Use authentic {_lyric_language} vocabulary and natural phrasing throughout. "
            f"Write every line in {_lyric_language} — no English translation."
        )
    # Rapid Fire Rap accent: structure the lyrics for speed-rapping, not just the vocal style.
    # The accent value is the full descriptor string, so match on a signature phrase.
    if "rapid-fire rap" in (accent or "").lower():
        user_message += (
            "\n\nWrite these lyrics for extremely fast double-time rap delivery. "
            "Write moderately MORE lyrics than usual — roughly 1.3x the normal verse length — "
            "enough to avoid repetition without cramming. The goal is a faster CADENCE (each "
            "word and syllable hitting quicker), NOT squeezing more words into the same pace. "
            "Use tight internal rhymes, short punchy multi-syllabic words and a steady rhythmic "
            "pocket built for a sped-up double-time flow with clear, un-mumbled diction. "
            "Avoid repetitive hooks — keep generating fresh bars throughout, minimal repetition."
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

    # A user-supplied title always wins. Otherwise name it properly from the
    # finished lyrics rather than using the unguided one Sonnet tacked on.
    final_title = song_title or generate_song_title(
        parsed["lyrics"], brief=brief, genres=genres, fallback=parsed["title"])

    _lyrics_text = parsed["lyrics"]
    if intermittent_vocals:
        # Mostly-instrumental: hand Suno only a tiny hook so it can't sing full verses.
        _genre = genres[0] if genres else None
        _lyrics_text = build_intermittent_hook(_lyrics_text, genre=_genre)
        logger.info("generate_lyrics: intermittent mode — genre=%r reduced lyrics to hook (len=%d)", _genre, len(_lyrics_text))
    elif "rapid-fire rap" in (accent or "").lower():
        # Bracketed performance tags go INSIDE the lyrics (not the style box) so Suno
        # renders fast double-time delivery rather than mumbling through.
        _lyrics_text = _apply_rapidfire_section_tags(_lyrics_text)
        logger.info("generate_lyrics: rapid-fire — injected fast-flow section tags (len=%d)", len(_lyrics_text))

    conn = db._conn(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?)",
            (user_id, brief, _lyrics_text, final_title),
        )
        lyric_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {
        "lyric_id": lyric_id,
        "lyrics": _lyrics_text,
        "title": final_title,
    }


def store_custom_lyrics(user_id: str, brief: str, lyrics_text: str, db_path: pathlib.Path, song_title: str | None = None, intermittent_vocals: bool = False, genre: str | None = None) -> dict:
    """Store user-supplied lyrics directly without calling Claude."""
    # Was literally "Custom Song" every time. Their words, so name it from them —
    # this is the only Claude call on this path and it costs a fraction of a second.
    title = song_title or generate_song_title(
        lyrics_text, brief=brief, genres=[genre] if genre else None, fallback="Custom Song")
    if intermittent_vocals:
        lyrics_text = build_intermittent_hook(lyrics_text, genre=genre)
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
