# Zeus AI Hub MVP

Routes: `/hub`, `/hub/ask`, `/hub/council`; API: `/api/hub`.
Existing `/dashboard`, its website-edit query parameters, `/websites`, `/songs`,
Zeus Beats frontend and Stripe billing remain intact. Login without a requested
destination now opens `/hub`.

## Modes and rollout

`ZEUS_HUB_MODE` defaults to `disabled`. Missing/invalid live configuration fails
closed. Provider credentials alone never enable Hub calls.

`development` uses three deterministic simulated models. It cannot instantiate
an HTTP provider client, reserves test credits to exercise safeguards, charges
zero, and labels every result as a simulation. Each user gets a one-time 100-credit
test allowance. Development and live wallets/history are separate namespaces.

`live` requires `ZEUS_HUB_CONFIG`, a JSON object following
`hub-config.example.json`. Replace every null rate with a verified positive USD
price per million tokens, select provider model IDs, explicitly set the USD value
of one Hub credit and allowances, then validate locally. The example is deliberately
invalid for live usage. Set credentials only in the existing backend secret store:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`,
`OPENROUTER_API_KEY`. No frontend secret configuration is needed.

Enabling live mode, assigning production allowances/rates, changing Stripe or
deploying this implementation were not performed. They require the operator's
separate rollout decision. Models must support the text chat API used by their
adapter. Provider compatibility is verified with mocked HTTP responses; live
provider/account availability must be checked before rollout.

## Credit semantics

`hub_balances` is explicitly a **Zeus Hub credits** balance, keyed by user and mode.
`hub_ledger` records every grant, reservation and released credit with idempotent
references. There is no read, migration, conversion, or deduction of any legacy
music, video, premium or payment ledger. This isolated ledger can later feed an
explicit universal-wallet adapter.

The configured `initial_allowance` is a **one-time** grant per user in live mode,
not a recurring entitlement. Changing the configuration does not refill existing
accounts. Zero is allowed. No checkout or automatic paid top-up has been added.
For a future approved grant integration use `Store.grant(user_id, 'live', amount,
unique_reference)`; it is idempotent and rejects reuse with a different amount.
Keep that operation behind trusted administration. There is intentionally no public
credit-grant endpoint.

The quote uses a conservative UTF-8 input bound, output caps, model prices and the
Council multiplier. Council reserves **all members plus the synthesis call** before
starting any member. Quotes above `max_request_usd` are refused. The submitted
`max_credits` must cover the current server quote; clients cannot select models,
set rates or grant credits.

Successful requests settle from reported successful-call tokens, rounded up once
at request level and capped at the accepted reservation. Failed calls and calls
with unknown token usage are not charged to customers. A partial Council verdict
charges only successful measured work. If fewer than two members respond, the judge
fails, or the whole request times out, the **entire customer reservation is refunded**.
The platform absorbs costs already incurred. Refunded provider usage remains in
`hub_usage` for reconciliation.

Every attempted provider call gets a usage row before outbound work. Known token
counts and calculated provider cost are retained even for an empty final answer.
When an outage/timeout prevents retrieving usage, token counts are null and cost
remains the conservative pre-call estimate; status distinguishes these estimates
from successful measured usage. These amounts are estimates, not provider invoices.
Development usage records explicitly identify the simulated provider and zero cost.

## Safety and recovery

- Existing JWT authentication plus verified-email checks and user-scoped history.
- SQLite `BEGIN IMMEDIATE` protects reservations, grants, rate limits and settlement.
- User-scoped UUID request IDs detect duplicate submissions; payload changes under
  an existing ID produce 409. One running turn per conversation.
- Persisted per-minute and daily limits apply to free, paid and admin users. Failed
  attempts count toward limits. Free/paid limits are configurable separately.
- 12,000-byte prompt maximum, 24,000-byte context maximum, capped output and at most
  three Council members. Recent complete turns are included within context limits.
  Start a new conversation after 100 requests; the newest 100 conversations are listed.
- No automatic provider retry/failover, no tools, browsing, uploads or arbitrary
  provider endpoints. Model Markdown images are disabled to prevent automatic
  external requests. Normal clickable links are still allowed.
- Each provider has a timeout; the whole request has a bounded deadline. Background
  tasks run inside the existing server process. A durable queue is outside this MVP.
- Reservations expire after five minutes. The next authenticated Hub access lazily
  marks abandoned work failed and refunds it atomically. It never restarts paid work.
  Usage left running is marked unknown. Server timeouts are shorter than this lease.
- Browser recovery retains the original request ID in per-user session storage.
  It checks accepted work before retrying, restores the conversation and unlocks
  a definitively rejected request. New requests remain disabled during uncertain work.
- Logs contain request IDs and provider/model usage, not prompt bodies or keys.

## Verification

Run from `backend`: `python -m pytest tests/test_ai_hub.py --rootdir . --confcutdir .`.
Tests use temporary databases, simulated models and HTTP mocks, including explicit
live-mode settlement tests with a fake provider. They do not consume provider credit.
Run `npm run build` from `web`, then targeted ESLint on the added/changed JSX/JS.

The browser verification harness used the real FastAPI app, local seeded test user,
isolated database and production frontend build with `ZEUS_HUB_MODE=development`.
Application startup jobs were disabled for that local harness. No production database,
deployment settings or secrets were changed.

Provider API references consulted:
- https://developers.openai.com/api/reference/resources/chat
- https://platform.claude.com/docs/en/api/http/messages/create
- https://ai.google.dev/gemini-api/docs/openai
- https://docs.x.ai/developers/rest-api-reference/inference
- https://openrouter.ai/docs/api_reference/overview
