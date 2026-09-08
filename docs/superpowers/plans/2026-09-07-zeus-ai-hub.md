# Zeus AI Hub implementation plan

Approved scope: separate Hub credits; no changes to music, video, premium balances or production billing. Existing dashboard and website edit links remain available. No paid provider calls during implementation.

Architecture: isolated `backend/ai` package with configurable providers, routing, Council, pricing, SQLite reservations and an authenticated API. New React pages reuse existing auth, navigation and colours. Live mode requires explicit rates and allowances; default mode is disabled. Developer mode uses deterministic simulated providers and a separate test wallet.

- [x] Write and run failing backend tests for disabled defaults, routing, Council failure, ownership, credit reservation/refund, concurrency and idempotency.
- [x] Implement provider/configuration modules, then run provider and routing tests with HTTP mocks.
- [x] Implement additive Hub tables, atomic quotes/reservations/settlement, request progress, history and per-user persisted limits. No Stripe changes.
- [x] Add authenticated routes to the existing FastAPI app. Verify API behavior against temporary SQLite databases.
- [x] Add Hub missions and shared Ask Zeus/Council interface with server progress, New Chat, conversation history, credit quote and error recovery. Link existing builder/music.
- [x] Verify frontend production build, targeted lint, desktop/mobile browser interactions and existing backend regression tests.
- [x] Document configuration, credit grants, failure policy, restart recovery and rollout limitations. Review the final diff for secrets and unintended changes.

Billing design: reserve the total worst-case price (Council includes all members plus judge); successful output charges actual reported tokens up to the accepted quote. Failed overall requests refund all customer credits, while retaining incurred provider-cost records. Partial Council success charges successful work only. Requests interrupted by a process crash expire, refund and become terminal; never replay provider calls automatically.

Security: all data access is user-scoped; no uploads for this MVP; bounded input/output, fixed provider endpoints, timeout enforcement, no tools or autonomous actions, normal final text only. Model selection and pricing are server-owned. Development balances cannot spend live funds.

