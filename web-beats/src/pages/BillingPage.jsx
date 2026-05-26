import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BeatsNavbar } from '../components/BeatsNavbar';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

function UsageBar({ used, limit }) {
  const { t } = useTranslation();
  if (limit === null || limit === undefined) {
    return (
      <div className="usage-bar-wrap">
        <div className="usage-bar">
          <div className="usage-bar-fill usage-bar-fill--unlimited" style={{ width: '100%' }} />
        </div>
        <span className="usage-label">{t('billing.unlimited')}</span>
      </div>
    );
  }
  const pct = Math.min(100, (used / limit) * 100);
  const isNearLimit = pct >= 75;
  return (
    <div className="usage-bar-wrap">
      <div className="usage-bar">
        <div
          className={`usage-bar-fill${isNearLimit ? ' usage-bar-fill--warn' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="usage-label">{t('billing.songsMonth', { used, limit })}</span>
    </div>
  );
}

export default function BillingPage() {
  const { user, token } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();
  const [status, setStatus]           = useState(null);
  const [credits, setCredits]         = useState(null);
  const [loadingPortal, setLoadingPortal]     = useState(false);
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [error, setError]             = useState('');
  const [successMsg, setSuccessMsg]   = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading]         = useState(false);
  const [deleteSuccess, setDeleteSuccess]         = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelLoading, setCancelLoading]         = useState(false);
  const [cancelResult, setCancelResult]           = useState(null);
  const [paygLoading, setPaygLoading]             = useState(null);
  const [cpCurrent, setCpCurrent] = useState('');
  const [cpNew, setCpNew] = useState('');
  const [cpConfirm, setCpConfirm] = useState('');
  const [cpLoading, setCpLoading] = useState(false);
  const [cpError, setCpError] = useState('');
  const [cpSuccess, setCpSuccess] = useState('');
  const [anName, setAnName]       = useState('');
  const [anLoading, setAnLoading] = useState(false);
  const [anError, setAnError]     = useState('');
  const [anSuccess, setAnSuccess] = useState('');
  const [soundPersona, setSoundPersona]     = useState(null);
  const [soundResetLoading, setSoundResetLoading] = useState(false);

  const successParam = new URLSearchParams(location.search).get('success');
  const ytParam      = new URLSearchParams(location.search).get('youtube');

  useEffect(() => {
    if (successParam === 'true') {
      setSuccessMsg('__payment_success__');
    }
  }, [successParam]);

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/billing/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStatus(data); })
      .catch(() => {});

    fetch(`${BACKEND_URL}/api/users/me/song_credits`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) { setCredits(data); setAnName(data.artist_name || ''); } })
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!user) return;
    setSoundPersona(
      user.sound_persona_id
        ? {
            sound_persona_id: user.sound_persona_id,
            sound_persona_title: user.sound_persona_title,
          }
        : null
    );
  }, [user]);

  const handleResetSound = async () => {
    setSoundResetLoading(true);
    try {
      await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setSoundPersona(null);
    } catch (err) {
      console.error('Failed to reset sound:', err);
    } finally {
      setSoundResetLoading(false);
    }
  };

  const handleSaveArtistName = async (e) => {
    e.preventDefault();
    setAnLoading(true);
    setAnError('');
    setAnSuccess('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/users/artist-name`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ artist_name: anName }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Save failed');
      }
      setAnSuccess(t('billing.artistNameSaved'));
    } catch (err) {
      setAnError(err.message);
    } finally {
      setAnLoading(false);
    }
  };

  const handlePortal = async () => {
    setError('');
    setLoadingPortal(true);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/portal`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to open billing portal');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setLoadingPortal(false);
    }
  };

  const handleCheckout = async (plan) => {
    setError('');
    setLoadingCheckout(plan);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create checkout');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setLoadingCheckout(null);
    }
  };

  const handleConnectYouTube = () => {
    window.location.href = `${BACKEND_URL}/api/youtube/auth?token=${token}&origin=beats`;
  };

  const handleDisconnectYouTube = async () => {
    try {
      await fetch(`${BACKEND_URL}/api/youtube/disconnect`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setCredits((prev) => prev ? { ...prev, youtube_connected: false } : prev);
    } catch (_) {}
  };

  const handlePayg = async (pack) => {
    setError('');
    setPaygLoading(pack);
    try {
      const res = await fetch(`${BACKEND_URL}/api/songs/payg`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ pack }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create checkout');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setPaygLoading(null);
    }
  };

  const handleCancel = async () => {
    setCancelLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/subscription/cancel`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Cancellation failed');
      setCancelResult(data);
      setShowCancelConfirm(false);
      setStatus((prev) => prev ? { ...prev, cancel_at: data.cancel_at } : prev);
    } catch (err) {
      setError(err.message);
    } finally {
      setCancelLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setCpError('');
    setCpSuccess('');
    if (cpNew.length < 8) { setCpError('New password must be at least 8 characters'); return; }
    if (cpNew !== cpConfirm) { setCpError('New passwords do not match'); return; }
    setCpLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: cpCurrent, new_password: cpNew }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to change password');
      setCpSuccess('Password changed successfully.');
      setCpCurrent(''); setCpNew(''); setCpConfirm('');
    } catch (err) {
      setCpError(err.message);
    } finally {
      setCpLoading(false);
    }
  };

  const handleDeleteRequest = async () => {
    setDeleteLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/account/delete-request`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setDeleteSuccess(true);
      setShowDeleteConfirm(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const isAdmin       = status?.is_admin === true;
  const isActive      = status?.is_active || isAdmin;
  const effectivePlan = isAdmin ? 'enterprise' : status?.plan;
  const planName      = isAdmin ? 'Enterprise (Admin)' : (status?.plan_name || 'Free');
  const ytConnected   = credits?.youtube_connected || false;
  const songBalance   = credits?.balance ?? 0;
  const songAllowance = credits?.monthly_allowance ?? 0;
  const isMusicPlan   = ['music_starter', 'music_pro', 'music_agency'].includes(effectivePlan);
  const canFacebook   = isAdmin || effectivePlan === 'music_agency';

  const PLAN_FEATURES = {
    music_starter: [t('billing.plans.features.songs15'), t('billing.plans.features.youtube'), t('billing.plans.features.download'), t('billing.plans.features.genres'), t('billing.plans.features.coverArt')],
    music_pro:     [t('billing.plans.features.songs40'), t('billing.plans.features.youtube'), t('billing.plans.features.avatar3'), t('billing.plans.features.download'), t('billing.plans.features.genres'), t('billing.plans.features.coverArt')],
    music_agency:  [t('billing.plans.features.songs80'), t('billing.plans.features.youtube'), t('billing.plans.features.avatar10'), t('billing.plans.features.download'), t('billing.plans.features.genres'), t('billing.plans.features.coverArt'), t('billing.plans.features.facebook')],
    free:          [t('billing.plans.features.songs5'), t('billing.plans.features.download'), t('billing.plans.features.allGenres')],
  };
  const planFeatures = (isMusicPlan && isActive)
    ? PLAN_FEATURES[effectivePlan]
    : PLAN_FEATURES.free;

  return (
    <div className="billing-page">
      <BeatsNavbar />
      <div className="page billing-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-2" />
        </div>

        <h1 className="billing-title">{t('billing.title')}</h1>

        {successMsg && <div className="success-banner">{t('billing.paymentSuccess')}</div>}
        {ytParam === 'connected' && (
          <div className="success-banner">{t('billing.ytSuccess')}</div>
        )}
        {ytParam === 'error' && (
          <div className="form-error form-error--banner">{t('billing.ytError')}</div>
        )}
        {error && <div className="form-error form-error--banner">{error}</div>}

        {/* ── Your Sound ─────────────────────────────────────────────────── */}
        <div className="billing-card" style={{ marginBottom: 20 }}>
          <div className="billing-card-header" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.1rem' }}>🎧</span>
            <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#00f0ff' }}>Your Sound</h2>
          </div>
          {(() => {
            const isPaid =
              user?.is_admin ||
              (user?.subscription_status === 'active' &&
                ['music_starter', 'music_pro', 'music_agency'].includes(user?.subscription_plan));
            if (!isPaid) {
              return (
                <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14, margin: '12px 0 0' }}>
                  Upgrade to Music Starter to lock your sonic DNA — every future song will sound like you.
                </p>
              );
            }
            if (soundPersona) {
              return (
                <div style={{ marginTop: 14 }}>
                  <p style={{ margin: '0 0 14px', fontSize: 14, color: 'rgba(255,255,255,0.75)' }}>
                    🔒 Locked to: <strong style={{ color: '#fff' }}>{soundPersona.sound_persona_title}</strong>
                  </p>
                  <p style={{ margin: '0 0 16px', fontSize: 13, color: 'rgba(255,255,255,0.45)' }}>
                    All future songs will carry your sonic DNA — even across different genres.
                  </p>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <Link
                      to="/songs"
                      style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid rgba(0,240,255,0.4)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 13, fontWeight: 600, textDecoration: 'none', display: 'inline-block' }}
                    >
                      Change Sound
                    </Link>
                    <button
                      onClick={handleResetSound}
                      disabled={soundResetLoading}
                      style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600, cursor: soundResetLoading ? 'default' : 'pointer' }}
                    >
                      {soundResetLoading ? 'Resetting…' : 'Reset'}
                    </button>
                  </div>
                </div>
              );
            }
            return (
              <div style={{ marginTop: 14 }}>
                <p style={{ margin: '0 0 8px', fontSize: 14, color: 'rgba(255,255,255,0.45)' }}>
                  Not set — go to a song you love and click "Lock My Sound" to save your sonic DNA.
                </p>
                <Link
                  to="/songs"
                  style={{ color: '#00f0ff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
                >
                  → Go to My Songs
                </Link>
              </div>
            );
          })()}
        </div>

        {/* Current plan card */}
        <div className="billing-card">
          <div className="billing-card-header">
            <h2 className="billing-card-title">{t('billing.currentPlan')}</h2>
            {effectivePlan === 'music_starter' && <span className="badge-pro">{t('billing.plans.starter')}</span>}
            {effectivePlan === 'music_pro'     && <span className="badge-pro">{t('billing.plans.pro')}</span>}
            {effectivePlan === 'music_agency'  && <span className="badge-agency">{t('billing.plans.agency')}</span>}
            {(!isMusicPlan && !isAdmin) && <span className="badge-free">{t('billing.plans.free')}</span>}
            {isAdmin && <span className="badge-enterprise">Admin</span>}
          </div>

          <div className="billing-plan-name">{planName}</div>

          {credits ? (
            <UsageBar used={songBalance} limit={isAdmin ? null : songAllowance} />
          ) : (
            <div className="spinner" />
          )}

          <div className="billing-actions">
            {isActive && user?.stripe_customer_id ? (
              <button className="btn btn-outline" onClick={handlePortal} disabled={loadingPortal}>
                {loadingPortal ? <span className="spinner spinner--inline" /> : t('billing.manageSubscription')}
              </button>
            ) : null}
            {!isActive && (
              <Link to="/pricing" className="btn btn-primary">{t('billing.upgradePlan')}</Link>
            )}
          </div>

          {/* Cancel subscription */}
          {(() => {
            const cancelAt = cancelResult?.cancel_at || status?.cancel_at;
            const cancelDateDisplay = cancelAt
              ? new Date(cancelAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
              : null;
            if (cancelDateDisplay) {
              return (
                <p style={{ marginTop: 12, fontSize: '0.85rem', color: '#475569' }}>
                  {t('billing.cancelledOn', { date: cancelDateDisplay })}
                </p>
              );
            }
            if (isActive && !isAdmin) {
              return (
                <button
                  style={{ marginTop: 12, background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: '#64748b', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem' }}
                  onClick={() => setShowCancelConfirm(true)}
                >
                  {t('billing.cancelSubscription')}
                </button>
              );
            }
            return null;
          })()}
        </div>

        {/* Upgrade grid — music plans only */}
        {!isActive && (
          <div className="billing-upgrade-section">
            <h2 className="billing-section-title">{t('billing.choosePlan')}</h2>
            <div className="billing-upgrade-grid">
              <div className="billing-upgrade-card">
                <span className="badge-pro">{t('billing.plans.starter')}</span>
                <div className="billing-upgrade-price">{t('billing.plans.starterPrice')}</div>
                <p className="billing-upgrade-desc">{t('billing.plans.starterDesc')}</p>
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingCheckout === 'music_starter'}
                  onClick={() => handleCheckout('music_starter')}
                >
                  {loadingCheckout === 'music_starter' ? <span className="spinner spinner--inline" /> : t('billing.plans.getStarter')}
                </button>
              </div>

              <div className="billing-upgrade-card">
                <span className="badge-pro">{t('billing.plans.pro')}</span>
                <div className="billing-upgrade-price">{t('billing.plans.proPrice')}</div>
                <p className="billing-upgrade-desc">{t('billing.plans.proDesc')}</p>
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingCheckout === 'music_pro'}
                  onClick={() => handleCheckout('music_pro')}
                >
                  {loadingCheckout === 'music_pro' ? <span className="spinner spinner--inline" /> : t('billing.plans.getPro')}
                </button>
              </div>

              <div className="billing-upgrade-card">
                <span className="badge-agency">{t('billing.plans.agency')}</span>
                <div className="billing-upgrade-price">{t('billing.plans.agencyPrice')}</div>
                <p className="billing-upgrade-desc">{t('billing.plans.agencyDesc')}</p>
                <button
                  className="btn btn-outline btn-full"
                  disabled={loadingCheckout === 'music_agency'}
                  onClick={() => handleCheckout('music_agency')}
                >
                  {loadingCheckout === 'music_agency' ? <span className="spinner spinner--inline" /> : t('billing.plans.getAgency')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Plan features */}
        <div className="billing-card">
          <h2 className="billing-card-title">{t('billing.planIncludes')}</h2>
          <ul className="pricing-features" style={{ marginTop: '1rem' }}>
            {planFeatures.map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
          </ul>
        </div>

        {/* Pay As You Go */}
        <div className="billing-card">
          <h2 className="billing-card-title">Pay As You Go</h2>
          <p style={{ fontSize: 13, color: '#666', marginBottom: 20 }}>
            No subscription needed — buy song credits whenever you need them.
          </p>
          {error && <div className="form-error form-error--banner" style={{ marginBottom: 12 }}>{error}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
            {[
              { pack: 'song_pack_099', label: '2 songs', price: '£0.99' },
              { pack: 'song_pack_200', label: '5 songs', price: '£2.00' },
              { pack: 'song_pack_400', label: '10 songs', price: '£4.00' },
            ].map(({ pack, label, price }) => (
              <button
                key={pack}
                onClick={() => handlePayg(pack)}
                disabled={paygLoading !== null}
                style={{
                  padding: '14px 12px',
                  borderRadius: 10,
                  border: '1px solid rgba(0,240,255,0.25)',
                  background: 'rgba(0,240,255,0.05)',
                  color: '#e0fffe',
                  cursor: paygLoading ? 'default' : 'pointer',
                  textAlign: 'center',
                  opacity: paygLoading && paygLoading !== pack ? 0.5 : 1,
                }}
              >
                {paygLoading === pack ? (
                  <span className="spinner spinner--inline" />
                ) : (
                  <>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#00F0FF' }}>{price}</div>
                    <div style={{ fontSize: 13, color: '#aaa', marginTop: 4 }}>{label}</div>
                  </>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Connected Accounts */}
        <div className="billing-card">
          <h2 className="billing-card-title">{t('billing.connectedAccounts')}</h2>

          {/* YouTube */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <div>
              <div style={{ fontWeight: 600, color: '#e2d9f3', marginBottom: 4 }}>
                {t('billing.youtubeLabel')}
              </div>
              <div style={{ fontSize: 13, color: '#666' }}>
                {ytConnected ? t('billing.ytConnectedDesc') : t('billing.ytNotConnectedDesc')}
              </div>
            </div>
            {ytConnected ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)', borderRadius: 999, padding: '4px 14px', fontSize: 12, fontWeight: 600 }}>
                  {t('billing.ytConnected')}
                </span>
                <button
                  onClick={handleDisconnectYouTube}
                  className="btn btn-outline"
                  style={{ fontSize: 12, padding: '4px 12px', color: '#94a3b8', borderColor: 'rgba(255,255,255,0.1)' }}
                >
                  {t('billing.disconnectYoutube')}
                </button>
              </div>
            ) : (
              <button
                onClick={handleConnectYouTube}
                disabled={!isActive && !isAdmin}
                className="btn btn-outline"
                style={{ fontSize: 13, padding: '6px 16px' }}
                title={(!isActive && !isAdmin) ? t('billing.requiresActivePlan') : undefined}
              >
                {t('billing.connectYoutube')}
              </button>
            )}
          </div>

          {/* Facebook */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0' }}>
            <div>
              <div style={{ fontWeight: 600, color: '#e2d9f3', marginBottom: 4 }}>
                {t('billing.facebookLabel')}
              </div>
              <div style={{ fontSize: 13, color: '#666' }}>
                {canFacebook ? t('billing.fbActiveDesc') : t('billing.fbUpgradeDesc')}
              </div>
            </div>
            {canFacebook ? (
              <span style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)', borderRadius: 999, padding: '4px 14px', fontSize: 12, fontWeight: 600 }}>
                {t('billing.fbActive')}
              </span>
            ) : (
              <Link to="/pricing" style={{ fontSize: 13, color: '#a855f7', textDecoration: 'none', fontWeight: 500 }}>
                {t('billing.fbUpgrade')}
              </Link>
            )}
          </div>
        </div>

        <p className="billing-note">
          {t('billing.questions')}{' '}
          <a href="mailto:hello@zeusbeats.com" className="auth-link">
            hello@zeusbeats.com
          </a>
          {'. '}
          View our <Link to="/refund-policy" className="auth-link">{t('billing.refundPolicy')}</Link>.
        </p>

        {/* Artist Name */}
        <div className="billing-card" style={{ marginTop: '2rem' }}>
          <h2 className="billing-card-title">{t('billing.artistNameTitle')}</h2>
          <p style={{ fontSize: '0.875rem', color: '#94a3b8', marginBottom: '1rem' }}>
            {t('billing.artistNameDesc')}
          </p>
          <form onSubmit={handleSaveArtistName} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: 400 }}>
            <input
              type="text"
              placeholder={t('billing.artistNamePlaceholder')}
              value={anName}
              onChange={e => setAnName(e.target.value)}
              maxLength={60}
              className="form-input"
            />
            {anError && <p style={{ color: '#ef4444', fontSize: '0.875rem', margin: 0 }}>{anError}</p>}
            {anSuccess && <p style={{ color: '#22c55e', fontSize: '0.875rem', margin: 0 }}>{anSuccess}</p>}
            <button type="submit" disabled={anLoading} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
              {anLoading ? t('billing.saving') : t('billing.saveArtistName')}
            </button>
          </form>
        </div>

        {/* Change Password */}
        <div className="billing-card" style={{ marginTop: '2rem' }}>
          <h2 className="billing-card-title">{t('billing.changePassword')}</h2>
          <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: 400 }}>
            <input
              type="password"
              placeholder={t('billing.currentPasswordPlaceholder')}
              value={cpCurrent}
              onChange={e => setCpCurrent(e.target.value)}
              required
              className="form-input"
            />
            <input
              type="password"
              placeholder={t('billing.newPasswordPlaceholder')}
              value={cpNew}
              onChange={e => setCpNew(e.target.value)}
              required
              className="form-input"
            />
            <input
              type="password"
              placeholder={t('billing.confirmPasswordPlaceholder')}
              value={cpConfirm}
              onChange={e => setCpConfirm(e.target.value)}
              required
              className="form-input"
            />
            {cpError && <p style={{ color: '#ef4444', fontSize: '0.875rem', margin: 0 }}>{cpError}</p>}
            {cpSuccess && <p style={{ color: '#22c55e', fontSize: '0.875rem', margin: 0 }}>{t('billing.passwordChanged')}</p>}
            <button type="submit" disabled={cpLoading} className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>
              {cpLoading ? t('billing.saving') : t('billing.updatePassword')}
            </button>
          </form>
        </div>

        {/* Danger zone */}
        <div className="billing-card" style={{ borderColor: 'rgba(239,68,68,0.3)', marginTop: '2rem' }}>
          <h2 className="billing-card-title" style={{ color: '#ef4444' }}>{t('billing.deleteAccount')}</h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '1rem' }}>
            {t('billing.deleteDesc')}
          </p>
          {deleteSuccess ? (
            <p style={{ color: '#22c55e', fontSize: '0.9rem' }}>
              {t('billing.deleteSuccess')}
            </p>
          ) : (
            <button
              style={{ background: 'transparent', border: '1px solid #ef4444', color: '#ef4444', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem', fontWeight: 600 }}
              onClick={() => setShowDeleteConfirm(true)}
            >
              {t('billing.requestDeletion')}
            </button>
          )}
        </div>

        {/* Cancel subscription modal */}
        {showCancelConfirm && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
            <div style={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '28px 32px', maxWidth: 420, width: '100%' }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '1.1rem', color: '#e2e8f0' }}>{t('billing.cancelModal.title')}</h3>
              <p style={{ margin: '0 0 24px', color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {status?.cancel_at
                  ? t('billing.cancelModal.descWithDate', { date: new Date(status.cancel_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }) })
                  : t('billing.cancelModal.descNoDate')}
              </p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.12)', color: '#94a3b8', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  {t('billing.cancelModal.keep')}
                </button>
                <button
                  onClick={handleCancel}
                  disabled={cancelLoading}
                  style={{ background: '#374151', border: 'none', color: '#fff', padding: '8px 18px', borderRadius: 6, cursor: cancelLoading ? 'not-allowed' : 'pointer', fontSize: '0.875rem', fontWeight: 600, opacity: cancelLoading ? 0.7 : 1 }}
                >
                  {cancelLoading ? t('billing.cancelModal.cancelling') : t('billing.cancelModal.confirm')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Confirmation modal */}
        {showDeleteConfirm && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
            <div style={{ background: '#12121e', border: '1px solid rgba(239,68,68,0.4)', borderRadius: 12, padding: '28px 32px', maxWidth: 420, width: '100%' }}>
              <h3 style={{ margin: '0 0 12px', color: '#ef4444', fontSize: '1.1rem' }}>{t('billing.deleteModal.title')}</h3>
              <p style={{ margin: '0 0 24px', color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {t('billing.deleteModal.desc')}
              </p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.12)', color: '#94a3b8', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  {t('billing.deleteModal.cancel')}
                </button>
                <button
                  onClick={handleDeleteRequest}
                  disabled={deleteLoading}
                  style={{ background: '#ef4444', border: 'none', color: '#fff', padding: '8px 18px', borderRadius: 6, cursor: deleteLoading ? 'not-allowed' : 'pointer', fontSize: '0.875rem', fontWeight: 600, opacity: deleteLoading ? 0.7 : 1 }}
                >
                  {deleteLoading ? t('billing.deleteModal.submitting') : t('billing.deleteModal.confirm')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
