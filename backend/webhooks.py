"""Apiframe v2 + Telegram admin webhook handlers."""
import os
import hmac
import hashlib
import pathlib
import shutil
import sqlite3
import logging
import subprocess
import textwrap
import threading
import requests
import httpx
import db as _db
from PIL import Image, ImageDraw, ImageFont
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("zeus.webhooks")

router = APIRouter()

GENRE_COVER_PROMPTS: dict[str, str] = {
    "bluegrass":      "cinematic album cover, bluegrass band in foreground, rustic American countryside behind, wooden barn, warm golden light, authentic Appalachian aesthetic, banjos and fiddles, ultra detailed professional music artwork",
    "britpop":        "90s Britpop band album cover, Union Jack aesthetic, British indie cool, Oasis Blur era vibe, ultra detailed",
    "indierock":      "indie rock band album cover, underground aesthetic, raw authentic photography, indie cool, ultra detailed",
    "folk":           "folk musician album cover, warm countryside aesthetic, acoustic instruments, earthy natural tones, ultra detailed",
    "acousticballad": "singer songwriter album cover, intimate moody lighting, acoustic guitar, emotional aesthetic, ultra detailed",
    "patriotic":      "patriotic music album cover, Union Jack or national flag, grand ceremonial aesthetic, brass instruments, ultra detailed",
    "blues":        "cinematic album cover, Black blues guitarist in foreground, worn guitar, Mississippi Delta landscape behind, warm sunset, dusty road, deep soulful atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "soul":         "cinematic album cover, Black soul singer performing in foreground, elegant stage lighting, warm golden tones, emotional powerful expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "rnb":          "cinematic album cover, Black RnB artist in foreground, stylish urban setting, moody blue and purple lighting, confident expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "country":      "cinematic album cover, rugged American cowboy with acoustic guitar in foreground, massive speakers either side, Monument Valley canyon sunset behind him, blazing orange and crimson sky, wildflowers and sagebrush, ultra detailed professional music artwork, correct ethnicity",
    "reggae":       "cinematic album cover, beautiful Black woman with long dreadlocks in foreground, massive speakers either side, tropical rainforest and palm trees behind her, Rastafarian colours red gold green, cannabis leaves, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "pop":          "cinematic album cover, glamorous young pop star in sparkling outfit in foreground, massive speakers either side, neon-lit arena stage behind her, enormous LED screens, holographic light beams, confetti explosion, ultra detailed professional music artwork, correct ethnicity",
    "rock":         "cinematic album cover, electric guitarist in leather jacket in foreground, massive speakers either side, rain-soaked rooftop stage behind him, lightning bolt in bruised purple sky, Marshall amp stacks, pyrotechnic fire pillars, ultra detailed professional music artwork, correct ethnicity",
    "hiphop":       "cinematic album cover, Black rapper in gold chain jewellery in foreground, massive speakers either side, New York City rooftop at midnight behind him, glittering Manhattan skyline, graffiti mural wall, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "lofi":         "cinematic album cover, young woman with headphones at desk in foreground, rain-streaked window with soft city bokeh behind her, warm amber desk lamp, cassette tapes and vinyl records, steaming mug, ultra detailed professional music artwork, correct ethnicity",
    "edm":          "cinematic album cover, EDM DJ in neon-lit booth in foreground, massive speakers either side, outdoor festival crowd behind them, towering LED screens blazing with neon fractals, laser beams, fire cannons erupting, ultra detailed professional music artwork, correct ethnicity",
    "acoustic":     "cinematic album cover, female singer-songwriter with vintage acoustic guitar in foreground, Irish meadow at golden hour behind her, rolling green hills and wildflowers, ancient oak trees, ultra detailed professional music artwork, correct ethnicity",
    "irishjig":     "cinematic album cover, Irish céilí dancer in traditional green and gold costume in foreground, stone-walled pub with blazing turf fireplace behind her, fiddles and tin whistles on walls, Guinness on oak tables, ultra detailed professional music artwork, correct ethnicity",
    "celticpunk":       "cinematic album cover, punk band mid-performance in a packed low-ceilinged pub in foreground, fiddle and accordion players alongside electric guitarists, crowd with pints raised singing along, sweat and stage haze, warm amber and green stage lighting, worn wooden floorboards, raucous joyful energy, ultra detailed professional music artwork",
    "irishfolk":    "cinematic album cover, solitary Irish bard with acoustic guitar in foreground, Atlantic cliff edge at dawn behind him, ancient stone ruins, dramatic slate blue sky, waves crashing below, ultra detailed professional music artwork, correct ethnicity",
    "drumandbass":  "cinematic album cover, Black British DJ with headphones in foreground, massive speakers either side, cavernous industrial rave behind him, strobe lights in electric white and ice blue cutting through fog, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "grime":        "cinematic album cover, Black grime MC holding microphone in foreground, massive speakers either side, rain-slicked East London council estate at midnight behind him, tower blocks, cold blue streetlight, graffiti-tagged shutters, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "ukgarage":     "cinematic album cover, stylish Black British MC in designer clothes in foreground, massive speakers either side, gleaming luxury car and neon-lit London club behind him, wet tarmac reflecting electric blue and pink neon, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "jungle":       "cinematic album cover, Black jungle MC on the mic in foreground, massive speakers either side, dark 1993 London warehouse rave behind him, green and gold laser beams through smoke, Jamaican and British flags, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "bassline":     "cinematic album cover, Black British DJ at decks in foreground, massive sub-bass speaker wall either side, underground Sheffield warehouse club behind him, red and amber lighting, raw northern underground energy, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "house":        "cinematic album cover, DJ at the decks in foreground, massive speakers either side, euphoric Ibiza open-air sunrise terrace behind them, blazing coral and gold Mediterranean sky, crowd with hands raised, palm trees, ultra detailed professional music artwork, correct ethnicity",
    "deephouse":    "cinematic album cover, deep house DJ in foreground, intimate underground club behind, warm amber low lighting, minimalist sophisticated aesthetic, deep atmospheric mood, ultra detailed professional music artwork",
    "dancehouse":   "cinematic album cover, DJ performing in foreground, massive festival crowd behind, colourful laser lights, euphoric hands in the air energy, festival main stage aesthetic, ultra detailed professional music artwork",
    "bluessoul":    "cinematic album cover, Black blues soul singer in foreground, warm intimate venue, golden candlelight, raw emotional expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "loversrock":   "cinematic album cover, romantic Black British couple in foreground, moonlit Caribbean beach behind them, tropical flowers, warm pink and gold tiki torch light, turquoise water, palm trees swaying, ultra detailed professional music artwork, Black musicians, NOT white, correct ethnicity",
    "ukdrill":      "cinematic album cover, Black drill artist in designer puffer jacket in foreground, massive speakers either side, dark South London estate at night behind him, cold blue CCTV glow, concrete brutalist tower blocks, barbed wire fencing, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "kpop":         "cinematic album cover, Korean K-pop idol group in colour-coordinated pastel outfits in foreground, massive speakers either side, futuristic Seoul rooftop stage behind them, enormous holographic displays, cherry blossoms and confetti explosion, ultra detailed professional music artwork, Korean musicians, NOT white, correct ethnicity",
    "deepsoulblues": "cinematic album cover, elderly Black woman gospel singer in foreground, powerful dignified expression, old American church or Southern porch behind her, warm amber candlelight, deep emotional atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "niche":          "cinematic album cover, female vocalist in sequined dress in foreground, massive speakers either side, underground Sheffield warehouse club behind her, purple and blue neon, cigarette smoke swirling, raw Yorkshire underground energy, ultra detailed professional music artwork, correct ethnicity",
    "ukstreetsoul":   "cinematic album cover, stylish Black British singer in foreground, sun-drenched Peckham backstreet at golden hour behind him, warm amber street lights, graffiti murals, long shadows across pavement, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "triphop":        "cinematic album cover, lone figure in a smoky dimly lit Bristol underpass, deep blue and grey noir palette, rain-slicked concrete, sparse street light, brooding melancholic atmosphere, ultra detailed professional music artwork",
    "classical":      "cinematic album cover, orchestra conductor with baton raised in foreground, grand concert hall behind him, enormous chandelier blazing overhead, full symphony in black formal wear, gilded balconies packed with audience, ultra detailed professional music artwork, correct ethnicity",
    "indie":          "cinematic album cover, indie guitarist with vintage guitar in foreground, intimate underground music venue behind them, exposed brick walls plastered with tour posters, warm amber and red stage lights, ultra detailed professional music artwork, correct ethnicity",
    "techno":         "cinematic album cover, techno DJ at modular synth wall in foreground, massive speakers either side, dark Berlin underground warehouse behind them, minimal cold white strobes cutting through smoke, exposed concrete pillars, ultra detailed professional music artwork, correct ethnicity",
    "technhouse":     "cinematic album cover, tech house DJ at sleek decks in foreground, massive speakers either side, minimal underground club interior behind them, black and gunmetal grey architecture, cool blue and amber lighting, ultra detailed professional music artwork, correct ethnicity",
    "hyperpop":       "cinematic album cover, young hyperpop artist in oversized candy-coloured clothing in foreground, exploding glitter and shattered pixels around them, electric pink and cyan light rays, holographic butterfly wings and melting emoji faces, glitchy digital chaos, ultra detailed professional music artwork, correct ethnicity",
    "afrobeats":      "cinematic album cover, beautiful Black woman with dreadlocks in foreground, vibrant West African cityscape behind her, massive speakers on each side, tropical plants, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "amapiano":       "cinematic album cover, well-dressed young Black South African DJ in foreground, massive speakers either side, rooftop party in Johannesburg at golden sunset behind him, city skyline blazing amber, log step dancers in vibrant outfits, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "driftphonk":     "cinematic album cover, phonk driver in cap and face mask in foreground, modified Nissan Silvia S15 power-sliding on neon-lit Japanese mountain touge behind him, deep red tail lights, VHS grain and chromatic aberration, dark Memphis aesthetic, ultra detailed professional music artwork, correct ethnicity",
    "jerseyclub":     "cinematic album cover, Jersey Club DJ elevated on booth in foreground, massive speakers either side, packed Newark warehouse party behind them, dancers locked in sharp footwork, strobes, raw East Coast energy, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "afroswing":      "cinematic album cover, stylish Black British man with dreadlocks standing confidently in foreground, London urban street background at golden hour, large speakers either side, warm tropical colours, professional music artwork, ultra detailed, Black musician, NOT white, correct ethnicity",
    "rastadub":       "cinematic album cover, Black Rastafarian musician with long dreadlocks in foreground, massive speakers either side, vibrant tropical Jamaican landscape behind, Rastafarian colours red gold green, cannabis leaves, palm trees, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "deeprotbassline": "cinematic album cover, UK bassline DJ at decks in foreground, dark Northern rave warehouse behind, purple and blue neon lights, heavy bass atmosphere, ultra detailed professional music artwork, correct ethnicity",
    "purebassline":    "cinematic album cover, UK bassline DJ in foreground, energetic Northern England nightclub behind, deep blue and purple club lighting, bass speakers, 4x4 dancefloor energy, gritty underground rave aesthetic, ultra detailed professional music artwork",
    "jazz":            "cinematic album cover, Black jazz musician playing saxophone in foreground, smoky intimate jazz club behind, warm amber and gold lighting, vintage microphone, brick walls, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "electronicfunk":  "cinematic album cover, smooth Black musician with vocoder/talk box in foreground, 80s retro cityscape at night behind, warm amber and purple neon lights, classic electro funk aesthetic, vintage synth equipment, ultra detailed professional music artwork",
    "syntheticpop":    "cinematic album cover, glamorous pop artist in foreground, bright neon pink and blue futuristic cityscape behind, glossy synthetic aesthetic, 80s inspired colour palette, ultra detailed professional music artwork",
    "ragga":           "cinematic album cover, Black Jamaican ragga MC in foreground, vibrant tropical Caribbean setting behind, bright colours, dancehall energy, palm trees, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "dancehall":        "cinematic album cover, dancehall artist with microphone mid-performance in foreground, towering stacked sound system speakers either side, open-air street dance at night behind, vivid green gold and red lighting, crowd with hands raised, tropical humid atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "dubstep":         "cinematic album cover, dubstep producer at decks in foreground, dark industrial warehouse behind, blue and purple neon lights, massive speakers, bass wave visual effects, ultra detailed professional music artwork",
    "bhangra":         "cinematic album cover, Punjabi bhangra dancer in traditional colourful outfit in foreground, vibrant Indian celebration behind, bright yellows and oranges, dhol drums, ultra detailed professional music artwork",
    "rockney":         "cinematic album cover, cheeky Cockney musician in foreground, traditional East London pub behind, warm amber lighting, dartboard and beer, British working class aesthetic, ultra detailed professional music artwork",
    "metal":           "cinematic album cover, heavy metal guitarist in foreground, dark dramatic stage with fire and lightning behind, dark red and black colour scheme, massive amplifiers, ultra detailed professional music artwork",
    "bluesrock":       "cinematic album cover, blues rock band in foreground, dramatic dark stage behind, red and orange stage lighting, electric guitars, raw rock energy, classic rock aesthetic, smoke and spotlights, ultra detailed professional music artwork",
    "hardrock":        "cinematic album cover, hard rock band in foreground, massive stadium stage behind, dramatic spotlights and pyrotechnics, electric guitars and towering amplifiers, raw powerful anthemic rock energy, ultra detailed professional music artwork",
    "punkrock":        "cinematic album cover, punk rock band in foreground, gritty underground dive bar behind, raw DIY aesthetic, torn posters and graffiti, rebellious high energy, ultra detailed professional music artwork",
    "reggaeton":       "cinematic album cover, Latin reggaeton artist in foreground, vibrant urban Latin cityscape behind, warm tropical neon lights, street art, energetic Caribbean atmosphere, ultra detailed professional music artwork",
    "latintrap":       "cinematic album cover, Latin trap artist in foreground, dark moody Latin city at night behind, blue and purple neon lights, rain slicked streets, urban darkness, ultra detailed professional music artwork",
    "rootsreggae":    "cinematic album cover, Jamaican roots reggae musician in foreground, lush tropical Jamaican countryside behind, warm golden sunset, red gold and green colours, natural organic aesthetic, peaceful spiritual atmosphere, ultra detailed professional music artwork",
    "countryamericana": "cinematic album cover, country musician standing in foreground, dusty American highway or field behind, warm golden sunset, pickup truck, Americana aesthetic, authentic Southern US atmosphere, ultra detailed professional music artwork",
    "traditionalcountry": "cinematic album cover, rural American landscape, rustic timber barn, acoustic guitar resting against a fence, warm golden sunset over open fields, vintage country aesthetic, weathered wood and wildflowers, nostalgic film grain, ultra detailed professional music artwork",
    "countrypop":       "cinematic album cover, country pop singer in foreground, warm golden Nashville sunset behind, flowers and open countryside, bright optimistic colours, classic country pop aesthetic, ultra detailed professional music artwork",
    "southemsoul":      "cinematic album cover, Southern soul singer in foreground, warm Southern American church or juke joint behind, amber and golden lighting, Hammond organ visible, Deep South atmosphere, gospel soul aesthetic, ultra detailed professional music artwork",
    "soulrnb":          "cinematic album cover, soul R&B singer in foreground, warm dimly lit intimate setting behind, romantic candles and soft lighting, classic soul aesthetic, elegant sophisticated mood, ultra detailed professional music artwork",
    "orchestralsoul":   "cinematic album cover, deep soul singer in foreground, warm dimly lit romantic setting behind, sweeping strings visible, candles and soft golden lighting, 1970s orchestral soul aesthetic, ultra detailed professional music artwork",
    "classicfunk":      "cinematic album cover, funk band performing in foreground, dramatic 1970s stage behind, warm amber stage lighting, brass instruments, funky energy, classic soul funk aesthetic, ultra detailed professional music artwork",
    "swing":            "cinematic album cover, jazz musician in vintage suit at microphone in foreground, elegant 1940s Art Deco ballroom behind, warm golden vintage stage lighting, chandelier overhead, couples dancing, big band orchestra visible, ultra detailed professional music artwork",
    "vocaljazz":        "cinematic album cover, jazz vocalist leaning into vintage microphone in foreground, smoky intimate jazz supper club behind, warm amber candlelight, upright bass and piano visible, velvet curtains, sophisticated late-night atmosphere, ultra detailed professional music artwork",
    # Added 2026-08-06 — these two genres shipped without cover prompts and were
    # falling through to the generic default, which is exactly the untailored art
    # the Flux restore is meant to fix.
    "scat":             "cinematic album cover, jazz vocalist mid-improvisation at a vintage ribbon microphone in foreground, 1950s big band behind with brass section raised, warm golden stage lighting, upright bass and music stands, smoky supper club atmosphere, ultra detailed professional music artwork, correct ethnicity",
    "opera":            "cinematic album cover, opera singer mid-aria in a dramatic flowing gown in foreground, grand gilded opera house behind, deep red velvet curtains and tiered balconies, enormous crystal chandelier blazing overhead, orchestra pit lit below, single theatrical spotlight, ultra detailed professional music artwork, correct ethnicity",
    "acousticblues":    "cinematic album cover, blues musician playing a steel resonator guitar on a weathered porch in foreground, Mississippi delta cotton fields stretching behind, dusty golden late-afternoon light, slide on the finger, worn wooden boards, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "folkblues":        "cinematic album cover, lone folk singer with acoustic guitar seated in foreground, sparse candlelit room behind, single window with dusk light, bare floorboards and a simple wooden chair, intimate haunting stillness, ultra detailed professional music artwork",
    "roots":            "cinematic album cover, roots musicians with acoustic guitar banjo and fiddle in foreground, old timber barn interior behind, warm hay-lit golden light, hand-painted signage, front-porch Americana atmosphere, ultra detailed professional music artwork",
    "traditionalpop":   "cinematic album cover, classic crooner in elegant tuxedo at vintage microphone in foreground, opulent 1950s ballroom behind, warm golden spotlights, lush orchestral ensemble, glamorous sophisticated vintage atmosphere, ultra detailed professional music artwork",
    "rocknroll":        "cinematic album cover, rock and roll musician with quiff hairstyle at mic in foreground, vibrant 1950s ballroom or diner behind, neon signs blazing red and yellow, jukebox visible, rebellious youthful energy, ultra detailed professional music artwork",
    "trap":             "cinematic album cover, Black trap artist in designer streetwear in foreground, dark Atlanta cityscape at night behind, deep red and purple neon, fog rolling over concrete, 808 energy, urban darkness, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "eastcoasthiphop":  "cinematic album cover, Black hip-hop MC in foreground, New York City skyline at night behind, Brooklyn Bridge and Manhattan skyscrapers, graffiti mural wall, classic boom bap energy, gritty authentic NYC atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "westcoasthiphop":  "cinematic album cover, Black West Coast rapper in foreground, Los Angeles palm-lined boulevard at golden hour behind, lowrider silhouette, warm orange sunset lighting, 90s G-funk aesthetic, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "poprap":           "cinematic album cover, pop rap artist in foreground, bright colourful arena stage behind, massive LED screens, confetti explosion, crossover energy, commercially vibrant stadium atmosphere, ultra detailed professional music artwork, correct ethnicity",
    "synthwave":        "cinematic album cover, synthwave artist in neon-lit retro studio in foreground, 80s retrofuturist cityscape at night behind, purple and pink neon grid horizon, palm trees silhouetted against sunset, glowing synthesizers, VHS aesthetic, ultra detailed professional music artwork",
    "trance":           "cinematic album cover, trance festival mainstage at night, sweeping laser beams over a vast crowd with hands raised, euphoric blue and violet lighting, glowing horizon behind the stage, ultra detailed professional music artwork",
    "gospel":           "cinematic album cover, powerful Black gospel choir in foreground, grand cathedral with warm golden rays of light streaming through stained glass behind, hands raised in praise, joyful spiritual energy, warm amber and gold lighting, ultra detailed professional music artwork, Black musicians, NOT white, correct ethnicity",
    "hymns":            "cinematic album cover, grand cathedral interior, towering pipe organ, stained glass windows with golden light streaming through, reverent and majestic atmosphere, ultra detailed professional music artwork",
    "trapsoul":         "cinematic album cover, Black R&B artist in moody atmospheric studio in foreground, dark intimate setting, soft purple and blue ambient light, emotional introspective atmosphere, rain-streaked window in background, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "meditation":       "serene meditation album cover, peaceful zen garden with still reflecting pool in foreground, soft glowing dawn light, lotus flowers floating on water, mist over mountains behind, calming pastel colours, tranquil healing atmosphere, ultra detailed professional music artwork, NOT dark or intense",
    "ambient":          "serene ambient album cover, vast ethereal atmospheric landscape, soft evolving gradients of light, misty infinite horizon, calming minimalist aesthetic, deep peaceful space, no people, ultra detailed professional music artwork, NOT dark or intense",
    "christmas":        "warm festive Christmas album cover, cosy snow-covered village at night, glowing Christmas tree with golden lights in foreground, children playing in snow, gifts wrapped in ribbon, warm amber window glow, falling snowflakes, joyful holiday warmth, ultra detailed professional music artwork, NOT dark or spooky",
    "corridos":         "cinematic album cover, Mexican corridos musician with acoustic guitar in foreground, vibrant Mexican landscape at sunset behind, cacti silhouettes, warm golden and terracotta tones, traditional colourful decor, heartfelt authentic storytelling atmosphere, ultra detailed professional music artwork",
    "salsa":            "cinematic album cover, Latino salsa band on a vibrant dancefloor, brass section and timbales in foreground, dancers mid-spin behind, warm red and gold lighting, festive Havana nightclub aesthetic, ultra detailed professional music artwork, Latino musicians, correct ethnicity",
    "healingfrequency": "serene healing frequency album cover, glowing singing bowls in foreground, soft sacred geometry light patterns glowing outward, pastel pink and gold healing energy, crystals and gentle light rays, sound bath wellness atmosphere, peaceful calming aesthetic, ultra detailed professional music artwork, NOT dark or intense",
    "naturesounds":     "serene nature soundscape album cover, misty rainforest with gentle rainfall, soft dawn light through lush green trees, a calm winding stream, tranquil natural landscape, no people, deeply calming atmosphere, ultra detailed professional music artwork, NOT dark or intense",
    "whalesong":        "deep ocean album cover, majestic humpback whale gliding through deep blue sea, ethereal rays of sunlight through the water, serene underwater depths, calming oceanic atmosphere, no people, tranquil aesthetic, ultra detailed professional music artwork, NOT dark or intense",
    "cracklingfire":    "cosy fireplace album cover, warm crackling fire in a stone hearth, soft golden glow, comfortable winter cabin interior, blankets and gentle warm light, tranquil relaxing atmosphere, no people, ultra detailed professional music artwork, NOT dark or intense",
    "thunderstorm":     "dramatic thunderstorm album cover, dark storm clouds with forked lightning over a moody landscape, heavy rain, cinematic stormy atmosphere, no people, ultra detailed professional music artwork",
    "oceanwaves":       "serene ocean album cover, gentle waves rolling onto a golden sandy beach at sunset, soft sea foam, distant horizon, calming coastal atmosphere, no people, ultra detailed professional music artwork, NOT dark or intense",
    "forest":           "lush forest album cover, sunlight streaming through tall green trees, a clear stream, mossy woodland, tranquil natural atmosphere, no people, ultra detailed professional music artwork, NOT dark or intense",
    "nightsounds":      "peaceful moonlit night album cover, calm countryside under a starry sky, soft moonlight, silhouetted trees, serene nocturnal atmosphere, no people, ultra detailed professional music artwork, NOT dark or intense",
    "psychedelicguitar": "cinematic album cover, psychedelic rock guitarist in foreground, swirling colourful 1960s psychedelic backdrop, electric guitar, vibrant purple orange lighting, retro psychedelic aesthetic, ultra detailed professional music artwork",
    "saxophone":        "cinematic album cover, saxophone in foreground, warm late-night jazz club backdrop, smoky amber lighting, sophisticated jazz aesthetic, ultra detailed professional music artwork",
    "pianosolo":        "cinematic album cover, grand piano in foreground, intimate concert hall backdrop, soft dramatic lighting, elegant emotive aesthetic, ultra detailed professional music artwork",
    "violinsolo":       "cinematic album cover, violin in foreground, dramatic concert hall backdrop, sweeping golden light, elegant classical aesthetic, ultra detailed professional music artwork",
    "electricbluesguitar": "cinematic album cover, electric blues guitar in foreground, smoky blues club backdrop, warm amber lighting, gritty authentic blues aesthetic, ultra detailed professional music artwork",
    "trumpet":          "cinematic album cover, trumpet in foreground, warm intimate jazz club backdrop, golden amber lighting, sophisticated jazz aesthetic, ultra detailed professional music artwork",
    "flamencoguitar":   "cinematic album cover, flamenco guitar in foreground, warm dramatic Spanish courtyard backdrop, fiery red and amber lighting, passionate Spanish aesthetic, ultra detailed professional music artwork",
    # Scene descriptors only — no artist names and no named cities, venues or
    # landmarks. Ethnicity cues follow the existing entries above, which state
    # them explicitly to stop the image model defaulting away from the culture
    # the genre actually comes from.
    "disco":            "cinematic album cover, glamorous singer in a sequinned jumpsuit in foreground, mirrorball scattering light across a packed dancefloor behind, glowing illuminated floor panels, warm gold and magenta lighting, flared silhouettes mid-dance, ultra detailed professional music artwork",
    "nudisco":          "cinematic album cover, stylish performer in a metallic outfit in foreground, sleek modern club with mirrorball and LED strips behind, glossy reflective surfaces, neon pink and cyan lighting, retro-futuristic aesthetic, ultra detailed professional music artwork",
    "bollywood":        "cinematic album cover, South Asian singer in an ornate embroidered outfit in foreground, vibrant festival scene with marigold garlands and flowing silk drapes behind, saturated crimson gold and emerald jewel tones, swirling dancers, warm dramatic lighting, ultra detailed professional music artwork, South Asian musician, correct ethnicity",
    "boombap":          "cinematic album cover, Black rapper in vintage sportswear and a gold rope chain in foreground, graffiti-covered brick wall and iron fire escape behind, boombox and crates of vinyl records, grainy 90s film photography, muted warm tones, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "citypop":          "cinematic album cover, stylish woman in 80s fashion leaning on a convertible in foreground, neon-lit night skyline and elevated highway behind, warm purple and turquoise glow, chrome details and palm silhouettes, retro anime-inspired illustration style, ultra detailed professional music artwork",
    "futurebass":       "cinematic album cover, young producer silhouetted against a wall of light in foreground, iridescent holographic gradients and prismatic light shards behind, soft pastel pink blue and violet glow, floating geometric shapes, dreamy euphoric atmosphere, ultra detailed professional music artwork",
    "gogo":             "cinematic album cover, Black percussionists mid-performance in foreground, congas and timbales, packed crowd hands in the air behind them, warm stage lights and haze, brass section silhouettes, raw live party energy, ultra detailed professional music artwork, Black musicians, NOT white, correct ethnicity",
    "gqom":             "cinematic album cover, Black dancers caught mid-movement in foreground, raw concrete warehouse space with harsh strobe lighting behind, heavy shadow and stark contrast, dust suspended in the air, towering industrial speaker stacks, gritty underground energy, ultra detailed professional music artwork, Black musicians, NOT white, correct ethnicity",
}

_DEFAULT_COVER_PROMPT = "professional album cover art, cinematic, high quality"

KIDS_COVER_PROMPT = (
    "colourful children's book illustration style, bright cheerful colours, cute cartoon characters, "
    "friendly and fun, no adult themes, child-friendly artwork, Disney Pixar inspired, "
    "warm happy atmosphere, suitable for children aged 2-12"
)


def _add_text_overlay(image_path: str, title: str, artist_name: str = "") -> None:
    """Burn title (and optional artist name) into the bottom quarter of the cover image."""
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bar = ImageDraw.Draw(overlay)
    bar.rectangle([(0, h * 0.75), (w, h)], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(h * 0.07))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(h * 0.055))
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    lines = textwrap.wrap(title.upper(), width=20)
    y = int(h * 0.78)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((w - text_w) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += int(h * 0.09)

    if artist_name:
        artist_line = artist_name[:40]
        bbox = draw.textbbox((0, 0), artist_line, font=font_small)
        text_w = bbox[2] - bbox[0]
        draw.text(((w - text_w) / 2, y), artist_line, font=font_small, fill=(200, 200, 200, 220))

    img.convert("RGB").save(image_path, "JPEG", quality=95)


def _generate_flux_cover(variant_id: int, genre_tag: str | None, title: str = "", artist_name: str = "", style_prompt: str = "") -> str | None:
    """Generate a Flux cover image and save to song storage. Returns public URL or None."""
    import image_generator as _img
    if "children's" in style_prompt.lower() or genre_tag == 'kids_story':
        prompt = KIDS_COVER_PROMPT
    else:
        prompt = GENRE_COVER_PROMPTS.get(genre_tag or "", _DEFAULT_COVER_PROMPT)
    logger.info(
        "Starting Flux cover art for variant_id=%d genre=%r FAL_KEY_len=%d prompt=%.80r",
        variant_id, genre_tag, len(_img.FAL_API_KEY) if _img.FAL_API_KEY else 0, prompt,
    )
    try:
        flux_url = _img.submit_image_generation(prompt, "1:1")
        job_id = flux_url.rsplit("/", 1)[-1].replace(".jpg", "")
        src = pathlib.Path("/data/images") / f"{job_id}.jpg"
        dst = pathlib.Path(STORAGE_PATH) / f"{variant_id}_cover.jpg"
        if not src.exists():
            raise FileNotFoundError(f"Flux image not found at {src} (job_id={job_id}, flux_url={flux_url})")
        shutil.copy2(src, dst)
        _add_text_overlay(str(dst), title or genre_tag or "", artist_name)
        cover_url = f"{PUBLIC_BASE_URL}/{variant_id}_cover.jpg"
        logger.info("Cover art complete for variant_id=%d url=%s", variant_id, cover_url)
        return cover_url
    except Exception:
        logger.exception("Flux cover FAILED for variant_id=%d genre=%r — full traceback above", variant_id, genre_tag)
        return None


def _telegram_post_sync(message: str, image_url: str | None = None) -> None:
    """Sync Telegram post for use inside background threads.

    Automatically splits messages longer than 4096 chars into multiple sends
    so the admin can post lengthy content without truncation.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        return

    _TG_LIMIT = 4096
    _CAPTION_LIMIT = 1024  # Telegram caption limit for photos

    def _send(url: str, payload: dict) -> None:
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code >= 300:
                logger.warning("_telegram_post_sync: Telegram API %d: %s", resp.status_code, resp.text)
            else:
                logger.info("_telegram_post_sync: posted to Telegram channel")
        except Exception as exc:
            logger.warning("_telegram_post_sync: failed — %s", exc)

    def _chunks(text: str, size: int) -> list[str]:
        parts = []
        while text:
            parts.append(text[:size])
            text = text[size:]
        return parts

    if image_url:
        # Send photo with first chunk as caption, remaining chunks as plain messages
        caption = message[:_CAPTION_LIMIT]
        _send(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            {"chat_id": channel, "photo": image_url, "caption": caption, "parse_mode": "HTML"},
        )
        remainder = message[_CAPTION_LIMIT:]
    else:
        remainder = message

    for chunk in _chunks(remainder, _TG_LIMIT):
        _send(
            f"https://api.telegram.org/bot{token}/sendMessage",
            {"chat_id": channel, "text": chunk, "parse_mode": "HTML"},
        )


APIFRAME_API_KEY = os.environ["APIFRAME_API_KEY"]
SIGNING_SECRET = hashlib.sha256(APIFRAME_API_KEY.encode()).hexdigest()
STORAGE_PATH = os.environ["SONG_STORAGE_PATH"]
PUBLIC_BASE_URL = os.environ["SONG_PUBLIC_BASE_URL"]
DB_PATH = os.environ.get("DB_PATH", "/data/zeus.db")
FAL_API_KEY = os.environ.get("FAL_API_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
APIFRAME_BASE = "https://api.apiframe.ai"


# _kling_pipeline() removed 2026-08-06 along with animated covers. A 5s Kling
# clip cost ~$1.40 against a ~35-40p credit, and was ~90% of fal.ai spend for a
# feature users actively turned off. Premium credits live on as the currency for
# stem separation. Existing music videos still play — only new ones stopped.

def _stem_pipeline(variant_id: int, user_id: str, mp3_url: str) -> None:
    """Background thread: submit song to fal.ai Demucs, poll for result, save stem URLs."""
    import time as _time
    logger.info("Stem pipeline START: variant_id=%d user=%s mp3_url=%s", variant_id, user_id, mp3_url)
    db_path = pathlib.Path(DB_PATH)
    try:
        if not FAL_API_KEY:
            logger.warning("Stem pipeline: FAL_API_KEY not set — skipping variant_id=%d", variant_id)
            _db.fail_stems(db_path, variant_id)
            _db.increment_premium_credits(db_path, user_id, 1)
            return

        fal_headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "audio_url": mp3_url,
            "model": "htdemucs",
            "stems": ["vocals", "drums", "bass", "other"],
            "output_format": "mp3",
        }
        resp = requests.post(
            "https://queue.fal.run/fal-ai/demucs",
            headers=fal_headers,
            json=payload,
            timeout=30,
        )
        logger.info("Demucs submit: variant_id=%d status=%d body=%r", variant_id, resp.status_code, resp.text[:400])
        if resp.status_code in (401, 402, 403, 429):
            try:
                import alerts as _alerts
                _alerts.alert_service_error(
                    "fal.ai", resp.status_code, f"Demucs stems (variant_id={variant_id}): {resp.text[:300]}"
                )
            except Exception:
                logger.exception("failed to send fal.ai service-error alert variant_id=%d", variant_id)
        if resp.status_code == 403:
            raise RuntimeError(f"Demucs: 403 Forbidden — fal.ai balance likely exhausted. Body: {resp.text[:200]}")
        resp.raise_for_status()
        body = resp.json()
        status_url = body.get("status_url")
        response_url = body.get("response_url")
        if not status_url or not response_url:
            raise RuntimeError(f"Demucs: missing status_url/response_url: {body!r}")

        logger.info("Demucs submitted: variant_id=%d polling %s", variant_id, status_url)
        poll_headers = {"Authorization": f"Key {FAL_API_KEY}"}
        for attempt in range(1, 37):  # max 36 × 10s = 6 min
            _time.sleep(10)
            sr = requests.get(status_url, headers=poll_headers, timeout=15)
            sr.raise_for_status()
            poll_status = sr.json().get("status", "")
            logger.info("Demucs poll: variant_id=%d attempt=%d status=%s", variant_id, attempt, poll_status)
            if poll_status == "COMPLETED":
                _result_resp = requests.get(response_url, headers=poll_headers, timeout=15)
                _result_resp.raise_for_status()
                result = _result_resp.json()
                vocals_url = result.get("vocals", {}).get("url", "")
                drums_url  = result.get("drums", {}).get("url", "")
                bass_url   = result.get("bass", {}).get("url", "")
                other_url  = result.get("other", {}).get("url", "")
                logger.info(
                    "Demucs COMPLETE: variant_id=%d vocals=%s drums=%s bass=%s other=%s",
                    variant_id, vocals_url[:60], drums_url[:60], bass_url[:60], other_url[:60],
                )
                _db.save_stems(db_path, variant_id,
                               vocals_url=vocals_url, drums_url=drums_url,
                               bass_url=bass_url, other_url=other_url)
                return
            if poll_status in ("FAILED", "ERROR"):
                raise RuntimeError(f"Demucs job failed: {sr.json()!r}")

        raise RuntimeError(f"Demucs timeout after 6 min for variant_id={variant_id}")

    except Exception as exc:
        logger.exception("Stem pipeline FAILED: variant_id=%d error=%s", variant_id, exc)
        _db.fail_stems(db_path, variant_id)
        _db.increment_premium_credits(db_path, user_id, 1)  # refund


def _cover_pipeline(variant_id: int, source_mp3_url: str, lyrics_text: str) -> None:
    """Background thread: upload source song to Apiframe, EXTEND with user lyrics."""
    import time as _time
    logger.info("Cover pipeline START: variant_id=%d source=%s lyrics_len=%d", variant_id, source_mp3_url, len(lyrics_text))
    db_path = pathlib.Path(DB_PATH)
    apiframe_headers_json = {"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"}
    webhook_url = f"{WEBHOOK_URL}?variant_id={variant_id}"
    try:
        # Step 1: Download source mp3
        audio_resp = requests.get(source_mp3_url, timeout=30)
        audio_resp.raise_for_status()
        audio_data = audio_resp.content
        logger.info("Cover pipeline: downloaded %d bytes for variant_id=%d", len(audio_data), variant_id)

        # Step 2: Upload to Apiframe
        # TODO: Cover This Song extend is broken — uses same /v2/music/upload path that 502s
        # Fix: update to api.apiframe.pro/suno-upload + /suno-extend once working endpoint confirmed with Apiframe support
        # Tracked: same fix needed as auto-extend (shelved pending Apiframe endpoint verification)
        # Do not attempt until working URL confirmed — will 502 same as auto-extend
        upload_resp = requests.post(
            f"{APIFRAME_BASE}/v2/music/upload",
            headers={"X-API-Key": APIFRAME_API_KEY},
            files={"audio": ("source.mp3", audio_data, "audio/mpeg")},
            timeout=60,
        )
        logger.info("Cover upload: variant_id=%d status=%d body=%r", variant_id, upload_resp.status_code, upload_resp.text[:300])
        upload_resp.raise_for_status()
        parent_task_id = upload_resp.json().get("task_id")
        if not parent_task_id:
            raise RuntimeError(f"Cover upload: no task_id in response: {upload_resp.json()!r}")

        # Step 3: Extend with user lyrics
        extend_payload = {
            "parent_task_id": parent_task_id,
            "lyrics": lyrics_text,
            "continue_at": 0,
            "webhookUrl": webhook_url,
            "webhookEvents": ["completed", "failed"],
        }
        extend_resp = requests.post(
            f"{APIFRAME_BASE}/v2/music/extend",
            headers=apiframe_headers_json,
            json=extend_payload,
            timeout=30,
        )
        logger.info("Cover extend: variant_id=%d status=%d body=%r", variant_id, extend_resp.status_code, extend_resp.text[:300])
        extend_resp.raise_for_status()
        logger.info("Cover pipeline: EXTEND submitted for variant_id=%d — awaiting webhook", variant_id)

    except Exception as exc:
        logger.exception("Cover pipeline FAILED: variant_id=%d error=%s", variant_id, exc)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status='failed' WHERE id=?", (variant_id,))
            conn.commit()
        finally:
            conn.close()


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        SIGNING_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature_header, expected)


_EXTEND_TARGET_SECONDS = 150
# upload/extend live on the api.apiframe.pro base with an Authorization header — NOT the
# api.apiframe.ai/v2 base used for generation (that base 404s for upload/extend).
_APIFRAME_PRO_BASE = "https://api.apiframe.pro"
# SHELVED: the trigger logic is complete and tested, but the Apiframe extend endpoint
# isn't confirmed working — .ai/v2/music/upload 404s and .pro/suno-upload returns 502.
# Disabled so we don't hammer a dead endpoint. Flip back to True once Apiframe confirms
# a working upload/extend URL (see _maybe_extend_short_song below — flow is ready).
_AUTO_EXTEND_ENABLED = False


def _maybe_extend_short_song(variant_id: int, mp3_path: str, duration: int, style_prompt: str, lyric_id) -> None:
    """Continue a short intermittent/instrumental song to full length via Apiframe
    extend. BEST-EFFORT: the short take is already delivered before this runs, and it
    never raises into the webhook path.

    Mode is inferred from style_prompt (no DB column): intermittent carries the
    "3 minute duration" cue; instrumental carries the INSTRUMENTAL_SUFFIX marker. The
    result is delivered to the SEPARATE /webhooks/apiframe-extend route so it bypasses
    the claim/dedup guards that reject re-processing of a complete variant.
    """
    sp = (style_prompt or "").lower()
    is_intermittent = "full length track, 3 minute duration" in sp
    is_instrumental = "fully instrumental, extended arrangement" in sp
    if not (is_intermittent or is_instrumental):
        return
    if not duration or duration >= _EXTEND_TARGET_SECONDS:
        return
    if not _AUTO_EXTEND_ENABLED:
        logger.info("AUTO_EXTEND skipped — extend endpoint not yet confirmed, shelved pending Apiframe verification")
        return
    mode = "intermittent" if is_intermittent else "instrumental"
    try:
        with open(mp3_path, "rb") as fh:
            audio_data = fh.read()
        up = requests.post(
            f"{_APIFRAME_PRO_BASE}/suno-upload",
            headers={"Authorization": APIFRAME_API_KEY},
            files={"audio": ("source.mp3", audio_data, "audio/mpeg")},
            timeout=60,
        )
        logger.info("AUTO_EXTEND variant_id=%d upload status=%d body=%r", variant_id, up.status_code, up.text[:200])
        up.raise_for_status()
        parent_task_id = up.json().get("task_id")
        if not parent_task_id:
            logger.error("AUTO_EXTEND variant_id=%d: upload returned no task_id: %r", variant_id, up.text[:200])
            return
        lyrics_text = ""
        if is_intermittent and lyric_id:
            try:
                _c = sqlite3.connect(DB_PATH)
                try:
                    _row = _c.execute("SELECT lyrics_text FROM lyrics WHERE id = ?", (lyric_id,)).fetchone()
                    lyrics_text = (_row[0] if _row else "") or ""
                finally:
                    _c.close()
            except Exception:
                lyrics_text = ""
        payload = {
            "parent_task_id": parent_task_id,
            "continue_at": max(0, int(duration) - 1),
            "tags": (style_prompt or "")[:990],
            "webhook_url": f"{WEBHOOK_URL}-extend?variant_id={variant_id}",
        }
        if lyrics_text:
            payload["lyrics"] = lyrics_text
        ext = requests.post(
            f"{_APIFRAME_PRO_BASE}/suno-extend",
            headers={"Authorization": APIFRAME_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        logger.info(
            "AUTO_EXTEND variant_id=%d mode=%s duration=%ss (<%d) → extend submitted "
            "(parent_task=%s continue_at=%d status=%d) body=%r",
            variant_id, mode, duration, _EXTEND_TARGET_SECONDS, parent_task_id,
            payload["continue_at"], ext.status_code, ext.text[:200],
        )
        ext.raise_for_status()
    except Exception as exc:
        logger.exception("AUTO_EXTEND failed variant_id=%d (non-fatal — short song already delivered): %s", variant_id, exc)


@router.post("/webhooks/apiframe-extend")
async def apiframe_extend_webhook(request: Request) -> dict:
    """Apply an AUTO-EXTEND result: swap the variant's audio for the longer version and
    update its duration. SEPARATE from the main webhook on purpose — it must not hit the
    claim/dedup guards that reject re-processing of an already-complete variant."""
    import json as _json
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    if signature and not _verify_signature(raw_body, signature):
        logger.warning("apiframe-extend: signature MISMATCH — rejecting")
        raise HTTPException(401, "Invalid signature")
    try:
        variant_id = int(request.query_params.get("variant_id"))
    except (TypeError, ValueError):
        logger.warning("apiframe-extend: bad variant_id=%r", request.query_params.get("variant_id"))
        return {"ok": False, "status": "bad_variant_id"}
    try:
        body = _json.loads(raw_body)
    except Exception:
        body = {}
    status = (body.get("status") or "").upper()
    if status and status not in ("COMPLETED", "FINISHED"):
        logger.warning("apiframe-extend: variant_id=%d status=%s — not applying", variant_id, status)
        return {"ok": True, "status": "ignored"}
    tracks = (body.get("result") or {}).get("tracks", []) or body.get("songs", [])
    if not tracks:
        logger.error("apiframe-extend: no tracks for variant_id=%d body=%r", variant_id, str(body)[:400])
        return {"ok": True, "status": "no_tracks"}
    track = tracks[0]
    new_url = track.get("audioUrl") or track.get("audio_url")
    new_duration = round(track.get("duration", 0) or 0)
    if not new_url:
        logger.error("apiframe-extend: no audio url in track for variant_id=%d track=%r", variant_id, str(track)[:300])
        return {"ok": True, "status": "no_audio"}
    try:
        dl = requests.get(new_url, timeout=120)
        dl.raise_for_status()
        local_path = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
        with open(local_path, "wb") as fh:
            fh.write(dl.content)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET duration_seconds = ? WHERE id = ?", (new_duration, variant_id))
            conn.commit()
        finally:
            conn.close()
        logger.info("AUTO_EXTEND COMPLETE variant_id=%d → lengthened to %ss, overwrote %s", variant_id, new_duration, local_path)
        return {"ok": True, "status": "extended", "duration": new_duration}
    except Exception as exc:
        logger.exception("apiframe-extend: failed to apply extended audio variant_id=%d: %s", variant_id, exc)
        return {"ok": False, "status": "error_logged"}


_FADE_SECONDS = 8
_FFMPEG_TIMEOUT = 60


def _probe_duration_seconds(mp3_path: str) -> float | None:
    """Exact file duration via ffprobe, in seconds. None on any failure — the
    caller falls back to the Apiframe-reported duration rather than skipping
    the fade over a probe hiccup."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3_path],
            check=True, capture_output=True, timeout=15, text=True,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def _apply_fade_out(mp3_path: str, variant_id, fallback_duration: int | None = None) -> None:
    """Apply an 8s exponential fade-out to the end of mp3_path, in place.

    BEST-EFFORT: a fade is cosmetic. Any failure (ffmpeg missing, probe failure,
    timeout, non-zero exit) logs and returns without raising — same log-first,
    never-block-delivery shape as alerts.py and _maybe_extend_short_song. The
    original file is only replaced after ffmpeg succeeds, so a failed run can
    never leave a corrupt or truncated file in place.

    Locked in at 8s/exponential after listening to 4/6/8/10s comparisons on
    real abrupt-ending songs — 8s was the one that sounded natural, not
    chopped. Measured against 8 real production songs: all were at or within a
    few dB of full mid-track volume until the last 1-3 seconds, one dropped to
    near-total digital silence in the final 0.75s — a hard content stop, not a
    musical decrescendo, which is exactly what this fade is covering for.
    """
    tmp_path = mp3_path + ".fade.tmp"
    try:
        duration = _probe_duration_seconds(mp3_path) or fallback_duration
        if not duration or duration <= _FADE_SECONDS:
            logger.info(
                "FADE_OUT skip variant_id=%s duration=%s (<=%ds or unknown)",
                variant_id, duration, _FADE_SECONDS,
            )
            return
        fade_start = round(duration - _FADE_SECONDS, 3)
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path,
             "-af", f"afade=t=out:st={fade_start}:d={_FADE_SECONDS}:curve=exp",
             "-c:a", "libmp3lame", "-b:a", "192k", tmp_path],
            check=True, capture_output=True, timeout=_FFMPEG_TIMEOUT,
        )
        os.replace(tmp_path, mp3_path)
        logger.info(
            "FADE_OUT applied variant_id=%s duration=%.1fs start=%.1fs", variant_id, duration, fade_start,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        detail = stderr or stdout or str(exc)
        logger.error(
            "FADE_OUT failed variant_id=%s (non-fatal — serving unfaded audio) "
            "returncode=%s stderr=%r stdout=%r",
            variant_id, getattr(exc, "returncode", None), stderr[-2000:], stdout[-500:],
        )
        try:
            import alerts as _alerts
            _alerts.alert_fade_out_failed(variant_id, detail)
        except Exception:
            logger.exception("failed to send fade-out-failed alert variant_id=%s", variant_id)
    except Exception as exc:
        logger.exception("FADE_OUT failed variant_id=%s (non-fatal — serving unfaded audio)", variant_id)
        try:
            import alerts as _alerts
            _alerts.alert_fade_out_failed(variant_id, str(exc))
        except Exception:
            logger.exception("failed to send fade-out-failed alert variant_id=%s", variant_id)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@router.post("/webhooks/apiframe")
async def apiframe_webhook(request: Request):
    # Log BEFORE reading body so this fires even if body parsing fails
    _raw_variant_id = request.query_params.get("variant_id", "MISSING")
    logger.info(
        "WEBHOOK RECEIVED: POST /webhooks/apiframe variant_id=%s header_keys=%s",
        _raw_variant_id,
        sorted(request.headers.keys()),
    )

    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    # If Apiframe sends no signature at all, log a warning and continue rather
    # than rejecting — Apiframe v2 may not sign webhooks with our custom secret.
    if signature:
        if not _verify_signature(raw_body, signature):
            logger.warning(
                "Apiframe webhook: signature MISMATCH for variant_id=%s has_signature=%s - rejecting",
                _raw_variant_id, bool(signature),
            )
            raise HTTPException(401, "Invalid signature")
        logger.info("Apiframe webhook: signature OK for variant_id=%s", _raw_variant_id)
    else:
        logger.warning(
            "Apiframe webhook: no X-Webhook-Signature header for variant_id=%s — "
            "proceeding without verification (Apiframe v2 may not sign)",
            _raw_variant_id,
        )

    body = await request.json()
    variant_id = request.query_params.get("variant_id")
    if not variant_id:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id)
    except ValueError:
        raise HTTPException(400, "variant_id must be an integer")

    event = body.get("event")
    job_status = body.get("status")
    logger.info(
        "Webhook received variant_id=%d status=%s event=%s body_keys=%s",
        variant_id, job_status, event, list(body.keys()),
    )

    # Early check: Apiframe may include a job ID in the body (task_id / jobId).
    # If we've already processed or claimed this job, return immediately.
    _body_job_id = body.get("task_id") or body.get("jobId") or body.get("job_id")
    if _body_job_id:
        _bj_conn = sqlite3.connect(DB_PATH)
        try:
            _bj_done = _bj_conn.execute(
                "SELECT id FROM song_variants WHERE provider_job_id = ? AND status IN ('complete', 'processing')",
                (_body_job_id,),
            ).fetchone()
        finally:
            _bj_conn.close()
        if _bj_done:
            logger.warning(
                "Duplicate webhook ignored early: job_id=%s already %s (variant_id=%d)",
                _body_job_id, "processed/processing", _bj_done[0],
            )
            return {"ok": True, "status": "already_processed"}

    if event == "failed" or job_status == "FAILED":
        error_msg = body.get("error") or body.get("message") or body.get("error_message") or "unknown error"
        logger.error("Apiframe FAILED variant_id=%d error=%s", variant_id, error_msg)
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            _ref_row = cur.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "FAILED")
        try:
            import alerts as _alerts
            _ec = sqlite3.connect(DB_PATH)
            try:
                _row = _ec.execute(
                    "SELECT u.email, l.kids_story FROM song_variants sv "
                    "JOIN users u ON u.id = sv.user_id "
                    "LEFT JOIN lyrics l ON l.id = sv.lyric_id WHERE sv.id = ?",
                    (variant_id,),
                ).fetchone()
                _song_type = "kids-story" if (_row and _row[1]) else "normal"
                _alerts.alert_song_failed(
                    _row[0] if _row else "unknown", variant_id,
                    error_msg=error_msg, song_type=_song_type,
                )
            finally:
                _ec.close()
        except Exception:
            pass
        try:
            import zeus_ops_agent as _ops
            _ops.on_song_failed(variant_id)
        except Exception:
            pass
        return {"ok": True, "status": "failed"}

    # Progress: ignore for now (we only subscribed to completed + failed)
    if event == "progress" or job_status == "PROCESSING":
        return {"ok": True, "status": "progress_ignored"}

    if event != "completed" and job_status != "COMPLETED":
        logger.warning("Unexpected webhook event=%r status=%r body=%r", event, job_status, body)
        return {"ok": True, "status": "unexpected"}

    # Completed — extract tracks from result dict
    result = body.get("result")
    if not result or not isinstance(result, dict):
        logger.error("Completed webhook missing/invalid result: %r", body)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "no_result")
        return {"ok": True, "status": "no_result"}

    tracks = result.get("tracks", [])
    if not tracks:
        logger.error("Completed webhook has no tracks: %r", result)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "no_tracks")
        return {"ok": True, "status": "no_tracks"}

    # Atomic claim: take a SQLite write-reservation lock so only ONE concurrent
    # webhook delivery can proceed past this point.  The losing delivery sees
    # status='processing' and exits before downloading anything — preventing
    # duplicate variants AND duplicate animation-credit deductions.
    _claim_conn = sqlite3.connect(DB_PATH)
    try:
        _claim_conn.execute("BEGIN IMMEDIATE")
        _claim_row = _claim_conn.execute(
            "SELECT status FROM song_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        if _claim_row and _claim_row[0] in ("complete", "processing"):
            _claim_conn.execute("ROLLBACK")
            logger.info(
                "Webhook variant_id=%d already %s — concurrent duplicate ignored",
                variant_id, _claim_row[0],
            )
            return {"ok": True, "status": "already_" + _claim_row[0]}
        _claim_conn.execute(
            "UPDATE song_variants SET status = 'processing' WHERE id = ?", (variant_id,)
        )
        _claim_conn.execute("COMMIT")
    finally:
        _claim_conn.close()

    # Look up the original variant row now — needed for take 2 insertion
    conn = sqlite3.connect(DB_PATH)
    try:
        orig = conn.execute(
            "SELECT lyric_id, user_id, style_prompt, genre_tag, provider_job_id, animate_cover FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    # orig[5] = animate_cover (default True for rows predating this column)
    orig_animate_cover = bool(orig[5]) if orig and orig[5] is not None else True

    os.makedirs(STORAGE_PATH, exist_ok=True)

    # Guard: skip if already complete (duplicate webhook delivery)
    conn = sqlite3.connect(DB_PATH)
    try:
        _existing = conn.execute(
            "SELECT status, mp3_url FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()
    if _existing and _existing[0] == "complete" and _existing[1]:
        logger.info("Apiframe webhook: variant_id=%d already complete — duplicate delivery skipped", variant_id)
        return {"ok": True, "status": "already_complete"}

    # Guard: skip if this Apiframe job ID was already fully processed (catches
    # race conditions where the status hasn't been written yet on first delivery)
    if orig and orig[4]:
        conn = sqlite3.connect(DB_PATH)
        try:
            _job_done = conn.execute(
                "SELECT id FROM song_variants WHERE provider_job_id = ? AND status = 'complete' AND mp3_url IS NOT NULL",
                (orig[4],),
            ).fetchone()
        finally:
            conn.close()
        if _job_done:
            logger.warning(
                "Duplicate webhook ignored: Apiframe job_id=%s already processed as variant_id=%d",
                orig[4], _job_done[0],
            )
            return {"ok": True, "status": "already_processed"}

    # ── Take 1: update existing variant row ──────────────────────────────────
    track1 = tracks[0]
    temp_url1 = track1["audioUrl"]
    duration1 = round(track1.get("duration", 0))

    # Guard: audio_url dedup — skip if this permanent URL was already stored
    audio_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"
    conn = sqlite3.connect(DB_PATH)
    try:
        _audio_exists = conn.execute(
            "SELECT id FROM song_variants WHERE mp3_url = ?", (audio_url1,)
        ).fetchone()
    finally:
        conn.close()
    if _audio_exists:
        logger.warning(
            "Duplicate webhook ignored for audio_url=%s (variant_id=%d)",
            audio_url1, variant_id,
        )
        return {"ok": True, "status": "already_processed"}

    logger.info("Apiframe webhook: downloading take 1 from %s", temp_url1)
    dl1 = requests.get(temp_url1, timeout=120)
    dl1.raise_for_status()
    local_path1 = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
    with open(local_path1, "wb") as fh:
        fh.write(dl1.content)
    if os.path.getsize(local_path1) < 100_000:
        logger.warning(
            "Apiframe webhook: take 1 MP3 suspiciously small (%d bytes) for variant_id=%d — marking failed",
            os.path.getsize(local_path1), variant_id,
        )
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if orig and orig[1]:
            _refund_song_credit(variant_id, orig[1], "small_file")
        try:
            import zeus_ops_agent as _ops
            _ops.on_song_failed(variant_id)
        except Exception:
            pass
        return {"ok": True, "status": "failed", "reason": "mp3_too_small"}
    _apply_fade_out(local_path1, variant_id, duration1)
    permanent_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"

    permanent_image_url1 = None
    temp_image_url1 = track1.get("imageUrl")
    if temp_image_url1:
        logger.info("Apiframe webhook: downloading take 1 cover art from %s", temp_image_url1)
        try:
            img1 = requests.get(temp_image_url1, timeout=60)
            img1.raise_for_status()
            with open(os.path.join(STORAGE_PATH, f"{variant_id}.jpg"), "wb") as fh:
                fh.write(img1.content)
            permanent_image_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.jpg"
        except Exception as exc:
            logger.warning("Apiframe webhook: failed to download take 1 cover art: %s", exc)

    genre_tag = orig[3] if orig else None
    song_title = ""
    artist_name = ""
    if orig:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (orig[0],)).fetchone()
            song_title = row[0] if row and row[0] else ""
            user_row = conn.execute("SELECT artist_name FROM users WHERE id = ?", (orig[1],)).fetchone()
            artist_name = (user_row[0] or "") if user_row else ""
        finally:
            conn.close()
    # Genre-tailored Flux artwork. Restored 2026-08-06 after briefly falling back
    # to Suno's own covers: at ~$0.025 an image this is negligible next to the
    # ~$1.40 Kling clips that were the actual cost problem (now removed), and
    # Suno's generic art was noticeably less matched to the genre.
    #
    # Suno's cover has already been downloaded into permanent_image_url1 above, so
    # it stays as the fallback if Flux fails — a song is never left with no art.
    logger.info("Starting Flux cover art for variant_id=%d genre=%s", variant_id, genre_tag)
    flux_cover1 = _generate_flux_cover(variant_id, genre_tag, song_title, artist_name, orig[2] if orig else "")
    if flux_cover1:
        logger.info("Cover art complete for variant_id=%d url=%s", variant_id, flux_cover1)
        permanent_image_url1 = flux_cover1
    elif permanent_image_url1:
        logger.warning("Flux failed for variant_id=%d — keeping Suno's cover art", variant_id)
    else:
        logger.warning("Cover art FAILED for variant_id=%d — no Flux and no Suno artwork", variant_id)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """UPDATE song_variants
               SET status = 'complete', mp3_url = ?, image_url = ?, duration_seconds = ?,
                   take_number = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (permanent_url1, permanent_image_url1, duration1, variant_id),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Apiframe webhook take 1 complete: variant_id=%d url=%s", variant_id, permanent_url1)

    # Auto-extend short intermittent/instrumental songs to full length. Best-effort:
    # the short take is already delivered above; the extend result is applied by the
    # separate /webhooks/apiframe-extend route (bypassing the claim/dedup guards).
    if orig:
        _maybe_extend_short_song(variant_id, local_path1, duration1, orig[2], orig[0])

    # Animated covers were removed 2026-08-06. A 5s Kling clip cost ~$1.40 while
    # an animation credit sold for ~35-40p, and it was ~90% of fal.ai spend for a
    # feature users actively switched off. Premium credits remain — they are the
    # currency for stem separation. Existing music videos still play; only new
    # generation stopped.

    # ── Take 2: insert new row, download second track if present ─────────────
    take2_variant_id = None
    permanent_url2 = None

    if len(tracks) >= 2 and orig:
        track2 = tracks[1]
        temp_url2 = track2["audioUrl"]
        duration2 = round(track2.get("duration", 0))

        # Guard: skip if a take-2 row already exists for this Apiframe job
        conn = sqlite3.connect(DB_PATH)
        try:
            _t2 = conn.execute(
                "SELECT id FROM song_variants WHERE provider_job_id = ? AND take_number = 2",
                (orig[4],),
            ).fetchone()
        finally:
            conn.close()

        if _t2:
            logger.info("Apiframe webhook: take 2 already exists for job=%s — duplicate delivery skipped", orig[4])
        else:
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.cursor()
                # Atomic check-and-insert: SQLite serialises writes so WHERE NOT EXISTS
                # prevents a concurrent duplicate webhook from inserting a second take-2 row.
                cur.execute(
                    """INSERT INTO song_variants
                       (lyric_id, user_id, style_prompt, genre_tag, provider_job_id,
                        take_number, status, duration_seconds, completed_at)
                       SELECT ?, ?, ?, ?, ?, 2, 'complete', ?, CURRENT_TIMESTAMP
                       WHERE NOT EXISTS (
                           SELECT 1 FROM song_variants
                           WHERE provider_job_id = ? AND take_number = 2
                       )""",
                    (orig[0], orig[1], orig[2], orig[3], orig[4], duration2, orig[4]),
                )
                take2_variant_id = cur.lastrowid if cur.rowcount > 0 else None
                conn.commit()
            finally:
                conn.close()

            if not take2_variant_id:
                logger.warning(
                    "Apiframe webhook: take 2 already exists (atomic check) for job=%s — duplicate skipped",
                    orig[4],
                )
            else:
                logger.info("Apiframe webhook: downloading take 2 from %s", temp_url2)
                dl2 = requests.get(temp_url2, timeout=120)
                dl2.raise_for_status()
                local_path2 = os.path.join(STORAGE_PATH, f"{take2_variant_id}.mp3")
                with open(local_path2, "wb") as fh:
                    fh.write(dl2.content)
                if os.path.getsize(local_path2) < 100_000:
                    logger.warning(
                        "Apiframe webhook: take 2 MP3 suspiciously small (%d bytes) for variant_id=%d — marking failed",
                        os.path.getsize(local_path2), take2_variant_id,
                    )
                    conn = sqlite3.connect(DB_PATH)
                    try:
                        conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (take2_variant_id,))
                        conn.commit()
                    finally:
                        conn.close()
                    take2_variant_id = None
                else:
                    _apply_fade_out(local_path2, take2_variant_id, duration2)
                    permanent_url2 = f"{PUBLIC_BASE_URL}/{take2_variant_id}.mp3"

                    permanent_image_url2 = None
                    temp_image_url2 = track2.get("imageUrl")
                    if temp_image_url2:
                        logger.info("Apiframe webhook: downloading take 2 cover art from %s", temp_image_url2)
                        try:
                            img2 = requests.get(temp_image_url2, timeout=60)
                            img2.raise_for_status()
                            _take2_cover_path = os.path.join(STORAGE_PATH, f"{take2_variant_id}.jpg")
                            with open(_take2_cover_path, "wb") as fh:
                                fh.write(img2.content)
                            # Take 2 now ships this image rather than a Flux one, so it
                            # needs the same burned-in title/artist bar that
                            # _generate_flux_cover applies — otherwise the two takes of
                            # the same song look inconsistent. Guarded: a failed overlay
                            # must cost us the text, never the cover.
                            try:
                                _add_text_overlay(_take2_cover_path, song_title or genre_tag or "", artist_name)
                            except Exception as exc:
                                logger.warning("Take 2 cover overlay failed for variant_id=%d (keeping plain art): %s",
                                               take2_variant_id, exc)
                            permanent_image_url2 = f"{PUBLIC_BASE_URL}/{take2_variant_id}.jpg"
                        except Exception as exc:
                            logger.warning("Apiframe webhook: failed to download take 2 cover art: %s", exc)

                    # Take 2 keeps Suno's own cover; only take 1 gets bespoke Flux art.
                    # This halves fal.ai cover spend (2 paid images per song → 1) using
                    # artwork that was already being downloaded above and then thrown
                    # away by the Flux overwrite a few lines later.
                    #
                    # Flux remains the FALLBACK here so take 2 is never left blank: if
                    # Suno sent no artwork, or the download above failed, we pay for one
                    # image rather than ship a song with no cover at all.
                    if permanent_image_url2:
                        logger.info("Cover art for variant_id=%d (take2): using Suno artwork %s (no Flux call)",
                                    take2_variant_id, permanent_image_url2)
                    else:
                        logger.info("Take 2 has no Suno artwork — falling back to Flux for variant_id=%d genre=%s",
                                    take2_variant_id, genre_tag)
                        flux_cover2 = _generate_flux_cover(take2_variant_id, genre_tag, song_title, artist_name, orig[2] if orig else "")
                        if flux_cover2:
                            logger.info("Cover art complete for variant_id=%d (take2, Flux fallback) url=%s",
                                        take2_variant_id, flux_cover2)
                            permanent_image_url2 = flux_cover2
                        else:
                            logger.warning("Cover art FAILED for variant_id=%d (take2) — no Suno artwork and Flux failed",
                                           take2_variant_id)

                    conn = sqlite3.connect(DB_PATH)
                    try:
                        conn.execute(
                            "UPDATE song_variants SET mp3_url = ?, image_url = ? WHERE id = ?",
                            (permanent_url2, permanent_image_url2, take2_variant_id),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    logger.info("Apiframe webhook take 2 complete: variant_id=%d url=%s", take2_variant_id, permanent_url2)


    payload = {"ok": True, "status": "complete", "take1_url": permanent_url1}
    if take2_variant_id:
        payload["take2_variant_id"] = take2_variant_id
        payload["take2_url"] = permanent_url2
    return payload


# ── Telegram admin bot ───────────────────────────────────────────────────────

async def _tg_send(token: str, chat_id: int, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )


async def _tg_send_photo(token: str, chat_id: int, photo: str, caption: str) -> None:
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            json={"chat_id": chat_id, "photo": photo, "caption": caption,
                  "parse_mode": "HTML"},
        )


async def _handle_post_song(token: str, chat_id: int, variant_id: int) -> None:
    """Look up song variant and post to channel, then confirm to admin."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT sv.id, sv.mp3_url, sv.image_url, l.title
               FROM song_variants sv
               LEFT JOIN lyrics l ON l.id = sv.lyric_id
               WHERE sv.id = ?""",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        await _tg_send(token, chat_id, f"❌ Variant {variant_id} not found")
        return

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    title = row["title"] or f"Song #{variant_id}"
    mp3_url = row["mp3_url"] or ""
    image_url = row["image_url"] or ""

    caption = f"🎵 <b>{title}</b>\n\n🎧 <a href=\"{mp3_url}\">Listen</a>"
    if image_url:
        _telegram_post_sync(caption, image_url)
    else:
        _telegram_post_sync(caption)

    await _tg_send(token, chat_id,
                   f"✅ Posted <b>{title}</b> to {channel}")


@router.post("/webhooks/telegram")
async def telegram_admin_webhook(request: Request):
    """Unified Telegram webhook — admin commands for TELEGRAM_ADMIN_USER_ID,
    Porick chatbot for everyone else."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {"ok": True}

    message = body.get("message") or body.get("edited_message") or {}
    if not message:
        return {"ok": True}

    chat_id: int = message.get("chat", {}).get("id")
    from_id: int = message.get("from", {}).get("id")
    text: str = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    logger.info("Telegram message from user_id=%s text=%r", from_id, text[:200])

    admin_uid_str = os.environ.get("TELEGRAM_ADMIN_USER_ID", "").strip()

    # ── Admin path ────────────────────────────────────────────────────────────
    if admin_uid_str and str(from_id) == admin_uid_str:
        logger.info("telegram_admin: command from admin uid=%s: %r", from_id, text[:80])
        import telegram_admin as _tg_admin
        result = _tg_admin.parse_and_run(text, chat_id=str(chat_id))

        if result.startswith("__POST__:"):
            msg = result[len("__POST__:"):]
            _telegram_post_sync(msg)
            await _tg_send(token, chat_id, "✅ Posted to channel")

        elif result.startswith("__POST_SONG__:"):
            vid = int(result.split(":", 1)[1])
            await _handle_post_song(token, chat_id, vid)

        elif result.startswith("__AI__:"):
            user_text = result[len("__AI__:"):]
            try:
                from zeus_agent import get_anthropic_client
                ai_resp = await get_anthropic_client().messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                    system=(
                        "You are Zeus, an AI music assistant for Zeus Beats. "
                        "Help users with song ideas, genre suggestions, lyrics inspiration "
                        "and questions about the Zeus Beats platform at zeusbeats.com. "
                        "Keep responses concise and friendly."
                    ),
                    messages=[{"role": "user", "content": user_text}],
                )
                reply = ai_resp.content[0].text
            except Exception as exc:
                logger.exception("telegram_admin: Claude fallback failed")
                reply = "Sorry, I'm having trouble right now. Try again in a moment."
            await _tg_send(token, chat_id, reply[:4000])

        else:
            # Telegram message limit is 4096 chars
            await _tg_send(token, chat_id, result[:4000])

        return {"ok": True}

    # ── Non-admin: reject with Unauthorised ───────────────────────────────────
    if admin_uid_str:
        logger.warning("telegram_admin: rejected uid=%s (not admin)", from_id)
        await _tg_send(token, chat_id, "Unauthorised")
        return {"ok": True}

    # ── No admin configured: fall through silently (existing Porick logic
    #    in /api/telegram/webhook handles public users) ─────────────────────
    return {"ok": True}


def _refund_song_credit(variant_id: int, user_id: str, reason: str) -> None:
    try:
        _db.increment_song_credits(DB_PATH, user_id, 1)
        logger.info("Credit refunded: variant_id=%d user_id=%s reason=%s", variant_id, user_id, reason)
    except Exception:
        logger.exception("Failed to refund credit: variant_id=%d user_id=%s", variant_id, user_id)


@router.post("/webhooks/cometapi")
async def cometapi_webhook(request: Request):
    """Callback handler for CometAPI persona-based song generations."""
    _raw_variant_id = request.query_params.get("variant_id", "MISSING")
    logger.info("COMETAPI WEBHOOK: variant_id=%s", _raw_variant_id)

    body = await request.json()

    variant_id = request.query_params.get("variant_id")
    if not variant_id:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id)
    except ValueError:
        raise HTTPException(400, "variant_id must be an integer")

    token = request.query_params.get("token", "")
    import cometapi as _comet
    if not _comet.verify_webhook_token(variant_id, token):
        logger.warning("CometAPI webhook: invalid token for variant_id=%d — rejecting", variant_id)
        raise HTTPException(401, "Invalid webhook token")

    status = body.get("status", "")
    data = body.get("data", [])
    logger.info("CometAPI webhook: variant_id=%d status=%s", variant_id, status)

    if status == "FAILED":
        logger.error("CometAPI webhook FAILED for variant_id=%d body=%r", variant_id, body)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "FAILED")
        return {"ok": True, "status": "failed"}

    if status != "SUCCESS":
        logger.warning("CometAPI unexpected status=%r variant_id=%d", status, variant_id)
        return {"ok": True, "status": "unexpected"}

    # Atomic claim — prevent duplicate deliveries from processing twice
    _claim_conn = sqlite3.connect(DB_PATH)
    try:
        _claim_conn.execute("BEGIN IMMEDIATE")
        _claim_row = _claim_conn.execute(
            "SELECT status FROM song_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        if _claim_row and _claim_row[0] in ("complete", "processing"):
            _claim_conn.execute("ROLLBACK")
            logger.info("CometAPI webhook: variant_id=%d already %s — ignoring duplicate", variant_id, _claim_row[0])
            return {"ok": True, "status": "already_" + _claim_row[0]}
        _claim_conn.execute("UPDATE song_variants SET status = 'processing' WHERE id = ?", (variant_id,))
        _claim_conn.execute("COMMIT")
    finally:
        _claim_conn.close()

    tracks = data if isinstance(data, list) else [data]
    if not tracks:
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "no_data")
        return {"ok": True, "status": "no_data"}

    track = tracks[0]
    audio_url = track.get("audio_url") or track.get("audioUrl")
    duration = round(float(track.get("duration", 0) or 0))

    if not audio_url:
        logger.error("CometAPI webhook: no audio_url in data: %r", track)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "no_audio_url")
        return {"ok": True, "status": "no_audio_url"}

    # Fetch variant metadata for cover art + animation
    conn = sqlite3.connect(DB_PATH)
    try:
        orig = conn.execute(
            "SELECT lyric_id, user_id, genre_tag, animate_cover, style_prompt FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    animate_cover = bool(orig[3]) if orig and orig[3] is not None else True
    genre_tag = orig[2] if orig else None
    orig_style_prompt = (orig[4] or "") if orig else ""
    song_title = ""
    artist_name = ""
    if orig:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (orig[0],)).fetchone()
            song_title = row[0] if row and row[0] else ""
            ur = conn.execute("SELECT artist_name FROM users WHERE id = ?", (orig[1],)).fetchone()
            artist_name = (ur[0] or "") if ur else ""
        finally:
            conn.close()

    os.makedirs(STORAGE_PATH, exist_ok=True)
    try:
        logger.info("CometAPI webhook: downloading MP3 from %s", audio_url)
        dl = requests.get(audio_url, timeout=120)
        dl.raise_for_status()
        local_path = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
        with open(local_path, "wb") as fh:
            fh.write(dl.content)
    except Exception as _dl_exc:
        logger.exception("CometAPI webhook: MP3 download failed variant_id=%d url=%s: %s", variant_id, audio_url, _dl_exc)
        _fail_conn = sqlite3.connect(DB_PATH)
        try:
            _fail_conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            _fail_conn.commit()
        finally:
            _fail_conn.close()
        if orig and orig[1]:
            _refund_song_credit(variant_id, orig[1], "download_failed")
        return {"ok": True, "status": "download_failed"}

    if os.path.getsize(local_path) < 100_000:
        logger.warning("CometAPI webhook: MP3 too small (%d bytes) variant_id=%d", os.path.getsize(local_path), variant_id)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if orig and orig[1]:
            _refund_song_credit(variant_id, orig[1], "small_file")
        return {"ok": True, "status": "small_file"}

    public_mp3_url = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"

    # Generate cover art via Flux (same as Apiframe path)
    flux_cover = _generate_flux_cover(variant_id, genre_tag, song_title, artist_name, orig_style_prompt)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """UPDATE song_variants
               SET mp3_url = ?, image_url = ?, duration_seconds = ?,
                   status = 'complete', take_number = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (public_mp3_url, flux_cover, duration, variant_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("CometAPI webhook: complete variant_id=%d mp3=%s", variant_id, public_mp3_url)

    # Animated covers removed 2026-08-06 — see the note in the Apiframe webhook.

    return {"ok": True, "status": "complete"}


@router.post("/webhooks/goapi")
async def goapi_webhook(request: Request):
    """Callback handler for GoAPI (Suno fallback) song generations."""
    _raw_variant_id = request.query_params.get("variant_id", "MISSING")
    logger.info("GOAPI WEBHOOK: variant_id=%s", _raw_variant_id)

    body = await request.json()
    logger.info("GOAPI WEBHOOK body_keys=%s raw=%r", list(body.keys()), str(body)[:500])

    variant_id = request.query_params.get("variant_id")
    if not variant_id:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id)
    except ValueError:
        raise HTTPException(400, "variant_id must be an integer")

    # GoAPI status can be at top level or nested inside data
    data = body.get("data") or {}
    status = body.get("status") or data.get("status") or ""
    task_id = data.get("task_id") or body.get("task_id") or ""
    logger.info("GoAPI webhook: variant_id=%d task_id=%s status=%s", variant_id, task_id, status)

    status_lower = status.lower()
    if status_lower in ("failed", "error"):
        logger.error("GoAPI webhook FAILED for variant_id=%d body=%r", variant_id, body)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "FAILED")
        return {"ok": True, "status": "failed"}

    if status_lower not in ("success", "completed", "succeed"):
        logger.warning("GoAPI unexpected status=%r variant_id=%d", status, variant_id)
        return {"ok": True, "status": "unexpected"}

    # Extract audio URL from GoAPI clips structure (dict or list)
    clips = data.get("clips") or {}
    audio_url = None
    duration = 0
    if isinstance(clips, dict):
        for _clip_id, clip in clips.items():
            audio_url = clip.get("audio_url") or clip.get("audioUrl")
            duration = round(float(clip.get("duration", 0) or 0))
            break
    elif isinstance(clips, list) and clips:
        clip = clips[0]
        audio_url = clip.get("audio_url") or clip.get("audioUrl")
        duration = round(float(clip.get("duration", 0) or 0))

    if not audio_url:
        logger.error("GoAPI webhook: no audio_url found in clips — data=%r", data)
        conn = sqlite3.connect(DB_PATH)
        try:
            _ref_row = conn.execute("SELECT user_id, status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if _ref_row and _ref_row[1] != 'failed' and _ref_row[0]:
            _refund_song_credit(variant_id, _ref_row[0], "no_audio_url")
        return {"ok": True, "status": "no_audio_url"}

    # Atomic claim — prevent duplicate deliveries from processing twice
    _claim_conn = sqlite3.connect(DB_PATH)
    try:
        _claim_conn.execute("BEGIN IMMEDIATE")
        _claim_row = _claim_conn.execute(
            "SELECT status FROM song_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        if _claim_row and _claim_row[0] in ("complete", "processing"):
            _claim_conn.execute("ROLLBACK")
            logger.info("GoAPI webhook: variant_id=%d already %s — ignoring duplicate", variant_id, _claim_row[0])
            return {"ok": True, "status": "already_" + _claim_row[0]}
        _claim_conn.execute("UPDATE song_variants SET status = 'processing' WHERE id = ?", (variant_id,))
        _claim_conn.execute("COMMIT")
    finally:
        _claim_conn.close()

    # Fetch variant metadata for cover art + animation
    conn = sqlite3.connect(DB_PATH)
    try:
        orig = conn.execute(
            "SELECT lyric_id, user_id, genre_tag, animate_cover, style_prompt FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    animate_cover = bool(orig[3]) if orig and orig[3] is not None else True
    genre_tag = orig[2] if orig else None
    orig_style_prompt = (orig[4] or "") if orig else ""
    song_title = ""
    artist_name = ""
    if orig:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (orig[0],)).fetchone()
            song_title = row[0] if row and row[0] else ""
            ur = conn.execute("SELECT artist_name FROM users WHERE id = ?", (orig[1],)).fetchone()
            artist_name = (ur[0] or "") if ur else ""
        finally:
            conn.close()

    os.makedirs(STORAGE_PATH, exist_ok=True)
    try:
        logger.info("GoAPI webhook: downloading MP3 from %s", audio_url)
        dl = requests.get(audio_url, timeout=120)
        dl.raise_for_status()
        local_path = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
        with open(local_path, "wb") as fh:
            fh.write(dl.content)
    except Exception as _dl_exc:
        logger.exception("GoAPI webhook: MP3 download failed variant_id=%d: %s", variant_id, _dl_exc)
        _fail_conn = sqlite3.connect(DB_PATH)
        try:
            _fail_conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            _fail_conn.commit()
        finally:
            _fail_conn.close()
        if orig and orig[1]:
            _refund_song_credit(variant_id, orig[1], "download_failed")
        return {"ok": True, "status": "download_failed"}

    if os.path.getsize(local_path) < 100_000:
        logger.warning("GoAPI webhook: MP3 too small (%d bytes) variant_id=%d — marking failed", os.path.getsize(local_path), variant_id)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        if orig and orig[1]:
            _refund_song_credit(variant_id, orig[1], "small_file")
        return {"ok": True, "status": "small_file"}

    public_mp3_url = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"
    flux_cover = _generate_flux_cover(variant_id, genre_tag, song_title, artist_name, orig_style_prompt)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """UPDATE song_variants
               SET mp3_url = ?, image_url = ?, duration_seconds = ?,
                   status = 'complete', take_number = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (public_mp3_url, flux_cover, duration, variant_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("GoAPI webhook: complete variant_id=%d mp3=%s", variant_id, public_mp3_url)

    # Animated covers removed 2026-08-06 — see the note in the Apiframe webhook.

    return {"ok": True, "status": "complete"}
