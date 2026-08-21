// Run: node --test src/pages/generateGating.test.mjs
//
// The requirement under test, in the user's words:
//   "don't enable the Generate button until credits are confirmed loaded AND
//    sufficient for the cost"
//
// SongsPage.jsx:1431 used to read:
//
//     canAfford = isAdmin || !creditsLoaded || (credits.balance >= cost && cost > 0)
//
// The `!creditsLoaded` clause enabled Generate before the balance was known, on
// the reasoning that the server would reject anything unaffordable. It does — but
// only AFTER generate_lyrics has written a lyrics row, so the request 402s and
// leaves an orphaned row with no song. Three exist since 1 August: lyric 602
// (dominic.rowle@yahoo.com) and 680, 695 (kingshaza727@gmail.com).
//
// The second, subtler rule: 'error' must stay distinct from 'ready'. fetchCredits
// set its flag in a `finally`, so a failed request looked identical to a
// successful one reporting zero — which would now assert "you have no credits" to
// someone whose network merely hiccuped. Unknown is not zero.
//
// SongsPage.jsx is a React module that cannot be imported outside a bundler, so
// the gating rule is mirrored here and the source is asserted to still match it.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const SRC = readFileSync(new URL('./SongsPage.jsx', import.meta.url), 'utf8');

/** Mirror of the shipped rule. */
function canAfford({ isAdmin = false, creditsStatus, balance = 0, cost = 1 }) {
  return isAdmin || (creditsStatus === 'ready' && balance >= cost && cost > 0);
}

describe('Generate gating', () => {
  it('is disabled while credits are still loading', () => {
    assert.equal(canAfford({ creditsStatus: 'loading', balance: 99, cost: 1 }), false);
  });

  it('is disabled when the credits fetch failed', () => {
    assert.equal(canAfford({ creditsStatus: 'error', balance: 99, cost: 1 }), false);
  });

  it('is enabled once credits are confirmed sufficient', () => {
    assert.equal(canAfford({ creditsStatus: 'ready', balance: 3, cost: 3 }), true);
  });

  it('is disabled when confirmed insufficient', () => {
    assert.equal(canAfford({ creditsStatus: 'ready', balance: 2, cost: 3 }), false);
  });

  it('costs one credit per genre, so 5 genres needs 5 credits', () => {
    assert.equal(canAfford({ creditsStatus: 'ready', balance: 3, cost: 5 }), false,
      'the exact case that orphaned lyric rows 680 and 695');
    assert.equal(canAfford({ creditsStatus: 'ready', balance: 5, cost: 5 }), true);
  });

  it('admins bypass the check entirely', () => {
    assert.equal(canAfford({ isAdmin: true, creditsStatus: 'loading', balance: 0, cost: 7 }), true);
  });

  it('never enables on zero cost', () => {
    assert.equal(canAfford({ creditsStatus: 'ready', balance: 10, cost: 0 }), false);
  });

  // ── the shipped source must still implement the rule above ────────────────

  it('SongsPage no longer optimistically allows while loading', () => {
    const code = SRC.split('\n').filter(l => !l.trim().startsWith('//')).join('\n');
    assert.ok(!/canAfford\s*=\s*isAdmin\s*\|\|\s*!creditsLoaded/.test(code),
      'the !creditsLoaded escape hatch is back — Generate can fire before the balance is known');
    assert.ok(/creditsStatus === 'ready'/.test(code),
      'canAfford must require a confirmed credits load');
  });

  it('a failed credits fetch is recorded as error, not ready', () => {
    assert.ok(SRC.includes("setCreditsStatus('error')"),
      'fetchCredits must distinguish failure from a confirmed zero balance');
    assert.ok(!/finally\s*\{\s*setCreditsLoaded\(true\)/.test(SRC),
      'marking loaded in a finally makes a failed fetch look like a successful one');
  });

  it('the unknown state offers a retry rather than a verdict', () => {
    assert.ok(SRC.includes('creditsUnavailableHint'));
    assert.ok(SRC.includes('songs.retry'));
  });

  it('creditExceeded is only claimed once the balance is known', () => {
    assert.ok(/creditExceeded\s*=\s*!isAdmin\s*&&\s*creditsStatus === 'ready'/.test(SRC),
      'an unread balance of 0 must not render as "not enough credits"');
  });
});
