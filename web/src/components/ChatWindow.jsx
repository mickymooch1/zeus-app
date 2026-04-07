import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';
import { Toolbar } from './Toolbar';

export function ChatWindow({ messages, streaming, onSend }) {
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const [inputValue, setInputValue] = useState('');
  const [grammarMode, setGrammarMode] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleChipClick = (starter) => {
    setInputValue(starter);
    textareaRef.current?.focus();
  };

  return (
    <main className="chat-window">
      <div className="message-list">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <div className="empty-title">Ask Zeus anything.</div>
            <div className="empty-sub">Websites · Writing · Research · Business</div>
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
      <Toolbar onChipClick={handleChipClick} />
      <InputBar
        onSend={onSend}
        disabled={streaming}
        value={inputValue}
        setValue={setInputValue}
        grammarMode={grammarMode}
        setGrammarMode={setGrammarMode}
        textareaRef={textareaRef}
      />
    </main>
  );
}
