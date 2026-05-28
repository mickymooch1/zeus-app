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
  const ref = useRef(null);

  const langCode = i18n.language?.slice(0, 2);
  const current = LANGUAGES.find((l) => l.code === langCode) || LANGUAGES[0];

  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

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

      {open && (
        <div className="lang-dropdown" style={{
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
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => select(lang.code)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '8px 12px',
                background: lang.code === current.code ? 'rgba(255,255,255,0.06)' : 'none',
                border: 'none',
                color: lang.code === current.code ? '#e2e8f0' : '#94a3b8',
                cursor: 'pointer',
                fontSize: '0.85rem',
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
