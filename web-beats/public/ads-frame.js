// Runs inside the hidden /ads-frame.html frame that src/utils/adsConsent.js
// creates for ONE consented sign-up, then removes. Google's tag lives only in
// this otherwise empty frame, so it can't see the app's pages, navigation or
// forms — it sends the sign-up conversion and nothing else.
//
// - Only runs when framed by a zeusbeats.com page (opened directly, or framed by
//   another site, it does nothing).
// - The ad click ids (gclid / gbraid / wbraid) are in this frame's query string,
//   where Google's tag reads them; the transaction id (the new user's id) is in
//   the #fragment.
// - Consent Mode v2: everything denied by default, then only ad_storage and
//   ad_user_data granted — the frame only exists because the visitor accepted.
// - No gtag('config'): it would add page_view pings.
// - Tells the parent 'handed-off' when the tag's event_callback fires (the tag
//   took the event; a browser can't see whether Google's server accepted it),
//   or 'failed' if gtag.js can't load.
(function () {
  var ADS_ID = 'AW-18517714190';
  var LABEL = 'o7SdCLShsZ8dEI7K9_1E';
  var tid = null;

  function sameOriginParent() {
    try {
      return window.parent !== window && window.parent.location.origin === window.location.origin;
    } catch {
      return false; // cross-origin parent
    }
  }

  function tell(status) {
    try {
      window.parent.postMessage({ type: 'zeus-ads-frame', tid: tid, status: status }, window.location.origin);
    } catch { /* parent gone */ }
  }

  if (!sameOriginParent()) return;
  try {
    tid = new URLSearchParams(window.location.hash.slice(1)).get('tid');
  } catch { tid = null; }
  if (!tid) { tell('failed'); return; }

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  gtag('consent', 'default', {
    ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
  });
  gtag('consent', 'update', {
    ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'denied', analytics_storage: 'denied',
  });
  gtag('js', new Date());

  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ADS_ID;
  s.onerror = function () { tell('failed'); };
  s.onload = function () {
    gtag('event', 'conversion', {
      send_to: ADS_ID + '/' + LABEL,
      transaction_id: tid,
      event_callback: function () { tell('handed-off'); },
    });
  };
  document.head.appendChild(s);
}());
