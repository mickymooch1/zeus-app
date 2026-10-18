// Saves the QR greeting card PNG. On phones (incl. the Android app and iOS
// Safari) it opens the native share sheet so the card can go straight to
// Photos or a chat; desktop, or a browser that can't share files, downloads it.
export async function shareOrDownloadCard(blob, filename, {
  preferShare,
  nav = globalThis.navigator,
  doc = globalThis.document,
  url = globalThis.URL,
} = {}) {
  if (preferShare && typeof nav?.share === 'function' && typeof nav?.canShare === 'function') {
    const file = new File([blob], filename, { type: 'image/png' });
    if (nav.canShare({ files: [file] })) {
      try {
        await nav.share({ files: [file] });
        return 'shared';
      } catch (err) {
        if (err?.name === 'AbortError') return 'cancelled';
        // anything else (e.g. lost user activation) — fall through to download
      }
    }
  }
  const href = url.createObjectURL(blob);
  const a = doc.createElement('a');
  a.href = href;
  a.download = filename;
  doc.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => url.revokeObjectURL(href), 1000);
  return 'downloaded';
}
