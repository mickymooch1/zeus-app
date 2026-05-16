import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [tcAccepted, setTcAccepted] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const errors = {};
    if (!name.trim()) errors.name = t('auth.register.errors.name');
    if (!email || !email.includes('@')) errors.email = t('auth.register.errors.email');
    if (password.length < 8) errors.password = t('auth.register.errors.password');
    if (password !== confirmPassword) errors.confirmPassword = t('auth.register.errors.passwordMatch');
    return errors;
  };

  const canSubmit =
    name.trim() && email && password.length >= 8 && password === confirmPassword && tcAccepted;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const errors = validate();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setLoading(true);
    try {
      await register(email, password, name, tcAccepted);
      navigate('/pricing', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" />
        <div className="orb orb-2" />
      </div>

      <div className="auth-card auth-card--wide">
        <div className="auth-logo">
          <span className="auth-logo-icon">⚡</span>
          <span className="auth-logo-text">{BRAND.name}</span>
        </div>

        <h1 className="auth-title">{t('auth.register.title')}</h1>
        <p className="auth-sub">{t('auth.register.subtitle')}</p>

        {error && <div className="form-error form-error--banner">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label" htmlFor="name">{t('auth.register.nameLabel')}</label>
            <input
              id="name"
              type="text"
              className={`form-input${fieldErrors.name ? ' form-input--error' : ''}`}
              placeholder={t('auth.register.namePlaceholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoComplete="name"
            />
            {fieldErrors.name && <span className="form-error">{fieldErrors.name}</span>}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="email">{t('auth.register.emailLabel')}</label>
            <input
              id="email"
              type="email"
              className={`form-input${fieldErrors.email ? ' form-input--error' : ''}`}
              placeholder={t('auth.register.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            {fieldErrors.email && <span className="form-error">{fieldErrors.email}</span>}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">{t('auth.register.passwordLabel')}</label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className={`form-input${fieldErrors.password ? ' form-input--error' : ''}`}
                placeholder={t('auth.register.passwordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                style={{ paddingRight: 40 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                aria-label={showPassword ? t('auth.register.hidePassword') : t('auth.register.showPassword')}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#666', padding: 4, display: 'flex', alignItems: 'center' }}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                )}
              </button>
            </div>
            {fieldErrors.password && <span className="form-error">{fieldErrors.password}</span>}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="confirm-password">{t('auth.register.confirmPasswordLabel')}</label>
            <div style={{ position: 'relative' }}>
              <input
                id="confirm-password"
                type={showConfirmPassword ? 'text' : 'password'}
                className={`form-input${fieldErrors.confirmPassword ? ' form-input--error' : ''}`}
                placeholder={t('auth.register.confirmPasswordPlaceholder')}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                style={{ paddingRight: 40 }}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(v => !v)}
                aria-label={showConfirmPassword ? t('auth.register.hidePassword') : t('auth.register.showPassword')}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#666', padding: 4, display: 'flex', alignItems: 'center' }}
              >
                {showConfirmPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                )}
              </button>
            </div>
            {fieldErrors.confirmPassword && (
              <span className="form-error">{fieldErrors.confirmPassword}</span>
            )}
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={tcAccepted}
              onChange={(e) => setTcAccepted(e.target.checked)}
              className="checkbox-input"
            />
            <span className="checkbox-label">
              {t('auth.register.termsAgree')}{' '}
              <a href="/terms" target="_blank" rel="noopener noreferrer" className="auth-link">
                {t('auth.register.termsLink')}
              </a>{' '}
              {t('auth.register.and')}{' '}
              <a href="/privacy" target="_blank" rel="noopener noreferrer" className="auth-link">
                {t('auth.register.privacyLink')}
              </a>
            </span>
          </label>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={!canSubmit || loading}
          >
            {loading ? <span className="spinner spinner--inline" /> : t('auth.register.submit')}
          </button>
        </form>

        <p className="auth-footer-text">
          {t('auth.register.haveAccount')}{' '}
          <Link to="/login" className="auth-link">{t('auth.register.signIn')}</Link>
        </p>
      </div>
    </div>
  );
}
