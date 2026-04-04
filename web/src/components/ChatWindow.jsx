import { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';

export function ChatWindow({ messages, streaming, onSend }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <main className="chat-window">
      <div className="message-list">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <div className="empty-title">Ask Zeus anything.</div>
            <div className="empty-sub">Websites · Research · Emails · Business</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={
              streaming &&
              i === messages.length - 1 &&
              msg.role === 'zeus'
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>
      <InputBar onSend={onSend} disabled={streaming} />
    </main>
  );
}
