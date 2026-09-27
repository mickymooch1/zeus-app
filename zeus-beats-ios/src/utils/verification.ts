// Email-verification gate helpers for the Create screen.
//
// /api/songs/generate returns 403 with detail {code: 'email_unverified', ...}
// for an account that hasn't clicked its verification link. The app had no way
// out of that state (2026-09-27), so the blocked screen now offers a resend via
// POST /api/auth/resend-verification — the same endpoint web-beats uses.

// The endpoint defaults to app="ai", which sends a Zeus AI-branded email linking
// to zeusaidesign.com. This app must always ask for the Zeus Beats one.
export const RESEND_BODY = { app: 'beats' } as const;

/** The address the gate refers to ('' if not given), or null if this isn't the gate. */
export function unverifiedEmail(detail: unknown): string | null {
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const d = detail as { code?: unknown; email?: unknown };
  if (d.code !== 'email_unverified') return null;
  return typeof d.email === 'string' ? d.email : '';
}

export type ResendKind = 'sent' | 'already' | 'bounced' | 'ratelimited' | 'error';

export function resendOutcome(status: number, data: any, email: string): { kind: ResendKind; message: string } {
  if (data?.bounced) {
    const base = typeof data.message === 'string' && data.message
      ? data.message
      : 'This email address is rejecting our messages.';
    return { kind: 'bounced', message: `${base} You can change your email at zeusbeats.com.` };
  }
  // Limited to 3/minute server-side — say so, or people hammer the button.
  if (status === 429) {
    return { kind: 'ratelimited', message: 'Please wait a minute before asking for another email.' };
  }
  if (status >= 200 && status < 300 && data?.ok) {
    if (typeof data.message === 'string' && /already verified/i.test(data.message)) {
      return { kind: 'already', message: 'Your email is already verified — tap Try again.' };
    }
    const to = email ? ` to ${email}` : '';
    return {
      kind: 'sent',
      message: `Verification email sent${to}. Open the link in it (check your Junk or Spam folder too), then tap Try again.`,
    };
  }
  return { kind: 'error', message: "Couldn't send the email — please try again." };
}
