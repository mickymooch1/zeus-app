import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Lyric Workshop — conversational lyric writing, before generation.
 *
 * Users were leaving to write lyrics elsewhere and pasting the result into
 * "Write my own". This keeps that loop inside the app.
 *
 * State lives here and in the parent's `customLyricsText` — the backend is
 * stateless, so the transcript below IS the conversation. Nothing is persisted;
 * closing the tab is how you discard a draft.
 */
export default function LyricWorkshop({ onUseLyrics, backendUrl, token }) {
  const { t } = useTranslation();
  const [input, setInput]       = useState('');
  const [messages, setMessages] = useState([]);   // {role, content} — sent verbatim
  const [lyrics, setLyrics]     = useState('');
  const [title, setTitle]       = useState('');
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState('');
  const threadRef = useRef(null);

  // Follow the conversation as it grows. Guarded on length so editing the lyrics
  // textarea doesn't yank the thread around under the user.
  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages.length]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;

    // Optimistic: the user's line appears immediately, and it is also what we send.
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setBusy(true);
    setError('');

    try {
      // Token comes from useAuth() via the parent, as everywhere else on this page.
      // Reading localStorage directly here would look right and silently fail: the
      // key is 'zeus_token', so getItem('token') is null and every request 401s.
      const r = await fetch(`${backendUrl}/api/lyrics/workshop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ messages: next, current_lyrics: lyrics || null }),
      });

      if (!r.ok) {
        let detail = '';
        try {
          const j = await r.json();
          detail = typeof j.detail === 'string' ? j.detail : (j.detail?.message || '');
        } catch { /* non-JSON error body */ }
        throw new Error(detail || t('workshop.errorGeneric'));
      }

      const data = await r.json();
      setLyrics(data.lyrics || '');
      if (data.title) setTitle(data.title);
      setMessages([...next, { role: 'assistant', content: data.reply || '' }]);
    } catch (e) {
      // Roll the user's turn back into the box so a failure doesn't eat what they
      // typed — they can retry without re-typing it.
      setMessages(messages);
      setInput(text);
      setError(e.message || t('workshop.errorGeneric'));
    } finally {
      setBusy(false);
    }
  };

  const startOver = () => {
    setMessages([]); setLyrics(''); setTitle(''); setInput(''); setError('');
  };

  const panel = {
    background: 'rgba(255,255,255,0.025)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 12,
    padding: 14,
  };

  return (
    <div>
      <p style={{ color: '#cccccc', fontSize: 14, marginTop: 0, marginBottom: 14 }}>
        {t('workshop.subtitle')}
      </p>

      {/* Conversation — only once there is something to show, so the empty state
          stays uncluttered on a 375px screen. */}
      {messages.length > 0 && (
        <div
          ref={threadRef}
          style={{ ...panel, maxHeight: 200, overflowY: 'auto', marginBottom: 12 }}
        >
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: 8, display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <span style={{
                display: 'inline-block',
                maxWidth: '85%',
                padding: '8px 12px',
                borderRadius: 12,
                background: m.role === 'user' ? '#7c3aed' : 'rgba(255,255,255,0.07)',
                color: '#ffffff',
                fontSize: 14,
                lineHeight: 1.4,
                wordBreak: 'break-word',
              }}>{m.content}</span>
            </div>
          ))}
          {busy && (
            <div style={{ color: 'rgba(255,255,255,0.55)', fontSize: 13, fontStyle: 'italic' }}>
              {t('workshop.writing')}
            </div>
          )}
        </div>
      )}

      {/* Request box */}
      <textarea
        className="songs-textarea"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          // Enter sends; Shift+Enter is a newline. Skipped on mobile, where Enter
          // should insert a newline rather than fire a paid request.
          if (e.key === 'Enter' && !e.shiftKey && window.innerWidth > 640) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={messages.length === 0 ? t('workshop.placeholderFirst') : t('workshop.placeholderFollowUp')}
        rows={3}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 10,
          padding: '12px 14px',
          color: '#ffffff',
          fontSize: 15,
          resize: 'vertical',
          fontFamily: 'inherit',
          outline: 'none',
          marginBottom: 10,
        }}
      />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          style={{
            flex: '1 1 160px',
            minHeight: 44,
            padding: '0 18px',
            borderRadius: 10,
            border: 'none',
            background: busy || !input.trim() ? 'rgba(255,255,255,0.08)' : '#7c3aed',
            color: busy || !input.trim() ? 'rgba(255,255,255,0.4)' : '#ffffff',
            fontSize: 15,
            fontWeight: 600,
            cursor: busy || !input.trim() ? 'not-allowed' : 'pointer',
          }}
        >
          {busy ? t('workshop.writing') : (messages.length === 0 ? t('workshop.write') : t('workshop.update'))}
        </button>
        {(messages.length > 0 || lyrics) && (
          <button
            onClick={startOver}
            disabled={busy}
            style={{
              minHeight: 44,
              padding: '0 18px',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.15)',
              background: 'transparent',
              color: '#ffffff',
              fontSize: 14,
              fontWeight: 600,
              cursor: busy ? 'not-allowed' : 'pointer',
            }}
          >{t('workshop.startOver')}</button>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 10,
          padding: '10px 12px',
          color: '#fca5a5',
          fontSize: 13,
          marginBottom: 12,
        }}>{error}</div>
      )}

      {/* The sheet. Editable, because the fastest fix for one wrong line is to type
          over it rather than describe the change. */}
      {lyrics && (
        <>
          <label style={{ display: 'block', color: '#ffffff', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            {t('workshop.lyricsLabel')}
          </label>
          <textarea
            className="songs-textarea"
            value={lyrics}
            onChange={(e) => setLyrics(e.target.value)}
            rows={12}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 10,
              padding: '12px 14px',
              color: '#ffffff',
              fontSize: 14,
              lineHeight: 1.55,
              resize: 'vertical',
              fontFamily: 'inherit',
              outline: 'none',
              marginBottom: 12,
            }}
          />
          <button
            onClick={() => onUseLyrics(lyrics.trim(), title)}
            disabled={!lyrics.trim()}
            style={{
              width: '100%',
              minHeight: 44,
              borderRadius: 10,
              border: 'none',
              background: 'linear-gradient(135deg,#7c3aed,#00f0ff)',
              color: '#ffffff',
              fontSize: 16,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >{t('workshop.useLyrics')}</button>
        </>
      )}
    </div>
  );
}
