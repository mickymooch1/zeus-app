import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStoryModeEnabled } from '../../hooks/useStoryModeEnabled';
import ComingSoonBadge from '../../components/ComingSoonBadge';
import ComingSoonModal from '../../components/ComingSoonModal';

export default function KidsHomePage() {
  const navigate = useNavigate();
  const { storyModeEnabled } = useStoryModeEnabled();
  const [showStoryComingSoon, setShowStoryComingSoon] = useState(false);

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '24px 20px', gap: 24,
      textAlign: 'center',
    }}>
      <p style={{ fontSize: 'clamp(16px, 3vw, 20px)', color: 'rgba(255,255,255,0.85)', margin: 0, fontWeight: 700 }}>
        What would you like to do today? ✨
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, width: '100%', maxWidth: 320 }}>
        <button
          className="kids-btn kids-btn-primary"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/song')}
        >
          🎵 Make a Song!
        </button>

        <div style={{ position: 'relative', width: '100%' }}>
          <button
            className="kids-btn kids-btn-coral"
            style={{ width: '100%' }}
            onClick={() => storyModeEnabled ? navigate('/kids/story') : setShowStoryComingSoon(true)}
          >
            📖 Hear a Story!
          </button>
          {!storyModeEnabled && <ComingSoonBadge />}
        </div>

        <button
          className="kids-btn kids-btn-mint"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/songs')}
        >
          📚 My Songs
        </button>

        <button
          className="kids-btn kids-btn-primary"
          style={{ width: '100%', background: 'linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%)', boxShadow: '0 4px 18px rgba(167,139,250,0.45)' }}
          onClick={() => navigate('/kids/language')}
        >
          🌍 Learn a Language!
        </button>
      </div>

      {showStoryComingSoon && (
        <ComingSoonModal
          message="Story Mode is coming soon — we're putting the finishing touches on it!"
          onClose={() => setShowStoryComingSoon(false)}
        />
      )}
    </div>
  );
}
