import { useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import { isClipViewerPath, COOKIE_BANNER_H_VAR } from '../utils/clipsChrome';

const STORAGE_KEY = 'zeus_cookie_accepted';

export default function CookieBanner() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [visible, setVisible] = useState(() => !localStorage.getItem(STORAGE_KEY));
  const ref = useRef(null);
  // On the full-screen clip viewers the Remix button and song bar are pinned
  // to the bottom — a first-time visitor must be able to hit Remix without
  // dismissing this first. So: a smaller banner there, and its live height
  // published as a CSS variable those pages add to their bottom offsets.
  const compact = isClipViewerPath(pathname);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const el = ref.current;
    if (!visible || !el) {
      root.style.setProperty(COOKIE_BANNER_H_VAR, '0px');
      return undefined;
    }
    const publish = () => root.style.setProperty(COOKIE_BANNER_H_VAR, `${el.offsetHeight}px`);
    publish();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(publish) : null;
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      root.style.setProperty(COOKIE_BANNER_H_VAR, '0px');
    };
  }, [visible, compact]);

  if (!visible) return null;

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, '1');
    setVisible(false);
  };

  return (
    <div ref={ref} style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 9999,
      background: 'rgba(11, 18, 34, 0.97)',
      borderTop: '1px solid #1f5f8a',
      boxShadow: '0 -8px 32px rgba(22, 200, 255, 0.12)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      fontFamily: "Barlow, 'Segoe UI', system-ui, sans-serif",
      padding: compact ? '8px 12px' : '14px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: compact ? '10px' : '16px',
      flexWrap: compact ? 'nowrap' : 'wrap',
    }}>
      <p style={{
        color: '#c9d6ea', fontSize: compact ? '11px' : '13px', lineHeight: compact ? 1.35 : 1.5,
        flex: 1, minWidth: compact ? 0 : '220px', ...(compact ? { margin: 0 } : {}),
      }}>
        {/* Trans, not t() — the Privacy Policy link sits mid-sentence and languages
            place it differently. The <privacy> tag lets each locale position it. */}
        <Trans
          i18nKey="cookies.message"
          components={{
            privacy: <Link to="/privacy" style={{ color: '#16c8ff', textDecoration: 'underline' }} />,
          }}
        />
      </p>
      <div style={{ display: 'flex', gap: '10px', flexShrink: 0 }}>
        {/* Compact drops "Learn more" — the message already links the policy inline. */}
        {!compact && (
          <Link
            to="/privacy"
            style={{
              padding: '7px 16px',
              borderRadius: '999px',
              fontSize: '13px',
              fontWeight: 600,
              color: '#16c8ff',
              border: '1px solid rgba(22, 200, 255, 0.45)',
              background: 'transparent',
              textDecoration: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {t('cookies.learnMore')}
          </Link>
        )}
        <button
          onClick={accept}
          style={{
            padding: compact ? '6px 14px' : '7px 20px',
            borderRadius: '999px',
            fontSize: compact ? '12px' : '13px',
            fontWeight: 700,
            fontFamily: 'inherit',
            background: '#16c8ff',
            color: '#031018',
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {t('cookies.accept')}
        </button>
      </div>
    </div>
  );
}
