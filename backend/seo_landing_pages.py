"""Server-rendered SEO landing pages for zeusbeats.com (2026-09-29).

The Zeus Beats site is a client-rendered SPA: every route answers with the same
index.html shell, so a crawler that doesn't run JavaScript (OAI-SearchBot, and
Google's first pass) sees one title, one description and a <noscript> block
for every URL. These pages are rendered here as complete HTML instead, so the
title, description, H1, body copy, FAQs and JSON-LD are all in the first
response with no JS needed.

serve_spa calls `render(path, genre_count)` before its SPA fallback, for the
zeusbeats.com host only. The pages carry no pricing figures on purpose — they
link to /pricing, which stays the single source of truth for plans and prices.

Content rules: every claim here must match what the product actually does
today (see TermsPage.jsx section 10 for commercial rights; MemorialsLandingPage
for the memorial package). "{genres}" is replaced with the live genre count.
"""
import html as _html
import json as _json
import re as _re

BASE_URL = "https://zeusbeats.com"

# Response header the service worker checks so it never stores one of these
# pages as the offline app shell (it caches every other navigation under "/").
LANDING_HEADER = ("X-Zeus-Page", "landing")

PAGES = {
    "ai-music-generator": {
        "title": "AI Music Generator — Make Original Songs Free | Zeus Beats",
        "description": (
            "Describe a song and Zeus Beats writes the lyrics and produces a finished track "
            "with vocals in {genres}+ genres. Start with 3 free songs, no card needed."
        ),
        "h1": "AI Music Generator",
        "lede": (
            "Describe the song you want in a sentence or two. Zeus Beats writes the lyrics, "
            "picks up the mood and produces a finished track with vocals — usually in a couple "
            "of minutes, with no studio, instruments or music theory needed."
        ),
        "sections": [
            ("How the AI music generator works", """
<ol>
  <li><strong>Describe your song.</strong> Tell Zeus what it's about — a person, a memory, a joke, a feeling, a brand. Add names or details you want included.</li>
  <li><strong>Pick a genre and vocal style.</strong> Choose from {genres}+ genres, from Soul, Grime and Afrobeats to Country, Jazz, Drum &amp; Bass and Lo-Fi.</li>
  <li><strong>Zeus writes the lyrics.</strong> Zeus turns your brief into verses and a chorus. Prefer your own words? Paste in your own lyrics instead.</li>
  <li><strong>The track is produced.</strong> The music, vocals and arrangement are generated for you, ready to play, download and share.</li>
</ol>"""),
            ("What you can make", """
<ul>
  <li><strong>Personal songs</strong> — birthdays, anniversaries, weddings, leaving dos and in-jokes.</li>
  <li><strong>Tributes</strong> — <a href="/ai-memorial-song-generator">memorial songs</a> for someone you've lost.</li>
  <li><strong>Content music</strong> — tracks for your <a href="/ai-youtube-song-maker">YouTube channel</a>, reels and podcasts.</li>
  <li><strong>Genre experiments</strong> — try the same idea as <a href="/ai-country-song-generator">country</a>, grime or jazz and hear how it changes.</li>
  <li><strong>Songs in other languages</strong> — lyrics can be written in 30+ languages.</li>
</ul>"""),
            ("Beyond one song", """
<p>Every track you make is kept in your library. From there you can share a link, publish to
<a href="/discover">Discover</a> to hear what other people are making, mix tracks in the built-in DJ mixer,
or upload straight to YouTube on a paid plan.</p>
<p>If you plan to earn money from your music, read how <a href="/commercial-use-ai-music">commercial use</a>
works on each plan before you publish.</p>"""),
        ],
        "faqs": [
            ("Is the Zeus Beats AI music generator free?",
             "Yes, you can start free. New accounts get 3 free songs, with no credit card needed. "
             "Paid plans add more songs each month and extra features — see <a href=\"/pricing\">pricing</a> for the current plans."),
            ("Do I need to write my own lyrics?",
             "No. Zeus writes the lyrics from your description. If you'd rather use your own words, you can paste in your own lyrics, and you can edit the lyrics of a finished song and remake it."),
            ("How long does it take to make a song?",
             "Most songs are ready in a couple of minutes from the moment you press create."),
            ("Can I use the songs commercially?",
             "Songs made on a paid plan, or with purchased song credits, come with full commercial rights. "
             "Songs made on the Free plan are for personal, non-commercial use only. "
             "See <a href=\"/commercial-use-ai-music\">commercial use of AI music</a> for the details."),
        ],
        "related": ["ai-country-song-generator", "ai-youtube-song-maker", "commercial-use-ai-music", "suno-alternative"],
    },

    "ai-country-song-generator": {
        "title": "AI Country Song Generator — Write & Produce Country | Zeus Beats",
        "description": (
            "Make a country song with AI: storytelling lyrics plus a finished track in styles from "
            "traditional and outlaw country to country pop and country rap. 3 free songs."
        ),
        "h1": "AI Country Song Generator",
        "lede": (
            "Country music lives on storytelling — a name, a town, a truck, a heartbreak. Give Zeus "
            "the story and it writes the verses and chorus, then produces the song with the "
            "instruments and vocal feel of the country style you choose."
        ),
        "sections": [
            ("Country styles you can choose", """
<ul>
  <li><strong>Traditional Country</strong> — steel guitar, fiddle, honky-tonk piano and a classic Nashville feel.</li>
  <li><strong>Country Pop</strong> — polished, radio-friendly, big sing-along chorus.</li>
  <li><strong>Country Ballad</strong> — slow, tender and emotional, built for heartfelt stories.</li>
  <li><strong>Country Soul</strong> — soulful vocals, pedal steel and Hammond organ.</li>
  <li><strong>Dark Outlaw Country</strong> — gritty, Southern Gothic, deep gravelly vocals.</li>
  <li><strong>Country Rap</strong> and <strong>Outlaw Country Rap</strong> — banjo and acoustic guitar over trap beats and 808s.</li>
  <li><strong>Country Americana</strong>, <strong>Bluegrass</strong> and <strong>Roots</strong> — acoustic, organic and rooted in tradition.</li>
</ul>"""),
            ("Tips for a better country song", """
<ul>
  <li><strong>Be specific.</strong> “My dad's old red pickup and fishing at Miller's Creek” beats “a song about my dad”.</li>
  <li><strong>Name the feeling.</strong> Proud, homesick, heartbroken, rowdy — it shapes the lyrics and the delivery.</li>
  <li><strong>Match the style to the story.</strong> A ballad for a tribute, country pop for a wedding, outlaw for attitude.</li>
  <li><strong>Try two styles.</strong> The same story can sound completely different as bluegrass and as country rap.</li>
</ul>"""),
            ("Good occasions for a country song", """
<p>Birthdays, anniversaries, a first dance, a retirement, a road trip, a hometown or a tribute
to someone special. For a song remembering someone who has died, see the
<a href="/ai-memorial-song-generator">AI memorial song generator</a>.</p>"""),
        ],
        "faqs": [
            ("Can AI write a real country song?",
             "Yes. Zeus writes lyrics in a country storytelling style from your description and produces a full track with vocals and country instrumentation such as acoustic and steel guitar, fiddle and banjo."),
            ("Can I include names and places in the lyrics?",
             "Yes. Add names, places and small details to your description and Zeus will work them into the verses and chorus. You can also edit the lyrics afterwards and remake the song."),
            ("Can I choose a male or female voice?",
             "Yes, you can choose the vocal style when you create the song."),
            ("Is it free to try?",
             "New accounts get 3 free songs with no card needed. Free songs are for personal use; see <a href=\"/commercial-use-ai-music\">commercial use</a> if you want to release or monetise the music."),
        ],
        "related": ["ai-music-generator", "ai-memorial-song-generator", "ai-youtube-song-maker"],
    },

    "ai-memorial-song-generator": {
        "title": "AI Memorial Song Generator — Personal Tribute Songs | Zeus Beats",
        "description": (
            "Create a personal memorial song for someone you've lost, written from your memories of "
            "them. Add photos for a slideshow and share a memorial page with a QR code."
        ),
        "h1": "AI Memorial Song Generator",
        "lede": (
            "A memorial song can say what's hard to put into words. Share a few memories of the "
            "person — their name, what they loved, the moments you'll remember — and Zeus writes "
            "and produces a song that is about them, not a generic tribute."
        ),
        "sections": [
            ("What a Zeus Beats memorial includes", """
<ul>
  <li><strong>A personalised song</strong> written from the memories you share.</li>
  <li><strong>Up to 10 photos</strong> shown as a slideshow with the song.</li>
  <li><strong>A memorial page</strong> you can share with family and friends.</li>
  <li><strong>A permanent QR code</strong> that links to the page — for an order of service, a card or a keepsake.</li>
</ul>
<p>The memorial package is a separate purchase. See <a href="/memorials">memorial tributes</a> for what's included and to get started.</p>"""),
            ("Writing the brief", """
<p>You don't need to write lyrics or poetry. A few honest details make the song personal:</p>
<ul>
  <li>Their name, and what people called them.</li>
  <li>Places, hobbies, sayings, songs or smells that bring them back.</li>
  <li>How you'd like the song to feel — gentle and peaceful, hopeful, or a celebration of their life.</li>
</ul>"""),
            ("Choosing a musical style", """
<p>Gentle styles such as Acoustic Ballad, Country Ballad, Soul, Gospel, Hymns or Piano suit most
services. If the person loved a particular kind of music, choose that instead — a reggae,
<a href="/ai-country-song-generator">country</a> or jazz tribute can feel far more like them.</p>"""),
        ],
        "faqs": [
            ("Can I make a memorial song for a funeral?",
             "Yes. Many people use a memorial song at a funeral, celebration of life or wake, and share the memorial page afterwards."),
            ("Can the song include their name?",
             "Yes. Include their name and personal details in your brief and Zeus will write them into the lyrics."),
            ("How do people find the memorial page?",
             "Each memorial has its own page and a permanent QR code, so you can print the code or send the link to family and friends."),
        ],
        "related": ["ai-music-generator", "ai-country-song-generator"],
    },

    "ai-youtube-song-maker": {
        "title": "AI YouTube Song Maker — Create & Upload Songs | Zeus Beats",
        "description": (
            "Make original songs for YouTube with AI and upload them straight to your channel. "
            "{genres}+ genres, lyrics written for you, commercial rights on paid plans."
        ),
        "h1": "AI YouTube Song Maker",
        "lede": (
            "Need original music for your channel? Zeus Beats writes and produces songs from a "
            "short description, and on a paid plan you can upload them directly to YouTube "
            "without downloading and re-uploading files yourself."
        ),
        "sections": [
            ("From idea to YouTube", """
<ol>
  <li><strong>Create the song.</strong> Describe it, pick one of {genres}+ genres and let Zeus write the lyrics and produce the track.</li>
  <li><strong>Connect your channel.</strong> Link your YouTube account once in Settings.</li>
  <li><strong>Upload.</strong> Send the song to your channel from your library in a couple of taps.</li>
</ol>
<p>YouTube upload is included on paid plans — see <a href="/pricing">pricing</a>.</p>"""),
            ("Ideas for YouTube songs", """
<ul>
  <li>An original channel theme or intro song.</li>
  <li>Songs about your niche — gaming, football, cooking, travel, fitness.</li>
  <li>Birthday and celebration songs for your community.</li>
  <li>Lo-Fi, ambient or meditation tracks for background and study videos.</li>
  <li>Genre series — the same story told as grime, <a href="/ai-country-song-generator">country</a> and jazz.</li>
</ul>"""),
            ("Monetising and disclosure", """
<p>If you plan to monetise videos that use your songs, make them on a paid plan or with
purchased song credits — those songs come with full commercial rights. Free plan songs are
for personal use only. Read <a href="/commercial-use-ai-music">commercial use of AI music</a> for the details.</p>
<p>Follow YouTube's own rules on disclosing AI-generated or synthetic content when you upload.</p>"""),
        ],
        "faqs": [
            ("Can I upload Zeus Beats songs directly to YouTube?",
             "Yes, on a paid plan. Connect your YouTube account in Settings and upload songs from your library straight to your channel."),
            ("Can I monetise YouTube videos that use Zeus Beats songs?",
             "Songs made on a paid plan or with purchased song credits come with full commercial rights, including YouTube monetisation. Songs made on the Free plan can't be used in monetised videos."),
            ("Will my song be unique?",
             "Every song is generated fresh from your description, but Zeus Beats doesn't guarantee exclusivity — similar outputs can be generated from similar prompts. For important releases, consider registering with a performing rights organisation."),
            ("Do I need to disclose that the music is AI-generated?",
             "Where the law or a platform's policy requires it, yes. YouTube has its own rules for labelling AI-generated or altered content, so check them when you upload."),
        ],
        "related": ["ai-music-generator", "commercial-use-ai-music", "suno-alternative"],
    },

    "commercial-use-ai-music": {
        "title": "Commercial Use AI Music — Who Owns Your Songs? | Zeus Beats",
        "description": (
            "Can you sell, stream or monetise AI music from Zeus Beats? What each plan allows, "
            "who owns the songs, and what to check before releasing AI-generated music."
        ),
        "h1": "Commercial Use of AI Music on Zeus Beats",
        "lede": (
            "Before you sell, stream or monetise a song made with AI, you need to know what "
            "you're allowed to do with it. Here is how ownership and commercial rights work on "
            "Zeus Beats, in plain English."
        ),
        "sections": [
            ("Who owns the songs?", """
<p>The music, lyrics and cover art generated from your prompts are yours. What you're allowed to
<em>do</em> with them commercially depends on how the song was made.</p>"""),
            ("What each plan allows", """
<div class="zl-grid">
  <div class="zl-card">
    <h3>Paid plans &amp; song credits</h3>
    <p><strong>Full commercial rights.</strong> Songs made on Music Starter, Music Pro or Music Agency, or with purchased pay-as-you-go song credits, can be sold, licensed, synced, broadcast, streamed, monetised and distributed — including on YouTube, Spotify, Apple Music and TikTok, and in advertising, film, TV and branded content.</p>
    <p>Songs keep their commercial rights if you later cancel or downgrade.</p>
  </div>
  <div class="zl-card">
    <h3>Free plan</h3>
    <p><strong>Personal, non-commercial use only</strong> — private listening, sharing with friends and personal projects. Free plan songs can't be sold, licensed, used in advertising or monetised.</p>
    <p>Upgrading later doesn't add commercial rights to songs already made on the Free plan.</p>
  </div>
</div>
<p>Current plans and prices are on the <a href="/pricing">pricing page</a>.</p>"""),
            ("Before you release AI-generated music", """
<ul>
  <li><strong>Disclose AI use where required.</strong> Some laws, platforms and distributors require you to say music was made with AI. We recommend being open about it even when it isn't required.</li>
  <li><strong>No exclusivity guarantee.</strong> Similar outputs can be generated for other people from similar prompts, so a song isn't guaranteed to be unique.</li>
  <li><strong>Register important works.</strong> For commercially significant songs, consider registering with a performing rights organisation such as PRS for Music.</li>
  <li><strong>Check your distributor's rules.</strong> Streaming distributors set their own policies on AI-generated music.</li>
  <li><strong>The models aren't yours.</strong> Owning your songs doesn't give you rights to the underlying AI models or software.</li>
</ul>
<p>This page is a summary, not legal advice. The <a href="/terms">Terms of Service</a> (section 10) are the binding version.</p>"""),
        ],
        "faqs": [
            ("Can I sell music made with Zeus Beats?",
             "Yes, if it was made on a paid plan or with purchased song credits. Those songs come with full commercial rights. Free plan songs are for personal use only."),
            ("Can I put Zeus Beats songs on Spotify and Apple Music?",
             "Songs made on a paid plan or with purchased song credits can be distributed to streaming services. Check your distributor's own policy on AI-generated music, and disclose AI use where required."),
            ("Do I keep commercial rights if I cancel my subscription?",
             "Yes. Songs made during an active paid subscription keep their commercial rights after you cancel or downgrade."),
            ("If I upgrade, can I use my old free songs commercially?",
             "No. Upgrading doesn't retroactively grant commercial rights to songs made on the Free plan. Remake the song on your paid plan instead."),
            ("Is my AI-generated song unique?",
             "It's generated fresh from your prompt, but uniqueness isn't guaranteed — similar outputs can come from similar prompts."),
        ],
        "related": ["ai-youtube-song-maker", "ai-music-generator", "suno-alternative"],
    },

    "suno-alternative": {
        # Slug kept as requested; the visible copy and metadata deliberately
        # name no third-party provider and make no comparison claims.
        "title": "AI Music Generator Alternative | Zeus Beats",
        "description": (
            "Create AI songs with {genres}+ genre presets, YouTube tools, memorial songs "
            "and more with Zeus Beats."
        ),
        "h1": "Looking for an AI Music Generator Alternative?",
        "lede": (
            "Zeus Beats is built for people who want a finished, personal song without writing "
            "prompts or lyrics. Describe the song in plain English, pick a genre, and Zeus writes "
            "the lyrics and produces the track — with tools for sharing, publishing and special "
            "occasions built in."
        ),
        "sections": [
            ("What you get with Zeus Beats", """
<ul>
  <li><strong>Lyrics written for you.</strong> Zeus writes the verses and chorus from a plain-English description — or you can use your own lyrics.</li>
  <li><strong>{genres}+ tuned genre presets.</strong> Each genre carries a detailed production style, including UK sounds such as Grime, UK Drill, Jungle, UK Garage and Bassline, so you don't need to write style tags.</li>
  <li><strong>YouTube upload</strong> straight to your channel on paid plans — see the <a href="/ai-youtube-song-maker">AI YouTube song maker</a>.</li>
  <li><strong>Memorial tributes</strong> with a song, photo slideshow, memorial page and QR code — see the <a href="/ai-memorial-song-generator">AI memorial song generator</a>.</li>
  <li><strong>A DJ mixer, Kids Story Mode and a <a href="/discover">Discover</a> feed</strong> of songs other people have made.</li>
  <li><strong>Clear commercial terms</strong> by plan — see <a href="/commercial-use-ai-music">commercial use</a>.</li>
</ul>"""),
            ("How it works", """
<ol>
  <li><strong>Describe your song</strong> — who or what it's about, and how it should feel.</li>
  <li><strong>Pick a genre and vocal style</strong> from {genres}+ genres.</li>
  <li><strong>Zeus writes the lyrics and produces the track</strong>, usually in a couple of minutes.</li>
  <li><strong>Share, download or publish</strong> — to Discover, to YouTube on a paid plan, or as a link.</li>
</ol>"""),
            ("Who Zeus Beats is built for", """
<ul>
  <li>You want a finished, personal song from a short description, without writing lyrics or prompts.</li>
  <li>You're making a song for an occasion — a birthday, a wedding, a roast or a tribute.</li>
  <li>You want UK genres to sound right without experimenting with style tags.</li>
  <li>You publish to YouTube and want to upload from the same place you create.</li>
</ul>"""),
        ],
        "faqs": [
            ("What does Zeus Beats focus on?",
             "Finished, personal songs. Zeus writes the lyrics from a plain-English description, applies a tuned production style for each of {genres}+ genres, and includes tools such as YouTube upload, memorial tributes and a DJ mixer."),
            ("Is Zeus Beats free to try?",
             "Yes. New accounts get 3 free songs with no card needed. See <a href=\"/pricing\">pricing</a> for paid plans."),
            ("Do I need to write prompts or style tags?",
             "No. Describe the song in plain English and pick a genre — Zeus handles the lyrics and the production style."),
            ("Can I use Zeus Beats songs commercially?",
             "Songs made on a paid plan or with purchased song credits come with full commercial rights. Free plan songs are for personal use only."),
        ],
        "related": ["ai-music-generator", "commercial-use-ai-music", "ai-youtube-song-maker"],
    },
}

# Short labels for the related/footer link lists.
LINK_LABELS = {
    "ai-music-generator": "AI Music Generator",
    "ai-country-song-generator": "AI Country Song Generator",
    "ai-memorial-song-generator": "AI Memorial Song Generator",
    "ai-youtube-song-maker": "AI YouTube Song Maker",
    "commercial-use-ai-music": "Commercial Use of AI Music",
    "suno-alternative": "AI Music Generator Alternative",
}

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:#000;color:#fff;font-family:'Rajdhani',system-ui,sans-serif;font-size:18px;line-height:1.6;overflow-x:hidden}
a{color:#00f0ff}
a:hover{color:#1af5ff}
.zl-wrap{max-width:880px;margin:0 auto;padding:0 20px}
.zl-nav{position:sticky;top:0;z-index:10;background:rgba(0,0,0,.92);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);box-shadow:0 1px 0 rgba(0,240,255,.12)}
.zl-nav-inner{max-width:1180px;margin:0 auto;padding:0 20px;height:64px;display:flex;align-items:center;gap:24px}
.zl-logo{display:flex;align-items:center;gap:8px;font-family:'Orbitron',sans-serif;font-weight:900;font-size:1.05rem;letter-spacing:.05em;color:#fff;text-decoration:none;white-space:nowrap}
.zl-links{display:flex;gap:24px;list-style:none;flex:1}
.zl-links a{color:#888;text-decoration:none;font-weight:500;font-size:.95rem}
.zl-links a:hover{color:#00f0ff}
.zl-btn{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#00f0ff 0%,#00d0e8 100%);color:#000;font-weight:700;border-radius:6px;text-decoration:none;padding:10px 18px;white-space:nowrap}
.zl-btn:hover{color:#000;box-shadow:0 0 32px rgba(0,240,255,.6)}
.zl-btn-lg{padding:14px 28px;font-size:1.05rem}
.zl-ghost{color:#888;text-decoration:none;font-weight:600;white-space:nowrap}
.zl-hero{position:relative;padding:72px 0 40px;overflow:hidden}
.zl-hero::before{content:"";position:absolute;inset:0;background:radial-gradient(600px 300px at 20% 0%,rgba(0,240,255,.14),transparent 70%),radial-gradient(500px 300px at 90% 20%,rgba(255,0,153,.10),transparent 70%);pointer-events:none}
.zl-crumbs{position:relative;font-size:.85rem;color:#888;margin-bottom:18px}
.zl-crumbs a{color:#888;text-decoration:none}
.zl-hero h1{position:relative;font-family:'Orbitron',sans-serif;font-weight:900;font-size:clamp(1.8rem,5vw,2.8rem);line-height:1.15;letter-spacing:.02em;background:linear-gradient(135deg,#00f0ff,#ff0099,#00ff41);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;overflow-wrap:anywhere}
.zl-lede{position:relative;margin-top:18px;font-size:1.2rem;color:#cfd8e3}
.zl-cta{position:relative;margin-top:28px;display:flex;flex-wrap:wrap;gap:14px;align-items:center}
.zl-note{color:#888;font-size:.95rem}
main section{padding:28px 0;border-top:1px solid rgba(0,240,255,.12)}
main h2{font-family:'Orbitron',sans-serif;font-weight:700;font-size:1.25rem;letter-spacing:.03em;color:#00f0ff;margin-bottom:14px}
main h3{font-size:1.15rem;margin-bottom:8px}
main p{color:#cfd8e3;margin-bottom:12px}
main ul,main ol{padding-left:22px;color:#cfd8e3}
main li{margin-bottom:8px}
main li strong,main p strong{color:#fff}
.zl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:14px}
.zl-card{background:rgba(13,13,20,.85);border:1px solid rgba(0,240,255,.12);border-radius:16px;padding:20px}
.zl-faq details{background:rgba(13,13,20,.85);border:1px solid rgba(0,240,255,.12);border-radius:10px;padding:14px 18px;margin-bottom:10px}
.zl-faq summary{cursor:pointer;font-weight:600;color:#fff}
.zl-faq details p{margin:10px 0 0}
.zl-related ul{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:10px}
.zl-related a{display:inline-block;border:1px solid rgba(0,240,255,.25);background:rgba(0,240,255,.08);border-radius:999px;padding:6px 14px;text-decoration:none;font-weight:600}
.zl-final{text-align:center;padding:40px 0 56px}
.zl-final p{margin-bottom:18px}
.zl-footer{border-top:1px solid rgba(0,240,255,.12);padding:32px 0 40px;color:#888;font-size:.9rem}
.zl-footer-cols{display:flex;flex-wrap:wrap;gap:32px;margin-bottom:20px}
.zl-footer h2{font-family:'Orbitron',sans-serif;font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:#fff;margin-bottom:10px}
.zl-footer ul{list-style:none}
.zl-footer li{margin-bottom:6px}
.zl-footer a{color:#888;text-decoration:none}
.zl-footer a:hover{color:#00f0ff}
@media (max-width:720px){.zl-links{display:none}.zl-nav-inner{justify-content:space-between;gap:12px}.zl-hero{padding-top:48px}.zl-ghost-nav{display:none}}
"""


def _fill(text: str, genre_count: int) -> str:
    return text.replace("{genres}", str(genre_count))


def _plain(fragment: str) -> str:
    """Visible text of an HTML fragment, for JSON-LD answers."""
    return _html.unescape(_re.sub(r"<[^>]+>", "", fragment)).strip()


def _json_ld(data: dict) -> str:
    # "</" must not appear inside a <script> block.
    return _json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")


def render(path: str, genre_count: int) -> str | None:
    """Full HTML for a landing page, or None if `path` isn't one."""
    slug = path.strip("/")
    page = PAGES.get(slug)
    if page is None:
        return None
    esc = _html.escape
    url = f"{BASE_URL}/{slug}"
    title = _fill(page["title"], genre_count)
    desc = _fill(page["description"], genre_count)

    sections = "\n".join(
        f'<section><h2>{esc(h2)}</h2>{_fill(body, genre_count)}</section>'
        for h2, body in page["sections"]
    )
    faq_items = "\n".join(
        f"<details><summary>{esc(q)}</summary><p>{_fill(a, genre_count)}</p></details>"
        for q, a in page["faqs"]
    )
    related = "\n".join(
        f'<li><a href="/{s}">{esc(LINK_LABELS[s])}</a></li>' for s in page["related"]
    )
    footer_guides = "\n".join(
        f'<li><a href="/{s}">{esc(label)}</a></li>' for s, label in LINK_LABELS.items()
    )

    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": url,
                "url": url,
                "name": title,
                "description": desc,
                "inLanguage": "en-GB",
                "isPartOf": {"@type": "WebSite", "name": "Zeus Beats", "url": BASE_URL},
                "about": {
                    "@type": "SoftwareApplication",
                    "name": "Zeus Beats",
                    "url": BASE_URL,
                    "applicationCategory": "MusicApplication",
                    "operatingSystem": "Web",
                },
                "publisher": {"@type": "Organization", "name": "Zeus Beats Ltd", "url": BASE_URL},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Zeus Beats", "item": BASE_URL + "/"},
                    {"@type": "ListItem", "position": 2, "name": page["h1"], "item": url},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": _plain(_fill(a, genre_count))},
                    }
                    for q, a in page["faqs"]
                ],
            },
        ],
    }

    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Zeus Beats">
<meta property="og:image" content="{BASE_URL}/icons/icon-512.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{BASE_URL}/icons/icon-512.png">
<meta name="theme-color" content="#00f0ff">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/icons/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Rajdhani:wght@500;600;700&display=swap">
<style>{_CSS}</style>
<script type="application/ld+json">
{_json_ld(ld)}
</script>
</head>
<body>
<nav class="zl-nav" aria-label="Main">
  <div class="zl-nav-inner">
    <a href="/" class="zl-logo"><span aria-hidden="true">⚡</span> Zeus Beats</a>
    <ul class="zl-links">
      <li><a href="/ai-music-generator">AI Music Generator</a></li>
      <li><a href="/discover">Discover</a></li>
      <li><a href="/pricing">Pricing</a></li>
    </ul>
    <a href="/login" class="zl-ghost zl-ghost-nav">Sign in</a>
    <a href="/register" class="zl-btn">Start free</a>
  </div>
</nav>
<header class="zl-hero">
  <div class="zl-wrap">
    <nav class="zl-crumbs" aria-label="Breadcrumb"><a href="/">Zeus Beats</a> › {esc(page["h1"])}</nav>
    <h1>{esc(page["h1"])}</h1>
    <p class="zl-lede">{esc(_fill(page["lede"], genre_count))}</p>
    <div class="zl-cta">
      <a href="/register" class="zl-btn zl-btn-lg">Make a song free →</a>
      <span class="zl-note">3 free songs on signup · no card needed</span>
    </div>
  </div>
</header>
<main class="zl-wrap">
{sections}
<section class="zl-faq">
  <h2>Frequently asked questions</h2>
  {faq_items}
</section>
<section class="zl-related">
  <h2>Related guides</h2>
  <ul>
    {related}
  </ul>
</section>
<section class="zl-final">
  <p>Ready to hear your idea as a finished song?</p>
  <a href="/register" class="zl-btn zl-btn-lg">Start creating free →</a>
</section>
</main>
<footer class="zl-footer">
  <div class="zl-wrap">
    <div class="zl-footer-cols">
      <div>
        <h2>Zeus Beats</h2>
        <ul>
          <li><a href="/">Home</a></li>
          <li><a href="/discover">Discover</a></li>
          <li><a href="/pricing">Pricing</a></li>
          <li><a href="/memorials">Memorial tributes</a></li>
          <li><a href="/contact">Contact</a></li>
        </ul>
      </div>
      <div>
        <h2>Guides</h2>
        <ul>
          {footer_guides}
        </ul>
      </div>
      <div>
        <h2>Legal</h2>
        <ul>
          <li><a href="/terms">Terms</a></li>
          <li><a href="/privacy">Privacy</a></li>
          <li><a href="/refund-policy">Refund policy</a></li>
        </ul>
      </div>
    </div>
    <p>© Zeus Beats Ltd. All rights reserved. Company No. 17230535</p>
  </div>
</footer>
</body>
</html>
"""
