import { useState } from 'react';
import { BACKEND_URL } from '../brand';

export default function ParentPINGate({ token, action = 'enter', onSuccess, onCancel }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [shake, setShake] = useState(false);
  const [loading, setLoading] = useState(false);

  const digits = [1,2,3,4,5,6,7,8,9,'',0,'⌫'];

  const handleKey = (k) => {
    if (k === '⌫') {
      setPin(p => p.slice(0, -1));
      setError('');
      return;
    }
    if (k === '') return;
    if (pin.length >= 4) return;
    const next = pin + String(k);
    setPin(next);
    if (next.length === 4) submit(next);
  };

  const submit = async (code) => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/kids/pin/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ pin: code }),
      });
      if (res.ok) {
        onSuccess();
      } else {
        setShake(true);
        setError('Oops! Try again 😊');
        setPin('');
        setTimeout(() => setShake(false), 500);
      }
    } catch {
      setError('Connection error — try again');
      setPin('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(26,43,74,0.55)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16,
    }}>
      <div className="kids-card" style={{
        maxWidth: 360, width: '100%', textAlign: 'center',
        animation: shake ? 'shake 0.4s ease' : 'none',
      }}>
        <style>{`
          @keyframes shake {
            0%,100% { transform: translateX(0); }
            20%,60%  { transform: translateX(-8px); }
            40%,80%  { transform: translateX(8px); }
          }
        `}</style>

        <div style={{ fontSize: 40, marginBottom: 8 }}>🔑</div>
        <h2 style={{ margin: '0 0 4px', fontSize: 20 }}>Parent exit code</h2>
        <p style={{ margin: '0 0 20px', fontSize: 14, color: '#64748b' }}>
          {action === 'exit' ? 'Enter your PIN to return to Zeus Beats' : 'Enter your PIN to open Zeus Baby Beats'}
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginBottom: 24 }}>
          {[0,1,2,3].map(i => (
            <div key={i} className={`kids-pin-dot${pin.length > i ? ' filled' : ''}`} />
          ))}
        </div>

        {error && <p style={{ color: '#ef4444', fontSize: 14, margin: '0 0 12px', fontWeight: 700 }}>{error}</p>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, maxWidth: 260, margin: '0 auto 20px' }}>
          {digits.map((d, i) => (
            <button
              key={i}
              onClick={() => handleKey(d)}
              disabled={loading}
              className="kids-pin-key"
              style={{ opacity: d === '' ? 0 : 1, pointerEvents: d === '' ? 'none' : 'auto' }}
            >
              {d}
            </button>
          ))}
        </div>

        <button onClick={onCancel} className="kids-btn kids-btn-ghost" style={{ minWidth: 120, minHeight: 44, fontSize: 14 }}>
          Cancel
        </button>
      </div>
    </div>
  );
}
