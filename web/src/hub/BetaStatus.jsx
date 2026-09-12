export default function BetaStatus({ balance, mode = 'development' }) {
  const liveBeta = mode === 'beta';
  return <details className="hub-beta-status">
    <summary><span className="hub-beta-label">{liveBeta ? 'Public beta' : 'Beta'}</span><span>{liveBeta ? `${balance ?? '—'} Hub Credits · Ask Zeus & Council` : 'Test environment'}</span></summary>
    <div className="hub-beta-details">
      <p>{liveBeta ? 'Zeus Hub is currently in beta. Usage is subject to your Hub Credit balance and fair-use limits.' : 'Simulated responses only. No paid AI providers are called.'}</p>
      <p>{liveBeta ? 'Verified accounts receive 20 Hub Credits once for the public beta. Hub Credits are separate from music and website-builder balances.' : <><strong>{balance ?? '—'} test Hub credits</strong> · for testing reservations and refunds. These are separate from live balances.</>}</p>
    </div>
  </details>;
}
