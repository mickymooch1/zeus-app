// Run: node --test src/utils/*.test.ts   (Node 24 strips the types natively)
import { test } from 'node:test';
import assert from 'node:assert/strict';
// @ts-expect-error TS5097 — Node's native type stripping needs the explicit .ts extension
import { unverifiedEmail, resendOutcome, RESEND_BODY } from './verification.ts';

// 2026-09-27: an unverified user was stuck on the Create screen with only
// "Try again" — the app had no way to re-send the verification link.

test('the generate 403 gate is recognised, with the address it was sent to', () => {
  const detail = { code: 'email_unverified', message: 'Please verify…', email: 'a@b.com', bounced: false };
  assert.equal(unverifiedEmail(detail), 'a@b.com');
});

test('the gate is recognised even if the email field is missing', () => {
  assert.equal(unverifiedEmail({ code: 'email_unverified', message: 'x' }), '');
});

test('anything else is not the verification gate', () => {
  for (const d of [undefined, null, 'Please verify', { code: 'other' }, [{ type: 'x' }], 42]) {
    assert.equal(unverifiedEmail(d), null);
  }
});

test('the resend asks for the Zeus Beats email, not the Zeus AI default', () => {
  assert.deepEqual(RESEND_BODY, { app: 'beats' });
});

test('a successful resend says where to look', () => {
  const o = resendOutcome(200, { ok: true, bounced: false, message: 'Verification email sent. Please check your inbox.' }, 'a@b.com');
  assert.equal(o.kind, 'sent');
  assert.match(o.message, /a@b\.com/);
  assert.match(o.message, /junk|spam/i);
});

test('an already-verified account is told to just try again', () => {
  const o = resendOutcome(200, { ok: true, message: 'Email is already verified.' }, 'a@b.com');
  assert.equal(o.kind, 'already');
  assert.match(o.message, /already verified/i);
});

test('a bounced address uses the server message and points to the website to change it', () => {
  const o = resendOutcome(200, { ok: false, bounced: true, bounce_origin: 'x', message: 'This email address is rejecting our messages — update it to receive a verification link.' }, 'a@b.com');
  assert.equal(o.kind, 'bounced');
  assert.match(o.message, /rejecting our messages/);
  assert.match(o.message, /zeusbeats\.com/);
});

test('the 3-per-minute limit is explained, not shown as a failure', () => {
  const o = resendOutcome(429, { detail: 'Rate limit exceeded' }, 'a@b.com');
  assert.equal(o.kind, 'ratelimited');
  assert.match(o.message, /minute/);
});

test('any other failure is a plain retry message', () => {
  for (const [status, data] of [[500, {}], [401, { detail: 'Invalid or expired token' }], [0, null]] as const) {
    const o = resendOutcome(status, data, 'a@b.com');
    assert.equal(o.kind, 'error');
    assert.ok(!o.message.includes('[object Object]'));
  }
});
