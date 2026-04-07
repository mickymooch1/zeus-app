import { useState } from 'react';

export function InputBar({ onSend, disabled, value, setValue, grammarMode, setGrammarMode, textareaRef }) {
  // If value/setValue not provided, manage state locally (backwards compat)
  const [localValue, setLocalValue] = useState('');
  const inputValue = value !== undefined ? value : localValue;
  const setInputValue = setValue !== undefined ? setValue : setLocalValue;

  const [localGrammarMode, setLocalGrammarMode] = useState(false);
  const activeGrammarMode = grammarMode !== undefined ? grammarMode : localGrammarMode;
  const setActiveGrammarMode = setGrammarMode !== undefined ? setGrammarMode : setLocalGrammarMode;

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text || disabled) return;
    const prompt = activeGrammarMode
      ? `Please proofread and correct the following text. Return the corrected version with a brief list of changes made:\n\n${text}`
      : text;
    onSend(prompt);
    setInputValue('');
    setActiveGrammarMode(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-bar">
      <textarea
        ref={textareaRef}
        className="input-field"
        value={inputValue}
        onChange={e => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={activeGrammarMode ? 'Paste your text here for proofreading...' : 'Ask Zeus anything...'}
        rows={1}
        disabled={disabled}
      />
      <button
        className={`grammar-btn${activeGrammarMode ? ' grammar-btn--active' : ''}`}
        onClick={() => setActiveGrammarMode(g => !g)}
        disabled={disabled}
        type="button"
        title="Grammar check mode"
        aria-pressed={activeGrammarMode}
      >
        GC
      </button>
      <button
        className="send-btn"
        onClick={handleSend}
        disabled={disabled || !inputValue.trim()}
        aria-label="Send"
      >
        ⚡
      </button>
    </div>
  );
}
