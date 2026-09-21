"""Paths only a vulnerability scanner asks for.

Shared by serve_spa (answers them 404 instead of the SPA shell's 200) and the
bot-guard middleware (counts them as strikes). It is a BLOCKLIST, not a
whitelist: SPA routes are arbitrary, so a whitelist would 404 every future
client route. See docs/superpowers/specs/2026-09-21-security-monitor-design.md.
"""

SCANNER_SEGMENTS = frozenset({
    "wp-admin", "wp-login.php", "wp-content", "wp-includes", "wp-json", "wordpress",
    "xmlrpc.php", "phpmyadmin", "pma", "cgi-bin", "server-status", "actuator",
    "hnap1", "boaform",
})
SCANNER_SUFFIXES = (
    ".php", ".phtml", ".asp", ".aspx", ".jsp", ".jspx", ".cgi", ".sql", ".bak", ".old", ".swp",
)


def is_scanner_path(path: str) -> bool:
    """True for paths only a vulnerability scanner asks for.

    Any dot-segment is scanner traffic (.git, .env, .svn, .aws, .DS_Store, and
    `..` traversal attempts) — the one legitimate dot-path, .well-known, is
    served by its own route/mount before serve_spa's catch-all is reached.
    """
    segments = [s for s in path.lower().split("/") if s]
    for seg in segments:
        if seg in SCANNER_SEGMENTS or (seg.startswith(".") and seg != ".well-known"):
            return True
    return bool(segments) and segments[-1].endswith(SCANNER_SUFFIXES)
