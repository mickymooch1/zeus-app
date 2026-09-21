"""Paths only a vulnerability scanner asks for.

Shared by serve_spa (answers them 404 instead of the SPA shell's 200) and the
bot-guard middleware (counts them as strikes). It is a BLOCKLIST, not a
whitelist: SPA routes are arbitrary, so a whitelist would 404 every future
client route. See docs/superpowers/specs/2026-09-21-security-monitor-design.md.

2026-09-21: a scanner on a rented cloud VM found these still returned the shell's
200 — /phpinfo, /info, /_profiler/phpinfo, /_environment, /webroot/index.php/_environment,
phpinfo.php~ and phpinfo.php.save — because the extension rule only looked at the
LAST segment and only for a plain ".php". A scanner reads 200 as "found". Rules below
now cover scripts in ANY segment, backup suffixes, and no-extension probe names.
"""
import re

# Names that are never legitimate here, matched as any whole path segment.
SCANNER_SEGMENTS = frozenset({
    "wp-admin", "wp-login.php", "wp-content", "wp-includes", "wp-json", "wordpress",
    "xmlrpc.php", "phpmyadmin", "pma", "cgi-bin", "server-status", "actuator",
    "hnap1", "boaform",
    "phpinfo", "_profiler", "_environment", "server-info",
})

# Generic words: blocked ONLY as the whole path (`/info`), never as a segment of a longer
# route (`/songs/info` stays a normal SPA route).
SCANNER_EXACT = frozenset({"info"})

# Last-segment suffixes: scripts, dumps and editor/backup leftovers.
SCANNER_SUFFIXES = (
    ".php", ".phtml", ".asp", ".aspx", ".jsp", ".jspx", ".cgi", ".sql", ".bak", ".old", ".swp",
    ".save", ".orig", "~",
)

# A server-side script extension in ANY segment, optionally followed by a backup suffix:
# x.php5, index.php/<path-info>, phpinfo.php.save, config.php.orig, x.jsp_bak.
_SCRIPT_EXT = re.compile(r"\.(?:php\d?|phtml|asp|aspx|jsp|jspx|cgi)(?:[~._-]|$)")


def is_scanner_path(path: str) -> bool:
    """True for paths only a vulnerability scanner asks for.

    Any dot-segment is scanner traffic (.git, .env, .svn, .aws, .DS_Store, and
    `..` traversal attempts) — the one legitimate dot-path, .well-known, is
    served by its own route/mount before serve_spa's catch-all is reached.
    """
    segments = [s for s in path.lower().split("/") if s]
    if len(segments) == 1 and segments[0] in SCANNER_EXACT:
        return True
    for seg in segments:
        if (seg in SCANNER_SEGMENTS
                or (seg.startswith(".") and seg != ".well-known")
                or _SCRIPT_EXT.search(seg)):
            return True
    return bool(segments) and segments[-1].endswith(SCANNER_SUFFIXES)
