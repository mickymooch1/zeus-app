export default function UsageDiagnostics({ request }) {
  const label = request.mode === 'beta' ? 'Hub Beta Credits' : 'Hub credits';
  return <details className="hub-usage-diagnostics">
    <summary>Usage diagnostics · {request.zeus_credits_charged ?? 0} {label} charged</summary>
    <p>Request ID: {request.request_id}</p>
    <p>{request.status === 'running' ? `${request.reserved} credits reserved; final charge pending.` : `${request.reserved - request.zeus_credits_charged} credits released from the reservation.`}</p>
    {request.usage?.map(call => <section key={call.id}>
      <p><strong>{call.provider} / {call.model}</strong> · {call.status}</p>
      <dl>
        <dt>Input tokens</dt><dd>{call.input_tokens ?? 'Unknown'}</dd>
        <dt>Output tokens</dt><dd>{call.output_tokens ?? 'Unknown'}</dd>
        <dt>Estimated provider cost (USD)</dt><dd>{call.estimated_cost == null ? 'Unknown' : `$${call.estimated_cost.toFixed(6)}`}{(call.input_tokens == null || call.output_tokens == null) && ' (reservation estimate; actual usage unavailable)'}</dd>
        <dt>{label} charged</dt><dd>{call.zeus_credits_charged ?? 0}</dd>
      </dl>
    </section>)}
    {!request.usage?.length && <p>No provider calls recorded.</p>}
    <p>Provider cost is estimated from configured model rates, not a provider invoice.</p>
  </details>;
}
