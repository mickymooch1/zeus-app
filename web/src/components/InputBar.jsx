import { useRef, useState } from 'react';

export function InputBar({ onSend, disabled, value, setValue, grammarMode, setGrammarMode, textareaRef }) {
  // If value/setValue not provided, manage state locally (backwards compat)
  const [localValue, setLocalValue] = useState('');
  const inputValue = value !== undefined ? value : localValue;
  const setInputValue = setValue !== undefined ? setValue : setLocalValue;

  const [localGrammarMode, setLocalGrammarMode] = useState(false);
  const activeGrammarMode = grammarMode !== undefined ? grammarMode : localGrammarMode;
  const setActiveGrammarMode = setGrammarMode !== undefined ? setGrammarMode : setLocalGrammarMode;

  const [imageAttachment, setImageAttachment] = useState(null); // { data, media_type, preview }
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const mediaType = file.type; // e.g. 'image/jpeg'
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target.result; // data:<type>;base64,<data>
      const base64 = dataUrl.split(',')[1];
      setImageAttachment({ data: base64, media_type: mediaType, preview: dataUrl });
    };
    reader.readAsDataURL(file);
    // Reset so the same file can be re-selected after removal
    e.target.value = '';
  };

  const removeImage = () => setImageAttachment(null);

  const handleSend = () => {
    const text = inputValue.trim();
    if ((!text && !imageAttachment) || disabled) return;
    const prompt = activeGrammarMode && text
      ? `Please proofread and correct the following text. Return the corrected version with a brief list of changes made:\n\n${text}`
      : text;
    onSend(prompt, imageAttachment ?? null);
    setInputValue('');
    setImageAttachment(null);
    setActiveGrammarMode(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-bar-wrap">
      {imageAttachment && (
        <div className="image-preview-row">
          <div className="image-preview-thumb">
            <img src={imageAttachment.preview} alt="Attachment preview" />
            <button className="image-preview-remove" onClick={removeImage} type="button" aria-label="Remove image">×</button>
          </div>
        </div>
      )}
      <div className="input-bar">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          className="attach-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          type="button"
          title="Attach image"
          aria-label="Attach image"
        >
          📎
        </button>
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
          disabled={disabled || (!inputValue.trim() && !imageAttachment)}
          aria-label="Send"
        >
          ⚡
        </button>
      </div>
    </div>
  );
}
