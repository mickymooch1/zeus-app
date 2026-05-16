import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';
import { LanguageSelector } from './LanguageSelector';

export function BeatsNavbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <span className="navbar-logo-icon">⚡</span>
          <span className="navbar-logo-text">{BRAND.name}</span>
        </Link>

        <div className="navbar-links">
          <Link to="/#features" className="navbar-link">{t('nav.features')}</Link>
          <Link to="/pricing" className="navbar-link">{t('nav.pricing')}</Link>
          <Link to="/terms" className="navbar-link">{t('nav.terms')}</Link>
        </div>

        <div className="navbar-auth">
          {user ? (
            <>
              <Link to="/songs" className="btn btn-sm btn-ghost">{t('nav.songs')}</Link>
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>
                {t('nav.signOut')}
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-sm btn-ghost">{t('nav.signIn')}</Link>
              <Link to="/register" className="btn btn-sm btn-primary">{t('nav.startFree')}</Link>
            </>
          )}
          <LanguageSelector />
        </div>
      </div>
    </nav>
  );
}
