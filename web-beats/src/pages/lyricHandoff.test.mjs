/**
 * The Lyric Workshop → Create hand-off.
 *
 * This is the one path in the feature that fails SILENTLY. The generate payload
 * reads `custom_lyrics` only when `useCustomLyrics` is true:
 *
 *   brief:         useCustomLyrics ? (songTitle.trim() || 'Custom song') : brief.trim(),
 *   custom_lyrics: useCustomLyrics ? customLyricsText.trim() : undefined,
 *
 * So a hand-off that fills the lyrics but forgets the mode flag sends the user's
 * *brief* instead — Claude rewrites the lyrics from scratch and the user gets a
 * different song than the one they approved, with no error anywhere. Nothing in
 * the UI would show it; you would only catch it by comparing the finished track to
 * the sheet. Hence a test rather than trusting the four lines to stay correct.
 *
 * These model the real reducers rather than importing SongsPage, which needs a
 * full React + router + audio environment to mount.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const SRC = fs.readFileSync(path.join(import.meta.dirname, 'SongsPage.jsx'), 'utf8');

/** The four state writes handleUseWorkshopLyrics performs. */
function handoff(state, lyrics, title) {
  return {
    ...state,
    isRoastMode: false,                                        // 4
    useCustomLyrics: true,                                     // 1
    customLyricsText: lyrics,                                  // 2
    songTitle: state.songTitle.trim() || title || '',          // 3
    creatorTab: 'create',
  };
}

/** The real payload builder, transcribed from SongsPage.jsx. */
function buildPayload(s) {
  return {
    brief: s.useCustomLyrics ? (s.songTitle.trim() || 'Custom song') : s.brief.trim(),
    custom_lyrics: s.useCustomLyrics ? s.customLyricsText.trim() : undefined,
    song_title: s.songTitle.trim() || undefined,
  };
}

const base = {
  brief: 'something the user typed earlier',
  songTitle: '',
  useCustomLyrics: false,
  customLyricsText: '',
  isRoastMode: false,
  creatorTab: 'lyrics',
};

const LYRICS = '[Verse 1]\nstarted with nothing\n\n[Chorus]\nlook at me now';

test('the workshop lyrics are what actually get generated', () => {
  const payload = buildPayload(handoff(base, LYRICS, 'Look At Me Now'));
  assert.equal(payload.custom_lyrics, LYRICS,
    'the approved sheet must be the thing sent');
});

test('the brief is NOT what gets generated from', () => {
  const payload = buildPayload(handoff(base, LYRICS, 'Look At Me Now'));
  assert.notEqual(payload.brief, base.brief,
    'sending the old brief means Claude rewrites the lyrics from scratch');
});

test('skipping the mode flag silently discards the lyrics — the bug this guards', () => {
  // Exactly what a three-step hand-off would produce.
  const broken = { ...base, customLyricsText: LYRICS, creatorTab: 'create' };
  const payload = buildPayload(broken);
  assert.equal(payload.custom_lyrics, undefined,
    'without useCustomLyrics the lyrics never leave the browser');
  assert.equal(payload.brief, base.brief,
    'and the stale brief is generated from instead — a different song, no error');
});

test('a suggested title replaces the "Custom song" placeholder', () => {
  const payload = buildPayload(handoff(base, LYRICS, 'Look At Me Now'));
  assert.equal(payload.song_title, 'Look At Me Now');
  assert.equal(payload.brief, 'Look At Me Now',
    'in custom mode the title becomes the brief; otherwise every entry reads "Custom song"');
});

test('a title the user already typed is not overwritten', () => {
  const typed = { ...base, songTitle: 'My Own Title' };
  assert.equal(handoff(typed, LYRICS, 'Suggested').songTitle, 'My Own Title');
});

test('roast mode is cleared, or the lyrics field never renders', () => {
  const roast = { ...base, isRoastMode: true };
  assert.equal(handoff(roast, LYRICS, 'T').isRoastMode, false);
});

test('the hand-off lands the user on the Create tab', () => {
  assert.equal(handoff(base, LYRICS, 'T').creatorTab, 'create');
});

// ── The source itself, so the transcriptions above cannot drift ──────────────

test('SongsPage still performs all four state writes', () => {
  const fn = SRC.slice(SRC.indexOf('handleUseWorkshopLyrics = useCallback'));
  const body = fn.slice(0, fn.indexOf('}, []);'));
  for (const call of ['setIsRoastMode(false)', 'setUseCustomLyrics(true)',
                      'setCustomLyricsText(', 'setSongTitle(']) {
    assert.ok(body.includes(call), `hand-off must still call ${call}`);
  }
});

test('the payload builder still gates custom_lyrics on useCustomLyrics', () => {
  assert.ok(
    SRC.includes('custom_lyrics: useCustomLyrics ? customLyricsText.trim() : undefined'),
    'if this line changes shape, the transcription above is stale and these tests lie',
  );
});

test('the workshop is given a real auth token, not a localStorage guess', () => {
  // Caught in review: the component originally read localStorage.getItem('token'),
  // which is always null — the key is 'zeus_token'. That sends `Bearer null` and
  // 401s every request, while looking completely correct in the source.
  const WS = fs.readFileSync(
    path.join(import.meta.dirname, '..', 'components', 'LyricWorkshop.jsx'), 'utf8');
  assert.ok(!WS.includes("localStorage.getItem('token')"),
    "'token' is not the storage key — the token must come from useAuth via props");
  assert.ok(SRC.includes('token={token}'),
    'SongsPage must pass the useAuth token down to the workshop');
});

test('the Lyrics tab is not offered in kids mode', () => {
  // Both panels are mounted and toggled with display, so a tab switch preserves the
  // conversation and the genre/Advanced picks. The kids guard therefore wraps the
  // whole workshop card rather than the tab condition.
  const card = SRC.slice(SRC.indexOf('LyricWorkshop onUseLyrics') - 1400,
                         SRC.indexOf('LyricWorkshop onUseLyrics'));
  assert.ok(card.includes('{!isKidsMode && ('),
    'kids mode has no custom-lyrics field, so the hand-off would dead-end');
  assert.ok(card.includes("display: creatorTab === 'lyrics' ? 'block' : 'none'"),
    'the workshop must be hidden, not unmounted, or switching tabs wipes the chat');
  assert.ok(SRC.includes('{!isKidsMode && ('),
    'the tab buttons themselves must be hidden in kids mode too');
});
