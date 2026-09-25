import { test } from 'node:test';
import assert from 'node:assert/strict';
import { apiErrorMessage, ROAST_DETAILS_MAX } from './apiErrorMessage.js';

// A failed roast (2026-09-25) showed only "Generation failed" — the backend's
// 422 detail is a LIST of Pydantic errors, which the old string/.message check
// dropped on the floor. This turns any detail shape into a readable sentence.

const tooLong = (field, max) => ({
  type: 'string_too_long', loc: ['body', field],
  msg: `String should have at most ${max} characters`, ctx: { max_length: max },
});

test('a plain string detail is shown as-is', () => {
  assert.equal(apiErrorMessage('Not enough credits', 'Generation failed'), 'Not enough credits');
});

test('an object detail with a message uses the message', () => {
  assert.equal(apiErrorMessage({ code: 'x', message: 'Try again soon' }, 'Generation failed'), 'Try again soon');
});

test('an over-long roast details 422 names the box and the limit', () => {
  assert.equal(
    apiErrorMessage([tooLong('roast_details', 800)], 'Generation failed'),
    'Roast details are too long — max 800 characters.',
  );
});

test('other known fields get friendly names too', () => {
  assert.equal(apiErrorMessage([tooLong('roast_name', 120)], 'x'), 'Name is too long — max 120 characters.');
  assert.equal(apiErrorMessage([tooLong('brief', 2000)], 'x'), 'Song description is too long — max 2000 characters.');
  assert.equal(
    apiErrorMessage([{ type: 'too_long', loc: ['body', 'genres'], msg: 'List should have at most 7 items', ctx: { max_length: 7 } }], 'x'),
    'Too many genres — pick up to 7.',
  );
});

test('an unknown field or rule falls back to the field label plus the server message', () => {
  assert.equal(
    apiErrorMessage([{ type: 'string_type', loc: ['body', 'roast_vibe'], msg: 'Input should be a valid string' }], 'x'),
    'Roast vibe: Input should be a valid string',
  );
  assert.equal(
    apiErrorMessage([{ type: 'weird', loc: ['body', 'mystery_field'], msg: 'Nope' }], 'x'),
    'mystery_field: Nope',
  );
});

test('several errors are joined', () => {
  assert.equal(
    apiErrorMessage([tooLong('roast_details', 800), tooLong('roast_name', 120)], 'x'),
    'Roast details are too long — max 800 characters. Name is too long — max 120 characters.',
  );
});

test('missing or unusable details fall back', () => {
  for (const d of [undefined, null, '', [], {}, [{}], 42]) {
    assert.equal(apiErrorMessage(d, 'Generation failed'), 'Generation failed');
  }
});

test('the roast details cap matches the backend limit', () => {
  assert.equal(ROAST_DETAILS_MAX, 800);
});
