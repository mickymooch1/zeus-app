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

  const [consent, setConsent]   = useState(false);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy]         = useState(false);
  const [status, setStatus]     = useState('');
  const [error, setError]       = useState('');
  const [elapsed, setElapsed]   = useState(0);

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
        if (blob.size < 20000) { setError('Recording too short — please record 1-3 minutes.'); return; }
        upload(blob, 'voice.webm');
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true); setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
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
      <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 20 }}>⚙️ Settings</h1>
      <div className="voice-clone-section" style={{ background: '#12121e', border: '1px solid rgba(0,240,255,0.2)', borderRadius: 16, padding: 24 }}>
        <h3 style={{ fontSize: 18, fontWeight: 800, margin: '0 0 6px' }}>🎙️ Clone Your Voice</h3>
        <p style={{ color: '#94a3b8', fontSize: 14, marginBottom: 16 }}>
          Record your voice and use it to narrate bedtime stories for your children in Zeus Little Beats.
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
              <button onClick={stopRecording} style={btn('#f87171')}>⏹ Stop recording ({mmss(elapsed)})</button>
            ) : (
              <button onClick={startRecording} disabled={busy || !consent} style={{ ...btn('#00f0ff'), opacity: (!consent || busy) ? 0.5 : 1 }}>
                🎙️ Record my voice (1-3 minutes)
              </button>
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
