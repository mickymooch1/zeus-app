import { useEffect, useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function CreditsIndicator({ token, isAdmin }) {
  const [state, setState] = useState({ loading: true, balance: null, message: null });

  useEffect(() => {
    if (!isAdmin || !token) {
      setState({ loading: false, balance: null, message: null });
      return;
    }
    fetch(`${BACKEND_URL}/admin/credits`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setState({ loading: false, balance: data.balance, message: data.message || null }))
      .catch(() => setState({ loading: false, balance: null, message: 'Balance unavailable' }));
  }, [token, isAdmin]);

  if (!isAdmin) return null;
  if (state.loading) return null;

  const label = state.balance !== null
    ? `⚡ $${state.balance.toFixed(2)} credits`
    : 'Balance unavailable';

  return (
    <div className="credits-indicator" title="Anthropic API credit balance">
      {label}
    </div>
  );
}
