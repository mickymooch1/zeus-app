// Google Ads conversion tracking behind explicit cookie consent (UK PECR /
// Google Consent Mode v2).
//
// "Basic" Consent Mode, deliberately: the Consent Mode defaults (everything
// 'denied') are pushed on every page load, but gtag.js itself is not requested
// at all until the visitor clicks Accept — so a visitor who rejects, or never
// chooses, sends nothing to Google. The trade-off is that Google can't model
// conversions from people who didn't accept; that's the price of not touching
// their device without consent.
//
// The only thing measured is the "Sign-up" conversion, fired once per new
// account from RegisterPage after the backend has created it. The user id is
// the transaction_id, so Google Ads also drops any duplicate it does receive.
export const GOOGLE_ADS_ID = 'AW-18517714190';
export const SIGNUP_CONVERSION_LABEL = 'o7SdCLShsZ8dEI7K9_1E';

// { ads: 'granted' | 'denied', v: 1, ts } — the visitor's choice. The old
// 'zeus_cookie_accepted' flag came from an "OK, by using the site you agree"
// banner, which isn't valid consent for advertising cookies, so it is ignored:
// those visitors are simply asked again.
export const CONSENT_STORAGE_KEY = 'zeus_cookie_consent';
export const COOKIE_SETTINGS_EVENT = 'zeus:cookie-settings';
const SENT_KEY_PREFIX = 'zeus_ads_signup_sent_';
const SCRIPT_ID = 'zeus-gtag';

const DENIED = {
  ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
};
// Accept covers measuring sign-ups from our adverts, nothing more: ad cookies
// and sending the conversion. ad_personalization (remarketing / personalised
// ads) and analytics_storage (no analytics product is used) stay denied.
const GRANTED = { ...DENIED, ad_storage: 'granted', ad_user_data: 'granted' };

let blocked = false;

function gtag() {
  // gtag.js only processes real Arguments objects, so this must stay a
  // `function` using `arguments` (not rest params / an array).
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(arguments);
}

export function readConsent() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CONSENT_STORAGE_KEY));
    return parsed?.ads === 'granted' || parsed?.ads === 'denied' ? parsed.ads : null;
  } catch {
    return null;
  }
}

function loadTag() {
  if (blocked || document.getElementById(SCRIPT_ID)) return;
  const s = document.createElement('script');
  s.id = SCRIPT_ID;
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_ID}`;
  document.head.appendChild(s);
  gtag('js', new Date());
  gtag('config', GOOGLE_ADS_ID);
}

// Google Ads' first-party cookies (_gcl_aw, _gcl_au, _gcl_gb, …). Cleared on
// Reject so withdrawing consent actually removes what Accept allowed. They are
// set on the registrable domain, so try each parent domain as well as none.
function clearAdCookies() {
  try {
    const names = document.cookie.split(';').map((c) => c.split('=')[0].trim())
      .filter((n) => n.startsWith('_gcl_'));
    const labels = (window.location?.hostname || '').split('.');
    const domains = [null];
    for (let i = 0; i < labels.length - 1; i += 1) domains.push(`.${labels.slice(i).join('.')}`);
    for (const name of names) {
      for (const d of domains) {
        document.cookie = `${name}=; Max-Age=0; path=/${d ? `; domain=${d}` : ''}`;
      }
    }
  } catch {
    // cookies unavailable — nothing to clear
  }
}

// Call once, before the app renders. `blocked` is true inside the iOS app,
// where Apple's tracking rules apply — the tag never loads there.
export function initConsentMode({ blocked: isBlocked = false } = {}) {
  blocked = isBlocked;
  try {
    gtag('consent', 'default', DENIED);
    if (readConsent() === 'granted' && !blocked) {
      gtag('consent', 'update', GRANTED);
      loadTag();
    }
  } catch {
    // tracking must never break the app
  }
}

export function setConsent(choice) {
  const granted = choice === 'granted';
  try {
    localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify({ ads: granted ? 'granted' : 'denied', v: 1, ts: Date.now() }));
  } catch {
    // storage blocked — the choice still applies for this page view
  }
  try {
    if (granted && !blocked) {
      gtag('consent', 'update', GRANTED);
      loadTag();
    } else if (!granted) {
      gtag('consent', 'update', DENIED);
      clearAdCookies();
    }
  } catch {
    // tracking must never break the app
  }
}

export function openCookieSettings() {
  try {
    window.dispatchEvent(new Event(COOKIE_SETTINGS_EVENT));
  } catch {
    // no window (tests / SSR)
  }
}

// Returns true only when a conversion was actually queued for Google.
export function trackSignupConversion(userId) {
  try {
    if (userId === undefined || userId === null || userId === '') return false;
    if (blocked || readConsent() !== 'granted') return false;
    const sentKey = `${SENT_KEY_PREFIX}${userId}`;
    if (localStorage.getItem(sentKey)) return false;
    loadTag();
    gtag('event', 'conversion', {
      send_to: `${GOOGLE_ADS_ID}/${SIGNUP_CONVERSION_LABEL}`,
      transaction_id: String(userId),
    });
    localStorage.setItem(sentKey, '1');
    return true;
  } catch {
    return false;
  }
}
