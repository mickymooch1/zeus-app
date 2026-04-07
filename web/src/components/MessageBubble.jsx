const DOWNLOAD_RE = /https?:\/\/\S+\/download\/\S+\.zip/gi;

function renderTextWithDownloads(text) {
  if (!text) return null;
  const parts = [];
  let last = 0;
  let match;
  const re = new RegExp(DOWNLOAD_RE.source, 'gi');
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    const url = match[0];
    const filename = url.split('/').pop().split('_').slice(1).join('_') || url.split('/').pop();
    parts.push(
      <a
        key={match.index}
        href={url}
        download={filename}
        target="_blank"
        rel="noopener noreferrer"
        className="download-btn download-btn--inline"
      >
        ⬇ Download {filename}
      </a>
    );
    last = match.index + url.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length > 0 ? parts : text;
}

export function MessageBubble({ message, isStreaming }) {
  if (message.role === 'user') {
    return (
      <div className="message-user">
        <div className="bubble-user">{message.text}</div>
      </div>
    );
  }

  const showCursor = isStreaming && !message.error;
  const textContent = renderTextWithDownloads(message.text);

  return (
    <div className="message-zeus">
      <div className="zeus-avatar">⚡</div>
      <div className="bubble-zeus">
        <div className="zeus-label">ZEUS</div>

        {(message.text || showCursor) && (
          <div className="zeus-text">
            {textContent}
            {showCursor && <span className="cursor">▍</span>}
          </div>
        )}

        {message.tools?.length > 0 && (
          <div className="tool-log">
            {message.tools.map((t, i) => (
              <div key={i} className={`tool-item ${t.status}`}>
                {t.status === 'done' ? '✓' : '⟳'} {t.name}
                {t.path ? `: ${t.path}` : ''}
              </div>
            ))}
          </div>
        )}

        {message.downloads?.length > 0 && (
          <div className="download-list">
            {message.downloads.map((d, i) => (
              <a
                key={i}
                href={d.url}
                download={d.filename}
                target="_blank"
                rel="noopener noreferrer"
                className="download-btn"
              >
                ⬇ Download {d.filename}
              </a>
            ))}
          </div>
        )}

        {message.error && (
          <div className="error-banner">{message.error}</div>
        )}
      </div>
    </div>
  );
}
