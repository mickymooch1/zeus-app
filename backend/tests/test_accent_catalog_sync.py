"""3-way guard: backend ACCENT_STYLE_MAP/ACCENT_GROUPS == web ACCENT_OPTIONS == iOS
ACCENT_OPTIONS (keys AND groups). Text-scan, like the genre catalog guards."""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENTRY = re.compile(r"\{\s*key:\s*'([a-z_]+)'[^}]*?group:\s*'([a-z_]+)'")


def _client(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r"ACCENT_OPTIONS[^=]*=\s*\[([\s\S]*?)\n\];", src)
    assert m, f"ACCENT_OPTIONS not found in {rel}"
    pairs = _ENTRY.findall(m.group(1))
    assert len(pairs) >= 20, f"parser matched too few entries in {rel}"
    return pairs


def _backend():
    from song_genres import ACCENT_GROUPS
    return [(k, g) for g, ks in ACCENT_GROUPS for k in ks]


def test_web_matches_backend():
    assert _client("web-beats/src/utils/genres.js") == _backend()


def test_ios_matches_backend():
    assert _client("zeus-beats-ios/src/screens/CreateSongScreen.tsx") == _backend()


def test_ios_sends_vocal_accent():
    src = (ROOT / "zeus-beats-ios/src/screens/CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert re.search(r"vocal_accent:\s+accent \|\| undefined", src)
    assert "🎤 Singer's Accent (optional)" in src
