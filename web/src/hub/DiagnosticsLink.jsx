import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// This only controls link visibility. The diagnostics endpoint remains
// authoritative and enforces admin, verified-email and its existing gate.
export default function DiagnosticsLink({ mode }) {
  const { user } = useAuth();
  if (!(user?.is_admin && user?.email_verified && mode === 'beta')) return null;
  return <Link to="/hub/diagnostics" className="hub-diag-link">Diagnostics</Link>;
}
