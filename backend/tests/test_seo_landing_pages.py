"""Server-rendered SEO landing pages (2026-09-29).

The six pages in seo_landing_pages.PAGES must reach crawlers as complete HTML
(no JS), each with its own title, description, H1, canonical and JSON-LD, only
on zeusbeats.com, and be listed in the sitemap. The generic Zeus Beats meta
must no longer advertise animated cover art (removed 2026-08-06).
"""
import asyncio
from html import unescape
import json
import os
import pathlib
import re
import sys

import pytest
from starlette.requests import Request

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-seo-landing-tests")

import seo_landing_pages as seo  # noqa: E402

SLUGS = [
    "ai-music-generator",
    "ai-country-song-generator",
    "ai-memorial-song-generator",
    "ai-youtube-song-maker",
    "commercial-use-ai-music",
    "ai-music-generator-alternative",
]
REPO = pathlib.Path(__file__).parent.parent.parent


@pytest.fixture
def site(tmp_path, monkeypatch):
    import main as _main
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        (REPO / "web-beats" / "index.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(_main, "_beats_dist", dist)
    monkeypatch.setattr(_main, "_dist", dist)
    return dist


def _request(path, host):
    scope = {
        "type": "http", "method": "GET", "scheme": "https", "path": path,
        "raw_path": path.encode(), "query_string": b"",
        "headers": [(b"host", host.encode()), (b"user-agent", b"pytest")],
        "server": ("testserver", 443), "client": ("203.0.113.9", 1234),
    }
    return Request(scope)


def _get(full_path, host="zeusbeats.com"):
    import main as _main
    return asyncio.run(_main.serve_spa(full_path, _request("/" + full_path, host)))


def _body(resp):
    return bytes(resp.body).decode("utf-8")


def _one(pattern, text):
    found = re.findall(pattern, text, flags=re.DOTALL)
    assert len(found) == 1, (pattern, found)
    return found[0]


def test_page_set_is_exactly_the_six_requested():
    assert sorted(seo.PAGES) == sorted(SLUGS)
    assert sorted(seo.LINK_LABELS) == sorted(SLUGS)


@pytest.mark.parametrize("slug", SLUGS)
def test_each_page_is_complete_html_without_js(site, slug):
    resp = _get(slug)
    assert resp.status_code == 200
    assert resp.headers["x-zeus-page"] == "landing"
    html = _body(resp)
    assert "<script type=\"module\"" not in html  # content must not depend on the SPA
    assert "{genres}" not in html and "{{GENRE_COUNT}}" not in html
    _one(r"<title>[^<]+</title>", html)
    _one(r'<meta name="description" content="[^"]+">', html)
    h1 = _one(r"<h1>([^<]+)</h1>", html)
    assert h1 == seo.PAGES[slug]["h1"]
    assert _one(r'<link rel="canonical" href="([^"]+)">', html) == f"https://zeusbeats.com/{slug}"
    assert "<details>" in html  # visible FAQs
    # Pricing lives only on /pricing — these pages must not hard-code prices.
    assert "£" not in html and "$" not in html


@pytest.mark.parametrize("slug", SLUGS)
def test_json_ld_is_valid_and_matches_visible_faqs(site, slug):
    html = _body(_get(slug))
    raw = _one(r'<script type="application/ld\+json">(.*?)</script>', html)
    data = json.loads(raw)
    types = {node["@type"] for node in data["@graph"]}
    assert types == {"WebPage", "BreadcrumbList", "FAQPage"}
    faq = next(n for n in data["@graph"] if n["@type"] == "FAQPage")
    questions = [q["name"] for q in faq["mainEntity"]]
    assert questions == [q for q, _ in seo.PAGES[slug]["faqs"]]
    for q in faq["mainEntity"]:
        assert "<" not in q["acceptedAnswer"]["text"]


def test_titles_and_descriptions_are_unique_and_sensible_length(site):
    titles, descs = set(), set()
    homepage = _body(_get(""))
    home_title = unescape(_one(r"<title>([^<]+)</title>", homepage))
    home_desc = unescape(_one(r'<meta name="description" content="([^"]+)">', homepage))
    for slug in SLUGS:
        html = _body(_get(slug))
        title = unescape(_one(r"<title>([^<]+)</title>", html))
        desc = unescape(_one(r'<meta name="description" content="([^"]+)">', html))
        assert len(title) <= 70, title
        assert 70 <= len(desc) <= 170, desc
        titles.add(title)
        descs.add(desc)
    assert len(titles) == len(descs) == len(SLUGS)
    assert home_title not in titles and home_desc not in descs


def test_trailing_slash_serves_same_page(site):
    assert _body(_get("ai-music-generator-alternative/")) == _body(_get("ai-music-generator-alternative"))


def test_not_served_on_zeus_ai_design_host(site):
    resp = _get("ai-music-generator", host="zeusaidesign.com")
    assert "x-zeus-page" not in resp.headers


def test_internal_links_point_at_real_routes():
    """Every internal href is a landing page or a route the SPA actually defines."""
    app_jsx = (REPO / "web-beats" / "src" / "App.jsx").read_text(encoding="utf-8")
    spa_routes = set(re.findall(r'path="(/[^"]*)"', app_jsx))
    html = seo.render("ai-music-generator", 100)
    hrefs = set(re.findall(r'href="(/[^"#]*)"', html))
    for slug in SLUGS:
        hrefs |= set(re.findall(r'href="(/[^"#]*)"', seo.render(slug, 100)))
    static_files = {"/favicon.svg", "/icons/icon-192.png"}
    for href in hrefs - static_files:
        assert href.strip("/") in seo.PAGES or href in spa_routes, href


def test_every_page_is_linked_from_another_page():
    linked = set()
    for slug in SLUGS:
        linked |= set(seo.PAGES[slug]["related"])
    assert linked == set(SLUGS)


def test_sitemap_lists_landing_pages_for_zeusbeats_only():
    import main as _main
    beats = bytes(asyncio.run(_main.sitemap(_request("/sitemap.xml", "zeusbeats.com"))).body).decode()
    design = bytes(asyncio.run(_main.sitemap(_request("/sitemap.xml", "zeusaidesign.com"))).body).decode()
    for slug in SLUGS:
        assert f"<loc>https://zeusbeats.com/{slug}</loc>" in beats
        assert slug not in design
    # Existing entries untouched.
    assert "<loc>https://zeusbeats.com/pricing</loc>" in beats


def test_generic_meta_no_longer_mentions_animated_cover_art(site):
    html = _body(_get("pricing"))
    assert "nimated cover" not in html


def test_robots_names_oai_searchbot_and_keeps_share_disallow():
    robots = (REPO / "web-beats" / "public" / "robots.txt").read_text(encoding="utf-8")
    groups = [g for g in re.split(r"\n\s*\n", robots) if "User-agent:" in g]
    oai = next(g for g in groups if "User-agent: OAI-SearchBot" in g)
    assert "Allow: /" in oai and "Disallow: /songs/share/" in oai
    wildcard = next(g for g in groups if "User-agent: *" in g)
    assert "Disallow: /songs/share/" in wildcard
    assert "Sitemap: https://zeusbeats.com/sitemap.xml" in robots


def test_sitemap_uses_real_refund_policy_route():
    import main as _main
    beats = bytes(asyncio.run(_main.sitemap(_request("/sitemap.xml", "zeusbeats.com"))).body).decode()
    assert "<loc>https://zeusbeats.com/refund-policy</loc>" in beats
    assert "<loc>https://zeusbeats.com/refund</loc>" not in beats
    app_jsx = (REPO / "web-beats" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert 'path="/refund-policy"' in app_jsx


def test_homepage_structured_data_is_valid_and_has_no_unbacked_rating():
    """The 4.8/120 AggregateRating was hard-coded with no review data behind it."""
    index = (REPO / "web-beats" / "index.html").read_text(encoding="utf-8")
    raw = _one(r'<script type="application/ld\+json">(.*?)</script>', index)
    data = json.loads(raw.replace("{{GENRE_COUNT}}", "100"))
    assert data["@type"] == "SoftwareApplication"
    assert "aggregateRating" not in data and "review" not in data
    assert "AggregateRating" not in index


@pytest.mark.parametrize("slug", SLUGS)
def test_no_third_party_provider_named_in_copy_or_metadata(slug):
    """Customer-facing copy, metadata and JSON-LD name no model/API provider.
    Since 2026-10-01 that includes the URLs themselves — no exceptions."""
    html = seo.render(slug, 100)
    for name in ("suno", "claude", "apiframe", "anthropic", "openai", "cometapi"):
        assert name not in html.lower(), (slug, name)


def test_alternative_page_metadata():
    html = seo.render("ai-music-generator-alternative", 135)
    assert "<title>AI Music Generator Alternative | Zeus Beats</title>" in html
    assert ('<meta name="description" content="Create AI songs with 135+ genre presets, '
            'YouTube tools, memorial songs and more with Zeus Beats.">') in html
    assert "better than" not in html.lower()


def test_old_suno_alternative_url_permanently_redirects(site):
    """Renamed 2026-10-01 so no URL names a provider; the old address must 301
    to the new one (links and search rankings carry over), with or without a
    trailing slash, and only on zeusbeats.com."""
    for path in ("suno-alternative", "suno-alternative/"):
        resp = _get(path)
        assert resp.status_code == 301, path
        assert resp.headers["location"] == "/ai-music-generator-alternative"
    assert seo.render("suno-alternative", 100) is None
    assert "x-zeus-page" not in _get("suno-alternative", host="zeusaidesign.com").headers
