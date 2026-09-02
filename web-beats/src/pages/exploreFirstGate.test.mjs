/**
 * The explore-first / onboarding-tour gate.
 *
 * Two independent localStorage flags decide which of three things a visit shows:
 *   zeus_onboarding_done       — set when the TOUR ITSELF is skipped or completed
 *   zeus_explore_first_seen    — set the moment the explore-first screen is decided
 *
 * The one state that's easy to get wrong: someone who clicked "Show me around"
 * last visit but closed the tab mid-tour has explore_first_seen=true and
 * onboarding_done still unset. That visitor must resume the TOUR directly, not
 * see the welcome screen a second time — verified in the browser at 375px, and
 * pinned here so the branching can't silently regress.
 *
 * Transcribed from the real initializers in SongsPage.jsx, same approach as
 * lyricHandoff.test.mjs (SongsPage needs a full React + router + audio
 * environment to mount, so the state logic is verified structurally instead).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const SRC = fs.readFileSync(path.join(import.meta.dirname, 'SongsPage.jsx'), 'utf8');

/** Transcribed from the real useState initializers. */
function gateState({ onboardingDone, exploreFirstSeen }) {
  return {
    showExploreFirst: !onboardingDone && !exploreFirstSeen,
    showTour: !onboardingDone && !!exploreFirstSeen,
  };
}

test('a true first visit shows the welcome screen, not the tour', () => {
  const s = gateState({ onboardingDone: false, exploreFirstSeen: false });
  assert.equal(s.showExploreFirst, true);
  assert.equal(s.showTour, false);
});

test('leaving mid-tour resumes the tour directly on the next visit', () => {
  // explore_first_seen=true, onboarding_done still unset — exactly what a closed
  // tab mid-tour leaves behind, since only dismiss() inside the tour sets
  // onboarding_done.
  const s = gateState({ onboardingDone: false, exploreFirstSeen: true });
  assert.equal(s.showExploreFirst, false, 'must not show the welcome screen twice');
  assert.equal(s.showTour, true, 'must resume the tour, not strand the visitor on neither screen');
});

test('a completed or skipped onboarding shows neither screen again', () => {
  const s = gateState({ onboardingDone: true, exploreFirstSeen: true });
  assert.equal(s.showExploreFirst, false);
  assert.equal(s.showTour, false);
});

test('"I\'ll explore myself" sets both flags, matching what skipping the tour itself does', () => {
  // Pulled directly from the onDismiss handler so the transcription can't drift.
  const start = SRC.indexOf('onDismiss={() => {');
  const body = SRC.slice(start, SRC.indexOf('/>', start));
  assert.ok(body.includes("localStorage.setItem('zeus_explore_first_seen', '1')"));
  assert.ok(body.includes("localStorage.setItem('zeus_onboarding_done'"),
    'must also mark onboarding done, or the 24h retrigger banner never offers a second chance to someone who skipped from this screen');
});

test('"Show me around" does NOT mark onboarding done — only the tour finishing does', () => {
  const start = SRC.indexOf('onShowTour={() => {');
  const end = SRC.indexOf('onDismiss={() => {', start);
  const body = SRC.slice(start, end);
  assert.ok(body.includes("localStorage.setItem('zeus_explore_first_seen', '1')"));
  assert.ok(!body.includes('zeus_onboarding_done'),
    'onboarding_done belongs to the tour completing/skipping, not to entering it');
});

// ── Advanced toggle first-visit pulse ─────────────────────────────────────────

/**
 * Transcribed from the real useState initializer, not a substring check —
 * `RED B` below is why: a substring check only proves the setItem call's text
 * exists SOMEWHERE in the source, not that it's reachable. An early
 * `return false` before it — the exact regression this guards — leaves the
 * string sitting in the file as dead code, and a text-presence test stays
 * green through that. This transcription actually executes the branching.
 */
function computeAdvancedPulse({ showAdvanced, alreadySeen }, setFlag) {
  if (showAdvanced) return false;
  if (alreadySeen) return false;
  setFlag();
  return true;
}

test('the pulse only fires when Advanced starts collapsed', () => {
  let set = false;
  const result = computeAdvancedPulse({ showAdvanced: true, alreadySeen: false }, () => { set = true; });
  assert.equal(result, false, 'an already-open panel has nothing to draw attention to opening');
  assert.equal(set, false, 'must not burn the once-per-lifetime flag on a visit that never pulses');
});

test('the pulse fires and sets the flag on a genuine first visit', () => {
  let set = false;
  const result = computeAdvancedPulse({ showAdvanced: false, alreadySeen: false }, () => { set = true; });
  assert.equal(result, true);
  assert.equal(set, true, 'flag must be set at mount, not deferred to a click that may never happen');
});

test('the pulse never fires again once the flag is set', () => {
  const result = computeAdvancedPulse({ showAdvanced: false, alreadySeen: true }, () => {
    throw new Error('must not re-set an already-set flag');
  });
  assert.equal(result, false);
});

test('the transcription above matches the real initializer, in order', () => {
  const block = SRC.slice(SRC.indexOf('const [showAdvancedPulse]'), SRC.indexOf('const [showSoundControl]'));
  const order = ['if (showAdvanced) return false;',
    "if (localStorage.getItem('zeus_advanced_pulse_seen')) return false;",
    "localStorage.setItem('zeus_advanced_pulse_seen', '1');",
    'return true;'];
  let cursor = 0;
  for (const line of order) {
    const idx = block.indexOf(line, cursor);
    assert.ok(idx >= cursor, `expected in order: ${line}`);
    cursor = idx + line.length;
  }
});

test('the pulse animation is finite, not infinite', () => {
  assert.ok(SRC.includes('.adv-toggle-pulse { animation: advancedTogglePulse 1.4s ease-in-out 3; }'),
    'a first-visit nudge must stop on its own — infinite would make it permanent, ' +
    'unlike .topup-section\'s intentionally-ongoing glow');
});
