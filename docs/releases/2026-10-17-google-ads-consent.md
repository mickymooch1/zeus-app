# Release runbook: Google Ads sign-up conversion + cookie consent

Branch `feature/google-ads-consent` (web-beats frontend only; no backend, database,
registration, credits, payments, subscriptions or song-generation changes).

- Google Ads tag: `AW-18517714190`
- Sign-up conversion label: `o7SdCLShsZ8dEI7K9_1E`
- Production before this release: Railway deployment `6b811676-9b00-4590-9ee2-9d4d29e4619d`
  (commit `45ca91c`), project `66477050-f3af-4ca4-93fe-030e80e59b8a`,
  service `548a3c4e-ae4b-49fd-8072-126cbea1d02b`, environment `production`
  (`33e84406-19f9-47f9-97f2-96c8de2da464`).

## What CI does (and doesn't)

There is no CI test pipeline: the GitHub repo has no Actions workflows, and the
Railway Docker build only runs `npm ci` + `vite build` for each frontend — it
does not run any tests. The only automated gate is "the build compiles". Every
test below must be run by hand before merging.

GitHub's combined commit status on `master` shows **failure** because a second
Railway project, `gracious-exploration - zeus-app`, is also connected to the repo
and its deploys fail ("Deployment failed"). Production (`steadfast-healing`)
reports success. That red status is unrelated to this change; check whether
`gracious-exploration` is still needed.

## Before merging

1. Compare the IDs above with the event snippet in Google Ads
   (Goals → Conversions → Sign-up → Tag setup → "Install the tag yourself"):
   `send_to: 'AW-18517714190/o7SdCLShsZ8dEI7K9_1E'`.
2. From `web-beats/`: `npm ci && npm test` — expect 0 failures.
3. `npm run build` — expect success; `grep -c googletagmanager ../web-beats-dist/index.html`
   must print `0` (the tag is never in the static HTML).
4. From `backend/` (backend tests also scan web-beats files):
   `ANTHROPIC_API_KEY=x APIFRAME_API_KEY=x SONG_STORAGE_PATH=<tmp> JWT_SECRET=x ZEUS_DATA_DIR=<tmp> py -m pytest tests -q`
   — expect 0 failures. Don't set `SONG_PUBLIC_BASE_URL` / `SONG_WEBHOOK_URL`.
5. Optional: the headless-Chrome end-to-end harness (intercepts every Google hit,
   fakes `/auth/register`) — 54 checks covering accept/reject/withdrawal/retry/
   storage failure.

## Deploying

Railway deploys production automatically on every push to `master`.

1. `git checkout master && git pull`
2. `git merge --no-ff feature/google-ads-consent`
3. Re-run step 2–4 above on the merged tree.
4. `git push origin master` — this starts the production deploy.
5. Watch the deployment in Railway until it is `SUCCESS` (about 1–2 minutes;
   health check `/health`). Note the new deployment id here: `__________`.

Existing visitors get the new bundle through the service worker's update toast
on their next visit; nobody needs to clear caches.

## Verifying in production (about 15 minutes)

Use a desktop Chrome **incognito** window, DevTools → Network, filter `google`.

1. Open https://zeusbeats.com — the new banner shows **Reject** and **Accept**,
   same size and style. Network: no requests to googletagmanager.com,
   googleadservices.com, google.com/pagead or doubleclick.net (Google Fonts only).
2. Click **Reject** → still no Google requests; reload → no banner, no requests.
3. New incognito window → `https://zeusbeats.com/?gclid=TEST_GCLID` → **Accept**
   → `gtag/js?id=AW-18517714190` loads.
4. Register a test account (plus-address email, e.g. `you+adstest1@…`). Network
   shows one conversion: `googleadservices.com/pagead/conversion/18517714190/…label=o7SdCLShsZ8dEI7K9_1E…oid=<user id>`
   (plus its `google.com/pagead/1p-conversion/…` companion — same `random`, one conversion).
5. Reload / go back → no second conversion.
6. Footer → **Cookie settings** → **Reject** → the page reloads; Application tab:
   no `_gcl_*` cookies, no `_gcl_ls` in Local Storage; no further Google requests.
7. Delete the test account in the admin panel.
8. Optional: Google Tag Assistant (desktop Chrome) on zeusbeats.com after Accept.

Google Ads usually moves the Sign-up action from "Unverified" to "Recording
conversions" within about 24 hours of the first real conversion. Test
conversions without a real ad click don't appear in campaign columns.

Also check registration still works normally: Railway logs for `/auth/register`
errors, and the usual sign-up count over the next day.

## Rollback

Roll back if registration errors rise, the banner breaks a page, or any Google
request is seen before Accept.

**Fast (about 2 minutes, no git needed):** Railway → zeus-app → production →
Deployments → `6b811676…` (commit `45ca91c`) → **Rollback** / Redeploy.
(Railway MCP: `redeploy` / rollback on that deployment id.) Railway marks it
`canRollback: true`.

**Then make it permanent** so the next push doesn't re-ship it:
`git revert -m 1 <merge commit>` on master, run the tests, push. That push
redeploys — the same code as the rollback, so no visible change.

What a rollback leaves behind (all harmless):
- Browsers keep `zeus_cookie_consent`, the `zeus_ads_consent` cookie and any
  `zeus_ads_*` keys — the old code ignores them, and the old "Accept" banner
  shows again.
- `_gcl_au` / `_gcl_aw` / `_gcl_ls` already set for people who accepted stay until
  they expire (up to 90 days); after a rollback no code deletes them, but no tag
  reads them either.
- Conversions already sent to Google stay in Google Ads.
- The privacy policy goes back to saying no advertising cookies are used, which
  is again true once the tag is gone.

## Known limitations (accepted)

- Sign-ups by people who don't click Accept are not counted (strict opt-in).
- The browser can't confirm Google received a conversion: "handed off" means
  gtag.js loaded and processed the event. Retries use the same transaction id,
  so Google drops duplicates.
- School sign-ups and email verifications are not tracked.
