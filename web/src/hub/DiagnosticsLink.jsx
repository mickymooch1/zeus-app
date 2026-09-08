import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// UX-only visibility check — GET /api/hub/diagnostics enforces the real
// gate server-side (is_admin + email_verified + beta allowlist) and is
// the only authoritative source. This component mirrors all three
// conditions using signals already available on the caller, rather than
// showing the link on a weaker (is_admin-only) guess:
//   - is_admin, email_verified: real fields on the /auth/me user object.
//   - beta allowlist: there's no dedicated "am I allowlisted" field, but
//     `mode` is only ever visible here as 'beta' on a *successful*
//     GET /api/hub/status response — that endpoint shares the same
//     context() dependency as every other Hub route, whose authorize()
//     rejects (403, before the handler runs) any caller not on
//     beta_user_ids while mode=='beta'. So a caller can only ever see
//     mode==='beta' here if they already passed that same allowlist
//     check — it is not a value any Hub page could be tricked into
//     rendering for a non-allowlisted user. Pass the `mode` you already
//     have in state from that same request; don't fetch it separately.
export default function DiagnosticsLink({ mode }) {
  const { user } = useAuth();
  if (!(user?.is_admin && user?.email_verified && mode === 'beta')) return null;
  return <Link to="/hub/diagnostics" className="hub-diag-link">Diagnostics</Link>;
}
