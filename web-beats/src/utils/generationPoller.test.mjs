// Run: node --test src/utils/generationPoller.test.mjs
//
// The requirement under test, in the user's words:
//   "a song that completes will show up automatically without any manual
//    refresh, every time"
//
// Users were having to reload the page after five minutes to see a song that
// had already finished on the server, because the old poll re-armed only on
// success and so died on the first failed request. These tests drive the REAL
// poller with an injected clock and timer, so completion detection is proven
// rather than reasoned about.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  startGenerationPoll,
  MAX_JOB_MS,
  POLL_INTERVAL_MS,
} from './generationPoller.js';

/** Deterministic harness: a fake clock and a hand-cranked timer. */
function harness({ completesAt = 120_000, failPolls = new Set(), neverCompletes = false } = {}) {
  let clock = 0;
  let ticker = null;
  let attempt = 0;
  const state = { updates: [], settled: null, trouble: [], libraryReloads: 0 };

  const poller = startGenerationPoll({
    trackedIds: [1],
    fetchVariants: async () => {
      attempt += 1;
      if (failPolls.has(attempt)) throw new Error('network blip');
      const done = !neverCompletes && clock >= completesAt;
      return [{ variant_id: 1, status: done ? 'complete' : 'generating' }];
    },
    onUpdate: (mine) => state.updates.push({ at: clock, status: mine[0].status }),
    onSettled: async ({ anyComplete, reason }) => {
      state.libraryReloads += 1;              // what makes the song appear
      state.settled = { at: clock, anyComplete, reason };
    },
    onTrouble: (failures) => state.trouble.push({ at: clock, failures }),
    now: () => clock,
    startedAt: 0,
    setTimer: (fn) => { ticker = fn; return 'handle'; },
    clearTimer: () => { ticker = null; },
  });

  /** Advance the fake clock, running the poll on each interval. */
  const advance = async (ms) => {
    for (let i = 0; i < ms / POLL_INTERVAL_MS; i += 1) {
      clock += POLL_INTERVAL_MS;
      if (ticker) await ticker();
    }
  };
  return { state, advance, poller, clockNow: () => clock };
}

describe('a finished song appears on its own — no manual refresh', () => {
  it('detects completion automatically on the happy path', async () => {
    const h = harness({ completesAt: 120_000 });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled, 'never settled — the card would spin forever');
    assert.equal(h.state.settled.reason, 'settled');
    assert.equal(h.state.settled.anyComplete, true);
    assert.equal(h.state.settled.at, 120_000, 'should settle the moment it completes');
    assert.equal(h.state.libraryReloads, 1, 'library must reload so the song shows');
  });

  it('THE REGRESSION: one failed poll does not kill the loop', async () => {
    // The old code died here — attempt 3 fails at t=15s and nothing polls again.
    const h = harness({ completesAt: 120_000, failPolls: new Set([3]) });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled, 'a single blip must not stop detection');
    assert.equal(h.state.settled.at, 120_000);
    assert.equal(h.state.libraryReloads, 1);
  });

  it('survives a long burst of failures and still auto-detects', async () => {
    const failPolls = new Set([3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    const h = harness({ completesAt: 120_000, failPolls });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled, 'still must recover by itself');
    assert.equal(h.state.settled.at, 120_000);
  });

  it('survives failures at the exact moment the song completes', async () => {
    // Completion lands at 120s = attempt 24; fail 24 and 25 to be sure the next
    // successful poll still catches it.
    const h = harness({ completesAt: 120_000, failPolls: new Set([24, 25]) });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled);
    assert.equal(h.state.settled.at, 130_000, 'caught on the next good poll');
  });

  it('recovers even if every poll fails until after completion', async () => {
    const failPolls = new Set(Array.from({ length: 30 }, (_, i) => i + 1));  // polls 1-30
    const h = harness({ completesAt: 60_000, failPolls });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled, 'must recover once the network returns');
    assert.equal(h.state.settled.at, 155_000, 'first successful poll after the outage');
  });
});

describe('the 5-minute safety net reloads the library by itself', () => {
  it('gives up and reloads when the song never completes', async () => {
    const h = harness({ neverCompletes: true });
    await h.advance(10 * 60_000);
    assert.ok(h.state.settled, 'must not spin indefinitely');
    assert.equal(h.state.settled.reason, 'expired');
    assert.equal(h.state.libraryReloads, 1,
      'the expiry path MUST still reload — this is what removes the manual refresh');
    assert.ok(h.state.settled.at > MAX_JOB_MS);
    assert.ok(h.state.settled.at <= MAX_JOB_MS + POLL_INTERVAL_MS);
  });

  it('gives up if the network is down for the entire job', async () => {
    const failPolls = new Set(Array.from({ length: 500 }, (_, i) => i + 1));
    const h = harness({ failPolls });
    await h.advance(10 * 60_000);
    assert.equal(h.state.settled.reason, 'expired');
    assert.equal(h.state.libraryReloads, 1, 'still reloads so the song can appear');
  });

  it('does not expire early on a slow but normal generation', async () => {
    const h = harness({ completesAt: 165_000 });   // 2m45s — the slowest seen live
    await h.advance(10 * 60_000);
    assert.equal(h.state.settled.reason, 'settled');
    assert.equal(h.state.settled.anyComplete, true);
  });
});

describe('safety and reporting', () => {
  it('an empty variant list is never mistaken for success', async () => {
    // [].every() is vacuously true — this must not clear the card claiming done.
    let clock = 0, ticker = null;
    const seen = [];
    startGenerationPoll({
      trackedIds: [1],
      fetchVariants: async () => [],
      onUpdate: () => seen.push('update'),
      onSettled: async ({ reason }) => seen.push(reason),
      onTrouble: () => {},
      now: () => clock,
      startedAt: 0,
      setTimer: (fn) => { ticker = fn; return 'h'; },
      clearTimer: () => { ticker = null; },
    });
    for (let i = 0; i < 12; i += 1) { clock += POLL_INTERVAL_MS; await ticker?.(); }
    assert.deepEqual(seen, [], 'must keep waiting, not declare success');
  });

  it('warns the user only after sustained failure, not one blip', async () => {
    const one = harness({ completesAt: 120_000, failPolls: new Set([2]) });
    await one.advance(120_000);
    assert.equal(one.state.trouble.length, 0, 'a single blip must stay invisible');

    const many = harness({
      completesAt: 600_000,
      failPolls: new Set([1, 2, 3, 4, 5, 6, 7, 8]),
    });
    await many.advance(60_000);
    assert.ok(many.state.trouble.length > 0, 'sustained failure should be surfaced');
    assert.equal(many.state.trouble[0].failures, 6);
  });

  it('clears the warning once polling recovers', async () => {
    const h = harness({ completesAt: 300_000, failPolls: new Set([1, 2, 3, 4, 5, 6, 7]) });
    await h.advance(120_000);
    const cleared = h.state.trouble.filter((t) => t.failures === 0);
    assert.ok(cleared.length > 0, 'the warning must be withdrawn when it recovers');
  });

  it('stop() halts polling (component unmount)', async () => {
    const h = harness({ completesAt: 120_000 });
    await h.advance(30_000);
    h.poller.stop();
    await h.advance(300_000);
    assert.equal(h.state.settled, null, 'no work after unmount');
  });

  it('a failed song settles too — it must not spin', async () => {
    let clock = 0, ticker = null, settled = null;
    startGenerationPoll({
      trackedIds: [1],
      fetchVariants: async () => [{ variant_id: 1, status: clock >= 60_000 ? 'failed' : 'generating' }],
      onUpdate: () => {},
      onSettled: async (r) => { settled = r; },
      onTrouble: () => {},
      now: () => clock,
      startedAt: 0,
      setTimer: (fn) => { ticker = fn; return 'h'; },
      clearTimer: () => { ticker = null; },
    });
    for (let i = 0; i < 24; i += 1) { clock += POLL_INTERVAL_MS; await ticker?.(); }
    assert.ok(settled, 'a failed generation must clear the card');
    assert.equal(settled.anyComplete, false);
  });
});
