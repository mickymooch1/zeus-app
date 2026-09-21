"""bot_guard core logic — pure functions/classes, no I/O.

The single most dangerous failure here is blocking the WRONG address: behind
Railway, request.client.host is a rotating 100.64.x.x proxy, so keying on it
would lock out every visitor. client_ip() / is_protected_ip() are pinned hard.

Note: tests use real public addresses (8.8.8.8, 45.13.7.2 ...). Python's
ipaddress treats documentation ranges like 203.0.113.0/24 as non-global, so
they would count as "protected" and hide bugs.
"""
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-bot-guard-tests")

import bot_guard


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def _scope(peer, real_ip=None, extra=()):
    headers = list(extra)
    if real_ip is not None:
        headers.append((b"x-real-ip", real_ip.encode()))
    return {"type": "http", "client": (peer, 40000), "headers": headers}


# ── client_ip ────────────────────────────────────────────────────────────────

def test_real_ip_is_read_from_x_real_ip_when_peer_is_the_railway_proxy():
    assert bot_guard.client_ip(_scope("100.64.0.7", "45.13.7.2")) == "45.13.7.2"


def test_spoofed_x_real_ip_from_a_non_proxy_peer_is_ignored():
    # A direct client can send any header it likes; only Railway's proxy is trusted.
    assert bot_guard.client_ip(_scope("45.13.7.2", "8.8.8.8")) == "45.13.7.2"


def test_proxy_peer_without_a_usable_header_yields_none_never_the_proxy():
    assert bot_guard.client_ip(_scope("100.64.0.7")) is None
    assert bot_guard.client_ip(_scope("100.64.0.7", "not-an-ip")) is None


def test_unparseable_or_missing_peer_yields_none():
    assert bot_guard.client_ip({"type": "http", "headers": []}) is None
    assert bot_guard.client_ip(_scope("testclient")) is None  # starlette TestClient


def test_ipv6_real_ip_and_whitespace_are_handled():
    assert bot_guard.client_ip(_scope("100.64.0.7", " 2001:4860:4860::8888 ")) == "2001:4860:4860::8888"


# ── is_protected_ip ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("ip", [
    "10.1.2.3", "172.16.0.9", "192.168.1.1", "127.0.0.1", "::1", "169.254.1.1",
    "100.64.0.21", "100.127.255.254", "0.0.0.0", "224.0.0.1",
])
def test_private_loopback_cgnat_and_reserved_ips_are_never_blockable(ip):
    assert bot_guard.is_protected_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "45.13.7.2", "2001:4860:4860::8888"])
def test_ordinary_public_ips_are_blockable(ip):
    assert bot_guard.is_protected_ip(ip) is False


def test_allowlist_env_supports_single_ips_and_cidrs(monkeypatch):
    monkeypatch.setenv("SECURITY_IP_ALLOWLIST", "8.8.4.4, 45.0.0.0/8 ,junk")
    assert bot_guard.is_protected_ip("8.8.4.4") is True
    assert bot_guard.is_protected_ip("45.13.7.2") is True
    assert bot_guard.is_protected_ip("8.8.8.8") is False


def test_garbage_input_is_treated_as_protected_so_it_can_never_be_blocked():
    assert bot_guard.is_protected_ip("not-an-ip") is True


# ── user agents ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ua,name", [
    ("sqlmap/1.7.2#stable (https://sqlmap.org)", "sqlmap"),
    ("Mozilla/5.00 (Nikto/2.1.6) (Evasions:None)", "nikto"),
    ("masscan/1.3 (https://github.com/robertdavidgraham/masscan)", "masscan"),
    ("Mozilla/5.0 (compatible; Nmap Scripting Engine)", "nmap"),
    ("gobuster/3.1.0", "gobuster"),
    ("WPScan v3.8.22", "wpscan"),
    ("Nuclei - Open-source project (github.com/projectdiscovery/nuclei)", "nuclei"),
    ("FEROXBUSTER/2.7.1", "feroxbuster"),
])
def test_known_scanner_user_agents_are_named(ua, name):
    assert bot_guard.is_bad_user_agent(ua) == name


@pytest.mark.parametrize("ua", [
    "curl/8.4.0", "python-requests/2.31.0", "Go-http-client/2.0", "node-fetch",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "TelegramBot (like TwitterBot)", "WhatsApp/2.23.20.0", "", None,
])
def test_generic_clients_and_real_browsers_are_never_flagged(ua):
    assert bot_guard.is_bad_user_agent(ua) is None


# ── enforcement flag ─────────────────────────────────────────────────────────

def test_enforcement_is_off_by_default_and_on_for_truthy_values(monkeypatch):
    monkeypatch.delenv("SECURITY_ENFORCE", raising=False)
    assert bot_guard.enforce_enabled() is False
    for v in ("1", "true", "YES"):
        monkeypatch.setenv("SECURITY_ENFORCE", v)
        assert bot_guard.enforce_enabled() is True
    for v in ("0", "", "false", "no", "shadow"):
        monkeypatch.setenv("SECURITY_ENFORCE", v)
        assert bot_guard.enforce_enabled() is False


# ── canary header ────────────────────────────────────────────────────────────

def test_canary_token_is_stable_within_a_day_and_changes_across_days():
    d1 = datetime(2026, 9, 21, 9, 30, tzinfo=timezone.utc)
    assert bot_guard.canary_token(d1) == bot_guard.canary_token(d1 + timedelta(hours=5))
    assert bot_guard.canary_token(d1) != bot_guard.canary_token(d1 + timedelta(days=1))


def test_canary_request_accepts_today_and_yesterday_but_not_forgeries():
    now = datetime.now(timezone.utc)
    ok_today = [(b"x-security-canary", bot_guard.canary_token(now).encode())]
    ok_yday = [(b"x-security-canary", bot_guard.canary_token(now - timedelta(days=1)).encode())]
    old = [(b"x-security-canary", bot_guard.canary_token(now - timedelta(days=3)).encode())]
    fake = [(b"x-security-canary", b"deadbeef")]
    assert bot_guard.is_canary_request(ok_today) is True
    assert bot_guard.is_canary_request(ok_yday) is True
    assert bot_guard.is_canary_request(old) is False
    assert bot_guard.is_canary_request(fake) is False
    assert bot_guard.is_canary_request([]) is False


def test_canary_is_disabled_without_a_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert bot_guard.canary_token() == ""
    assert bot_guard.is_canary_request([(b"x-security-canary", b"")]) is False


# ── Detector ─────────────────────────────────────────────────────────────────

def test_fifth_scanner_hit_inside_the_window_decides_a_block():
    c = Clock()
    d = bot_guard.Detector(clock=c)
    for _ in range(4):
        assert d.record_scanner_hit("45.13.7.2") is None
        c.advance(10)
    dec = d.record_scanner_hit("45.13.7.2")
    assert dec is not None
    assert (dec.ip, dec.kind) == ("45.13.7.2", "scanner_paths")
    assert dec.reason == "5 probe attempts"


def test_old_scanner_hits_age_out_of_the_window():
    c = Clock()
    d = bot_guard.Detector(clock=c)
    for _ in range(4):
        d.record_scanner_hit("45.13.7.2")
    c.advance(301)
    assert d.record_scanner_hit("45.13.7.2") is None


def test_scanner_windows_are_per_ip():
    d = bot_guard.Detector(clock=Clock())
    for _ in range(4):
        d.record_scanner_hit("45.13.7.2")
    assert d.record_scanner_hit("8.8.8.8") is None


def test_a_decision_resets_that_ips_window():
    d = bot_guard.Detector(clock=Clock())
    for _ in range(4):
        d.record_scanner_hit("45.13.7.2")
    assert d.record_scanner_hit("45.13.7.2") is not None
    assert d.record_scanner_hit("45.13.7.2") is None


def test_twentieth_404_inside_sixty_seconds_decides_a_block():
    c = Clock()
    d = bot_guard.Detector(clock=c)
    for _ in range(19):
        assert d.record_notfound("45.13.7.2") is None
        c.advance(2)
    dec = d.record_notfound("45.13.7.2")
    assert dec is not None and dec.kind == "notfound_flood"
    assert dec.reason == "20 404s in 60s"


def test_slow_404s_never_reach_the_threshold():
    c = Clock()
    d = bot_guard.Detector(clock=c)
    for _ in range(100):
        assert d.record_notfound("45.13.7.2") is None
        c.advance(4)  # 15 per minute


def test_has_strikes_reflects_recent_scanner_hits_only():
    c = Clock()
    d = bot_guard.Detector(clock=c)
    assert d.has_strikes("45.13.7.2") is False
    d.record_scanner_hit("45.13.7.2")
    assert d.has_strikes("45.13.7.2") is True
    c.advance(301)
    assert d.has_strikes("45.13.7.2") is False


def test_detector_memory_is_bounded():
    c = Clock()
    d = bot_guard.Detector(clock=c, max_ips=10)
    for i in range(25):
        d.record_scanner_hit(f"45.13.7.{i}")
    c.advance(400)
    d.record_scanner_hit("8.8.8.8")
    assert d.tracked_ips() <= 10


# ── BlockCache ───────────────────────────────────────────────────────────────

def test_block_cache_load_add_remove_and_expiry():
    c = Clock(1_000.0)
    cache = bot_guard.BlockCache(clock=c)
    cache.load([("45.13.7.2", None), ("8.8.8.8", 1_100.0)])
    assert cache.is_blocked("45.13.7.2") and cache.is_blocked("8.8.8.8")
    c.advance(101)
    assert cache.is_blocked("8.8.8.8") is False       # expired
    assert cache.is_blocked("45.13.7.2") is True      # permanent
    cache.add("1.2.3.4", None)
    assert cache.is_blocked("1.2.3.4") is True
    assert cache.remove("1.2.3.4") is True
    assert cache.remove("1.2.3.4") is False
    assert cache.is_blocked("1.2.3.4") is False


def test_block_cache_load_replaces_previous_contents():
    cache = bot_guard.BlockCache(clock=Clock())
    cache.load([("45.13.7.2", None)])
    cache.load([("8.8.8.8", None)])
    assert cache.is_blocked("45.13.7.2") is False
    assert set(cache.snapshot()) == {"8.8.8.8"}


# ── AlertBudget ──────────────────────────────────────────────────────────────

def test_alert_budget_caps_bursts_and_reports_the_overflow_once():
    c = Clock()
    b = bot_guard.AlertBudget(limit=2, window=600, clock=c)
    assert [b.allow(), b.allow(), b.allow(), b.allow()] == [True, True, False, False]
    assert b.take_overflow() == 2
    assert b.take_overflow() == 0
    c.advance(601)
    assert b.allow() is True
