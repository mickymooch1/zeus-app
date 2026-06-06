import { useNavigate } from 'react-router-dom';

export default function KidsHomePage() {
  const navigate = useNavigate();

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '24px 20px', gap: 24,
      textAlign: 'center',
    }}>
      <p style={{ fontSize: 'clamp(16px, 3vw, 20px)', color: '#64748b', margin: 0, fontWeight: 600 }}>
        What would you like to make today? ✨
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, width: '100%', maxWidth: 320 }}>
        <button
          className="kids-btn kids-btn-primary"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/song')}
        >
          🎵 Make a Song!
        </button>

        <button
          className="kids-btn kids-btn-coral"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/story')}
        >
          📖 Hear a Story!
        </button>
      </div>

      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 0 }}>
        {['🌟','⭐','✨','🎵','🎶','💛','🌈'].map((e, i) => (
          <span key={i} style={{
            position: 'absolute',
            fontSize: `${14 + (i * 4) % 18}px`,
            left: `${(i * 13 + 5) % 90}%`,
            top: `${(i * 17 + 10) % 80}%`,
            opacity: 0.25,
            animation: `ziggyBounce ${2 + i * 0.4}s ease-in-out infinite`,
            animationDelay: `${i * 0.3}s`,
          }}>{e}</span>
        ))}
      </div>
    </div>
  );
}
