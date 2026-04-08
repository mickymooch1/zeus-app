import ReactMarkdown from 'react-markdown';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const DOWNLOAD_URL_RE = /https?:\/\/\S+\/download\/[^\s)]+\.zip/gi;

function linkRenderer({ href, children }) {
  const isDownload = href && /\/download\/.+\.zip$/i.test(href);
  const filename = isDownload
    ? href.split('/').pop().replace(/^[0-9a-f]{8}_/, '')
    : null;
  if (isDownload) {
    return (
      <a
        href={href}
        download={filename}
        target="_blank"
        rel="noopener noreferrer"
        className="download-btn"
      >
        ⬇ {children || `Download ${filename}`}
      </a>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

async function handleExport(message, format) {
  try {
    const res = await fetch(`${BACKEND_URL}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: message.text,
        format,
        title: message.exportReady.title,
        doc_type: message.exportReady.doc_type,
      }),
    });
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = message.exportReady.title + (format === 'pdf' ? '.pdf' : '.docx');
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert('Export failed — please try again.');
  }
}

export function MessageBubble({ message, isStreaming }) {
  if (message.role === 'user') {
    return (
      <div className="message-user">
        <div className="bubble-user">
          {message.imagePreview && (
            <img
              src={message.imagePreview}
              alt="Attached image"
              className="bubble-user-image"
            />
          )}
          {message.text && <span>{message.text}</span>}
        </div>
      </div>
    );
  }

  const showCursor = isStreaming && !message.error;
  const wc = message.text ? wordCount(message.text) : 0;

  return (
    <div className="message-zeus">
      <div className="zeus-avatar">⚡</div>
      <div className="bubble-zeus">
        <div className="zeus-label">ZEUS</div>

        {(message.text || showCursor) && (
          <div className="zeus-text">
            <ReactMarkdown
              components={{ a: linkRenderer }}
            >
              {message.text || ''}
            </ReactMarkdown>
            {showCursor && <span className="cursor">▍</span>}
          </div>
        )}

        {!isStreaming && wc >= 50 && (
          <div className="word-count">~{wc} words</div>
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

        {message.exportReady && (
          <div className="export-bar">
            <span className="export-label">Export as:</span>
            <button
              className="export-btn"
              onClick={() => handleExport(message, 'pdf')}
              type="button"
            >
              ⬇ PDF
            </button>
            <button
              className="export-btn"
              onClick={() => handleExport(message, 'docx')}
              type="button"
            >
              ⬇ Word
            </button>
          </div>
        )}

        {message.error && (
          <div className="error-banner">{message.error}</div>
        )}
      </div>
    </div>
  );
}
