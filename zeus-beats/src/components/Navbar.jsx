import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/');
    setMenuOpen(false);
  };

  return (
    <nav className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <span className="navbar-logo-icon">♪</span>
          <span className="navbar-logo-text">Zeus Beats</span>
        </Link>

        <div className="navbar-links">
          {!user && <a href="/#features" className="navbar-link">Features</a>}
          <Link to="/pricing" className="navbar-link">Pricing</Link>
        </div>

        <div className="navbar-auth">
          {user ? (
            <>
              <Link to="/songs" className="btn btn-sm btn-ghost">Songs</Link>
              <Link to="/settings" className="btn btn-sm btn-ghost">Settings</Link>
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>Sign out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-sm btn-ghost">Login</Link>
              <Link to="/register" className="btn btn-sm btn-primary">Get Started</Link>
            </>
          )}
        </div>

        <button className="navbar-hamburger" onClick={() => setMenuOpen(true)} aria-label="Open menu">☰</button>
      </div>

      <div className={`navbar-mobile-menu${menuOpen ? ' open' : ''}`}>
        <button className="mobile-close" onClick={() => setMenuOpen(false)}>✕</button>
        {!user && <a href="/#features" className="mobile-menu-link" onClick={() => setMenuOpen(false)}>Features</a>}
        <Link to="/pricing" className="mobile-menu-link" onClick={() => setMenuOpen(false)}>Pricing</Link>
        {user ? (
          <>
            <Link to="/songs" className="mobile-menu-link" onClick={() => setMenuOpen(false)}>Songs</Link>
            <Link to="/settings" className="mobile-menu-link" onClick={() => setMenuOpen(false)}>Settings</Link>
            <button className="btn btn-outline" onClick={handleLogout}>Sign out</button>
          </>
        ) : (
          <>
            <Link to="/login" className="mobile-menu-link" onClick={() => setMenuOpen(false)}>Login</Link>
            <Link to="/register" className="btn btn-primary" onClick={() => setMenuOpen(false)}>Get Started Free</Link>
          </>
        )}
      </div>
    </nav>
  );
}
