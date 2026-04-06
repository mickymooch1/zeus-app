import { useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="spinner-page">
        <div className="spinner" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If user has no active subscription and is not already on billing or pricing pages
  const freePaths = ['/billing', '/pricing', '/terms', '/privacy'];
  const isFreePath = freePaths.some((p) => location.pathname.startsWith(p));
  const isActive =
    user.subscription_status === 'active' &&
    user.subscription_plan;

  if (!isActive && !isFreePath) {
    return <Navigate to="/pricing" replace />;
  }

  return children;
}
