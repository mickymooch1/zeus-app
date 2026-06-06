import { useLocation, useNavigate } from 'react-router-dom';
import '../kids.css';
import KidsSpaceBackground from './KidsSpaceBackground';

const NAV = [
  { path: '/kids',       icon: '🏠', label: 'Home'    },
  { path: '/kids/song',  icon: '🎵', label: 'Song'    },
  { path: '/kids/story', icon: '📖', label: 'Story'   },
  { path: '/kids/songs', icon: '📚', label: 'Library' },
];

function Ziggy({ size = 56 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg" className="ziggy-bounce">
      <circle cx="28" cy="18" r="13" fill="#FBD155" stroke="#F59E0B" strokeWidth="2"/>
      <circle cx="23" cy="16" r="2.5" fill="#1A2B4A"/>
      <circle cx="33" cy="16" r="2.5" fill="#1A2B4A"/>
      <path d="M22 22 Q28 27 34 22" stroke="#1A2B4A" strokeWidth="2" strokeLinecap="round" fill="none"/>
      <path d="M28 31 L20 42 L27 42 L23 54 L36 39 L29 39 L34 31 Z" fill="#FBD155" stroke="#F59E0B" strokeWidth="1.5" strokeLinejoin="round"/>
      <circle cx="10" cy="12" r="2" fill="#FF6B9D" opacity="0.8"/>
      <circle cx="46" cy="20" r="1.5" fill="#4ECDC4" opacity="0.8"/>
      <circle cx="8" cy="30" r="1.5" fill="#A78BFA" opacity="0.7"/>
      <circle cx="48" cy="8" r="2" fill="#FBD155" opacity="0.8"/>
    </svg>
  );
}

export default function KidsShell({ children, showExitBtn = false, onExitClick }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div className="kids-shell" style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      <KidsSpaceBackground />

      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px 20px', gap: 12, position: 'relative', zIndex: 1,
      }}>
        <Ziggy size={48} />
        <h1 style={{ margin: 0, fontSize: 'clamp(22px, 5vw, 32px)', fontWeight: 900, lineHeight: 1 }}>
          <span className="kids-rainbow-text">Zeus Kids Beats</span>
          <span style={{ marginLeft: 8 }}>⚡</span>
        </h1>
        {showExitBtn && (
          <button
            onClick={onExitClick}
            style={{
              position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)',
              background: 'rgba(255,255,255,0.7)', border: '2px solid #45b7d1',
              borderRadius: 20, padding: '6px 14px', fontSize: 12, fontWeight: 700,
              color: '#45b7d1', cursor: 'pointer',
            }}
          >
            🔑 Parent Exit
          </button>
        )}
      </header>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>
        {children}
      </main>

      {/* Persistent bottom nav — always reachable, StoryPlayer (z-index:200) slides over it */}
      <nav style={{
        position: 'relative', zIndex: 1, flexShrink: 0,
        display: 'flex', justifyContent: 'space-around', alignItems: 'center',
        padding: '8px 0 max(10px, env(safe-area-inset-bottom))',
        background: 'rgba(255,255,255,0.07)',
        backdropFilter: 'blur(16px)',
        borderTop: '1px solid rgba(255,255,255,0.12)',
      }}>
        {NAV.map(({ path, icon, label }) => {
          const active = location.pathname === path;
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: 3, background: 'none', border: 'none', cursor: 'pointer',
                padding: '4px 18px', borderRadius: 12,
                fontFamily: 'Nunito, ui-rounded, system-ui, sans-serif',
                transition: 'opacity 0.15s, transform 0.15s',
                opacity: active ? 1 : 0.55,
                transform: active ? 'scale(1.12)' : 'scale(1)',
              }}
            >
              <span style={{ fontSize: 22, lineHeight: 1 }}>{icon}</span>
              <span style={{
                fontSize: 10, fontWeight: 800,
                color: active ? '#fbd155' : 'rgba(255,255,255,0.9)',
                letterSpacing: '0.3px',
              }}>
                {label}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
