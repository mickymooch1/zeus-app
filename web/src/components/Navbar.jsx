import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
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

  console.log('[Navbar] user object:', user);

  return (
    <nav className={`navbar${scrolled ? ' navbar--scrolled' : ''}`}>
      <div className="navbar-inner">
        <Link to="/" className="navbar-logo">
          <span className="navbar-logo-icon">⚡</span>
          <span className="navbar-logo-text">Zeus</span>
        </Link>

        <div className="navbar-links">
          <Link to="/#features" className="navbar-link">Features</Link>
          <Link to="/pricing" className="navbar-link">Pricing</Link>
          <Link to="/terms" className="navbar-link">Terms</Link>
        </div>

        <div className="navbar-auth">
          {user ? (
            <>
              <Link to="/dashboard" className="btn btn-sm btn-ghost">Dashboard</Link>
              {(user.is_admin || (user.subscription_plan === 'enterprise' && user.subscription_status === 'active')) && (
                <Link to="/tasks" className="btn btn-sm btn-ghost">Tasks</Link>
              )}
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-sm btn-ghost">Login</Link>
              <Link to="/register" className="btn btn-sm btn-primary">Get Started</Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
