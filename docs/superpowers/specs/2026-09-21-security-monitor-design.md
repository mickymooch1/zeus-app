# Security monitor — design (2026-09-21)

Approved by the owner in chat 2026-09-21 ("Approved as-is. All five defaults are fine — especially shadow mode first").

## Why
2026-09-21: a scanner-probe log line (`GET /.git/config 200`) led to finding a live path traversal in
`serve_spa` (fixed, 31b9e64). That fix closed the hole; this adds the visibility and noise-reduction
around it: detect scanners, block abusive IPs, scan for regressions, report to Porick.

## Facts that shape the design
1. Behind Railway `request.client.host` is a rotating `100.64.x.x` proxy. The real client IP is the
   `X-Real-IP` header (Railway docs). Blocking on `client.host` would block every visitor. See memory
   note `reference_railway_client_ip`.
2. Nothing persists request data and the app cannot read Railway logs, so the scan needs an events table
   fed by the middleware.
3. After the path fix the only HTML 404s are blocked paths; every other unknown path returns the SPA shell
   with 200. So "new probe paths" is inferred by association (paths requested by IPs already flagged),
   and the 404 rule must exclude `/files/*` and `/webhooks/*` (legit 404s / provider traffic).

## Components
| Unit | File | Purpose |
|---|---|---|
| Scanner path rules | `scanner_paths.py` | `is_scanner_path()` moved out of `main.py` so middleware can share it (main keeps a `_is_scanner_path` alias). |
| Guard core | `bot_guard.py` | client-IP extraction, never-block ranges + allowlist, bad-UA list, sliding-window `Detector`, in-memory `BlockCache`, alert budget, ASGI `BotGuardMiddleware`. **Fails open** on any internal error. |
| Store | `security_store.py` | SQL accessors for the three tables; DDL lives in `db.py`'s migration list. |
| Scan + weekly | `security_scan.py` | the 3-day scan, canary probes, weekly summary, `run_if_due`. |
| Porick | `telegram_admin.py` | exact-match `security status`, `blocked ips`, `unblock <ip>`, `security scan`. |
| Wiring | `scheduler.py`, `zeus_ops_agent.py`, `main.py` | flush job (30s), daily 09:30 scan-if-due, Monday weekly summary inside `daily_report()`, middleware + startup load. |

## Tables
- `blocked_ips(ip PK, reason, source auto|manual, blocked_at, expires_at NULL=permanent, unblocked_at, denied_requests)`
- `security_events(id, ts, ip, kind, path, status, ua)` — kinds: `blocked_path`, `blocked_path_200`, `notfound`,
  `auth_fail`, `bad_ua`, `assoc_path`. Pruned after 30 days. Per-IP write caps stop floods amplifying.
- `security_scans(id, ts, kind scan|weekly, trigger, status clean|review, summary, details JSON)`

## Detection (first match wins; all evaluated on the RESPONSE except bad UA)
- Bad scanner UA (sqlmap, nikto, masscan, nmap, zgrab, gobuster, dirbuster, wpscan, nuclei, acunetix,
  netsparker, feroxbuster, hydra…): block on first request. Generic clients (curl, python-requests…) are NOT listed.
- 5 scanner-path hits within 300s → block.
- 20 non-scanner 404s within 60s → block; exempt `/files/`, `/api/files/`, `/webhooks/` and requests bearing an
  `Authorization` header.
- A 200 on a scanner path = the fix regressed → immediate deduped alert + `blocked_path_200` event.
- 401 on `POST /auth/login` → `auth_fail` event (scan reports per-IP counts; nothing auto-blocks on it).

## Modes and safety
- **Shadow by default.** Decisions are stored and alerted ("🕵️ Would block: …") but no 403 is served until
  `SECURITY_ENFORCE=1`. Enforcement: 403 JSON on every http request and websocket handshake.
- Never block private / loopback / link-local / CGNAT (`100.64.0.0/10`) / reserved IPs; `SECURITY_IP_ALLOWLIST`
  (comma list of IPs/CIDRs) is also exempt.
- Client IP = `X-Real-IP` only when the direct peer is in `100.64.0.0/10`, else the peer; invalid → pass through.
- Auto-blocks expire after 7 days; manual blocks are permanent. `unblock` also clears the in-memory cache.
- Alerts: max 5 immediate per 10 min, overflow rolled into one "…and N more" line. Sent off the event loop.
- The scan's own canary requests carry an HMAC header (`X-Security-Canary`, keyed on `JWT_SECRET`, daily) so the
  app never strikes/blocks its own egress IP.

## Scan (daily 09:30 UTC job, runs only if ≥3 days since the last scheduled scan)
1. any `blocked_path_200` events in window; 2. live canary against `SECURITY_CANARY_HOSTS` (default both domains):
`/.git/config`, `/.env`, `/wp-admin` must not be 200 and a raw `/../app/requirements.txt` must not return the file;
3. scanner-hit volume vs trailing 7-day daily average (flag >5× and >100); 4. IPs with ≥20 failed logins;
5. generation volume: users with ≥30 songs/24h AND ≥5× their 14-day daily average, plus global 24h vs 14-day average
(>3× and ≥50); 6. new probe-path candidates (assoc paths not matching the blocklist, not seen in the previous scan).
Always reports; "✅ Security scan clean" when nothing found. Also prunes old events.

## Weekly (Mondays, from `daily_report()`, own try/except, idempotent via `security_scans`)
Blocked IPs this week (by reason), top probe paths, new threats, health ✅ clean / ⚠️ review needed
(review = canary failure, slipped 200, brute-force IP, generation anomaly, or unreviewed candidate paths).

## Out of scope (found, not touched)
`Limiter(key_func=get_remote_address)` and the two `X-Forwarded-For[0]` call sites in `main.py` (spoofable /
proxy-keyed). Left for a separate decision.

## Rollout
Merge → deploy in shadow mode → watch `security status` / `blocked ips` for a few days (also confirms `X-Real-IP` is
the true client IP and whether a CDN sits in front) → set `SECURITY_ENFORCE=1`.
