export default function BetaStatus({ balance, mode = 'development' }) {
  const liveBeta = mode === 'beta';
  return <details className="hub-beta-status">
    <summary><span className="hub-beta-label">Private beta</span><span>{liveBeta ? `${balance ?? '—'} Hub Beta Credits · Ask Zeus only` : 'Test environment'}</span></summary>
    <div className="hub-beta-details">
      <p>{liveBeta ? 'Invite-only access to one live AI model. Zeus Council live calls are disabled.' : 'Simulated responses only. No paid AI providers are called.'}</p>
      <p>{liveBeta ? 'Free beta allowance, separate from all existing balances. Provider usage is recorded per request. No Hub purchases or production billing are enabled.' : <><strong>{balance ?? '—'} test Hub credits</strong> · for testing reservations and refunds. These are separate from live balances.</>}</p>
    </div>
  </details>;
}
