import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

const LANGUAGES = [
  { code: 'en', label: 'English',    flag: '🇬🇧' },
  { code: 'fr', label: 'Français',   flag: '🇫🇷' },
  { code: 'es', label: 'Español',    flag: '🇪🇸' },
  { code: 'de', label: 'Deutsch',    flag: '🇩🇪' },
  { code: 'pt', label: 'Português',  flag: '🇧🇷' },
];

export function LanguageSelector() {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [isNarrow, setIsNarrow] = useState(
    typeof window !== 'undefined' && window.innerWidth <= 360
  );
  const ref = useRef(null);

  const langCode = i18n.language?.slice(0, 2);
  const current = LANGUAGES.find((l) => l.code === langCode) || LANGUAGES[0];

  useEffect(() => {
    const check = () => setIsNarrow(window.innerWidth <= 360);
    window.addEventListener('resize', check, { passive: true });
    return () => window.removeEventListener('resize', check);
  }, []);

  useEffect(() => {
    if (isNarrow) return; // bottom-sheet closes via overlay click
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [isNarrow]);

  const select = (code) => { i18n.changeLanguage(code); setOpen(false); };

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Select language"
        style={{
          background: 'none',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 6,
          color: '#94a3b8',
          cursor: 'pointer',
          padding: '4px 8px',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          fontSize: '0.8rem',
          lineHeight: 1,
        }}
      >
        🌐 {current.flag}
      </button>

      {open && isNarrow && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.55)',
            zIndex: 9998,
          }}
        />
      )}

      {open && (
        <div style={isNarrow ? {
          position: 'fixed',
          left: 0, right: 0, bottom: 0, top: 'auto',
          width: '100%',
          maxHeight: '60vh',
          overflowY: 'auto',
          background: '#12121e',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: '16px 16px 0 0',
          zIndex: 9999,
          boxShadow: '0 -8px 40px rgba(0,0,0,0.7)',
        } : {
          position: 'absolute',
          top: 'calc(100% + 6px)',
          right: 0,
          background: '#12121e',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 8,
          overflow: 'hidden',
          zIndex: 999,
          minWidth: 140,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        }}>
          {isNarrow && (
            <div style={{
              padding: '12px 16px 8px',
              fontSize: 12,
              fontWeight: 700,
              color: '#475569',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              Language
            </div>
          )}
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => select(lang.code)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: isNarrow ? '14px 20px' : '8px 12px',
                background: lang.code === current.code ? 'rgba(255,255,255,0.06)' : 'none',
                border: 'none',
                borderBottom: isNarrow ? '1px solid rgba(255,255,255,0.04)' : 'none',
                color: lang.code === current.code ? '#e2e8f0' : '#94a3b8',
                cursor: 'pointer',
                fontSize: isNarrow ? '1rem' : '0.85rem',
                textAlign: 'left',
              }}
            >
              <span>{lang.flag}</span>
              <span>{lang.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
