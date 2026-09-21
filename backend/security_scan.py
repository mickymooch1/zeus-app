"""The security scan (every 3 days), canary probes and the Monday weekly summary.

Design: docs/superpowers/specs/2026-09-21-security-monitor-design.md

The scan reads what bot_guard recorded (security_events) plus song_variants, and
also probes the LIVE site (canary) so a regression in routing, the Dockerfile or the
proxy is caught even if no scanner happens to trip over it. It ALWAYS reports —
"✅ Security scan clean" is a heartbeat as much as a result.
"""
from __future__ import annotations

import html
import http.client
import logging
import os
import pathlib
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import bot_guard
import db
import scanner_paths
import security_store as store

log = logging.getLogger("zeus.security_scan")

_TS = "%Y-%m-%d %H:%M:%S"
SCAN_INTERVAL = timedelta(days=3)
# A daily 09:30 job sees 2d23h59m55s after the last run; without slack the scan would
# drift to every 4 days.
SCAN_SLACK = timedelta(hours=1)
WEEKLY_MIN_GAP = timedelta(days=6)
WINDOW_DAYS = 3
EVENT_RETENTION_DAYS = 30

VOLUME_FLOOR, VOLUME_MULT = 100, 5          # scanner hits/24h: > floor AND > mult × trailing daily avg
BRUTE_MIN = 20                              # failed logins from one IP inside the window
USER_GEN_MIN, USER_GEN_MULT = 30, 5         # songs/24h: >= min AND >= mult × the user's own daily avg
GLOBAL_GEN_MIN, GLOBAL_GEN_MULT = 50, 3    # songs/24h across all non-admin users

CANARY_BLOCKED_PATHS = ("/.git/config", "/.env", "/wp-admin")
CANARY_TRAVERSAL = "/../app/requirements.txt"


@dataclass
class Finding:
    level: str   # 'critical' | 'review'
    text: str


@dataclass
class ScanReport:
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    candidates: list[tuple[str, int]] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "review" if self.findings else "clean"


def _utc(now):
    return now or datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, _TS).replace(tzinfo=timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS)


def _db_path():
    return db.get_db_path()


def _default_send(text: str) -> None:
    import alerts
    alerts._send_telegram(text)     # bypass dedup: a scan report must always send


# ── canary ───────────────────────────────────────────────────────────────────

def _fetch(host: str, path: str, headers: dict, timeout: float = 6):
    """One raw HTTPS GET. http.client sends the path verbatim (no `..` normalisation),
    which is the whole point of the traversal probe."""
    conn = http.client.HTTPSConnection(host, timeout=timeout)
    try:
        conn.putrequest("GET", path, skip_accept_encoding=True)
        for k, v in headers.items():
            conn.putheader(k, v)
        conn.putheader("User-Agent", "ZeusSecurityCanary/1")
        conn.endheaders()
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type", "") or "", r.read(2048)
    finally:
        conn.close()


def canary_probe(hosts=None, fetch=None, timeout: float = 6) -> list[Finding]:
    """Probe the live site: scanner paths must not return 200 and traversal must not
    return a real file. Carries the canary header so the app never strikes itself."""
    if hosts is None:
        hosts = [h.strip() for h in os.environ.get(
            "SECURITY_CANARY_HOSTS", "zeusbeats.com,zeusaidesign.com").split(",") if h.strip()]
    fetch = fetch or (lambda h, p, hd: _fetch(h, p, hd, timeout))
    headers = {"X-Security-Canary": bot_guard.canary_token()}
    tasks = [(h, p) for h in hosts for p in (*CANARY_BLOCKED_PATHS, CANARY_TRAVERSAL)]

    def probe(task):
        try:
            return task, fetch(task[0], task[1], headers), None
        except Exception as exc:  # network errors are findings, not crashes
            return task, None, exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, tasks))

    findings, unreachable = [], {}
    for (host, path), resp, exc in results:
        if exc is not None:
            unreachable.setdefault(host, exc)
            continue
        status, content_type, _body = resp
        if path == CANARY_TRAVERSAL:
            if status == 200 and "text/html" not in content_type.lower():
                findings.append(Finding(
                    "critical", f"canary: path traversal — https://{host}{path} returned a real file "
                                f"({content_type or 'no content-type'})"))
        elif status == 200:
            findings.append(Finding(
                "critical", f"canary: https://{host}{path} returned 200 (expected 404) — the "
                            f"scanner-path block has regressed"))
    for host, exc in unreachable.items():
        findings.append(Finding("review", f"canary could not reach {host}: {type(exc).__name__}: {exc}"))
    return findings


# ── checks ───────────────────────────────────────────────────────────────────

def _check_slips(path, since, report):
    n = store.count_events(path, "blocked_path_200", since)
    if n:
        top = ", ".join(p for p, _ in store.top_paths(path, ["blocked_path_200"], since, limit=3))
        report.findings.append(Finding(
            "critical", f"{n} request(s) got 200 on a scanner path ({top}) — the path blocklist has regressed"))


def _check_volume(path, now, report):
    today = store.count_events(path, "blocked_path", now - timedelta(days=1))
    prior = store.count_events(path, "blocked_path", now - timedelta(days=8), until=now - timedelta(days=1))
    avg = prior / 7
    report.stats["scanner_hits_24h"], report.stats["scanner_avg_7d"] = today, round(avg, 1)
    if today > VOLUME_FLOOR and today > VOLUME_MULT * avg:
        report.findings.append(Finding(
            "review", f"Scanner probe spike: {today} in the last 24h vs {avg:.0f}/day trailing average"))


def _check_logins(path, since, report):
    total = store.count_events(path, "auth_fail", since)
    report.stats["failed_logins"] = total
    offenders = store.ip_counts(path, "auth_fail", since, min_count=BRUTE_MIN)
    if offenders:
        who = ", ".join(f"{ip} ({n})" for ip, n in offenders[:5])
        report.findings.append(Finding(
            "review", f"Possible brute force — failed logins from {who} in the last {WINDOW_DAYS}d"))


def _check_generation(path, now, report):
    since24, since15 = _fmt(now - timedelta(days=1)), _fmt(now - timedelta(days=15))
    conn = db._conn(path)
    try:
        per_user = conn.execute(
            """SELECT u.email AS email,
                      SUM(CASE WHEN datetime(sv.created_at) >= datetime(?) THEN 1 ELSE 0 END) AS last24,
                      SUM(CASE WHEN datetime(sv.created_at) <  datetime(?) THEN 1 ELSE 0 END) AS prior
               FROM song_variants sv JOIN users u ON u.id = sv.user_id
               WHERE COALESCE(u.is_admin, 0) = 0 AND datetime(sv.created_at) >= datetime(?)
               GROUP BY sv.user_id HAVING last24 >= ? ORDER BY last24 DESC""",
            (since24, since24, since15, USER_GEN_MIN)).fetchall()
        totals = conn.execute(
            """SELECT COALESCE(SUM(CASE WHEN datetime(sv.created_at) >= datetime(?) THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN datetime(sv.created_at) <  datetime(?) THEN 1 ELSE 0 END), 0)
               FROM song_variants sv JOIN users u ON u.id = sv.user_id
               WHERE COALESCE(u.is_admin, 0) = 0 AND datetime(sv.created_at) >= datetime(?)""",
            (since24, since24, since15)).fetchone()
    finally:
        conn.close()
    total24, total_prior = totals[0], totals[1]
    report.stats["songs_24h"] = total24
    for row in per_user:
        avg = row["prior"] / 14
        if row["last24"] >= USER_GEN_MULT * avg:
            report.findings.append(Finding(
                "review", f"{row['email']} created {row['last24']} songs in 24h (their usual: {avg:.1f}/day)"))
    gavg = total_prior / 14
    if total24 >= GLOBAL_GEN_MIN and total24 > GLOBAL_GEN_MULT * gavg:
        report.findings.append(Finding(
            "review", f"Total generation volume {total24} songs in 24h vs {gavg:.0f}/day average"))


def _check_candidates(path, since, report):
    counts = Counter()
    for e in store.events_since(path, ["assoc_path"], since):
        p = re.sub(r"[?#].*$", "", e["path"] or "")
        if p and p != "/" and not scanner_paths.is_scanner_path(p):
            counts[p] += 1
    last = store.last_scan(path, "scan")
    reported = set((last or {}).get("details", {}).get("reported_candidates", []))
    new = sorted(((p, n) for p, n in counts.items() if p not in reported), key=lambda t: (-t[1], t[0]))
    report.candidates = new[:10]
    report.stats["_all_new_candidates"] = [p for p, _ in new]
    if new:
        listed = ", ".join(f"{p} ×{n}" for p, n in report.candidates)
        report.findings.append(Finding(
            "review", f"New probe path(s) not in the blocklist, requested by flagged IPs: {listed} — "
                      f"add to scanner_paths.py if they are not real routes"))


# ── scan ─────────────────────────────────────────────────────────────────────

def run_scan(db_path=None, trigger: str = "scheduled", now: datetime | None = None,
             canary=None, window_days: int = WINDOW_DAYS) -> ScanReport:
    """Run every check, persist a security_scans row, return the report."""
    path = db_path or _db_path()
    now = _utc(now)
    since = now - timedelta(days=window_days)
    report = ScanReport(stats={"window_days": window_days})

    _check_slips(path, since, report)
    _check_volume(path, now, report)
    _check_logins(path, since, report)
    _check_generation(path, now, report)
    _check_candidates(path, since, report)

    try:
        report.findings.extend((canary or canary_probe)())
    except Exception as exc:
        log.exception("security_scan: canary crashed")
        report.findings.append(Finding("review", f"canary crashed: {type(exc).__name__}: {exc}"))

    events = store.events_since(path, ["blocked_path", "blocked_path_200"], since)
    report.stats["scanner_hits"] = len(events)
    report.stats["scanner_ips"] = len({e["ip"] for e in events})
    report.stats["flagged_ips"] = len(store.blocked_since(path, since))
    report.stats["active_blocks"] = len(store.active_blocked(path, now))

    previous = (store.last_scan(path, "scan") or {}).get("details", {}).get("reported_candidates", [])
    reported = list(dict.fromkeys([*previous, *report.stats.pop("_all_new_candidates", [])]))[-200:]
    store.record_scan(
        path, "scan", trigger, report.status,
        "clean" if not report.findings else f"{len(report.findings)} finding(s)",
        {"stats": report.stats, "findings": [{"level": f.level, "text": f.text} for f in report.findings],
         "reported_candidates": reported},
        now=now)
    return report


def _mode_line() -> str:
    return ("ENFORCING — blocked IPs get 403" if bot_guard.enforce_enabled()
            else "shadow mode — flagging only, not blocking")


def format_scan(report: ScanReport) -> str:
    s = report.stats
    head = ("✅ <b>Security scan clean</b>" if not report.findings
            else "⚠️ <b>Security scan — review needed</b>")
    lines = [head]
    for f in report.findings:
        lines.append(("🚨 " if f.level == "critical" else "• ") + html.escape(f.text))
    lines += [
        "",
        f"🔎 Probes ({s.get('window_days', WINDOW_DAYS)}d): {s.get('scanner_hits', 0)} from "
        f"{s.get('scanner_ips', 0)} IP(s), all refused",
        f"🚫 IPs flagged: {s.get('flagged_ips', 0)} new, {s.get('active_blocks', 0)} active",
        f"🔐 Failed logins: {s.get('failed_logins', 0)}",
        f"🎵 Songs (24h): {s.get('songs_24h', 0)}",
        f"🛡️ Mode: {_mode_line()}",
    ]
    return "\n".join(lines)


def run_if_due(now: datetime | None = None, db_path=None, canary=None, send=None) -> ScanReport | None:
    """Daily-job entry point: run the scan only if >= 3 days have passed since the last
    SCHEDULED scan (a manual scan does not reset the clock). Also prunes old events."""
    path = db_path or _db_path()
    now = _utc(now)
    last = store.last_scan(path, "scan", trigger="scheduled")
    if last and now - _parse(last["ts"]) < SCAN_INTERVAL - SCAN_SLACK:
        return None
    try:
        store.prune_events(path, days=EVENT_RETENTION_DAYS, now=now)
    except Exception:
        log.exception("security_scan: pruning old events failed (non-fatal)")
    report = run_scan(path, "scheduled", now, canary)
    try:
        (send or _default_send)(format_scan(report))
    except Exception:
        log.exception("security_scan: sending the scan report failed")
    return report


# ── weekly ───────────────────────────────────────────────────────────────────

def weekly_summary(db_path=None, now: datetime | None = None) -> tuple[str, str]:
    """(message, health) where health is 'clean' or 'review'."""
    path = db_path or _db_path()
    now = _utc(now)
    since = now - timedelta(days=7)

    blocks = store.blocked_since(path, since)
    by_reason = Counter(b["reason"] for b in blocks)
    top = store.top_paths(path, ["blocked_path", "blocked_path_200"], since, limit=8)
    slips = store.count_events(path, "blocked_path_200", since)
    brute = store.ip_counts(path, "auth_fail", since, min_count=BRUTE_MIN)
    scans = store.scans_since(path, "scan", since)
    threats = list(dict.fromkeys(
        f["text"] for s in scans for f in s["details"].get("findings", [])))

    health = "review" if (slips or brute or any(s["status"] == "review" for s in scans)) else "clean"
    lines = [
        "🛡️ <b>Weekly security summary</b>",
        "Health: " + ("✅ clean" if health == "clean" else "⚠️ review needed"),
        f"Mode: {_mode_line()}",
        "",
        f"🚫 IPs flagged this week: <b>{len(blocks)}</b>",
    ]
    lines += [f"   • {html.escape(r)} ×{n}" for r, n in by_reason.most_common(6)]
    lines += ["", "🔎 Most common probe paths:"]
    lines += [f"   • {html.escape(p)} ×{n}" for p, n in top] or ["   • none"]
    lines += ["", "🆕 New threats detected:"]
    if slips:
        threats.insert(0, f"{slips} request(s) got 200 on a scanner path")
    lines += [f"   • {html.escape(t)}" for t in threats] or ["   • none"]
    return "\n".join(lines), health


def send_weekly_if_due(now: datetime | None = None, db_path=None, send=None) -> bool:
    """Monday only, and at most once per ~week (idempotent across redeploys/reruns)."""
    now = _utc(now)
    if now.weekday() != 0:
        return False
    path = db_path or _db_path()
    last = store.last_scan(path, "weekly")
    if last and now - _parse(last["ts"]) < WEEKLY_MIN_GAP:
        return False
    text, health = weekly_summary(path, now)
    (send or _default_send)(text)
    store.record_scan(path, "weekly", "scheduled", health, f"weekly summary ({health})", {}, now=now)
    return True
