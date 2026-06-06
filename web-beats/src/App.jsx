import { lazy, Suspense, useState } from 'react';
import { BrowserRouter, Route, Routes, Navigate, Outlet, useNavigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { NowPlayingProvider, useNowPlaying } from './contexts/NowPlayingContext';
import { useAuth } from './contexts/AuthContext';
import { ProtectedRoute, SchoolSafeRoute } from './components/ProtectedRoute';
import CookieBanner from './components/CookieBanner';
import NowPlayingBar from './components/NowPlayingBar';
import { UpdateToast } from './components/UpdateToast';
import KidsShell from './components/KidsShell';
import ParentPINGate from './components/ParentPINGate';
import SpaceBackground from './components/SpaceBackground';
const LandingPage = lazy(() => import('./pages/LandingPage'));
import './index.css';

const LoginPage          = lazy(() => import('./pages/LoginPage'));
const RegisterPage       = lazy(() => import('./pages/RegisterPage'));
const PricingPage        = lazy(() => import('./pages/PricingPage'));
const SongsPage          = lazy(() => import('./pages/SongsPage'));
const SongSharePage      = lazy(() => import('./pages/SongSharePage'));
const BillingPage        = lazy(() => import('./pages/BillingPage'));
const TermsPage          = lazy(() => import('./pages/TermsPage'));
const PrivacyPage        = lazy(() => import('./pages/PrivacyPage'));
const ContactPage        = lazy(() => import('./pages/ContactPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage  = lazy(() => import('./pages/ResetPasswordPage'));
const VerifyEmailPage    = lazy(() => import('./pages/VerifyEmailPage'));
const RefundPolicyPage   = lazy(() => import('./pages/RefundPolicyPage'));
const DataDeletionPage   = lazy(() => import('./pages/DataDeletionPage'));
const SearchPage         = lazy(() => import('./pages/SearchPage'));
const AdminBeats         = lazy(() => import('./pages/AdminBeats'));
const MixerPage          = lazy(() => import('./pages/MixerPage'));
const DiscoverPage       = lazy(() => import('./pages/DiscoverPage'));
const DiscoverSongPage   = lazy(() => import('./pages/DiscoverSongPage'));
const PlaylistPage       = lazy(() => import('./pages/PlaylistPage'));
const TutorialPage       = lazy(() => import('./pages/TutorialPage'));
const DownloadPage       = lazy(() => import('./pages/DownloadPage'));
const ResetPINPage           = lazy(() => import('./pages/ResetPINPage'));
const KidsHomePage           = lazy(() => import('./pages/kids/KidsHomePage'));
const KidsSongMode           = lazy(() => import('./pages/kids/KidsSongMode'));
const KidsStoryMode          = lazy(() => import('./pages/kids/KidsStoryMode'));
const KidsSongsListPage      = lazy(() => import('./pages/kids/KidsSongsListPage'));
const SchoolRegisterPage     = lazy(() => import('./pages/SchoolRegisterPage'));

function KidsProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="spinner-page"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.account_type === 'school') return children;
  if (sessionStorage.getItem('kidsMode') !== '1') return <Navigate to="/songs" replace />;
  return children;
}

function KidsShellWrapper() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [showPin, setShowPin] = useState(false);
  const isSchool = user?.account_type === 'school';

  const handleExit = () => {
    sessionStorage.removeItem('kidsMode');
    navigate('/songs');
  };

  return (
    <>
      <KidsShell showExitBtn={!isSchool} onExitClick={() => setShowPin(true)}>
        <Outlet />
      </KidsShell>
      {showPin && (
        <ParentPINGate
          token={token}
          hasPIN={!!user?.has_kids_pin}
          action="exit"
          onSuccess={handleExit}
          onCancel={() => setShowPin(false)}
        />
      )}
    </>
  );
}

const fallback = (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#0b0b14', gap: 16 }}>
    <div style={{ fontFamily: 'Orbitron, sans-serif', fontSize: '1.4rem', fontWeight: 900, background: 'linear-gradient(135deg,#7c3aed,#00f0ff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>⚡ Zeus Beats</div>
    <div style={{ width: 36, height: 36, border: '3px solid rgba(0,240,255,0.2)', borderTopColor: '#00f0ff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
  </div>
);

function AppInner() {
  const { currentSong } = useNowPlaying();
  return (
    <>
      <CookieBanner />
<UpdateToast />
      {currentSong?.mp3_url && <NowPlayingBar />}
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <NowPlayingProvider>
      <BrowserRouter>
        <SpaceBackground />
        <AppInner />
        <Suspense fallback={fallback}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/reset-pin" element={<ResetPINPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/refund-policy" element={<RefundPolicyPage />} />
            <Route path="/data-deletion" element={<DataDeletionPage />} />
            <Route
              path="/songs"
              element={
                <SchoolSafeRoute>
                  <SongsPage />
                </SchoolSafeRoute>
              }
            />
            <Route path="/songs/share/:variantId" element={<SongSharePage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/discover/:variantId" element={<DiscoverSongPage />} />
            <Route
              path="/billing"
              element={
                <SchoolSafeRoute>
                  <BillingPage />
                </SchoolSafeRoute>
              }
            />
            <Route
              path="/search"
              element={
                <SchoolSafeRoute>
                  <SearchPage />
                </SchoolSafeRoute>
              }
            />
            <Route
              path="/mixer"
              element={
                <SchoolSafeRoute>
                  <MixerPage />
                </SchoolSafeRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <SchoolSafeRoute>
                  <AdminBeats />
                </SchoolSafeRoute>
              }
            />
            <Route
              path="/playlists"
              element={
                <SchoolSafeRoute>
                  <PlaylistPage />
                </SchoolSafeRoute>
              }
            />
            <Route path="/tutorial" element={<TutorialPage />} />
            <Route path="/download" element={<DownloadPage />} />

            {/* ── Zeus Kids Beats ────────────────────────────────── */}
            <Route path="/schools" element={<SchoolRegisterPage />} />
            <Route
              path="/kids"
              element={
                <KidsProtectedRoute>
                  <KidsShellWrapper />
                </KidsProtectedRoute>
              }
            >
              <Route index element={<KidsHomePage />} />
              <Route path="song" element={<KidsSongMode />} />
              <Route path="story" element={<KidsStoryMode />} />
              <Route path="songs" element={<KidsSongsListPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
      </NowPlayingProvider>
    </AuthProvider>
  );
}
