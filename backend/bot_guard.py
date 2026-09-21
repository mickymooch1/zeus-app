"""bot_guard — scanner detection and IP blocking.

Design: docs/superpowers/specs/2026-09-21-security-monitor-design.md

The first half of the module is pure logic with no I/O: client-IP extraction, the
never-block rules, the detectors and the in-memory block cache. The second half
(Guard + BotGuardMiddleware) is the runtime. It sits in front of EVERY request,
so it fails open: any internal error lets the request through untouched.

The dangerous failure mode is blocking the WRONG address. Behind Railway,
`request.client.host` is a rotating 100.64.x.x proxy IP (see memory note
reference_railway_client_ip); blocking it would lock out every visitor. So:
  * client_ip() trusts X-Real-IP ONLY from a 100.64.0.0/10 peer;
  * is_protected_ip() refuses to ever block private/loopback/CGNAT/reserved
    addresses or anything in SECURITY_IP_ALLOWLIST, and treats garbage as protected.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import ipaddress
import logging
import os
import re
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import scanner_paths
import security_store

log = logging.getLogger("zeus.bot_guard")

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


# ── runtime ──────────────────────────────────────────────────────────────────

# Per-IP-per-hour caps on stored events, so a flood can't amplify into DB writes.
_EVENT_CAPS = {"blocked_path": 50, "blocked_path_200": 20, "notfound": 5,
               "auth_fail": 20, "assoc_path": 30, "bad_ua": 3}
_EVENT_BUFFER_MAX = 10000
_FALLBACK_TRACK_MAX_IPS = 2000
_FALLBACK_PER_IP = 20
_NO_DETECT_PREFIXES = ("webhooks/",)           # provider traffic (Stripe, Apiframe, Telegram)
_NO_404_PREFIXES = ("files/", "api/files/")     # missing media is a legitimate 404


def _safe(fn):
    def run(*args):
        try:
            fn(*args)
        except Exception:
            log.exception("bot_guard: background task failed")
    return run


def _executor_dispatch(fn, *args):
    """Run fn off the event loop (Telegram/SQLite are blocking); inline if there is no loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        fn(*args)
        return
    loop.run_in_executor(None, fn, *args)


def _default_db_path():
    import db
    return db.get_db_path()


def _default_alert(text):
    import alerts
    alerts.send_admin_alert(text)


def _default_critical(category, text):
    import alerts
    alerts.send_admin_alert_deduped(category, text, cooldown_seconds=3600)


def _header(headers, name: bytes):
    for k, v in headers:
        if k == name:
            return v.decode("latin-1")
    return None


class Guard:
    """Runtime state: detector + block cache + buffered events, and the decisions built on them.

    All collaborators are injectable so tests are deterministic (dispatch runs inline).
    """

    def __init__(self, db_path_fn=None, alert_fn=None, critical_alert_fn=None, dispatch=None,
                 detector=None, cache=None, budget=None):
        self._db_path_fn = db_path_fn or _default_db_path
        self._alert_fn = alert_fn or _default_alert
        self._critical_fn = critical_alert_fn or _default_critical
        self._dispatch = dispatch or _executor_dispatch
        self.detector = detector or Detector()
        self.cache = cache or BlockCache()
        self._budget = budget or AlertBudget()
        self._lock = threading.RLock()
        self._events: deque = deque(maxlen=_EVENT_BUFFER_MAX)
        self._pending_blocks: list[tuple[str, str]] = []
        self._denied: dict[str, int] = {}
        self._caps: dict[tuple[str, str], tuple[int, int]] = {}
        self._fallback: OrderedDict = OrderedDict()
        self._slips: dict[str, float] = {}
        self._denied_logged: dict[str, float] = {}
        self._loaded = False
        self._next_load_try = 0.0

    # ── loading ──
    def init(self, db_path) -> None:
        self.cache.load(security_store.cache_rows(db_path))
        self._loaded = True
        log.info("bot_guard: loaded %d active block(s); enforcement %s",
                 len(self.cache.snapshot()), "ON" if enforce_enabled() else "OFF (shadow mode)")

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        now = time.monotonic()
        if now < self._next_load_try:
            return
        try:
            self.init(self._db_path_fn())
        except Exception:
            log.exception("bot_guard: could not load blocked IPs (will retry)")
            self._next_load_try = now + 30

    # ── request hooks ──
    def is_blocked(self, ip: str) -> bool:
        return self.cache.is_blocked(ip)

    def count_denied(self, ip: str) -> None:
        with self._lock:
            self._denied[ip] = self._denied.get(ip, 0) + 1
            last = self._denied_logged.get(ip, 0.0)
            if time.time() - last > 3600:
                self._denied_logged[ip] = time.time()
                log.info("bot_guard: %s request from blocked IP %s",
                         "denying" if enforce_enabled() else "would deny (shadow)", ip)

    def on_request(self, ip: str, ua):
        """Pre-response check: scanner user agent. Returns the Decision if one was made."""
        name = is_bad_user_agent(ua)
        if not name:
            return None
        self._event(ip, "bad_ua", None, None, ua)
        decision = Decision(ip, "bad_ua", f"scanner tool {name}")
        self._apply(decision)
        return decision

    def on_response(self, ip: str, scope: dict, status: int, ua) -> None:
        path = scope.get("path") or "/"
        rel = path.lstrip("/")
        if rel.startswith(_NO_DETECT_PREFIXES):
            return
        method = scope.get("method", "GET")
        if scanner_paths.is_scanner_path(path):
            self._event(ip, "blocked_path_200" if status == 200 else "blocked_path", path, status, ua)
            if status == 200:
                self._slip(ip, method, path)
            self._release_fallback(ip)
            decision = self.detector.record_scanner_hit(ip)
            if decision:
                self._apply(decision)
            return
        if status == 404:
            if rel.startswith(_NO_404_PREFIXES) or _header(scope.get("headers") or [], b"authorization"):
                return
            self._event(ip, "notfound", path, 404, ua)
            decision = self.detector.record_notfound(ip)
            if decision:
                self._apply(decision)
            return
        if method == "POST" and path == "/auth/login" and status == 401:
            self._event(ip, "auth_fail", path, 401, ua)
            return
        if (scope.get("state") or {}).get("spa_fallback"):
            if self.detector.has_strikes(ip) or self.cache.is_blocked(ip):
                self._event(ip, "assoc_path", path, status, ua)
            else:
                self._remember_fallback(ip, path)

    # ── decisions ──
    def _apply(self, decision: Decision) -> None:
        ip = decision.ip
        if is_protected_ip(ip):
            log.info("bot_guard: %s would be blocked (%s) but is protected — ignoring", ip, decision.reason)
            return
        if self.cache.is_blocked(ip):
            return
        self.cache.add(ip, time.time() + AUTO_BLOCK_TTL_DAYS * 86400)
        with self._lock:
            self._pending_blocks.append((ip, decision.reason))
        self._release_fallback(ip)
        if enforce_enabled():
            self._send_alert(f"🚫 Bot blocked: {ip} — reason: {decision.reason}")
        else:
            self._send_alert(f"🕵️ [shadow] Would block: {ip} — reason: {decision.reason}")
        self._dispatch(_safe(self.persist))

    def _slip(self, ip: str, method: str, path: str) -> None:
        now = time.time()
        if now - self._slips.get(path, 0.0) < 3600:
            return
        if len(self._slips) > 1000:
            self._slips.clear()
        self._slips[path] = now
        text = (f"🚨 <b>Security regression</b> — {html.escape(method)} {html.escape(path)} "
                f"returned 200 to {ip}. A scanner path should be 404.")
        self._dispatch(_safe(self._critical_fn), "security_slip", text)

    def _send_alert(self, text: str) -> None:
        if self._budget.allow():
            self._dispatch(_safe(self._alert_fn), text)

    # ── events ──
    def _cap_ok(self, ip: str, kind: str) -> bool:
        limit = _EVENT_CAPS.get(kind)
        if limit is None:
            return True
        hour = int(time.time() // 3600)
        with self._lock:
            rec = self._caps.get((ip, kind))
            if rec and rec[0] == hour:
                if rec[1] >= limit:
                    return False
                self._caps[(ip, kind)] = (hour, rec[1] + 1)
            else:
                self._caps[(ip, kind)] = (hour, 1)
            if len(self._caps) > 50000:
                self._caps.clear()
        return True

    def _event(self, ip: str, kind: str, path, status, ua) -> None:
        if not self._cap_ok(ip, kind):
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self._events.append((ts, ip, kind, path, status, ua))

    def _remember_fallback(self, ip: str, path: str) -> None:
        with self._lock:
            dq = self._fallback.get(ip)
            if dq is None:
                dq = self._fallback[ip] = deque(maxlen=_FALLBACK_PER_IP)
            dq.append(path)
            self._fallback.move_to_end(ip)
            while len(self._fallback) > _FALLBACK_TRACK_MAX_IPS:
                self._fallback.popitem(last=False)

    def _release_fallback(self, ip: str) -> None:
        with self._lock:
            paths = self._fallback.pop(ip, ())
        for p in paths:
            self._event(ip, "assoc_path", p, 200, None)

    # ── persistence ──
    def persist(self) -> None:
        with self._lock:
            events, self._events = list(self._events), deque(maxlen=_EVENT_BUFFER_MAX)
            blocks, self._pending_blocks = self._pending_blocks, []
            denied, self._denied = self._denied, {}
        if not (events or blocks or denied):
            return
        try:
            path = self._db_path_fn()
            for ip, reason in blocks:
                security_store.add_blocked_ip(path, ip, reason, source="auto", ttl_days=AUTO_BLOCK_TTL_DAYS)
            security_store.insert_events(path, events)
            security_store.add_denied(path, denied)
        except Exception:
            log.exception("bot_guard: persist failed (blocks re-queued, events dropped)")
            with self._lock:
                self._pending_blocks[:0] = blocks

    def flush(self) -> None:
        """Scheduler entry point (every 30s): persist buffers, then summarise suppressed alerts."""
        self.persist()
        overflow = self._budget.take_overflow()
        if overflow:
            self._dispatch(_safe(self._alert_fn),
                           f"🚫 …and {overflow} more bot IP(s) flagged (alert limit reached) — "
                           f"send <code>blocked ips</code> to list them")

    def unblock(self, ip: str) -> bool:
        """Manual unblock: clear the in-memory cache and deactivate the DB row."""
        removed = self.cache.remove(ip)
        changed = security_store.unblock_ip(self._db_path_fn(), ip)
        return changed or removed


guard = Guard()


def init(db_path) -> None:
    guard.init(db_path)


def flush() -> None:
    guard.flush()


# ── ASGI middleware ──────────────────────────────────────────────────────────

async def _deny(scope, receive, send) -> None:
    if scope["type"] == "websocket":
        await receive()  # consume websocket.connect
        await send({"type": "websocket.close", "code": 1008})
        return
    from starlette.responses import JSONResponse
    await JSONResponse({"detail": "Forbidden"}, status_code=403)(scope, receive, send)


class BotGuardMiddleware:
    """Outermost middleware. Fails open: any internal error serves the request untouched."""

    def __init__(self, app, guard=None):
        self.app = app
        self._guard = guard

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        g = self._guard or globals()["guard"]
        plan, ip, ua = "pass", None, None
        try:
            headers = scope.get("headers") or []
            ip = client_ip(scope)
            if ip is not None and not (scope["type"] == "http" and is_canary_request(headers)):
                g.ensure_loaded()
                ua = _header(headers, b"user-agent")
                enforce = enforce_enabled()
                if g.is_blocked(ip):
                    g.count_denied(ip)
                    plan = "deny" if enforce else "watch"
                else:
                    plan = "watch"
                    if scope["type"] == "http":
                        decision = g.on_request(ip, ua)
                        if decision and enforce and g.is_blocked(ip):
                            plan = "deny"
        except Exception:
            log.exception("bot_guard: pre-request check failed (failing open)")
            plan = "pass"

        if plan == "deny":
            return await _deny(scope, receive, send)
        if plan == "watch" and scope["type"] == "http":
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    try:
                        g.on_response(ip, scope, message["status"], ua)
                    except Exception:
                        log.exception("bot_guard: response check failed (ignored)")
                await send(message)
            return await self.app(scope, receive, send_wrapper)
        return await self.app(scope, receive, send)
