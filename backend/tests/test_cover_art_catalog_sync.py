"""3-way guard: backend COVER_ART_STYLE_MAP <-> web genres.js <-> iOS CreateSongScreen.tsx."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from song_genres import COVER_ART_STYLE_MAP  # noqa: E402

WEB = (ROOT / "web-beats" / "src" / "utils" / "genres.js").read_text(encoding="utf-8")


def _keys(src: str) -> list[str]:
    if "COVER_ART_STYLE_OPTIONS" not in src:
        return []
    block = src.split("COVER_ART_STYLE_OPTIONS", 1)[1].split("];", 1)[0]
    return re.findall(r"key:\s*'([a-z_]+)'", block)


def test_web_cover_styles_match_backend():
    assert _keys(WEB) == list(COVER_ART_STYLE_MAP)
