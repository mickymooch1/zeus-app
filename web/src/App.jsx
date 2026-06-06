import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import CookieBanner from './components/CookieBanner';
import SpaceBackground from './components/SpaceBackground';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import PricingPage from './pages/PricingPage';
import DashboardPage from './pages/DashboardPage';
import BillingPage from './pages/BillingPage';
import TasksPage from './pages/TasksPage';
import WebsitesPage from './pages/WebsitesPage';
import SongsPage from './pages/SongsPage';
import SongSharePage from './pages/SongSharePage';
import AdminPage from './pages/AdminPage';
import TermsPage from './pages/TermsPage';
import PrivacyPage from './pages/PrivacyPage';
import ContactPage from './pages/ContactPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import RefundPolicyPage from './pages/RefundPolicyPage';
import DataDeletionPage from './pages/DataDeletionPage';
import './index.css';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <SpaceBackground />
        <CookieBanner />
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
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <BillingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <TasksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/websites"
            element={
              <ProtectedRoute>
                <WebsitesPage />
              </ProtectedRoute>
            }
          />
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
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
