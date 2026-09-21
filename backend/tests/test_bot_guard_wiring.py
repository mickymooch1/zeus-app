"""The guard is wired into the REAL app: installed outermost, fed by serve_spa,
and loaded at startup. Driven with a crafted proxied ASGI scope (Starlette's
TestClient presents peer 'testclient', which the guard deliberately ignores)."""
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-bot-guard-wiring-tests")

import bot_guard
import db
import security_store as store

BAD = "45.13.7.2"


@pytest.fixture
def wired(tmp_path, monkeypatch):
    import main as _main
    monkeypatch.delenv("SECURITY_ENFORCE", raising=False)
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SHELL {{GENRE_COUNT}}</html>", encoding="utf-8")
    monkeypatch.setattr(_main, "_beats_dist", dist)
    monkeypatch.setattr(_main, "_dist", dist)
    alerts = []
    g = bot_guard.Guard(db_path_fn=lambda: path, alert_fn=alerts.append,
                        critical_alert_fn=lambda c, m: alerts.append(m),
                        dispatch=lambda fn, *a: fn(*a))
    g.init(path)
    monkeypatch.setattr(bot_guard, "guard", g)      # the middleware resolves the guard at call time
    return type("W", (), dict(main=_main, guard=g, path=path, alerts=alerts))


def request(app, path, real=BAD, host="zeusbeats.com"):
    scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": [(b"host", host.encode()), (b"x-real-ip", real.encode()), (b"user-agent", b"Mozilla/5.0")],
             "client": ("100.64.0.7", 5000), "server": ("testserver", 443), "scheme": "https"}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        sent.append(m)

    asyncio.run(app(scope, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_the_middleware_is_installed_and_is_the_outermost_layer(wired):
    names = [m.cls.__name__ for m in wired.main.app.user_middleware]
    assert "BotGuardMiddleware" in names
    assert names[0] == "BotGuardMiddleware", "must wrap CORS and everything else"


def test_scanner_probes_through_the_real_app_end_in_a_block_decision(wired):
    for _ in range(5):
        assert request(wired.main.app, "/.git/config") == 404
    assert wired.guard.cache.is_blocked(BAD)
    assert wired.alerts and "Would block" in wired.alerts[0]      # shadow mode: alerts, does not deny
    assert request(wired.main.app, "/roast") == 200               # ...and still serves the site


def test_serve_spa_marks_the_shell_fallback_so_probe_paths_can_be_associated(wired):
    assert request(wired.main.app, "/some/odd/route") == 200
    assert BAD in wired.guard._fallback
    assert list(wired.guard._fallback[BAD]) == ["/some/odd/route"]


def test_enforcement_through_the_real_app(wired, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    store.add_blocked_ip(wired.path, BAD, "5 probe attempts")
    wired.guard.init(wired.path)
    assert request(wired.main.app, "/roast") == 403
    assert request(wired.main.app, "/roast", real="8.8.8.8") == 200   # other visitors unaffected


def test_startup_loads_the_blocked_ips(wired):
    src = pathlib.Path(wired.main.__file__).read_text(encoding="utf-8")
    assert "bot_guard.init(" in src, "lifespan must load the block list from the DB"
