# Release runbook: Google Ads sign-up conversion + cookie consent

Branch `feature/google-ads-consent`. Frontend (web-beats) + a CI workflow only:
no backend, database, registration, credits, payments, subscriptions or song
generation changes.

- Google Ads tag `AW-18517714190`, Sign-up conversion label `o7SdCLShsZ8dEI7K9_1E`
  (confirmed against the owner's screenshots of the original snippet, 2026-10-17).
- Design chosen by the owner (2026-10-17): **Option A — Google's standard
  sitewide tagging with basic Consent Mode.** (An earlier hidden-iframe design
  was dropped: Google's "Troubleshoot your sitewide tagging" help page says not
  to fire conversion tags inside iframes.)

## How the tracking works

- The cookie banner offers **Reject** and **Accept** (identical buttons) and
  says the tag runs on our pages to measure visits and sign-ups from our adverts.
  The choice is stored in localStorage and a first-party `zeus_ads_consent`
  cookie; "denied" in either wins; nothing is tracked if it can't be read. The
  old implied-consent flag (`zeus_cookie_accepted`) is ignored, so every visitor
  is asked once.
- **Before consent:** only the all-denied Consent Mode v2 default is pushed;
  gtag.js is not requested at all (Google's documented "basic" implementation —
  no data reaches Google).
- **After Accept:** the standard Google tag (`gtag.js?id=AW-18517714190`, one
  `config`) runs on every page: page views and the conversion linker (reads the
  ad click from the landing URL into `_gcl_aw`). Consent: `ad_storage` +
  `ad_user_data` granted; `ad_personalization` (remarketing) and
  `analytics_storage` stay denied.
- **The only conversion** is "Sign-up", fired from RegisterPage after the
  backend has created the account. `transaction_id` = a random UUID made once
  per sign-up in the browser — never the user id (Google: transaction IDs must
  not identify customers) — and reused for every retry, so Google drops
  duplicates. The user id stays in the browser only, for local de-duplication.
- **Retries:** the sign-up stays pending (localStorage) until gtag.js has loaded
  and its event_callback fires ("handed off" — the browser can't see Google's
  response). If the tag can't load, it is retried on later visits: max 5
  attempts within 30 days, same random id.
- **Reject / withdrawal (Cookie settings):** pushes all-denied, cancels pending
  sign-ups, deletes `_gcl_*` cookies and `_gcl*` local/session storage, and —
  if the tag was running on that page — reloads it (a loaded gtag.js can't be
  switched off any other way; measured). No reload if the withdrawal couldn't be
  saved (it would bring the old Accept back); it holds in memory instead.
- Nothing is sent inside the iOS app wrapper; the banner isn't shown there.

## Google Ads account settings (owner)

Before launch, in Google Ads: **enhanced conversions off** and, in the Google
tag settings, **"Allow user-provided data capabilities" off**. A browser-harness
run on 2026-10-17 (Option A build) already showed 0 `form-data` requests and no
`ec_mode` parameter — earlier runs the same day showed `ec_mode=a` and several
`form-data` pings — which is consistent with the settings being off; confirm in
the account before launch. The raw email never appeared in any request.

## Infrastructure facts (checked 2026-10-17, read-only)

- **zeusbeats.com is served by Railway project `steadfast-healing`**
  (`66477050-f3af-4ca4-93fe-030e80e59b8a`), service `zeus-app`
  (`548a3c4e-ae4b-49fd-8072-126cbea1d02b`), environment `production`
  (`33e84406-19f9-47f9-97f2-96c8de2da464`); DNS `zeusbeats.com CNAME
  0m9gg5gh.up.railway.app`. Live deployment `6b811676-9b00-4590-9ee2-9d4d29e4619d`
  (commit `45ca91c`), SUCCESS. Deploys automatically on every push to `master`
  only. "Wait for CI" is **off**: Railway does not wait for GitHub checks.
- **`gracious-exploration`** (`378a5815-2cea-46da-867c-0d98a8f52f28`): an older
  duplicate on the same repo/branch with no domain, no volume, only
  `ANTHROPIC_API_KEY`; every deploy fails (missing `APIFRAME_API_KEY`). Serves
  nothing; source of the red GitHub commit status. Left untouched.
- Pushing `feature/google-ads-consent` deploys nothing (both services build
  `master` only; no PR environments).

## CI

`.github/workflows/ci.yml` runs on every push and every PR to master:

| Job | What |
|---|---|
| web-beats | Node 20: `npm ci`, `npm test`, `npm run build`, and fails if the static `index.html` contains Google's tag |
| web | Node 20: `npm ci`, `npm run build` (zeusaidesign.com, also in the Docker image) |
| backend | Python 3.12: `pip install -r requirements.txt`, writable `/data`, `python -m pytest tests -q`; on failure the output tail is posted as an annotation |

Known: 2 backend tests (`test_library_batch::test_library_endpoint_is_registered_and_not_shadowed`,
`test_scanner_paths::test_no_registered_backend_route_is_a_scanner_path`) fail
with FastAPI 0.143.x (route introspection; `requirements.txt` isn't pinned).
They fail identically on `master` and are unrelated to this branch.

## Before merging

1. CI: web-beats and web green; backend green apart from the 2 known failures above.
2. Google Ads settings above confirmed off.
3. Optional: the headless-Chrome end-to-end harness (real gtag.js, every Google
   hit intercepted, `/auth/register` faked) — 51 checks.

## Deploying (needs the owner's approval)

1. `git checkout master && git pull`
2. `git merge --no-ff feature/google-ads-consent`
3. Re-run the tests on the merged tree (or let CI run on the merge commit).
4. `git push origin master` — starts the production deploy on `steadfast-healing`.
5. Watch Railway until the new deployment is SUCCESS (about 1–2 minutes).
   Record its id: `__________`.

## Verifying in production (about 15 minutes)

Desktop Chrome **incognito**, DevTools → Network, filter `google`.

1. https://zeusbeats.com — banner shows **Reject** and **Accept**. No request to
   googletagmanager.com / googleadservices.com / google.com/pagead /
   doubleclick.net (Google Fonts only).
2. **Reject** → still none; reload and browse → none.
3. New incognito window → `https://zeusbeats.com/?gclid=TEST_GCLID` → **Accept**
   → `gtag/js?id=AW-18517714190` loads; page-view requests appear; Application →
   Cookies shows `_gcl_aw`.
4. Register a test account (plus-address email). One conversion:
   `…/conversion/18517714190/?…label=o7SdCLShsZ8dEI7K9_1E…oid=<random UUID>…gclaw=TEST_GCLID`
   (plus companion requests with the same `random`). The `oid` is a UUID, not
   the account number. No `form-data` requests.
5. Reload / go back → no second conversion.
6. Footer → **Cookie settings** → **Reject** → page reloads; no `_gcl_*` cookies,
   no `_gcl_ls`; browsing sends nothing more to Google.
7. Delete the test account in the admin panel.
8. Google Tag Assistant (desktop Chrome) should now find the tag after Accept.

Google Ads usually shows the Sign-up action as "Recording conversions" within
about 24 hours of the first real conversion.

## Rollback

Roll back if registration errors rise, the banner breaks a page, or any Google
request appears before consent.

**Fast (about 2 minutes, no git):** Railway → `steadfast-healing` → zeus-app →
production → Deployments → `6b811676…` (commit `45ca91c`) → **Rollback**.
Railway reports it `canRollback: true` (re-checked 2026-10-17); it is the live
deployment today, so it becomes the rollback target as soon as the new one is
live. Older deployments `a714f518…` (`e0aaf5c`) and `94bf0ddd…` (`7266189`) are
also rollback-able. No database changes are involved.

**Then make it permanent:** `git revert -m 1 <merge commit>` on master, run the
tests, push (redeploys the same code as the rollback).

What a rollback leaves behind (harmless): browsers keep `zeus_cookie_consent`,
`zeus_ads_consent` and `zeus_ads_*` keys (the old code ignores them; the old
banner shows again); `_gcl_*` cookies set for people who accepted stay until
they expire (≤90 days) but nothing reads them; conversions and page views
already sent stay in Google Ads; the old privacy policy (no advertising
cookies) is accurate again once the code is gone.

## Known limitations (accepted)

- Sign-ups by people who don't click Accept are not counted (strict opt-in).
- If a visitor accepts only after navigating away from the ad's landing URL,
  the click can't be linked (the tag loads after the click id has left the URL).
- The browser can't confirm Google received a conversion ("handed off" = the tag
  processed it). Retries reuse the random id.
- School sign-ups and email verifications are not tracked.
