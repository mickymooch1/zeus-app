"""Genre tile artwork for the /songs genre picker (2026-10-01).

One square image per genre in the neon style from design-ref/DESIGN.md,
generated with Flux (fal.ai, same model the backend uses for song covers) and
stored as static files: public/images/genres/<genre>.webp (512×512). The
list of genres that have a tile goes to src/utils/genreTiles.manifest.json,
which the picker imports so it only ever requests images that exist.

Run from web-beats/:
  py scripts/generate_genre_tiles.py                 # DRY RUN: prompts + cost, no API calls
  FAL_KEY=... py scripts/generate_genre_tiles.py --generate --only grime,jazz,opera
  FAL_KEY=... py scripts/generate_genre_tiles.py --generate          # all missing tiles
Existing tiles are skipped (resumable); --force regenerates.
--out DIR writes candidates to DIR for review (live tiles and manifest untouched).
"""
from __future__ import annotations

import ast
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent          # web-beats/
OUT = ROOT / "public" / "images" / "genres"
WEBHOOKS = ROOT.parent / "backend" / "webhooks.py"
MANIFEST = ROOT / "src" / "utils" / "genreTiles.manifest.json"
MODEL_URL = "https://fal.run/fal-ai/flux/dev"
COST_PER_IMAGE_USD = 0.025                                      # fal flux/dev, 1 MP (1024×1024)

# The no-text and night/neon instructions lead because Flux has no negative prompt
# and weights early words most: lettering and warm sunsets crept into the first batch.
STYLE = (
    "no text, no letters, no signs, no lettering anywhere, plain unmarked walls and surfaces, "
    "night-time scene lit only by electric cyan and violet neon light, no sunset, no daylight, "
    "square music genre artwork, dark navy background (#04060c), electric cyan neon glow (#16c8ff) "
    "with small violet accents (#7b5cff), cinematic rim lighting, high contrast, moody, glossy, "
    "centered subject, ultra detailed, no text, no letters, no words, no logos, no watermark"
)

# Phrases in the backend's cover prompts that name real artists/bands or ask for
# text — removed so tiles never imitate a real act or carry lettering.
SCRUB = [
    r"Oasis Blur era vibe", r"\bOasis\b", r"\bBlur\b", r"Bob Marley\w*", r"Elvis\w*", r"Beatles\w*",
    r"Michael Jackson\w*", r"Taylor Swift\w*", r"Drake\b", r"Stormzy\b", r"Skepta\b", r"Wiley\b",
    r"album cover,?", r"album artwork,?", r"professional music artwork,?", r"ultra detailed,?",
    r"correct ethnicity,?", r"text[^,]*,?",
]


def genres_and_labels() -> list[tuple[str, str, str]]:
    """(genre, label, category id) for every genre in the picker, from utils/genres.js."""
    js = r"""
      import('./src/utils/genres.js').then(m => {
        const out = [];
        for (const c of m.GENRE_CATEGORIES) for (const g of c.genres) out.push([g, m.GENRE_LABEL[g] || g, c.id]);
        console.log(JSON.stringify(out));
      });"""
    res = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, check=True)
    seen, rows = set(), []
    for g, label, cat in json.loads(res.stdout):
        if g not in seen:
            seen.add(g)
            rows.append((g, label, cat))
    return rows


def backend_prompts() -> dict[str, str]:
    tree = ast.parse(WEBHOOKS.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "GENRE_COVER_PROMPTS":
            return ast.literal_eval(node.value)
    return {}


# Tile-only subjects. The song-cover prompts these genres borrow from ask for neon
# signs, sunsets or warm golden light, which Flux follows over the shared STYLE —
# so the tiles came out with garbled lettering or off-palette. Used only here; the
# song covers themselves are untouched.
TILE_SUBJECTS = {
    "chicagoblues": "harmonica player and electric guitarist on a small stage in a smoky blues club, "
                    "bare dark brick walls, blue stage spotlights, vintage microphone",
    "rocknroll": "rock and roll singer with a quiff and electric guitar at a chrome vintage microphone, "
                 "glowing jukebox, checkered dance floor, dark ballroom",
    "brazilianphonk": "lowered car on a wet hillside favela street at night, bass speakers in the open boot, "
                      "glowing cyan underglow, mist",
    "ukgarage": "stylish MC in designer clothes holding a microphone beside stacked speakers and a sleek "
                "unbranded sports car, plain wet street at night with bare dark brick walls, no shops, "
                "no shopfronts, no windows with displays",
    "corridos": "Mexican corridos musician with a twelve-string guitar sitting on a wooden crate, "
                "cacti silhouettes in a desert under a starry cyan night sky",
    "country": "cowboy with an acoustic guitar standing on a desert road at night, "
               "canyon silhouettes under a cyan moonlit sky",
    "countryamericana": "lone cowboy beside a vintage pickup truck on an empty highway at night, "
                        "headlights glowing, moonlit sky",
    "countryballad": "lone figure with a guitar walking down a long empty country road at night, "
                     "telephone poles, cyan moonlight",
    "countrypop": "country pop singer in a cowboy hat with an acoustic guitar on a stage strung with cyan "
                  "fairy lights, wildflowers in front",
    "countryrap": "rapper in a cap and chain sitting on the tailgate of a pickup truck in a field at night, "
                  "glowing cyan tail lights",
    "countrysoul": "acoustic guitar leaning on a porch rocking chair of a wooden farmhouse at night, "
                   "fireflies, moonlit fields",
    "traditionalcountry": "acoustic guitar leaning against an old wooden barn at night, "
                          "split-rail fence, moonlit prairie",
    "christmas": "Christmas tree lit with cyan and violet lights in a snowy village street at night, "
                 "gifts under the tree, falling snow",
}


def prompt_for(genre: str, label: str, backend: dict[str, str]) -> str:
    subject = TILE_SUBJECTS.get(genre) or backend.get(genre, "")
    for pat in SCRUB:
        subject = re.sub(pat, "", subject, flags=re.IGNORECASE)
    subject = re.sub(r"\s+", " ", subject)
    subject = re.sub(r"\s*,\s*(,\s*)+", ", ", subject).strip(" ,")
    base = f"{label} music"
    return f"{base}: {subject}, {STYLE}" if subject else f"{base}, the instruments and atmosphere of {label}, {STYLE}"


def generate(prompt: str, key: str) -> bytes:
    body = json.dumps({"prompt": prompt, "image_size": "square_hd", "num_images": 1,
                       "num_inference_steps": 28, "enable_safety_checker": True}).encode()
    req = urllib.request.Request(MODEL_URL, data=body, method="POST",
                                 headers={"Authorization": f"Key {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        url = json.load(r)["images"][0]["url"]
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def main() -> None:
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    rows = [r for r in genres_and_labels() if only is None or r[0] in only]
    backend = backend_prompts()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT
    if "--out" in args:                       # candidates for review: never touch live tiles/manifest
        out = pathlib.Path(args[args.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
    todo = [r for r in rows if "--force" in args or not (out / f"{r[0]}.webp").exists()]

    print(f"genres: {len(rows)}  |  to generate: {len(todo)}  |  "
          f"est. cost ${len(todo) * COST_PER_IMAGE_USD:.2f} (at ${COST_PER_IMAGE_USD}/image)")
    print(f"backend prompt available for {sum(1 for r in rows if r[0] in backend)}/{len(rows)}; the rest use a generic subject")
    if "--generate" not in args:
        for g, label, _ in todo[:12]:
            print(f"\n[{g}] {prompt_for(g, label, backend)}")
        print("\nDRY RUN — no API calls made. Add --generate (and FAL_KEY) to create images.")
        return

    key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if not key:
        sys.exit("FAL_KEY (or FAL_API_KEY) is not set — nothing generated.")
    from PIL import Image
    done = 0
    for g, label, _ in todo:
        prompt = prompt_for(g, label, backend)
        for attempt in range(3):
            # Only the paid API call and the save are retried — a retry costs money,
            # so nothing else (e.g. console output) may raise inside this block.
            try:
                img = Image.open(io.BytesIO(generate(prompt, key))).convert("RGB").resize((512, 512), Image.LANCZOS)
                img.save(out / f"{g}.webp", "WEBP", quality=86, method=6)
            except Exception as exc:                      # rate limit / transient — back off and retry
                print(f"  retry {g} ({exc})")
                time.sleep(5 * (attempt + 1))
                continue
            done += 1
            print(f"ok  {g}")
            break
        else:
            print(f"FAILED {g} after 3 attempts")
    if out != OUT:
        print(f"generated {done} candidate(s) in {out}; live tiles and manifest untouched")
        return
    available = sorted(p.stem for p in OUT.glob("*.webp"))
    MANIFEST.write_text(json.dumps(available) + "\n", encoding="utf-8")
    print(f"generated {done}; {len(available)} tiles available ({MANIFEST.name} updated)")


if __name__ == "__main__":
    main()
