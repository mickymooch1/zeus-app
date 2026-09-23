/**
 * UTM attribution — first-touch capture, surviving signup/login/email-
 * verification the same way utils/remixIntent.js does (localStorage; see that
 * file for the fuller "why localStorage, not sessionStorage" reasoning, which
 * applies here too).
 *
 * "First-touch wins" is the whole point of this file: captureUtmFromUrl must
 * NEVER overwrite an attribution that's already stored, no matter how many
 * more marketing links the visitor clicks before they convert.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

function installFakeLocalStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
}

beforeEach(() => {
  installFakeLocalStorage();
});

const { captureUtmFromUrl, readUtmAttribution } = await import('./utmAttribution.js');

test('captures all three params from a query string', () => {
  captureUtmFromUrl('?utm_source=instagram&utm_medium=social&utm_campaign=launch');
  assert.deepEqual(readUtmAttribution(), {
    utm_source: 'instagram', utm_medium: 'social', utm_campaign: 'launch',
  });
});

test('a query string with none of the three params captures nothing', () => {
  captureUtmFromUrl('?ref=someone');
  assert.equal(readUtmAttribution(), null);
});

test('a partial set of params still captures — missing ones are null', () => {
  captureUtmFromUrl('?utm_source=tiktok');
  assert.deepEqual(readUtmAttribution(), {
    utm_source: 'tiktok', utm_medium: null, utm_campaign: null,
  });
});

test('first touch wins: a second, different capture does not overwrite the first', () => {
  captureUtmFromUrl('?utm_source=instagram&utm_medium=social&utm_campaign=launch');
  captureUtmFromUrl('?utm_source=facebook&utm_medium=cpc&utm_campaign=retarget');
  assert.deepEqual(readUtmAttribution(), {
    utm_source: 'instagram', utm_medium: 'social', utm_campaign: 'launch',
  });
});

test('a later visit with no utm params at all does not clear the first touch', () => {
  captureUtmFromUrl('?utm_source=instagram&utm_medium=social&utm_campaign=launch');
  captureUtmFromUrl('');
  assert.deepEqual(readUtmAttribution(), {
    utm_source: 'instagram', utm_medium: 'social', utm_campaign: 'launch',
  });
});

test('nothing captured yet reads as null', () => {
  assert.equal(readUtmAttribution(), null);
});

test('an attribution older than the TTL is treated as absent', () => {
  const OLD = Date.now() - (31 * 24 * 60 * 60 * 1000); // 31 days ago
  localStorage.setItem('zeus_utm_attribution', JSON.stringify({
    utm_source: 'instagram', utm_medium: 'social', utm_campaign: 'launch', ts: OLD,
  }));
  assert.equal(readUtmAttribution(), null);
});

test('an expired attribution can be captured over — first touch resets once stale', () => {
  const OLD = Date.now() - (31 * 24 * 60 * 60 * 1000);
  localStorage.setItem('zeus_utm_attribution', JSON.stringify({
    utm_source: 'old', utm_medium: 'old', utm_campaign: 'old', ts: OLD,
  }));
  captureUtmFromUrl('?utm_source=fresh&utm_medium=fresh&utm_campaign=fresh');
  assert.deepEqual(readUtmAttribution(), {
    utm_source: 'fresh', utm_medium: 'fresh', utm_campaign: 'fresh',
  });
});

test('malformed JSON already in storage is treated as absent, not thrown', () => {
  localStorage.setItem('zeus_utm_attribution', '{not json');
  assert.equal(readUtmAttribution(), null);
});

test('localStorage throwing (private browsing) never throws out of capture/read', () => {
  globalThis.localStorage = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
    removeItem() { throw new Error('blocked'); },
  };
  assert.doesNotThrow(() => captureUtmFromUrl('?utm_source=x'));
  assert.equal(readUtmAttribution(), null);
});

test('overlong values are capped, matching the backend Field(max_length=200)', () => {
  captureUtmFromUrl(`?utm_source=${'x'.repeat(500)}`);
  assert.equal(readUtmAttribution().utm_source.length, 200);
});
