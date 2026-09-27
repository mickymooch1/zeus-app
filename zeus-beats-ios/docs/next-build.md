# Changes waiting for the next iOS build

Live build at time of writing: **ZeusBeats/17**. Everything below is merged to
`master` but only reaches users once a new EAS build is submitted and approved.

## 2026-09-27 — Create screen error handling

- **Readable errors instead of "[object Object]".** `src/utils/apiErrorMessage.ts`
  turns the backend's `detail` (string, `{message}` object, or 422 list) into
  text. Used by the Create screen and login.
- **"Resend verification email" button** on the Create screen when generation is
  blocked by the email-verification gate (403 `email_unverified`). Calls
  `POST /api/auth/resend-verification` with `{app: 'beats'}` (the default `ai`
  would send a Zeus AI-branded email). Handles sent / already verified /
  bounced / rate-limited (3 per minute) / error — see `src/utils/verification.ts`.

### Check on a device before submitting

Not visually verified yet (the app can't render in a desktop browser).

1. Sign up with a fresh, unverified address and tap Create. Expect the verify
   message plus a purple **Resend verification email** button, with no
   "[object Object]".
2. Tap it and expect "Verification email sent to …". The email should be
   **Zeus Beats**-branded and link to zeusbeats.com.
3. Tap it 4 times within a minute. The 4th should say to wait a minute.
4. Verify via the link, go back, tap **Try again** → Create, and expect the song
   to generate.

Tests: `node --test src/utils/*.test.ts` · types: `npx tsc --noEmit`
