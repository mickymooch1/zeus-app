export function MessageBubble({ message, isStreaming }) {
  if (message.role === 'user') {
    return (
      <div className="message-user">
        <div className="bubble-user">{message.text}</div>
      </div>
    );
  }

  const showCursor = isStreaming && !message.error;

  return (
    <div className="message-zeus">
      <div className="zeus-avatar">⚡</div>
      <div className="bubble-zeus">
        <div className="zeus-label">ZEUS</div>

        {(message.text || showCursor) && (
          <div className="zeus-text">
            {message.text}
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

        {message.error && (
          <div className="error-banner">{message.error}</div>
        )}
      </div>
    </div>
  );
}
