import { useState, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const btn = (color) => ({
  padding: '11px 18px', borderRadius: 10, border: `1.5px solid ${color}`,
  background: `${color}18`, color, fontWeight: 700, fontSize: 14, cursor: 'pointer',
});

export default function SettingsPage() {
  const { user, token, refreshUser } = useAuth();
  const hasCustomVoice = Boolean(user?.custom_voice_id);
  // ElevenLabs recommend 1-2 minutes of clean speech for Instant Voice Cloning,
  // and explicitly warn that beyond ~3 minutes "will yield little improvement".
  const MIN_SECONDS = 30;
  const GOOD_SECONDS = 45;
  const MAX_SECONDS = 150;
  const lengthHint = (secs) => {
    if (secs < MIN_SECONDS) return { text: `Keep going — at least ${MIN_SECONDS}s needed`, colour: '#f87171' };
    if (secs < GOOD_SECONDS) return { text: 'Almost there — aim for a minute', colour: '#fbbf24' };
    if (secs <= MAX_SECONDS) return { text: '✅ Good length — stop whenever you like', colour: '#4ade80' };
    return { text: 'Long enough — extra audio does not help', colour: '#fbbf24' };
  };

  const [consent, setConsent]   = useState(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy]         = useState(false);
  const [status, setStatus]     = useState('');
  const [error, setError]       = useState('');
  const [elapsed, setElapsed]   = useState(0);
  const elapsedRef = useRef(0);   // onstop closes over stale state

  const recorderRef = useRef(null);
  const chunksRef   = useRef([]);
  const timerRef    = useRef(null);

  const upload = async (blob, filename) => {
    setBusy(true); setError(''); setStatus('Uploading and cloning your voice — this can take up to a minute…');
    try {
      const fd = new FormData();
      fd.append('audio', blob, filename);
      fd.append('consent', 'true');
      const res = await fetch(`${BACKEND_URL}/api/voice/clone`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Voice cloning failed');
      setStatus('✅ Your voice is ready! Pick "🎙️ My Voice" as the narrator in Zeus Little Beats.');
      if (refreshUser) await refreshUser();
    } catch (e) {
      setError(e.message || 'Voice cloning failed');
      setStatus('');
    } finally {
      setBusy(false);
    }
  };

  const startRecording = async () => {
    setError('');
    if (!consent) { setError('Please confirm consent first.'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        clearInterval(timerRef.current);
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        if (elapsedRef.current < MIN_SECONDS) {
          setError(`Recording too short (${elapsedRef.current}s) — please record at least ${MIN_SECONDS} seconds, ideally about a minute.`);
          return;
        }
        upload(blob, 'voice.webm');
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true); setElapsed(0); elapsedRef.current = 0;
      timerRef.current = setInterval(() => {
        elapsedRef.current += 1;
        setElapsed(elapsedRef.current);
        // Past the useful ceiling — stop for them rather than wasting their breath.
        if (elapsedRef.current >= MAX_SECONDS) stopRecording();
      }, 1000);
    } catch (e) {
      setError('Could not access the microphone — check your browser permissions.');
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && recording) {
      recorderRef.current.stop();
      setRecording(false);
    }
  };

  const onUpload = (e) => {
    setError('');
    if (!consent) { setError('Please confirm consent first.'); e.target.value = ''; return; }
    const file = e.target.files?.[0];
    if (file) upload(file, file.name || 'voice.mp3');
    e.target.value = '';
  };

  const deleteVoice = async () => {
    setBusy(true); setError(''); setStatus('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/voice/clone`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Could not remove your voice');
      if (refreshUser) await refreshUser();
      setStatus('Your voice has been removed.');
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: '24px 20px', color: '#e2e8f0' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 20 }}>🎙️ Voice</h1>
      <div className="voice-clone-section" style={{ background: '#12121e', border: '1px solid rgba(0,240,255,0.2)', borderRadius: 16, padding: 24 }}>
        <h3 style={{ fontSize: 18, fontWeight: 800, margin: '0 0 6px' }}>🎙️ Clone Your Voice</h3>
        <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 12 }}>
          Record your voice and use it to narrate bedtime stories for your children in Zeus Little Beats.
        </p>
        <p style={{ color: '#94a3b8', fontSize: 13, lineHeight: 1.6, background: 'rgba(251,191,36,0.06)',
                    border: '1px solid rgba(251,191,36,0.25)', borderRadius: 10, padding: '10px 12px',
                    marginBottom: 16 }}>
          <strong style={{ color: '#fbbf24' }}>What to expect:</strong> this creates a voice
          <em> inspired by</em> yours rather than an exact copy. How close it gets varies a lot from
          person to person — strong regional accents and distinctive voices are the hardest to
          capture. A quiet room and a clear, natural reading give it the best chance.
        </p>

        {hasCustomVoice ? (
          <>
            <p style={{ color: '#4ade80', fontWeight: 600 }}>✅ Your voice is ready to use in Zeus Little Beats!</p>
            <button onClick={deleteVoice} disabled={busy} style={{ ...btn('#f87171'), opacity: busy ? 0.5 : 1 }}>Remove my voice</button>
          </>
        ) : (
          <>
            <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, color: '#cbd5e1', marginBottom: 16, cursor: 'pointer' }}>
              <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} style={{ marginTop: 3 }} />
              <span>I confirm this is my own voice and I consent to it being cloned for use in Zeus Beats.</span>
            </label>
            {recording ? (
              <>
                <button onClick={stopRecording} style={btn('#f87171')}>⏹ Stop recording ({mmss(elapsed)})</button>
                <p style={{ fontSize: 13, fontWeight: 600, color: lengthHint(elapsed).colour, margin: '10px 0 0' }}>
                  {lengthHint(elapsed).text}
                </p>
                <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden', marginTop: 8 }}>
                  <div style={{ height: '100%', width: `${Math.min(100, (elapsed / GOOD_SECONDS) * 100)}%`,
                                background: lengthHint(elapsed).colour, transition: 'width 0.3s, background 0.3s' }} />
                </div>
              </>
            ) : (
              <>
                <button onClick={startRecording} disabled={busy || !consent} style={{ ...btn('#00f0ff'), opacity: (!consent || busy) ? 0.5 : 1 }}>
                  🎙️ Record my voice (about a minute)
                </button>
                <ul style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.7, margin: '12px 0 0', paddingLeft: 18 }}>
                  <li>Find somewhere quiet — no music, TV or background chatter</li>
                  <li>Read naturally for <strong>about a minute</strong>, as if telling a story</li>
                  <li>Keep a steady distance from the mic and an even tone</li>
                  <li>Longer than two minutes doesn't help — it stops automatically</li>
                </ul>
              </>
            )}
            <p style={{ fontSize: 13, color: '#94a3b8', margin: '12px 0' }}>
              Or <label style={{ color: '#00f0ff', cursor: (busy || !consent) ? 'default' : 'pointer', textDecoration: 'underline' }}>upload an audio file
                <input type="file" accept="audio/*" onChange={onUpload} disabled={busy || !consent} style={{ display: 'none' }} />
              </label>
            </p>
            <p style={{ fontSize: 12, color: '#666' }}>Speak clearly for 1-3 minutes. Read a book, tell a story, or just talk naturally.</p>
          </>
        )}

        {status && <p style={{ marginTop: 14, color: '#00f0ff', fontSize: 13 }}>{status}</p>}
        {error && <p style={{ marginTop: 14, color: '#f87171', fontSize: 13 }}>{error}</p>}
      </div>
    </div>
  );
}
