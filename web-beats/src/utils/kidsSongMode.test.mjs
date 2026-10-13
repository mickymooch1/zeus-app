// Run: node --test src/utils/kidsSongMode.test.mjs
// Source scans of the standalone Zeus Kids song screen (no render library here).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const SRC = readFileSync(new URL('../pages/kids/KidsSongMode.jsx', import.meta.url), 'utf8');

test('kids song screen has an optional "What Happens?" box under Main Character', () => {
  const label = SRC.indexOf('✨ What Happens?');
  assert.ok(label > 0, 'missing the What Happens? label');
  assert.ok(label > SRC.indexOf('🦁 Main Character'), 'What Happens? must come after Main Character');
  assert.ok(label < SRC.indexOf('✨ Make My Song!'), 'What Happens? must come before the generate button');
  assert.match(SRC, /<textarea[\s\S]*?value=\{happens\}[\s\S]*?onChange=\{e => setHappens\(e\.target\.value\)\}/);
});

test('what the child types is sent in the song brief', () => {
  assert.match(SRC, /happens\.trim\(\)\s*&&\s*`What happens: \$\{happens\.trim\(\)\}`/);
});

test('a theme alone is still enough to make a song', () => {
  assert.match(SRC, /const canGenerate = theme !== null;/);
});

test('no music style is pre-selected, and tapping the selected one unpicks it', () => {
  assert.match(SRC, /const \[musicStyle, setMusicStyle\] = useState\(null\);/);
  assert.match(SRC, /setMusicStyle\(musicStyle === s\.value \? null : s\.value\)/);
  // With nothing picked the song still gets a genre (Fun Pop's).
  assert.match(SRC, /MUSIC_STYLES\.find\(s => s\.value === musicStyle\) \?\? MUSIC_STYLES\[1\]/);
  assert.equal(SRC.match(/value: 'funpop'[^}]*genres: \['pop'\]/) !== null, true);
});

// The Kids section of the main Create page has its own Music Style picker,
// shared by Song and Story mode.
const SONGS_PAGE = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');

test('Create-page Kids music style starts unpicked and both pickers can unpick it', () => {
  assert.match(SONGS_PAGE, /const \[kidsMusicStyle, setKidsMusicStyle\] = useState\(null\);/);
  const toggles = SONGS_PAGE.match(/onClick=\{\(\) => setKidsMusicStyle\(kidsMusicStyle === val \? null : val\)\}/g) || [];
  assert.equal(toggles.length, 2, 'Song and Story pickers must both toggle');
  assert.ok(!/setKidsMusicStyle\(val\)\}/.test(SONGS_PAGE), 'a picker still only selects');
  // Nothing picked → pop (see kidsRequestGenres in kidsGenres.test.mjs).
  assert.match(SONGS_PAGE, /genres: kidsRequestGenres\(selGenres, KIDS_MUSIC_GENRES\[kidsMusicStyle\]\)/);
});
