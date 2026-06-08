"""Song variant generation via Apiframe v2 (https://api.apiframe.ai/v2/music/generate)."""
import os
import random
import sqlite3
import logging
import re
import time
import threading
import requests

INSTRUMENTAL_GENRES: frozenset[str] = frozenset({'meditation', 'healingfrequency'})

GENRE_MODEL_OVERRIDES: dict[str, str] = {
    'ragga':       'V5_5',
    'bhangra':     'V5_5',
    'rastadub':    'V5_5',
    'deeproots':   'V5_5',
    'purebassline': 'V5_5',
}

# ── Cross-genre fallback variation pools ──────────────────────────────────────
# Used for any genre not listed in GENRE_VARIATION_POOLS below.
_DEFAULT_VARIATIONS: dict[str, list[str]] = {
    "structure": [
        "stripped-back intro building to full energy",
        "straight into the hook from bar one",
        "slow emotional build to an anthemic chorus",
        "dynamic mid-song breakdown then big finale",
        "sparse verse erupting into massive final chorus",
        "call-and-response structure throughout",
        "extended instrumental bridge before the last hook",
        "quiet intro layering up to rich full arrangement",
    ],
    "energy": [
        "high energy throughout",
        "moody and atmospheric",
        "uplifting and euphoric",
        "raw and gritty",
        "dark brooding tension",
        "warm and intimate",
        "dreamy hypnotic groove",
        "urgent and relentless",
    ],
    "production": [
        "rich layered production with harmonic depth",
        "minimal spacious mix with room to breathe",
        "vintage analogue warmth",
        "modern polished commercial sound",
        "reverb-drenched expansive atmosphere",
        "punchy dry in-your-face mix",
        "wide stereo cinematic sound",
        "lo-fi textured character",
    ],
}

# ── Per-genre variation pools ─────────────────────────────────────────────────
# One item is picked from each category per generation and appended to the style.
# Genres not listed fall back to _DEFAULT_VARIATIONS.
GENRE_VARIATION_POOLS: dict[str, dict[str, list[str]]] = {
    "drumandbass": {
        "structure": [
            "rolling intro building to a heavy amen drop",
            "straight into the breakbeat from bar one",
            "liquid intro flowing into deep rolling DnB",
            "dark atmospheric build with a neurofunk bass drop",
            "slow wind-up erupting into relentless DnB drums",
        ],
        "energy": [
            "high-octane dancefloor energy",
            "dark atmospheric liquid vibes",
            "neurofunk tension and aggression",
            "jump-up bouncy rave energy",
            "deep rolling hypnotic groove",
        ],
        "production": [
            "crisp punchy drums with deep Reese bass",
            "sampled jazz break with heavy sub bass weight",
            "distorted industrial texture and metallic snare",
            "wide stereo amen break with tight rolling bassline",
            "glassy synth stabs over sub-heavy bass",
        ],
    },
    "jungle": {
        "structure": [
            "ragga intro chopping into a furious amen break",
            "straight into the break from bar one",
            "bass-heavy dub intro before the jungle rush",
            "slow reggae introduction dropping into full jungle chaos",
        ],
        "energy": [
            "chaotic frenzied rave energy",
            "deep rolling spiritual jungle",
            "dark underground early-90s rawness",
            "euphoric uplifting jungle vibes",
        ],
        "production": [
            "chopped Amen break with heavy sub bass",
            "layered breakbeats with Jamaican dub echo",
            "raw lo-fi analogue rave production",
            "sliced jungle percussion with reggae samples",
        ],
    },
    "grime": {
        "structure": [
            "aggressive intro straight into gritty bars",
            "sparse icy beat building to intense MCing",
            "cold dark intro exploding into rapid-fire flow",
            "beat switch mid-track with harder breakdown",
        ],
        "energy": [
            "intense aggressive street energy",
            "icy cold dark threatening tension",
            "raw relentless underground grime",
            "rapid-fire delivery with menacing atmosphere",
        ],
        "production": [
            "dark icy synth stabs over pounding 808",
            "sparse minimalist grime production",
            "heavy sub bass with clipped hard snares",
            "chopped vocal samples over cold dark synths",
        ],
    },
    "ukdrill": {
        "structure": [
            "dark intro straight into menacing drill bars",
            "ambient piano intro dropping into heavy 808 drill",
            "sliding melody intro building to aggressive verse",
            "beat switch with contrasting melodic bridge",
        ],
        "energy": [
            "menacing cold street energy",
            "brooding South London darkness",
            "aggressive threatening atmosphere",
            "haunting melodic darkness",
        ],
        "production": [
            "rolling 808 with sliding chromatic bass notes",
            "dark piano sample over trap hi-hats",
            "ominous string stabs over heavy kick pattern",
            "minimal sinister production with reverb snare",
        ],
    },
    "ukgarage": {
        "structure": [
            "smooth intro rolling into a 2-step groove",
            "straight into the skippy rhythm from bar one",
            "pitched vocal intro building to a garage peak",
            "laid-back verse dropping into a punchy chorus",
        ],
        "energy": [
            "smooth late-night London underground cool",
            "bouncy infectious dancefloor groove",
            "romantic and sultry",
            "high-energy euphoric club peak",
        ],
        "production": [
            "skippy 2-step drums with deep sidechain bass",
            "pitched vocal chops over shuffled hi-hats",
            "warm sub bass with crisp garage drum pattern",
            "polished UK garage production with lush fills",
        ],
    },
    "hiphop": {
        "structure": [
            "boom bap intro rolling into a confident verse",
            "straight into the hook then a lyrical verse",
            "atmospheric intro building into a hip-hop groove",
            "classic verse-chorus-bridge structure",
            "extended rap verse with a minimal hook",
        ],
        "energy": [
            "confident street energy",
            "introspective late-night mood",
            "uplifting and motivational",
            "raw gritty underground feel",
            "smooth cool laid-back groove",
        ],
        "production": [
            "punchy boom bap drums with warm soul sample",
            "deep 808 bass with crisp snare snap",
            "dusty looped sample with layered percussion",
            "live drum break with a melodic piano hook",
            "soulful piano loop over heavy kick pattern",
        ],
    },
    "trap": {
        "structure": [
            "dark intro melting into a heavy 808 groove",
            "straight into the 808 from the first bar",
            "melodic intro building to a hard-hitting verse",
            "slow tense intro exploding into full trap energy",
        ],
        "energy": [
            "dark menacing street energy",
            "melodic introspective late-night mood",
            "aggressive hard-hitting power",
            "moody atmospheric brooding feel",
        ],
        "production": [
            "distorted 808 sub with fast hi-hat triplets",
            "atmospheric synth pads under heavy trap drums",
            "dark minor piano loop with rolling 808",
            "layered 808 stacks with a crisp clap",
        ],
    },
    "eastcoasthiphop": {
        "structure": [
            "jazz sample intro rolling into boom bap verse",
            "straight into lyrical bars over punchy drums",
            "soulful hook intro then an extended rap verse",
            "boom bap verse building to a melodic bridge",
        ],
        "energy": [
            "confident lyrical New York energy",
            "introspective underground seriousness",
            "smooth cool sophistication",
            "raw authentic street credibility",
        ],
        "production": [
            "looped jazz sample with punchy snare and kick",
            "dusty vinyl texture with chopped walking bass",
            "soulful horn sample over boom bap drums",
            "warm SP-1200 drum texture with deep bass loop",
        ],
    },
    "house": {
        "structure": [
            "four-bar rolling intro building to a soulful drop",
            "straight into the groove with warm piano from bar one",
            "atmospheric pad intro blooming into full house",
            "minimal intro slowly layering to full club energy",
            "organ-led intro with a euphoric chord drop",
        ],
        "energy": [
            "uplifting euphoric dancefloor energy",
            "deep soulful warm house groove",
            "late-night underground club feel",
            "pure joy and celebration",
            "hypnotic rolling deep house",
        ],
        "production": [
            "warm Rhodes piano with deep rolling sub bass",
            "lush gospel chord stabs with Hammond organ",
            "crisp Chicago house drum machine with sub bass",
            "filtered synth pads with tight 4x4 kick",
            "soulful vocal chops over warm house chords",
        ],
    },
    "techno": {
        "structure": [
            "industrial intro grinding into a relentless drop",
            "minimal kick-only intro layering into full techno",
            "hypnotic loop slowly adding elements over 4 minutes",
            "dark atmospheric intro erupting into hard techno",
        ],
        "energy": [
            "relentless industrial dancefloor energy",
            "dark hypnotic underground trance",
            "cold mechanical precision",
            "intense euphoric rave peak",
        ],
        "production": [
            "hard distorted kick with squelching acid bassline",
            "minimal metallic percussion with deep sub bass",
            "dark resonant synth stabs over pounding kick",
            "industrial noise texture with relentless groove",
        ],
    },
    "technhouse": {
        "structure": [
            "rolling minimal intro building to a groovy drop",
            "straight into the bass hook from bar one",
            "hypnotic loop gradually layering instrumentation",
            "stripped-back late-night intro growing to full energy",
        ],
        "energy": [
            "cool underground club groove",
            "hypnotic late-night floor filler",
            "dark sophisticated underground energy",
            "smooth flowing dancefloor warmth",
        ],
        "production": [
            "rolling bass hook with crisp minimal percussion",
            "filtered acid riff over tight drum machine",
            "deep organic bass with subtle hi-hat texture",
            "groove-driven minimal mix with wide stereo field",
        ],
    },
    "bassline": {
        "structure": [
            "heavy bass intro slamming into the 4x4 groove",
            "straight into the bassline and kick from bar one",
            "pitched vocal intro dropping into a Sheffield floor filler",
            "slow bass filter opening over 8 bars to full energy",
        ],
        "energy": [
            "raw underground Sheffield rave energy",
            "bouncy hypnotic dancefloor groove",
            "hard-hitting Northern rave intensity",
            "euphoric club peak energy",
        ],
        "production": [
            "heavy warped sub bass with organ stab accents",
            "punchy 4x4 kick with wobbling sidechain bass",
            "raw analogue synth bass with clipped hat patterns",
            "deep sub pressure with percussive top-line stabs",
        ],
    },
    "niche": {
        "structure": [
            "pitched vocal intro dropping into the niche groove",
            "straight into the Yorkshire club floor filler",
            "slow bass intro building to a bouncy niche peak",
            "call-and-response between female vocal and bassline",
        ],
        "energy": [
            "euphoric Yorkshire club energy",
            "cheeky bouncy Sheffield warehouse vibe",
            "raw underground rave intensity",
            "infectious high-energy crowd floor filler",
        ],
        "production": [
            "pitched-up female vocal chops over heavy sub",
            "speed garage bassline with bouncy organ stab",
            "raw niche production with punchy 4x4 kick",
            "filtered bass swell building over 4 bars",
        ],
    },
    "deeprotbassline": {
        "structure": [
            "deep bass intro building to a Nottingham bassline drop",
            "straight into the rolling sub from bar one",
            "atmospheric intro filtering in the heavy bass slowly",
            "slow hypnotic build to a euphoric bassline peak",
        ],
        "energy": [
            "deep hypnotic underground groove",
            "euphoric dancefloor intensity",
            "dark rolling bass weight",
            "relentless 4x4 pressure",
        ],
        "production": [
            "deep rolling sub with chopped vocal hooks",
            "UK garage-influenced bassline production",
            "warm analogue sub with tight drum machine",
            "filtered bass evolving and morphing throughout",
        ],
    },
    "purebassline": {
        "structure": [
            "organ stab intro slamming into heavy 4x4 bassline",
            "straight into the pumping Sheffield groove from bar one",
            "vocal chop intro building to a massive bass drop",
            "stripped bass and kick intro layering into full production",
        ],
        "energy": [
            "euphoric Northern England rave peak",
            "bouncy infectious Sheffield dancefloor groove",
            "hard-hitting underground club intensity",
            "uplifting high-energy bass music",
        ],
        "production": [
            "warped LFO modulated sub with organ stabs",
            "pitched R&B vocal chops over punchy 4x4 kick",
            "speed garage bassline with crisp shuffled hats",
            "heavy sidechain bass pressure with euphoric stabs",
        ],
    },
    "reggae": {
        "structure": [
            "one-drop intro building to a skanking groove",
            "straight into the off-beat rhythm and bassline",
            "dub intro echoing into a full reggae arrangement",
            "conscious intro building to a rootsy chorus",
        ],
        "energy": [
            "relaxed tropical dancefloor vibes",
            "conscious spiritual feeling",
            "joyful celebratory energy",
            "deep roots meditative groove",
        ],
        "production": [
            "warm analogue bass with crisp off-beat skank",
            "vintage studio dub echo production",
            "heavy one-drop drum with warm bass pressure",
            "layered harmony vocals over rootsy instrumentation",
        ],
    },
    "rootsreggae": {
        "structure": [
            "spiritual intro building to a conscious roots groove",
            "deep one-drop intro with bass coming in slowly",
            "dub instrumental intro fading into vocals",
            "meditative intro building to a conscious message",
        ],
        "energy": [
            "deep spiritual consciousness",
            "peaceful righteous energy",
            "heavy roots meditation",
            "joyful Rastafarian celebration",
        ],
        "production": [
            "vintage Studio One style analogue production",
            "heavy one-drop with deep rolling bass",
            "warm room reverb with subtle tape saturation",
            "layered roots harmonies over organic rhythm section",
        ],
    },
    "loversrock": {
        "structure": [
            "romantic intro easing into a smooth lovers groove",
            "straight into the sensual melody from bar one",
            "gentle guitar intro blooming into a lush arrangement",
            "sparse verse building to a rich warm chorus",
        ],
        "energy": [
            "sweet romantic intimacy",
            "sensual late-night warmth",
            "bittersweet emotional longing",
            "joyful loving celebration",
        ],
        "production": [
            "warm soft guitar over a smooth bassline",
            "lush string arrangement with Caribbean warmth",
            "vintage lovers rock with gentle reverb",
            "smooth organ fills and soft percussion",
        ],
    },
    "rastadub": {
        "structure": [
            "deep dub intro with echo slowly building",
            "straight into the heavy rolling groove",
            "slow roots intro dissolving into deep dub",
            "conscious verse with echoing dub breakdown",
        ],
        "energy": [
            "deep spiritual Rastafarian consciousness",
            "heavy meditative dub groove",
            "peaceful righteous power",
            "dark rolling dub pressure",
        ],
        "production": [
            "heavy echo and reverb on every element",
            "deep rolling dub bass with spring reverb",
            "warm analogue tape with cavernous room sound",
            "sound system sub bass with echoing dub effects",
        ],
    },
    "rnb": {
        "structure": [
            "atmospheric intro dissolving into a smooth R&B groove",
            "straight into the hook with lush production",
            "sparse verse building to a rich layered chorus",
            "slow seductive intro building to an emotional peak",
        ],
        "energy": [
            "smooth sultry late-night mood",
            "confident powerful expression",
            "emotional intimate vulnerability",
            "uplifting feel-good groove",
        ],
        "production": [
            "lush layered vocal harmonies over soft drums",
            "warm bass-forward production with Rhodes keys",
            "contemporary R&B with crisp programmed drums",
            "silky smooth production with gentle synth pads",
        ],
    },
    "soul": {
        "structure": [
            "gospel-inspired intro building to a soulful peak",
            "straight into the emotional hook from bar one",
            "sparse piano intro flowering into full soul arrangement",
            "call-and-response vocals with horn section",
        ],
        "energy": [
            "deeply emotional heartfelt delivery",
            "uplifting church gospel energy",
            "raw vulnerable soulful expression",
            "celebratory joyful soul vibes",
        ],
        "production": [
            "warm brass section with Hammond organ",
            "live rhythm section with lush strings",
            "vintage soul production with deep bass and horns",
            "layered gospel harmonies over warm arrangement",
        ],
    },
    "blues": {
        "structure": [
            "slow 12-bar intro building to an expressive guitar solo",
            "straight into the gritty blues groove",
            "sparse acoustic intro building to a full electric arrangement",
            "quiet verse building to a powerful emotional peak",
        ],
        "energy": [
            "raw emotional heartbreak",
            "deep brooding sorrow",
            "defiant resilient blues spirit",
            "joyful shuffling boogie energy",
        ],
        "production": [
            "raw electric guitar with warm amp tone",
            "sparse arrangement with breathing room",
            "vintage recording with subtle tape saturation",
            "live feel with improvised guitar texture",
        ],
    },
    "jazz": {
        "structure": [
            "relaxed intro building to a swinging jazz groove",
            "straight into the melody then free improvisation",
            "cool intro trading between piano and saxophone",
            "slow ballad evolving into an up-tempo swing",
        ],
        "energy": [
            "cool sophisticated elegance",
            "swinging joyful energy",
            "introspective late-night mood",
            "fiery bebop intensity",
        ],
        "production": [
            "warm upright bass with brushed drums",
            "intimate small-group close-mic production",
            "cool restrained spacing and melodic economy",
            "rich chord voicings with melodic improvisation",
        ],
    },
    "swing": {
        "structure": [
            "big band intro building to full swing energy",
            "straight into the swinging groove from bar one",
            "quiet brass intro erupting into full orchestra",
            "verse trading between vocalist and ensemble",
        ],
        "energy": [
            "pure joyful 1940s dancefloor energy",
            "sophisticated ballroom elegance",
            "playful upbeat swing charm",
            "fiery hot swing intensity",
        ],
        "production": [
            "full big band brass with walking bass",
            "tight swing rhythm section with brushed snare",
            "warm vintage recording with ensemble dynamics",
            "layered brass voicings over swinging rhythm",
        ],
    },
    "vocaljazz": {
        "structure": [
            "intimate piano intro leading into crooned verse",
            "straight into the vocal melody from bar one",
            "slow ballad intro building to an emotional chorus",
            "trading chorus between vocalist and piano",
        ],
        "energy": [
            "intimate late-night sophistication",
            "warmly emotional and tender",
            "cool confident velvet delivery",
            "bittersweet romantic longing",
        ],
        "production": [
            "warm close-mic vocal with piano and upright bass",
            "subtle room reverb on intimate jazz trio",
            "vintage tape warmth with brushed drum texture",
            "lush chord voicings under smooth vocal melody",
        ],
    },
    "pop": {
        "structure": [
            "pre-chorus intro building to a massive anthemic hook",
            "straight into the catchy hook from bar one",
            "emotional sparse verse exploding into euphoric chorus",
            "slow verse building to a huge stadium chorus",
        ],
        "energy": [
            "euphoric uplifting arena energy",
            "emotional heartfelt intimacy",
            "infectious feel-good happiness",
            "dramatic cinematic pop power",
        ],
        "production": [
            "polished layered synths with wide chorus effect",
            "organic live instruments under a glossy pop mix",
            "bright saturated production with lush harmonies",
            "cinematic strings with punchy pop drums",
        ],
    },
    "edm": {
        "structure": [
            "long energy build over 32 bars to a massive drop",
            "short punchy build straight into the main drop",
            "emotional breakdown before a euphoric final drop",
            "rolling groove intro building to a progressive peak",
        ],
        "energy": [
            "pure festival main-stage euphoria",
            "dark underground warehouse intensity",
            "emotional peak-hour anthem feel",
            "driving energetic peak-time energy",
        ],
        "production": [
            "massive supersawing lead synth over four-on-floor",
            "plucked melodic lead with deep sidechain bass",
            "atmospheric emotional pads with powerful drop",
            "layered synth stacks with wide reverb FX",
        ],
    },
    "synthwave": {
        "structure": [
            "slow pulsing 80s intro building to a neon peak",
            "straight into the retro groove from the first bar",
            "cinematic intro fading into a dreamy cruise",
            "atmospheric build to a euphoric retro-futurist peak",
        ],
        "energy": [
            "cool neon-lit nocturnal drive",
            "euphoric retro-futurist excitement",
            "dark dystopian tension",
            "warm nostalgic 80s emotion",
        ],
        "production": [
            "pulsing arpeggiated synth with gated reverb drum",
            "wide chorus synth leads over driving bass synth",
            "warm analog synth with vintage drum machine",
            "cinematic synth pads with layered melodic arps",
        ],
    },
    "afrobeats": {
        "structure": [
            "percussion intro building to a full Afrobeats groove",
            "straight into the infectious rhythm from bar one",
            "talking drum intro blooming into joyful chorus",
            "sparse intro layering up to a rich percussive peak",
        ],
        "energy": [
            "infectious joyful celebratory energy",
            "smooth romantic Afropop warmth",
            "driving rhythmic dancefloor power",
            "soulful emotional expression",
        ],
        "production": [
            "layered talking drums with warm bass and guitar hook",
            "afrobeats percussion stack with melodic guitar riff",
            "bright punchy melody with Afro drum pattern",
            "warm tropical production with layered percussion",
        ],
    },
    "amapiano": {
        "structure": [
            "log drum intro building to a full amapiano groove",
            "straight into the deep piano house from bar one",
            "sparse piano intro layering into smooth amapiano",
            "jazzy intro flowing into a smooth log-step rhythm",
        ],
        "energy": [
            "smooth sophisticated South African cool",
            "deep hypnotic dancefloor groove",
            "joyful uplifting log-step energy",
            "late-night understated cool",
        ],
        "production": [
            "log drum pattern with warm jazz piano chords",
            "deep bass with percussive log step and piano",
            "smooth amapiano mix with subtle reverb piano",
            "layered piano hooks over rhythmic log drum",
        ],
    },
    "metal": {
        "structure": [
            "slow heavy riff intro building to a crushing drop",
            "straight into the wall of guitars from bar one",
            "clean guitar intro shattering into full metal power",
            "slow dark verse building to a massive breakdown",
        ],
        "energy": [
            "crushing aggressive heavy power",
            "relentless high-speed intensity",
            "dark brooding heavy atmosphere",
            "triumphant epic metal grandeur",
        ],
        "production": [
            "heavily distorted guitar with double kick thunder",
            "tight rhythm section with massive guitar wall",
            "dark downtuned guitar tone with deep kick",
            "layered guitar harmonics with powerful fills",
        ],
    },
    "rock": {
        "structure": [
            "clean guitar intro building to a powerful rock surge",
            "straight into the anthemic hook from bar one",
            "slow verse building to an explosive chorus",
            "instrumental intro evolving into full band arrangement",
        ],
        "energy": [
            "powerful anthemic stadium energy",
            "raw gritty garage rock spirit",
            "emotional driving intensity",
            "euphoric uplifting rock triumph",
        ],
        "production": [
            "thick guitar wall with punchy live drums",
            "dry close-mic guitars with natural room drum sound",
            "layered guitar harmonies with powerful bass",
            "tight band production with dynamic range",
        ],
    },
    "trapsoul": {
        "structure": [
            "atmospheric intro dissolving into a dark R&B groove",
            "straight into the emotional hook from bar one",
            "sparse piano intro building to rich trap soul",
            "slow burn verse erupting into an emotional peak",
        ],
        "energy": [
            "dark emotional late-night mood",
            "sensual brooding intimacy",
            "raw vulnerable heartbreak",
            "smooth melancholic beauty",
        ],
        "production": [
            "dark 808 bass under lush R&B vocal production",
            "atmospheric synth pads with trap percussion",
            "emotional piano melody over rolling 808",
            "dreamy reverb-heavy production with sub bass",
        ],
    },
    "gospel": {
        "structure": [
            "quiet devotional intro building to a joyful choir peak",
            "straight into full choir energy from bar one",
            "solo voice intro building to a congregational chorus",
            "call-and-response building to a euphoric peak",
        ],
        "energy": [
            "joyful uplifting church celebration",
            "deeply spiritual emotional power",
            "powerful congregational unity",
            "intimate devotional worship",
        ],
        "production": [
            "full choir harmonies with Hammond organ",
            "live band with powerful gospel drums",
            "layered vocal harmonies with warm organ pads",
            "intimate piano and close-mic vocal warmth",
        ],
    },
    "meditation": {
        "structure": [
            "gently evolving drone building to peaceful fullness",
            "still and sustained from beginning to end",
            "slow gentle bloom from silence to warmth",
            "flowing ambient texture with gradual evolution",
        ],
        "energy": [
            "deeply serene and tranquil",
            "softly expansive and open",
            "gentle healing warmth",
            "peaceful meditative stillness",
        ],
        "production": [
            "soft layered synth pads with singing bowls",
            "warm drone texture with subtle nature sounds",
            "gentle reverb-rich ambient soundscape",
            "spacious minimalist healing atmosphere",
        ],
    },
    "healingfrequency": {
        "structure": [
            "sustained resonant tone slowly blooming",
            "still healing soundscape with gentle evolution",
            "slow gradual build of harmonic frequencies",
            "pure sustained drone with subtle overtones",
        ],
        "energy": [
            "deeply healing and restorative",
            "pure serene wellness energy",
            "gentle sacred stillness",
            "calming therapeutic warmth",
        ],
        "production": [
            "pure singing bowl resonance with ambient pads",
            "soft solfeggio tones with gentle nature texture",
            "warm harmonic drone with crystal bowl overtones",
            "spacious sacred geometry sound bath",
        ],
    },
}


def _pick_creative_variation(genre: str) -> str:
    """Pick one style tag from the energy and production pools for this genre.

    Omits 'structure' — those are prose sentences that confuse Suno's style parser.
    Energy and production entries are short comma-friendly tags that compose cleanly
    with the base genre preset.
    Uses genre-specific pools where available; falls back to _DEFAULT_VARIATIONS.
    Logs the picks so each generation is traceable in the logs.
    """
    base_genre = genre.split("__")[0] if "__" in genre else genre
    pools = GENRE_VARIATION_POOLS.get(base_genre, _DEFAULT_VARIATIONS)
    picks: dict[str, str] = {}
    for category in ("energy", "production"):
        if category in pools:
            picks[category] = random.choice(pools[category])
    logger.info(
        "CREATIVE_VARIATION genre=%r source=%s energy=%r production=%r",
        base_genre,
        "genre_pool" if base_genre in GENRE_VARIATION_POOLS else "default_pool",
        picks.get("energy"),
        picks.get("production"),
    )
    return ", ".join(picks.values())

logger = logging.getLogger("zeus.songs")

GENRE_MOTION_PROMPTS: dict[str, str] = {
    "blues":        "blues guitarist playing soulfully, fingers moving on strings, body swaying, warm amber light",
    "soul":         "soul singer performing passionately, hands moving expressively, warm golden light",
    "reggae":       "reggae musician playing bass, relaxed rhythmic movement, tropical setting",
    "hiphop":       "hip-hop artist performing confidently, hands moving, urban setting",
    "drumandbass":  "DJ performing at rave, hands on decks, strobe lights, energetic movement",
    "grime":        "grime MC performing intensely, microphone in hand, urban backdrop",
    "house":        "DJ at club, hands raised, euphoric crowd, colourful lights",
    "jungle":       "jungle MC on stage, energetic performance, rave lights",
    "country":      "country guitarist strumming, gentle swaying, warm natural light",
    "acoustic":     "acoustic guitarist playing intimately, fingers on strings, candlelight",
    "rock":         "rock guitarist shredding, dramatic movement, stage lighting",
    "lofi":         "indie musician playing piano, relaxed peaceful movement, cosy setting",
    "edm":          "EDM performer on stage, arms raised, laser lights, massive crowd",
    "kpop":         "K-pop performer dancing gracefully, precise choreography, bright stage",
    "niche":         "DJ performing at club, hands on decks, purple neon lights, Sheffield night",
    "ukdrill":       "drill artist performing, intense expression, dark urban setting",
    "loversrock":    "lovers rock singer performing romantically, smooth movement, warm light",
    "rnb":           "R&B singer performing smoothly, flowing movement, soft purple lighting, intimate atmosphere",
    "bluessoul":     "blues soul vocalist on stage, soulful expression, hands raised, warm golden spotlight",
    "deepsoulblues": "deep soul singer seated, emotional performance, eyes closed, dim amber light",
    "bassline":      "DJ at underground Sheffield club, hands on decks, hypnotic movement, red and amber lighting",
    "irishjig":      "Irish céilí dancers spinning, traditional costumes, lively energetic movement, warm firelight",
    "irishfolk":     "Irish folk musician playing acoustic guitar, gentle swaying, misty Atlantic clifftop backdrop",
    "pop":           "pop star performing on arena stage, energetic dancing, colourful lights, confetti falling",
    "ukgarage":      "UK garage MC performing, smooth confident movement, sleek urban setting, neon-lit night",
    "ukstreetsoul":  "soul singer performing smoothly, expressive hand gestures, warm golden lighting, urban backdrop",
    "classical":     "classical musician performing, precise graceful movement, concert hall, elegant conducting gestures",
    "indie":         "indie guitarist playing, relaxed natural movement, warm stage lighting, authentic performance",
    "techno":        "DJ performing at techno club, hands on decks, dark industrial setting, intense focused energy",
    "technhouse":    "tech house DJ mixing, smooth confident movement, underground club, cool atmospheric lighting",
    "hyperpop":      "hyperpop performer, energetic chaotic movement, neon lights, glitchy effects, youthful intense energy",
    "afrobeats":     "afrobeats performer dancing joyfully, rhythmic fluid movement, warm vibrant lighting, celebratory energy",
    "amapiano":      "amapiano DJ performing smoothly, confident fluid movement, warm golden lighting, sophisticated energy",
    "driftphonk":    "phonk performer, intense aggressive movement, dark red lighting, high energy drift culture vibes",
    "jerseyclub":    "Jersey Club DJ mixing, rapid energetic movement, bright club lights, high energy dance floor vibes",
    "afroswing":     "afroswing singer performing smoothly, relaxed romantic movement, warm golden lighting, stylish urban setting",
    "rastadub":      "rasta dub musician performing spiritually, slow rhythmic movement, warm golden lighting, dreadlocks moving gently, peaceful powerful energy",
    "deeprotbassline": "UK bassline DJ mixing, hands on decks, intense focused energy, dark club lighting, heavy bass atmosphere",
    "purebassline":    "UK bassline DJ performing, bouncy energetic 4x4 movement, deep blue purple club lighting, high energy dancefloor atmosphere",
    "jazz":            "jazz saxophonist playing expressively, swaying with the music, warm amber club lighting, smooth sophisticated movement, fingers moving on keys",
    "swing":           "swing jazz band performing energetically, lively big band movement, warm vintage stage lighting, upbeat swing era performance",
    "vocaljazz":       "jazz vocalist singing intimately at microphone, smooth emotional delivery, warm amber lighting, sophisticated jazz club atmosphere",
    "electronicfunk":  "electronic funk performer dancing groovily, robotic funky movement, warm purple neon lighting, infectious rhythm energy",
    "syntheticpop":    "synthetic pop performer dancing energetically, precise choreographed movement, bright pink and blue neon lights, glamorous high energy performance",
    "ragga":           "ragga MC performing energetically, aggressive dancehall movement, tropical warm lighting, high energy Caribbean performance",
    "dubstep":         "dubstep DJ performing, intense head nodding, dark blue purple lighting, massive bass drop energy",
    "bhangra":         "bhangra dancer performing energetically, traditional arm movements, vibrant colourful lighting, joyful celebration energy",
    "rockney":         "rockney musician performing cheerfully, pub singalong energy, warm amber pub lighting, cheeky energetic performance",
    "metal":           "metal guitarist shredding intensely, headbanging dramatic movement, dark red stage lighting, fierce powerful energy",
    "reggaeton":       "reggaeton performer dancing energetically, perreo movement, warm tropical neon lighting, confident Latin urban energy",
    "latintrap":       "Latin trap performer moving intensely, dark moody movement, blue purple neon lighting, brooding urban Latin energy",
    "rootsreggae":    "roots reggae musician performing peacefully, gentle swaying movement, warm golden sunset lighting, spiritual conscious energy",
    "countryamericana": "country Americana performer playing guitar, authentic Southern energy, warm golden lighting, heartfelt emotional performance",
    "southemsoul":      "Southern soul singer performing passionately, gospel church energy, warm amber lighting, deeply emotional soulful delivery",
    "traditionalpop":   "classic crooner performing elegantly, smooth sophisticated movement, warm golden vintage lighting, timeless pop performance",
    "rocknroll":        "rock and roll musician performing energetically, lively rockabilly movement, vintage stage lighting, rebellious 1950s energy",
    "trap":             "trap artist performing intensely, dark moody studio lighting, heavy bass atmosphere, intense focused expression",
    "eastcoasthiphop":  "East Coast MC performing lyrically, confident authentic delivery, urban New York backdrop, classic boom bap energy",
    "poprap":           "pop rap artist performing energetically, bright colourful stage lighting, melodic crossover energy, infectious crowd energy",
    "synthwave":        "synthwave artist in neon lit retro studio, dramatic 80s atmosphere, pulsing electronic energy, glowing synthesizer setup",
    "gospel":           "gospel choir performing passionately, hands raised, warm golden church lighting, powerful spiritual energy",
    "trapsoul":         "trap soul singer performing soulfully, smooth movement, dark atmospheric studio lighting, emotional R&B energy",
    "meditation":       "meditation practitioner in serene peaceful setting, slow gentle movement, soft natural lighting, tranquil spiritual energy",
    "christmas":        "Christmas performer singing joyfully, festive warm lighting, holiday celebration energy, cosy festive atmosphere",
    "corridos":         "corridos musician playing guitar passionately, traditional Mexican performance, vibrant warm lighting, heartfelt authentic storytelling energy",
    "healingfrequency": "peaceful healing frequency visuals, gentle energy waves, soft glowing calming light, serene meditative atmosphere",
}

APIFRAME_API_KEY = os.environ["APIFRAME_API_KEY"]
APIFRAME_BASE = "https://api.apiframe.ai"
WEBHOOK_URL = os.environ["SONG_WEBHOOK_URL"].strip().rstrip("/")
EXPECTED_PRODUCTION_WEBHOOK_URL = "https://zeusaidesign.com/webhooks/apiframe"
if WEBHOOK_URL != EXPECTED_PRODUCTION_WEBHOOK_URL:
    logger.warning("SONG_WEBHOOK_URL is %r; production should be %r", WEBHOOK_URL, EXPECTED_PRODUCTION_WEBHOOK_URL)

# GoAPI fallback — optional, only active when GOAPI_API_KEY is set
GOAPI_API_KEY = os.environ.get("GOAPI_API_KEY", "").strip()
GOAPI_BASE = "https://api.goapi.ai"
GOAPI_WEBHOOK_URL = os.environ.get("GOAPI_WEBHOOK_URL", "").strip().rstrip("/")
if GOAPI_API_KEY:
    logger.info("GoAPI fallback ENABLED (key configured, webhook=%r)", GOAPI_WEBHOOK_URL or "NOT SET")
else:
    logger.info("GoAPI fallback DISABLED — set GOAPI_API_KEY to enable")

DIRECT_ARTIST_STYLE_MAP = {
    "drake": "melodic rap, emotional vocals, atmospheric trap drums, late night mood, polished hip-hop production",
    "travis scott": "psychedelic trap, atmospheric synths, heavy 808 drums, spacious ad-libs, dark festival energy",
    "billie eilish": "intimate whisper vocals, minimalist dark pop, sub bass, eerie atmosphere, sparse percussion",
    "taylor swift": "confessional pop songwriting, bright melodic hooks, polished pop production, emotional storytelling",
    "the weeknd": "dark synth pop, falsetto vocals, nocturnal R&B, pulsing drums, cinematic atmosphere",
    "rihanna": "island-influenced pop, confident vocals, dancehall rhythm, glossy R&B production",
    "beyonce": "powerful R&B vocals, layered harmonies, dynamic pop production, danceable groove",
    "kendrick lamar": "conscious rap, intricate flow, jazz-influenced hip-hop, dramatic storytelling",
    "post malone": "melodic trap-pop, raspy vocals, guitar textures, laid back drums",
    "ariana grande": "airy pop vocals, agile runs, glossy R&B-pop production, stacked harmonies",
}

UNSAFE_INSPIRATION_PATTERNS = (
    r"\blike\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\binspired\s+by\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\bin\s+the\s+style\s+of\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\bsimilar\s+to\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\ba\s+la\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
)


def sanitize_inspired_by_descriptors(raw: str | None) -> str | None:
    """Convert user inspiration text into Suno-safe style descriptors."""
    if not raw:
        return None

    text = raw.strip()
    if not text:
        return None

    descriptor_parts: list[str] = []
    lower_text = text.lower()
    for artist, descriptors in DIRECT_ARTIST_STYLE_MAP.items():
        if artist in lower_text:
            descriptor_parts.append(descriptors)

    scrubbed = text
    for pattern in UNSAFE_INSPIRATION_PATTERNS:
        scrubbed = re.sub(pattern, "", scrubbed, flags=re.IGNORECASE)

    for artist in DIRECT_ARTIST_STYLE_MAP:
        scrubbed = re.sub(rf"\b{re.escape(artist)}\b", "", scrubbed, flags=re.IGNORECASE)

    scrubbed = re.sub(r"\b(like|inspired by|style of|similar to|a la)\b", "", scrubbed, flags=re.IGNORECASE)
    scrubbed = re.sub(r"\s+", " ", scrubbed)

    for part in re.split(r"[,;\n]+", scrubbed):
        part = part.strip(" .:-")
        if not part:
            continue
        if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", part):
            continue
        descriptor_parts.append(part)

    if not descriptor_parts:
        descriptor_parts.append("contemporary pop songwriting, polished production, expressive vocals")

    seen: set[str] = set()
    safe_parts: list[str] = []
    for part in descriptor_parts:
        for item in [p.strip(" .:-") for p in part.split(",")]:
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            safe_parts.append(item)

    return ", ".join(safe_parts)[:500] or None


def _dj_transition_style(style_a: str, style_b: str) -> str:
    """Build a Suno section-tag style string that switches genre per section."""
    return (
        f"[intro: {style_a}] "
        f"[verse: {style_a}] "
        f"[chorus: {style_b}] "
        f"[verse: {style_a}] "
        f"[bridge: {style_b}] "
        f"[outro: {style_b}] "
        "genre switch DJ mix, section by section genre change, not blended, alternating genres per section"
    )[:1000]


def _submit_to_apiframe(variant_id: int, lyrics: str, style_prompt: str, suno_model: str, extra_suno_params: dict) -> str:
    """Submit a generation job to Apiframe. Returns jobId or raises."""
    webhook_url = f"{WEBHOOK_URL}?variant_id={variant_id}"
    payload = {
        "prompt": lyrics,
        "model": "suno",
        "webhookUrl": webhook_url,
        "webhookEvents": ["completed", "failed"],
        "sunoParams": {
            "custom_mode": True,
            "instrumental": False,
            "model_version": suno_model,
            "style": style_prompt[:1000],
            **extra_suno_params,
        },
    }
    headers = {"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"}
    logger.info("APIFRAME_V2_SUBMIT variant_id=%d webhook=%r style_len=%d", variant_id, webhook_url, len(style_prompt))
    logger.info("APIFRAME_V2_STYLE variant_id=%d style=%r", variant_id, style_prompt[:600])

    for attempt in range(2):
        try:
            resp = requests.post(f"{APIFRAME_BASE}/v2/music/generate", headers=headers, json=payload, timeout=30)
            if resp.status_code == 504 and attempt == 0:
                logger.warning("Apiframe 504, retrying in 5s for variant_id=%d", variant_id)
                time.sleep(5)
                continue
            break
        except Exception as conn_err:
            if attempt == 0:
                logger.warning("Apiframe connection error (attempt 0), retrying in 5s for variant_id=%d: %s", variant_id, conn_err)
                time.sleep(5)
                continue
            raise

    logger.info("APIFRAME_V2_RESPONSE variant_id=%d status=%d body=%r", variant_id, resp.status_code, resp.text[:500])

    if resp.status_code == 504:
        raise ValueError("Music generation is taking longer than usual — please try again in a moment")
    resp.raise_for_status()
    try:
        body = resp.json()
    except Exception:
        raise ValueError(f"Apiframe non-JSON response: {resp.status_code}")
    job_id = body.get("jobId")
    if not job_id:
        raise RuntimeError(f"Apiframe response missing jobId: {body!r}")
    return job_id


# GoAPI Suno model version mapping (verify against GoAPI docs when key is available)
_GOAPI_MODEL_MAP = {
    "V5":   "chirp-v3-5",
    "V5_5": "chirp-v3-5",
    "V4":   "chirp-v4",
    "V3_5": "chirp-v3-5",
}


def _submit_to_goapi(variant_id: int, lyrics: str, style_prompt: str, suno_model: str, extra_suno_params: dict) -> str:
    """Submit a generation job to GoAPI (fallback). Returns task_id or raises.

    GoAPI endpoint: POST https://api.goapi.ai/api/suno/v1/music
    Webhook format documented at: https://goapi.ai/docs/suno
    Verify exact field names against docs when GOAPI_API_KEY is first configured.
    """
    if not GOAPI_API_KEY:
        raise RuntimeError("GOAPI_API_KEY not set")
    if not GOAPI_WEBHOOK_URL:
        raise RuntimeError("GOAPI_WEBHOOK_URL not set")

    webhook_url = f"{GOAPI_WEBHOOK_URL}?variant_id={variant_id}"
    goapi_model = _GOAPI_MODEL_MAP.get(suno_model, "chirp-v3-5")

    payload: dict = {
        "model": "suno",
        "task_type": "generate_music",
        "input": {
            "custom_mode": True,
            "mv": goapi_model,
            "prompt": lyrics,
            "tags": style_prompt[:500],
            "make_instrumental": bool(extra_suno_params.get("instrumental", False)),
        },
        "callback_url": webhook_url,
    }
    if extra_suno_params.get("negative_tags"):
        payload["input"]["negative_tags"] = str(extra_suno_params["negative_tags"])[:500]

    headers = {"X-API-Key": GOAPI_API_KEY, "Content-Type": "application/json"}
    logger.info("GOAPI_SUBMIT variant_id=%d webhook=%r model=%r", variant_id, webhook_url, goapi_model)

    resp = requests.post(f"{GOAPI_BASE}/api/suno/v1/music", headers=headers, json=payload, timeout=30)
    logger.info("GOAPI_RESPONSE variant_id=%d status=%d body=%r", variant_id, resp.status_code, resp.text[:500])
    resp.raise_for_status()

    data = resp.json()
    if data.get("code") not in (200, None):
        raise RuntimeError(f"GoAPI error code {data.get('code')}: {data!r}")
    task_id = (data.get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"GoAPI missing task_id in response: {data!r}")
    return task_id


def _alert_fallback_to_goapi(variant_id: int, apiframe_error: str) -> None:
    """Fire-and-forget Telegram alert when GoAPI fallback is triggered."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        return
    msg = (
        f"⚠️ <b>Apiframe down — switched to GoAPI</b>\n"
        f"variant_id={variant_id}\n"
        f"Apiframe error: {apiframe_error[:300]}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": channel, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to send GoAPI fallback Telegram alert: %s", exc)


class InsufficientCreditsError(Exception):
    """Raised when a user does not have enough song credits."""


def _check_and_deduct_credit(cur, user_id, is_admin: bool = False) -> None:
    if is_admin:
        return
    cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] < 1:
        raise InsufficientCreditsError("No song credits available. Top up to continue.")
    cur.execute(
        "UPDATE song_credits SET balance = balance - 1 WHERE user_id = ?",
        (user_id,),
    )


def _refund_credit(cur, user_id) -> None:
    cur.execute(
        "UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?",
        (user_id,),
    )


def generate_song_variant(
    user_id,
    lyric_id: int,
    style_prompt: str,
    genre_tag: str,
    db_path: str,
    extra_suno_params: dict | None = None,
    is_admin: bool = False,
    animate_cover: bool = True,
    suno_model: str = "V5",
) -> dict:
    """
    Submit a song generation job to Apiframe v2.
    Costs 1 song credit (1 credit = 11 Apiframe credits = 1 finished track).
    Returns immediately with variant_id; the actual MP3 arrives later via webhook.
    Admin users bypass credit check entirely.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        _check_and_deduct_credit(cur, user_id, is_admin=is_admin)

        cur.execute(
            "SELECT lyrics_text FROM lyrics WHERE id = ? AND user_id = ?",
            (lyric_id, user_id),
        )
        lyric_row = cur.fetchone()
        if not lyric_row:
            _refund_credit(cur, user_id)
            conn.commit()
            raise ValueError(f"Lyric {lyric_id} not found for user {user_id}")
        lyrics = lyric_row[0]

        cur.execute(
            """INSERT INTO song_variants
               (lyric_id, user_id, style_prompt, genre_tag, status, take_number, animate_cover)
               VALUES (?, ?, ?, ?, 'pending', 1, ?)""",
            (lyric_id, user_id, style_prompt, genre_tag, 1 if animate_cover else 0),
        )
        variant_id = cur.lastrowid
        conn.commit()
    except InsufficientCreditsError:
        conn.close()
        raise

    logger.info(
        "SONG_VARIANT_CREATED variant_id=%d lyric_id=%d user_id=%s genre=%r — webhook will fire to ?variant_id=%d",
        variant_id, lyric_id, user_id, genre_tag, variant_id,
    )
    logger.info(
        "APIFRAME_V2_SUBMIT api_key_configured=%s key_len=%d variant_id=%d webhook_url=%r",
        bool(APIFRAME_API_KEY),
        len(APIFRAME_API_KEY),
        variant_id,
        WEBHOOK_URL,
    )
    logger.info(
        "APIFRAME_V2_PAYLOAD variant_id=%d genre=%r style_len=%d lyrics_len=%d extra_params=%r",
        variant_id, genre_tag, len(style_prompt), len(lyrics), extra_suno_params,
    )
    logger.info("APIFRAME_V2_STYLE variant_id=%d style=%r", variant_id, style_prompt[:600])
    logger.info("APIFRAME_V2_WEBHOOK_URL variant_id=%d url=%r", variant_id, f"{WEBHOOK_URL}?variant_id={variant_id}")

    try:
        provider = "apiframe"
        try:
            job_id = _submit_to_apiframe(variant_id, lyrics, style_prompt, suno_model, extra_suno_params or {})
        except Exception as af_err:
            logger.error("APIFRAME_FAILED variant_id=%d — %s. Trying GoAPI fallback.", variant_id, af_err)
            if not GOAPI_API_KEY or not GOAPI_WEBHOOK_URL:
                raise
            job_id = _submit_to_goapi(variant_id, lyrics, style_prompt, suno_model, extra_suno_params or {})
            provider = "goapi"
            threading.Thread(
                target=_alert_fallback_to_goapi,
                args=(variant_id, str(af_err)),
                daemon=True,
            ).start()

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "UPDATE song_variants SET provider_job_id = ?, provider = ?, status = 'generating' WHERE id = ?",
                (job_id, provider, variant_id),
            )
            conn.commit()
        finally:
            conn.close()

    except Exception as exc:
        # Submission failed — refund credit (unless admin) and mark variant failed
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            if not is_admin:
                _refund_credit(cur, user_id)
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        if isinstance(exc, ValueError):
            raise  # propagate user-friendly message directly to the API layer
        raise RuntimeError(f"Music API submission failed: {exc}") from exc

    return {"variant_id": variant_id, "job_id": job_id, "status": "generating"}


def generate_multiple_variants(
    user_id,
    lyric_id: int,
    genres: list[str],
    db_path: str,
    extra_suno_params: dict | None = None,
    tempo_suffix: str | None = None,
    is_admin: bool = False,
    inspired_by_descriptors: str | None = None,
    animate_cover: bool = True,
    genre_b: str | None = None,
    blend_ratio: int | None = None,
    kids_story: bool = False,
) -> dict:
    """Generate the same lyrics in multiple genres. Costs len(genres) credits.
    Admin users bypass credit checks entirely."""
    from song_genres import GENRE_PRESETS

    valid_genres = [g for g in genres if g in GENRE_PRESETS]
    if not valid_genres:
        raise ValueError("No valid genres provided")
    if len(valid_genres) > 7:
        raise ValueError("Maximum 7 variants per request")

    if not is_admin:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            available = row[0] if row else 0
        finally:
            conn.close()

        if available < len(valid_genres):
            raise InsufficientCreditsError(
                f"Need {len(valid_genres)} credits, have {available}"
            )

    variants = []
    for genre in valid_genres:
        from song_genres import KIDS_STORY_PRESETS
        style = KIDS_STORY_PRESETS.get(genre, GENRE_PRESETS[genre]) if kids_story else GENRE_PRESETS[genre]
        # Apply DJ-transition style for genre blend
        if genre_b and genre_b in GENRE_PRESETS:
            style = _dj_transition_style(style, GENRE_PRESETS[genre_b])
            logger.info("genre_blend: %s × %s DJ-transition style len=%d", genre, genre_b, len(style))
        # Accent/vocal modifiers go BEFORE the genre preset so Suno weights them first.
        # Genre presets can contain strong location/vocal cues (e.g. "East London sound")
        # that override an accent appended at the end.
        if tempo_suffix:
            style = f"{tempo_suffix}, {style}"
        safe_inspired_by = sanitize_inspired_by_descriptors(inspired_by_descriptors)
        if safe_inspired_by:
            style = f"{style}, {safe_inspired_by}"
        if not kids_story:
            style = f"{style}, {_pick_creative_variation(genre)}"
        # Blend songs use section-tag structure (~700+ chars) so they need a higher cap.
        # Single-genre stays at 500. Both stay under Apiframe's own 1000-char limit.
        hard_cap = 900 if genre_b else 500
        if len(style) > hard_cap:
            logger.warning(
                "style string truncated from %d to %d chars for genre=%r blend=%s",
                len(style), hard_cap, genre, bool(genre_b),
            )
            style = style[:hard_cap]
        logger.info("BLEND_STYLE genre=%r genre_b=%r len=%d style=%r", genre, genre_b, len(style), style)
        # Genre tag encodes the blend so the frontend can display "Soul × Grime"
        genre_tag = f"{genre}__{genre_b}" if genre_b and genre_b in GENRE_PRESETS else genre
        suno_model = GENRE_MODEL_OVERRIDES.get(genre, GENRE_MODEL_OVERRIDES.get(genre_b or '', 'V5'))
        genre_suno_params = dict(extra_suno_params or {})
        if genre in INSTRUMENTAL_GENRES:
            genre_suno_params['instrumental'] = True
            logger.info("Forcing instrumental for genre=%r", genre)
        result = generate_song_variant(
            user_id=user_id,
            lyric_id=lyric_id,
            style_prompt=style,
            genre_tag=genre_tag,
            db_path=db_path,
            extra_suno_params=genre_suno_params,
            is_admin=is_admin,
            animate_cover=animate_cover,
            suno_model=suno_model,
        )
        variants.append({"genre": genre_tag, **result})

    return {"variants": variants, "count": len(variants)}
