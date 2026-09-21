# Security Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) or superpowers:subagent-driven-development. Steps use checkbox syntax. Every task is TDD: failing test → run (red) → minimal code → run (green) → commit.

**Goal:** Detect and (after a shadow period) block scanner IPs, scan for security regressions every 3 days, and report to Porick.

**Architecture:** A fail-open pure-ASGI middleware feeds an in-memory detector and a batched events table; a scheduler job flushes it; a daily-gated job runs the scan; Porick gets four exact-match commands.

**Tech Stack:** FastAPI/Starlette ASGI, APScheduler (`scheduler.py`), SQLite (`db.py`), Telegram via `alerts.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-21-security-monitor-design.md`

## Global Constraints
- Shadow mode by default; 403s only when env `SECURITY_ENFORCE` ∈ {1,true,yes}.
- Never block private/loopback/link-local/CGNAT(`100.64.0.0/10`)/reserved IPs or `SECURITY_IP_ALLOWLIST` entries.
- Client IP = `X-Real-IP` only if the direct peer is in `100.64.0.0/10`, else the peer; unparseable → pass through.
- Thresholds: 5 scanner hits/300s; 20 non-scanner 404s/60s (exempt `/files/`, `/api/files/`, `/webhooks/`, requests with `Authorization`); bad UA = first request.
- Auto-block TTL 7 days; manual permanent. Alert budget 5 per 600s, overflow summarised.
- Middleware must never raise into the request path (fail open). Existing tests (TestClient peer `testclient`) must be unaffected.
- Run pytest from `backend/` with the 6 env vars (see memory `reference_zeus_backend_test_baseline`); use `py`, not `python`.

## File Structure
- Create `backend/scanner_paths.py`, `backend/bot_guard.py`, `backend/security_store.py`, `backend/security_scan.py`
- Modify `backend/db.py` (DDL), `backend/main.py` (import alias, middleware, spa flag, lifespan), `backend/scheduler.py`, `backend/zeus_ops_agent.py`, `backend/telegram_admin.py`
- Tests: `backend/tests/test_bot_guard.py`, `test_security_store.py`, `test_bot_guard_middleware.py`, `test_security_scan.py`, `test_security_commands.py`

### Task 1: Extract scanner path rules
**Files:** create `scanner_paths.py`; modify `main.py` (replace the `_SCANNER_SEGMENTS/_SCANNER_SUFFIXES/_is_scanner_path` block with `from scanner_paths import is_scanner_path as _is_scanner_path`).
**Produces:** `SCANNER_SEGMENTS: frozenset[str]`, `SCANNER_SUFFIXES: tuple[str, ...]`, `is_scanner_path(path: str) -> bool` (identical behaviour).
- [ ] Existing `tests/test_serve_spa_hardening.py` is the regression net — run green before and after.
- [ ] Commit.

### Task 2: Guard core (pure logic, no I/O)
**Files:** create `bot_guard.py` (first half); test `tests/test_bot_guard.py`.
**Produces:**
- `client_ip(scope: dict) -> str | None`
- `is_protected_ip(ip: str) -> bool`
- `is_bad_user_agent(ua: str) -> str | None` (matched tool name)
- `enforce_enabled() -> bool`
- `canary_token(now: datetime | None = None) -> str`, `is_canary_request(headers: list[tuple[bytes, bytes]]) -> bool`
- `Decision(ip: str, kind: str, reason: str)`; `Detector(clock=time.monotonic, ...)` with `record_scanner_hit(ip) -> Decision | None`, `record_notfound(ip) -> Decision | None`, `has_strikes(ip) -> bool`
- `BlockCache(clock=time.time)`: `load(rows)`, `add(ip, expires_at)`, `remove(ip) -> bool`, `is_blocked(ip) -> bool`, `snapshot() -> dict[str, float | None]`
- `AlertBudget(limit=5, window=600, clock=time.monotonic)`: `allow() -> bool`, `take_overflow() -> int`
**Tests:** X-Real-IP honoured only from a `100.64.x.x` peer (spoofed header from a public peer ignored); protected ranges + allowlist; bad-UA hits sqlmap/nikto, misses curl/python-requests; scanner window (4 hits ok, 5th decides; old hits age out); 404 window; expiry in BlockCache; budget overflow; canary token stable per day and verified.
- [ ] Red → green → commit.

### Task 3: Storage
**Files:** modify `db.py` (append 3 `CREATE TABLE IF NOT EXISTS` + indexes to the migration list, per the `abuse_blocklist` pattern); create `security_store.py`; test `tests/test_security_store.py` (temp SQLite via `db.init_user_tables`).
**Produces** (all take `db_path` first; `now: datetime | None = None` where time matters; timestamps stored `YYYY-MM-DD HH:MM:SS` UTC):
- `add_blocked_ip(db_path, ip, reason, source="auto", ttl_days: int | None = 7, now=None)` (upsert; re-arms an unblocked/expired row)
- `unblock_ip(db_path, ip) -> bool`; `active_blocked(db_path, now=None) -> list[dict]`
- `add_denied(db_path, counts: dict[str, int])`
- `insert_events(db_path, rows: list[tuple[str, str, str, str | None, int | None, str | None]])` (ts, ip, kind, path, status, ua); `prune_events(db_path, days=30, now=None) -> int`
- Aggregates: `count_events(db_path, kind, since, until=None) -> int`, `events_since(db_path, kinds, since) -> list[dict]`, `top_paths(db_path, kinds, since, limit=10) -> list[tuple[str, int]]`, `ip_counts(db_path, kind, since, min_count) -> list[tuple[str, int]]`
- Scan log: `record_scan(db_path, kind, trigger, status, summary, details: dict, now=None)`, `last_scan(db_path, kind, trigger=None) -> dict | None`
- [ ] Red → green → commit.

### Task 4: Middleware + runtime + wiring
**Files:** extend `bot_guard.py` (runtime singletons, `BotGuardMiddleware`, `init(db_path)`, `flush()`, `block_ip(...)`); modify `main.py` (`app.add_middleware(BotGuardMiddleware)` LAST so it is outermost; `request.state.spa_fallback = True` where `serve_spa` returns the shell; `bot_guard.init(...)` in lifespan); test `tests/test_bot_guard_middleware.py` (drive the ASGI app directly with crafted scopes).
**Behaviour to pin:** peer `testclient`/unparseable → passthrough; blocked IP + enforce → 403 JSON (http) / close (websocket) and `denied_requests` counted; blocked IP + shadow → request served; scanner-path hits accumulate → block recorded (DB + cache) and alert queued; 200 on scanner path → `blocked_path_200` event + alert; canary header → no strikes; protected IP never blocked; exception inside the guard → request still served; `assoc_path` events emitted for an IP once it has strikes.
- [ ] Red → green → commit.

### Task 5: Scan + weekly summary
**Files:** create `security_scan.py`; test `tests/test_security_scan.py`.
**Produces:** `Finding(level, text)`, `ScanReport(findings, stats, candidates)` with `.status` (`"clean"|"review"`); `canary_probe(hosts, timeout=6) -> list[Finding]`; `run_scan(db_path=None, trigger="scheduled", now=None, canary=None) -> ScanReport` (persists a `security_scans` row); `format_scan(report) -> str`; `run_if_due(now=None) -> ScanReport | None` (≥3 days since last *scheduled* scan; also prunes events); `weekly_summary(db_path=None, now=None) -> str`; `send_weekly_if_due(now=None) -> bool`.
**Tests:** clean DB → "✅ Security scan clean"; slipped-200 → critical; failed-login IP over threshold; generation anomaly per user + global; volume spike; new candidate paths exclude already-blocked patterns and previously reported ones; canary failure surfaced (injected `canary` callable); `run_if_due` gating; weekly idempotent (no second send within 6 days) and health ✅/⚠️.
- [ ] Red → green → commit.

### Task 6: Porick commands, scheduler, daily-report hook
**Files:** modify `telegram_admin.py` (4 exact-match commands before the AI fallback + `HELP_TEXT`), `scheduler.py` (`__security_flush__` every 30s; `__security_scan__` daily 09:30 UTC calling `run_if_due` with misfire grace), `zeus_ops_agent.py` (call `security_scan.send_weekly_if_due()` in its own try/except at the end of `daily_report()` on Mondays); test `tests/test_security_commands.py` (+ extend `tests/test_stuck_song_sweep.py`-style source assertion for the new scheduler jobs).
**Commands:** `security status`, `blocked ips`, `unblock <ip>` (validates IP; clears cache + DB; audit via `_db_log_action`), `security scan` (runs `run_scan(trigger="manual")`, replies with `format_scan`). All accept an optional leading `porick `.
- [ ] Red → green → commit.

### Task 7: Verification
- [ ] Run the new test files, `test_serve_spa_hardening.py`, and the four related files from the earlier hardening work; run the wider suite twice per the baseline note and compare against master.
- [ ] Syntax check all touched files; confirm no test imports broke.
- [ ] Final commit; hold the push for owner confirmation (production deploy, new middleware).
