"""bot_guard — scanner detection and IP blocking.

Design: docs/superpowers/specs/2026-09-21-security-monitor-design.md

This half of the module is pure logic with no I/O: client-IP extraction, the
never-block rules, the detectors and the in-memory block cache. The ASGI
middleware and runtime wiring are further down (added in a later commit).

The dangerous failure mode is blocking the WRONG address. Behind Railway,
`request.client.host` is a rotating 100.64.x.x proxy IP (see memory note
reference_railway_client_ip); blocking it would lock out every visitor. So:
  * client_ip() trusts X-Real-IP ONLY from a 100.64.0.0/10 peer;
  * is_protected_ip() refuses to ever block private/loopback/CGNAT/reserved
    addresses or anything in SECURITY_IP_ALLOWLIST, and treats garbage as protected.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Railway's internal proxy range (RFC 6598 shared address space).
TRUSTED_PROXY_NET = ipaddress.ip_network("100.64.0.0/10")

# Thresholds (spec: "Detection").
SCANNER_HIT_LIMIT = 5
SCANNER_WINDOW_S = 300
NOTFOUND_LIMIT = 20
NOTFOUND_WINDOW_S = 60
AUTO_BLOCK_TTL_DAYS = 7

CANARY_HEADER = b"x-security-canary"


# ── client IP ────────────────────────────────────────────────────────────────

def _parse_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except (ValueError, TypeError):
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def client_ip(scope: dict) -> str | None:
    """The visitor's IP as a string, or None when it cannot be trusted/known.

    None means "pass the request through untouched" — never attribute traffic
    to the proxy itself.
    """
    peer = scope.get("client")
    if not peer or not isinstance(peer, (tuple, list)):
        return None
    peer_ip = _parse_ip(peer[0])
    if peer_ip is None:
        return None
    if peer_ip.version == 4 and peer_ip in TRUSTED_PROXY_NET:
        for name, value in scope.get("headers") or []:
            if name == b"x-real-ip":
                real = _parse_ip(value.decode("latin-1").strip())
                return str(real) if real is not None else None
        return None
    return str(peer_ip)


def _allowlist() -> list:
    nets = []
    for part in os.environ.get("SECURITY_IP_ALLOWLIST", "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return nets


def is_protected_ip(ip: str) -> bool:
    """True if this address must never be blocked."""
    addr = _parse_ip(ip)
    if addr is None:
        return True  # garbage in -> never block
    if (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
            or addr.is_reserved or addr.is_unspecified or not addr.is_global):
        return True
    if addr.version == 4 and addr in TRUSTED_PROXY_NET:
        return True
    return any(addr.version == n.version and addr in n for n in _allowlist())


# ── user agents ──────────────────────────────────────────────────────────────

# Scanner-specific tools only. Generic clients (curl, python-requests, Go-http-client,
# node-fetch) are deliberately NOT listed: legitimate integrations use them.
_BAD_UA = re.compile(
    r"\b(sqlmap|nikto|masscan|nmap|zgrab|gobuster|dirbuster|dirb|wpscan|nuclei|acunetix|"
    r"netsparker|feroxbuster|hydra|havij|openvas|nessus|whatweb)\b",
    re.IGNORECASE,
)


def is_bad_user_agent(ua) -> str | None:
    """The scanner tool's name if the UA is one, else None."""
    if not ua:
        return None
    m = _BAD_UA.search(ua)
    return m.group(1).lower() if m else None


def enforce_enabled() -> bool:
    """Shadow mode unless SECURITY_ENFORCE is truthy."""
    return os.environ.get("SECURITY_ENFORCE", "").strip().lower() in ("1", "true", "yes")


# ── canary header (the scan's own probes must not strike the app's own IP) ──

def canary_token(now: datetime | None = None) -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        return ""
    day = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return hmac.new(secret.encode(), f"security-canary:{day}".encode(), hashlib.sha256).hexdigest()


def is_canary_request(headers) -> bool:
    """Accepts today's or yesterday's token (survives midnight rollover)."""
    value = next((v for k, v in headers if k == CANARY_HEADER), None)
    if value is None:
        return False
    now = datetime.now(timezone.utc)
    valid = [canary_token(now), canary_token(now - timedelta(days=1))]
    given = value.decode("latin-1")
    return any(t and hmac.compare_digest(given, t) for t in valid)


# ── detector ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Decision:
    ip: str
    kind: str    # 'scanner_paths' | 'notfound_flood' | 'bad_ua'
    reason: str  # human-readable, goes in the alert and blocked_ips.reason


class Detector:
    """Sliding-window strike counters per IP. Thread-safe; clock is injectable."""

    def __init__(self, clock=time.monotonic, scanner_limit=SCANNER_HIT_LIMIT,
                 scanner_window=SCANNER_WINDOW_S, notfound_limit=NOTFOUND_LIMIT,
                 notfound_window=NOTFOUND_WINDOW_S, max_ips=20000):
        self._clock = clock
        self._scanner_limit, self._scanner_window = scanner_limit, scanner_window
        self._nf_limit, self._nf_window = notfound_limit, notfound_window
        self._max_ips = max_ips
        self._scanner: dict[str, deque] = {}
        self._notfound: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _record(self, store, ip, window, limit):
        now = self._clock()
        q = store.setdefault(ip, deque())
        while q and now - q[0] > window:
            q.popleft()
        q.append(now)
        if len(self._scanner) + len(self._notfound) > self._max_ips:
            self._prune(now)
        if len(q) >= limit:
            q.clear()
            return True
        return False

    def record_scanner_hit(self, ip: str) -> Decision | None:
        with self._lock:
            if self._record(self._scanner, ip, self._scanner_window, self._scanner_limit):
                return Decision(ip, "scanner_paths", f"{self._scanner_limit} probe attempts")
        return None

    def record_notfound(self, ip: str) -> Decision | None:
        with self._lock:
            if self._record(self._notfound, ip, self._nf_window, self._nf_limit):
                return Decision(ip, "notfound_flood", f"{self._nf_limit} 404s in {self._nf_window}s")
        return None

    def has_strikes(self, ip: str) -> bool:
        with self._lock:
            q = self._scanner.get(ip)
            if not q:
                return False
            now = self._clock()
            while q and now - q[0] > self._scanner_window:
                q.popleft()
            return bool(q)

    def tracked_ips(self) -> int:
        with self._lock:
            return len(set(self._scanner) | set(self._notfound))

    def _prune(self, now):
        # Called with the lock held. Drop IPs whose newest hit has left its window,
        # then, if still over budget, the least recently seen.
        for store, window in ((self._scanner, self._scanner_window), (self._notfound, self._nf_window)):
            for ip in [i for i, q in store.items() if not q or now - q[-1] > window]:
                del store[ip]
        while len(self._scanner) + len(self._notfound) > self._max_ips:
            oldest = min(
                ((store, ip, q[-1]) for store in (self._scanner, self._notfound) for ip, q in store.items()),
                key=lambda t: t[2],
            )
            del oldest[0][oldest[1]]


# ── block cache ──────────────────────────────────────────────────────────────

class BlockCache:
    """In-memory view of the active blocked_ips rows, so the hot path never hits the DB."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._entries: dict[str, float | None] = {}
        self._lock = threading.Lock()

    def load(self, rows) -> None:
        """rows: iterable of (ip, expires_epoch | None). Replaces the whole cache."""
        with self._lock:
            self._entries = {ip: exp for ip, exp in rows}

    def add(self, ip: str, expires_at: float | None) -> None:
        with self._lock:
            self._entries[ip] = expires_at

    def remove(self, ip: str) -> bool:
        with self._lock:
            return self._entries.pop(ip, _MISSING) is not _MISSING

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            if ip not in self._entries:
                return False
            exp = self._entries[ip]
            if exp is not None and exp <= self._clock():
                del self._entries[ip]
                return False
            return True

    def snapshot(self) -> dict[str, float | None]:
        now = self._clock()
        with self._lock:
            return {ip: exp for ip, exp in self._entries.items() if exp is None or exp > now}


_MISSING = object()


# ── alert budget ─────────────────────────────────────────────────────────────

class AlertBudget:
    """At most `limit` immediate alerts per `window` seconds; the rest are counted."""

    def __init__(self, limit=5, window=600, clock=time.monotonic):
        self._limit, self._window, self._clock = limit, window, clock
        self._sent: deque = deque()
        self._overflow = 0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = self._clock()
            while self._sent and now - self._sent[0] > self._window:
                self._sent.popleft()
            if len(self._sent) < self._limit:
                self._sent.append(now)
                return True
            self._overflow += 1
            return False

    def take_overflow(self) -> int:
        with self._lock:
            n, self._overflow = self._overflow, 0
            return n
