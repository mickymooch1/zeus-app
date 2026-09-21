"""BotGuardMiddleware + Guard runtime, driven with crafted ASGI scopes.

The middleware sits in front of EVERY request, so the tests weigh "must never
break the site" as heavily as "blocks scanners":
  * fail-open on any internal error,
  * pass-through when the client IP is unknown/untrusted (incl. Starlette TestClient),
  * shadow mode serves everything but still records/alerts,
  * protected IPs, the canary header and exempt paths never accumulate strikes.
"""
import asyncio
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-bot-guard-middleware-tests")

import bot_guard
import db
import security_store as store

BAD = "45.13.7.2"


@pytest.fixture(autouse=True)
def _shadow_by_default(monkeypatch):
    monkeypatch.delenv("SECURITY_ENFORCE", raising=False)
    monkeypatch.delenv("SECURITY_IP_ALLOWLIST", raising=False)


@pytest.fixture
def env(tmp_path):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    alerts, critical = [], []
    guard = bot_guard.Guard(
        db_path_fn=lambda: path,
        alert_fn=alerts.append,
        critical_alert_fn=lambda cat, msg: critical.append((cat, msg)),
        dispatch=lambda fn, *a: fn(*a),      # synchronous, so tests are deterministic
    )
    guard.init(path)
    served, routes = [], {}

    async def app(scope, receive, send):
        if scope["type"] == "websocket":
            served.append("ws")
            await send({"type": "websocket.accept"})
            return
        status, spa = routes.get(scope["path"], (200, False))
        served.append(scope["path"])
        if spa:
            scope.setdefault("state", {})["spa_fallback"] = True
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"ok"})

    mw = bot_guard.BotGuardMiddleware(app, guard=guard)
    return type("Env", (), dict(path=path, guard=guard, alerts=alerts, critical=critical,
                                served=served, routes=routes, mw=mw))


def call(env, path="/", real=BAD, peer="100.64.0.7", ua=None, method="GET", headers=(), typ="http"):
    hdrs = list(headers)
    if real:
        hdrs.append((b"x-real-ip", real.encode()))
    if ua is not None:
        hdrs.append((b"user-agent", ua.encode()))
    scope = {"type": typ, "method": method, "path": path, "headers": hdrs,
             "client": (peer, 5000), "query_string": b""}
    sent = []

    async def receive():
        if typ == "websocket":
            return {"type": "websocket.connect"}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        sent.append(m)

    asyncio.run(env.mw(scope, receive, send))
    return sent


def status(sent):
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def flush(env):
    env.guard.flush()


def events(env, kinds):
    from datetime import datetime, timedelta, timezone
    return store.events_since(env.path, kinds, datetime.now(timezone.utc) - timedelta(days=1))


# ── pass-through ─────────────────────────────────────────────────────────────

def test_unknown_client_ip_passes_through_without_touching_the_database(tmp_path):
    def boom():
        raise AssertionError("db must not be touched for an untrusted/unknown client")
    served = []

    async def app(scope, receive, send):
        served.append(1)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = bot_guard.BotGuardMiddleware(app, guard=bot_guard.Guard(db_path_fn=boom))
    scope = {"type": "http", "method": "GET", "path": "/.git/config", "headers": [],
             "client": ("testclient", 50000)}
    sent = []

    async def send(m):
        sent.append(m)

    asyncio.run(mw(scope, lambda: None, send))
    assert served and status(sent) == 200


def test_non_http_scopes_are_ignored(env):
    calls = []

    async def app(scope, receive, send):
        calls.append(scope["type"])

    mw = bot_guard.BotGuardMiddleware(app, guard=env.guard)
    asyncio.run(mw({"type": "lifespan"}, None, None))
    assert calls == ["lifespan"]


# ── blocked IPs: shadow vs enforce ───────────────────────────────────────────

def test_shadow_mode_serves_a_blocked_ip_but_counts_the_would_be_denial(env):
    store.add_blocked_ip(env.path, BAD, "5 probe attempts")
    env.guard.init(env.path)
    assert status(call(env, "/roast")) == 200
    flush(env)
    (row,) = store.active_blocked(env.path)
    assert row["denied_requests"] == 1


def test_enforce_mode_403s_a_blocked_ip_without_calling_the_app(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    store.add_blocked_ip(env.path, BAD, "5 probe attempts")
    env.guard.init(env.path)
    sent = call(env, "/roast")
    assert status(sent) == 403
    assert env.served == []
    assert b"Forbidden" in b"".join(m.get("body", b"") for m in sent)


def test_enforce_mode_closes_blocked_websocket_handshakes(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    store.add_blocked_ip(env.path, BAD, "x")
    env.guard.init(env.path)
    sent = call(env, "/ws", typ="websocket")
    assert {"type": "websocket.close", "code": 1008} in sent
    assert env.served == []


def test_block_cache_is_loaded_lazily_from_the_db_on_first_request(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    store.add_blocked_ip(env.path, BAD, "x")
    fresh = bot_guard.Guard(db_path_fn=lambda: env.path, dispatch=lambda fn, *a: fn(*a))
    env.mw = bot_guard.BotGuardMiddleware(env.mw.app, guard=fresh)
    assert status(call(env, "/")) == 403


# ── scanner strikes → block ──────────────────────────────────────────────────

def test_five_scanner_hits_block_the_ip_persist_it_and_alert(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    env.routes["/.git/config"] = (404, False)
    assert [status(call(env, "/.git/config")) for _ in range(5)] == [404] * 5
    assert env.guard.cache.is_blocked(BAD)
    assert env.alerts == [f"🚫 Bot blocked: {BAD} — reason: 5 probe attempts"]
    (row,) = store.active_blocked(env.path)
    assert row["ip"] == BAD and row["reason"] == "5 probe attempts" and row["source"] == "auto"
    served_before = len(env.served)
    assert status(call(env, "/anything")) == 403
    assert len(env.served) == served_before
    flush(env)
    assert len(events(env, ["blocked_path"])) == 5
    assert store.active_blocked(env.path)[0]["denied_requests"] == 1


def test_shadow_mode_records_and_alerts_but_never_denies(env):
    env.routes["/.git/config"] = (404, False)
    for _ in range(5):
        call(env, "/.git/config")
    assert env.alerts == [f"🕵️ [shadow] Would block: {BAD} — reason: 5 probe attempts"]
    assert len(store.active_blocked(env.path)) == 1
    assert status(call(env, "/roast")) == 200


def test_a_200_on_a_scanner_path_is_a_regression_alert_sent_once(env):
    env.routes["/.env"] = (200, False)
    call(env, "/.env")
    call(env, "/.env")
    assert len(env.critical) == 1
    cat, msg = env.critical[0]
    assert cat == "security_slip" and "/.env" in msg
    flush(env)
    assert len(events(env, ["blocked_path_200"])) == 2


# ── things that must never accumulate strikes ────────────────────────────────

def test_protected_ips_are_never_blocked(env):
    env.routes["/.git/config"] = (404, False)
    for _ in range(12):
        call(env, "/.git/config", real=None, peer="10.0.0.5")            # direct private peer
        call(env, "/.git/config", real="192.168.1.5")                     # private address via proxy
    assert env.alerts == [] and store.active_blocked(env.path) == []


def test_allowlisted_ip_is_never_blocked(env, monkeypatch):
    monkeypatch.setenv("SECURITY_IP_ALLOWLIST", BAD)
    env.routes["/.git/config"] = (404, False)
    for _ in range(12):
        call(env, "/.git/config")
    assert store.active_blocked(env.path) == []


def test_the_canary_header_exempts_the_scans_own_probes(env):
    env.routes["/.git/config"] = (404, False)
    hdr = [(b"x-security-canary", bot_guard.canary_token().encode())]
    for _ in range(12):
        call(env, "/.git/config", headers=hdr)
    flush(env)
    assert store.active_blocked(env.path) == [] and events(env, ["blocked_path"]) == []


def test_forged_canary_header_does_not_exempt(env):
    env.routes["/.git/config"] = (404, False)
    for _ in range(5):
        call(env, "/.git/config", headers=[(b"x-security-canary", b"forged")])
    assert len(store.active_blocked(env.path)) == 1


# ── bad user agents ──────────────────────────────────────────────────────────

def test_scanner_user_agent_is_blocked_on_the_first_request(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    assert status(call(env, "/", ua="sqlmap/1.7.2#stable")) == 403     # that very request
    (row,) = store.active_blocked(env.path)
    assert row["reason"] == "scanner tool sqlmap"
    assert env.alerts == [f"🚫 Bot blocked: {BAD} — reason: scanner tool sqlmap"]


def test_curl_and_python_requests_are_not_bad_user_agents(env, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    assert status(call(env, "/", ua="curl/8.4.0")) == 200
    assert status(call(env, "/", ua="python-requests/2.31.0")) == 200
    assert store.active_blocked(env.path) == []


# ── 404 flood ────────────────────────────────────────────────────────────────

def test_twenty_404s_in_a_minute_block_the_ip(env):
    env.routes["/api/nope"] = (404, False)
    for _ in range(20):
        call(env, "/api/nope")
    (row,) = store.active_blocked(env.path)
    assert row["reason"] == "20 404s in 60s"


@pytest.mark.parametrize("path,headers", [
    ("/files/songs/gone.mp3", ()),
    ("/api/files/songs/gone.mp3", ()),
    ("/webhooks/stripe", ()),
    ("/api/songs/999", [(b"authorization", b"Bearer abc")]),
])
def test_legitimate_404s_never_trigger_the_flood_rule(env, path, headers):
    env.routes[path] = (404, False)
    for _ in range(30):
        call(env, path, headers=headers)
    assert store.active_blocked(env.path) == []


# ── auth failures ────────────────────────────────────────────────────────────

def test_failed_logins_are_recorded_as_auth_fail_events(env):
    env.routes["/auth/login"] = (401, False)
    call(env, "/auth/login", method="POST")
    call(env, "/auth/login", method="GET")          # not a login attempt
    env.routes["/auth/login"] = (200, False)
    call(env, "/auth/login", method="POST")         # success
    flush(env)
    evs = events(env, ["auth_fail"])
    assert [(e["ip"], e["path"], e["status"]) for e in evs] == [(BAD, "/auth/login", 401)]


# ── probe-path candidates by association ─────────────────────────────────────

def test_spa_fallback_paths_become_assoc_events_once_the_ip_shows_scanner_behaviour(env):
    env.routes["/roast"] = (200, True)
    env.routes["/odd/thing"] = (200, True)
    env.routes["/.git/config"] = (404, False)
    call(env, "/roast")                       # remembered, not recorded (looks like a normal visitor)
    flush(env)
    assert events(env, ["assoc_path"]) == []
    call(env, "/.git/config")                 # strike -> remembered paths are recorded
    call(env, "/odd/thing")                   # ip now has strikes -> recorded directly
    flush(env)
    assert [e["path"] for e in events(env, ["assoc_path"])] == ["/roast", "/odd/thing"]


# ── alert flood control ──────────────────────────────────────────────────────

def test_alert_budget_caps_immediate_alerts_and_flush_summarises_the_rest(env):
    env.routes["/.git/config"] = (404, False)
    for i in range(8):
        for _ in range(5):
            call(env, "/.git/config", real=f"45.13.7.{i}")
    assert len(env.alerts) == 5
    flush(env)
    assert len(env.alerts) == 6 and "and 3 more" in env.alerts[-1]
    assert len(store.active_blocked(env.path)) == 8


# ── fail open ────────────────────────────────────────────────────────────────

def test_an_internal_error_never_breaks_the_request(env):
    env.routes["/.git/config"] = (404, False)

    def boom(ip):
        raise RuntimeError("detector exploded")
    env.guard.detector.record_scanner_hit = boom
    assert status(call(env, "/.git/config")) == 404
    assert status(call(env, "/roast")) == 200


def test_a_failing_database_does_not_break_requests_or_lose_the_block(env):
    def dead():
        raise RuntimeError("db down")
    env.guard._db_path_fn = dead
    env.routes["/.git/config"] = (404, False)
    for _ in range(5):
        assert status(call(env, "/.git/config")) == 404
    assert env.guard.cache.is_blocked(BAD)         # still protected in memory
    env.guard.flush()                              # must not raise
