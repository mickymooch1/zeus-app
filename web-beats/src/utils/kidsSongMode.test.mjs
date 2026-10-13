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
