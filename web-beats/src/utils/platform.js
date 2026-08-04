// Which client is this — 'web' | 'android' | 'ios'.
//
// The server cannot work this out on its own: an Android TWA is backed by
// Chrome and sends an ordinary Chrome User-Agent, indistinguishable from the
// mobile site. Both reliable signals are client-side:
//
//   android — document.referrer starts with "android-app://", the documented
//             way a Trusted Web Activity identifies itself. It is only present
//             on the FIRST document load, so the result is cached in
//             sessionStorage before SPA navigation throws it away.
//   ios     — the ?platform=ios-app param the native shell appends, or
//             window.webkit.messageHandlers which only exists inside WKWebView.
//             Same logic as hooks/useIsIOSWebView.js.
//
// Used for attribution only — never for gating features or content.

const KEY = 'zeus_platform';

function detect() {
  try {
    const cached = sessionStorage.getItem(KEY);
    if (cached) return cached;

    let result = 'web';
    if ((document.referrer || '').startsWith('android-app://')) {
      result = 'android';
    } else if (
      new URLSearchParams(window.location.search).get('platform') === 'ios-app' ||
      !!(window.webkit && window.webkit.messageHandlers)
    ) {
      result = 'ios';
    }

    sessionStorage.setItem(KEY, result);
    return result;
  } catch {
    return 'web';
  }
}

// Evaluated once at module load, while document.referrer is still meaningful.
export const PLATFORM = detect();
