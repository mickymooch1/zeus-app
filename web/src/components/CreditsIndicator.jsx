import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function CreditsIndicator({ token, isAdmin, user, messageCount }) {
  const [adminState, setAdminState] = useState({ loading: true, balance: null });
  const [dailyState, setDailyState] = useState({ loading: true, count: null });

  const isFree = !isAdmin && user && (user.subscription_status === 'free' || !user.subscription_status);

  useEffect(() => {
    if (!isAdmin || !token) {
      setAdminState({ loading: false, balance: null });
      return;
    }
    fetch(`${BACKEND_URL}/admin/credits`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data) => setAdminState({ loading: false, balance: data.balance }))
      .catch(() => setAdminState({ loading: false, balance: null }));
  }, [token, isAdmin]);

  useEffect(() => {
    if (!isFree || !token) {
      setDailyState({ loading: false, count: null });
      return;
    }
    fetch(`${BACKEND_URL}/api/users/me/chat-usage`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data) => setDailyState({ loading: false, count: data.daily_count }))
      .catch(() => setDailyState({ loading: false, count: null }));
  }, [token, isFree, messageCount]);

  if (isAdmin) {
    if (adminState.loading || adminState.balance === null) return null;
    return (
      <div className="credits-indicator" title="Anthropic API credit balance">
        {`⚡ $${adminState.balance.toFixed(2)} credits`}
      </div>
    );
  }

  if (isFree && !dailyState.loading && dailyState.count !== null) {
    const LIMIT = 30;
    const atLimit = dailyState.count >= LIMIT;
    return (
      <div className={`credits-indicator credits-indicator--free${atLimit ? ' credits-indicator--limit' : ''}`}>
        {atLimit ? (
          <>Daily limit reached. <Link to="/pricing">Upgrade</Link> for unlimited messages.</>
        ) : (
          `${dailyState.count} of ${LIMIT} daily messages used`
        )}
      </div>
    );
  }

  return null;
}
