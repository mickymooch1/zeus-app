// The loop that watches a song generation until it finishes.
//
// Extracted from SongsPage so the behaviour that matters — "a finished song
// appears on its own, with no manual refresh, every time" — can actually be
// tested. See utils/generationPoller.test.mjs.
//
// The bug this exists to prevent (shipped 2026-08-05): the original poll was a
// one-shot setTimeout that re-armed ONLY as a side effect of succeeding. A
// single failed request meant no next poll was ever scheduled, so the card span
// forever while the song sat finished on the server, and users learned to
// refresh the page manually after five minutes.
//
// Two guarantees this must uphold:
//   1. Failures NEVER end the loop. It keeps polling until settled or expired.
//   2. There is always an upper bound. On expiry it still refreshes the library,
//      so a finished song appears by itself rather than leaving a dead card.

export const POLL_INTERVAL_MS = 5_000;
export const MAX_JOB_MS = 5 * 60 * 1000;
export const POLL_FAILURES_BEFORE_WARNING = 6;   // ~30s of consecutive failures

/**
 * @param {object}   o
 * @param {number[]} o.trackedIds   variant ids this job owns
 * @param {Function} o.fetchVariants async () => [{variant_id, status}, ...]; may throw
 * @param {Function} o.onUpdate      (variants) => void — refresh the cards
 * @param {Function} o.onSettled     ({anyComplete, reason}) => Promise|void — clear + reload
 * @param {Function} o.onTrouble     (failures) => void — warn after repeated failures
 * @param {Function} [o.now]         () => ms, injectable for tests
 * @param {Function} [o.setTimer]    (fn, ms) => handle
 * @param {Function} [o.clearTimer]  (handle) => void
 * @returns {{stop: Function}}
 */
export function startGenerationPoll({
  trackedIds,
  fetchVariants,
  onUpdate,
  onSettled,
  onTrouble,
  now = () => Date.now(),
  // Pass the time the JOB began, not the time this poller was constructed, so a
  // restart (React re-running the effect) cannot silently extend the deadline.
  startedAt = null,
  setTimer = (fn, ms) => setInterval(fn, ms),
  clearTimer = (h) => clearInterval(h),
  intervalMs = POLL_INTERVAL_MS,
  maxJobMs = MAX_JOB_MS,
  failuresBeforeWarning = POLL_FAILURES_BEFORE_WARNING,
}) {
  const tracked = new Set(trackedIds);
  const jobStart = startedAt ?? now();
  let failures = 0;
  let warned = false;
  let stopped = false;
  let handle = null;

  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearTimer(handle);
  };

  const settle = async (anyComplete, reason) => {
    stop();
    await onSettled({ anyComplete, reason });
  };

  const tick = async () => {
    if (stopped) return;

    // Upper bound. Even here the library is reloaded, so a song that finished
    // while polling was failing still turns up without the user doing anything.
    if (now() - jobStart > maxJobMs) {
      await settle(false, 'expired');
      return;
    }

    try {
      const variants = await fetchVariants();
      failures = 0;
      if (warned) { warned = false; onTrouble(0); }

      const mine = (variants || []).filter((v) => tracked.has(v.variant_id));
      if (mine.length) onUpdate(mine);

      // mine.length is required: an empty list must not read as settled, since
      // [].every() is vacuously true and would clear the card claiming success.
      const settled = mine.length > 0 &&
        mine.every((v) => v.status === 'complete' || v.status === 'failed');
      if (settled) {
        await settle(mine.some((v) => v.status === 'complete'), 'settled');
      }
    } catch {
      // Deliberately swallowed AND the loop continues — this is the whole point.
      failures += 1;
      if (failures >= failuresBeforeWarning && !warned) {
        warned = true;
        onTrouble(failures);
      }
    }
  };

  handle = setTimer(tick, intervalMs);
  return { stop, tick };   // tick exposed for deterministic testing
}
