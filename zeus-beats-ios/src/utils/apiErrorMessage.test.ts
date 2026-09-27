// Run: node --test src/utils/*.test.ts   (Node 24 strips the types natively)
import { test } from 'node:test';
import assert from 'node:assert/strict';
// @ts-expect-error TS5097 — Node's native type stripping needs the explicit .ts extension
import { apiErrorMessage } from './apiErrorMessage.ts';

// 2026-09-27: an unverified user on the Create screen saw "[object Object]" —
// the generate endpoint's 403 detail is an OBJECT ({code, message, email, ...}),
// and `new Error(body.detail)` stringified it.

const unverified = {
  code: 'email_unverified',
  message: 'Please verify your email address before generating songs. We sent you a verification link when you signed up.',
  email: 'someone@example.com',
  bounced: false,
  bounce_origin: null,
};

test('the email_unverified 403 shows its real message, never [object Object]', () => {
  const msg = apiErrorMessage(unverified, 403);
  assert.ok(msg.startsWith('Please verify your email address'), msg);
  assert.ok(!msg.includes('[object Object]'));
});

test('a plain string detail is shown as-is', () => {
  assert.equal(apiErrorMessage('Not enough credits', 402), 'Not enough credits');
});

test('a FastAPI 422 list is turned into readable text', () => {
  const detail = [{ type: 'string_too_long', loc: ['body', 'brief'], msg: 'String should have at most 2000 characters', ctx: { max_length: 2000 } }];
  assert.equal(apiErrorMessage(detail, 422), 'Song description is too long — max 2000 characters.');
});

test('an unknown 422 field falls back to the server message', () => {
  const detail = [{ type: 'weird', loc: ['body', 'mystery'], msg: 'Nope' }];
  assert.equal(apiErrorMessage(detail, 422), 'mystery: Nope');
});

test('an object without a message, or no detail at all, falls back to the status', () => {
  for (const d of [undefined, null, '', {}, { code: 'x' }, [], [{}], 42]) {
    const msg = apiErrorMessage(d, 500);
    assert.equal(msg, 'Something went wrong (error 500). Please try again.');
  }
});
