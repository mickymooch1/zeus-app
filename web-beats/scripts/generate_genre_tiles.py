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

STYLE = (
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


def prompt_for(genre: str, label: str, backend: dict[str, str]) -> str:
    subject = backend.get(genre, "")
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
    todo = [r for r in rows if "--force" in args or not (OUT / f"{r[0]}.webp").exists()]

    print(f"genres: {len(rows)}  ·  to generate: {len(todo)}  ·  "
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
            try:
                img = Image.open(io.BytesIO(generate(prompt, key))).convert("RGB").resize((512, 512), Image.LANCZOS)
                img.save(OUT / f"{g}.webp", "WEBP", quality=86, method=6)
                done += 1
                print(f"✓ {g}")
                break
            except Exception as exc:                      # rate limit / transient — back off and retry
                print(f"  retry {g} ({exc})")
                time.sleep(5 * (attempt + 1))
        else:
            print(f"✗ {g} failed after 3 attempts")
    available = sorted(p.stem for p in OUT.glob("*.webp"))
    MANIFEST.write_text(json.dumps(available) + "\n", encoding="utf-8")
    print(f"generated {done}; {len(available)} tiles available ({MANIFEST.name} updated)")


if __name__ == "__main__":
    main()
