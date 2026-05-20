import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import CookieBanner from './components/CookieBanner';
import LandingPage from './pages/LandingPage';
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
const HermesAgentPage    = lazy(() => import('./pages/HermesAgentPage'));
const MixerPage          = lazy(() => import('./pages/MixerPage'));

const fallback = (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#0b0b14', color: '#94a3b8', fontSize: '1rem' }}>
    Loading…
  </div>
);

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <CookieBanner />
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
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/refund-policy" element={<RefundPolicyPage />} />
            <Route path="/data-deletion" element={<DataDeletionPage />} />
            <Route
              path="/songs"
              element={
                <ProtectedRoute>
                  <SongsPage />
                </ProtectedRoute>
              }
            />
            <Route path="/songs/share/:variantId" element={<SongSharePage />} />
            <Route
              path="/billing"
              element={
                <ProtectedRoute>
                  <BillingPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/search"
              element={
                <ProtectedRoute>
                  <SearchPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/mixer"
              element={
                <ProtectedRoute>
                  <MixerPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <AdminBeats />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/hermes"
              element={
                <ProtectedRoute>
                  <HermesAgentPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}
