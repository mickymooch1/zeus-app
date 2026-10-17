# Release runbook: Google Ads sign-up conversion + cookie consent

Branch `feature/google-ads-consent`. Frontend (web-beats) + a CI workflow only:
no backend, database, registration, credits, payments, subscriptions or song
generation changes.

- Google Ads tag `AW-18517714190`, Sign-up conversion label `o7SdCLShsZ8dEI7K9_1E`
  (confirmed against the owner's screenshots of the original snippet, 2026-10-17).

## How the tracking works

- The cookie banner offers **Reject** and **Accept** (same style). The choice is
  stored in localStorage and a first-party `zeus_ads_consent` cookie; "denied"
  in either wins; nothing is tracked if it can't be read.
- **Google's tag never runs on the app's pages.** Measured against the real
  gtag.js: on a page it sends page_view pings on every page/navigation whenever
  it is configured (`send_page_view: false` doesn't stop it), watches every form
  submission there ("form-data" pings — this account has automatic enhanced
  conversions), and can't be switched off once loaded.
- Instead, after a successful registration by a visitor who accepted, the app
  adds a hidden frame `/ads-frame.html` (+ `/ads-frame.js`). Only that frame loads
  gtag.js — Consent Mode v2 default all-denied, then `ad_storage` +
  `ad_user_data` granted (`ad_personalization`, `analytics_storage` stay
  denied), no `config` — sends the one conversion (transaction_id = user id) and
  is removed. It can't see the app's pages, forms or navigation.
- The ad click (gclid / gbraid / wbraid) from the landing URL is passed in the
  frame's URL, where the tag reads it; with consent it is remembered in
  `zeus_ads_click` for 90 days so a sign-up on a later visit is still credited.
- Delivery: "handed off" = the tag's event_callback fired in the frame (the
  browser can't see Google's response). Otherwise the sign-up stays pending and
  is retried on later visits — max 5 attempts within 30 days, same
  transaction_id, so Google drops duplicates.
- Withdrawal: stops a send in progress (removes the frame), cancels pending
  sign-ups, deletes `zeus_ads_click`, `_gcl_*` cookies and `_gcl*` storage.
- The service worker never caches the frame (iframe navigations are skipped),
  so it can't replace the offline app shell.
- Nothing is sent inside the iOS app wrapper.

## Infrastructure facts (checked 2026-10-17, read-only)

- **zeusbeats.com is served by Railway project `steadfast-healing`**
  (`66477050-f3af-4ca4-93fe-030e80e59b8a`), service `zeus-app`
  (`548a3c4e-ae4b-49fd-8072-126cbea1d02b`), environment `production`
  (`33e84406-19f9-47f9-97f2-96c8de2da464`): custom domains zeusbeats.com and
  zeusaidesign.com; DNS `zeusbeats.com CNAME 0m9gg5gh.up.railway.app`; the live
  page serves bundle `index-t-EXL-Gc.js` = deployment
  `6b811676-9b00-4590-9ee2-9d4d29e4619d` (commit `45ca91c`), status SUCCESS.
  Deploys automatically on every push to `master`. Volume `/data` (50 GB).
  "Wait for CI" (`checkSuites`) is **off**: Railway does not wait for GitHub
  checks.
- **`gracious-exploration`** (`378a5815-2cea-46da-867c-0d98a8f52f28`) is an older
  duplicate (created 4 Apr 2026, about 80 minutes before `steadfast-healing`): one
  service `zeus-app` on the same repo/branch, no domains, no volume, one
  variable (`ANTHROPIC_API_KEY`). Every deploy fails its health check because
  `APIFRAME_API_KEY` isn't set (`KeyError` at start-up) — all 40 most recent
  deployments (back to 27 Sept) FAILED. It serves nothing and is the source of
  the red GitHub commit status. Not needed for production; left untouched.

## CI

`.github/workflows/ci.yml` runs on every push and every PR to master:

| Job | What |
|---|---|
| web-beats | Node 20: `npm ci`, `npm test`, `npm run build`, checks the static `index.html` has no Google tag and `ads-frame.*` are built |
| web | Node 20: `npm ci`, `npm run build` (zeusaidesign.com, also in the Docker image) |
| backend | Python 3.12: `pip install -r requirements.txt`, `python -m pytest tests -q` with dummy keys |

Node 20 / Python 3.12 match the Dockerfile. Because Railway's "Wait for CI" is
off, a red run does **not** block a deploy — check the run is green before
merging (or turn "Wait for CI" on in Railway once CI has proved stable).

## Before merging

1. CI green on the branch (GitHub → Actions), or run the same commands locally.
2. Optional: the headless-Chrome end-to-end harness (intercepts every Google
   hit, fakes `/auth/register`) — 62 checks.

## Deploying (needs the owner's approval)

1. `git checkout master && git pull`
2. `git merge --no-ff feature/google-ads-consent`
3. Run the tests on the merged tree (or push to a branch and let CI run).
4. `git push origin master` — starts the production deploy on `steadfast-healing`.
   (`gracious-exploration` will also try and fail, as it does on every push.)
5. Watch Railway until the new deployment is SUCCESS (about 1–2 minutes).
   Record its id: `__________`.

## Verifying in production (about 15 minutes)

Desktop Chrome **incognito**, DevTools → Network, filter `google`.

1. https://zeusbeats.com — banner shows **Reject** and **Accept**. No requests to
   any Google ads domain (Google Fonts only).
2. **Reject** → still none; reload → no banner.
3. New incognito window → `https://zeusbeats.com/?gclid=TEST_GCLID` → **Accept**
   → still no Google requests (nothing loads until a sign-up).
4. Register a test account (plus-address email). Network shows `/ads-frame.html?gclid=TEST_GCLID`,
   then `gtag/js?id=AW-18517714190`, then the conversion
   (`…/conversion/18517714190/?…label=o7SdCLShsZ8dEI7K9_1E…oid=<user id>…gclaw=TEST_GCLID`,
   plus its companion requests with the same `random`). No `form-data` requests.
   Elements: no `iframe[src^="/ads-frame.html"]` left afterwards.
5. Reload / go back / submit another form → nothing more to Google.
6. Footer → **Cookie settings** → **Reject** → Application tab: no `_gcl_*`
   cookies, no `_gcl_ls`, no `zeus_ads_click`.
7. Delete the test account in the admin panel.

Google Ads usually shows the Sign-up action as "Recording conversions" within
about 24 hours of the first real conversion. Tag Assistant may not detect the
tag on the page — expected: the tag only exists briefly inside the hidden frame
after a sign-up.

## Rollback

Roll back if registration errors rise, the banner breaks a page, or any Google
request appears before a sign-up.

**Fast (about 2 minutes):** Railway → `steadfast-healing` → zeus-app → production
→ Deployments → `6b811676…` (commit `45ca91c`) → Rollback. Railway reports this
deployment `canRollback: true` (checked 2026-10-17; it's the current live
deployment, so it becomes the rollback target as soon as the new one is live).
Older deployments back to `a714f518…` (`e0aaf5c`) and `94bf0ddd…` (`7266189`) are
also rollback-able.

**Then make it permanent:** `git revert -m 1 <merge commit>` on master, run the
tests, push (redeploys the same code as the rollback).

What a rollback leaves behind (harmless): browsers keep `zeus_cookie_consent`,
`zeus_ads_consent`, `zeus_ads_*` keys (the old code ignores them; the old
banner shows again); `_gcl_au` set for people who signed up with consent stays
until it expires (≤90 days); conversions already sent stay in Google Ads; the
old privacy policy (no advertising cookies) is accurate again once the code is gone.

## Known limitations (accepted)

- Sign-ups by people who don't click Accept are not counted (strict opt-in).
- The browser can't confirm Google received a conversion ("handed off" = the tag
  processed it). Retries reuse the transaction id.
- School sign-ups and email verifications are not tracked.
- The Google Ads account has **automatic enhanced conversions** on (`ec_mode=a`).
  The frame contains no user data, so there's nothing for it to collect (tests
  show `em=tv.1~ec.e3`, no hash). Recommended: switch it off in Google Ads, since
  the privacy policy says no email is sent.
