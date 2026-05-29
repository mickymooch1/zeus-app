// Detects when the web app is running inside the Zeus Beats iOS WKWebView.
//
// Primary signal: ?platform=ios-app query param injected by the native app
// on every URL it loads. Persisted to sessionStorage so SPA navigation
// (which strips query params) doesn't lose the signal mid-session.
//
// Fallback signal: window.webkit?.messageHandlers is only defined inside
// WKWebView — undefined in Mobile Safari and all desktop browsers.

function detect() {
  try {
    const cached = sessionStorage.getItem('zeus_ios_webview');
    if (cached !== null) return cached === '1';

    const fromParam = new URLSearchParams(window.location.search).get('platform') === 'ios-app';
    const fromWebkit = !!(window.webkit?.messageHandlers);
    const result = fromParam || fromWebkit;

    sessionStorage.setItem('zeus_ios_webview', result ? '1' : '0');
    return result;
  } catch {
    return false;
  }
}

// Evaluated once at module load time — no re-renders needed.
export const isIOSWebView = detect();
