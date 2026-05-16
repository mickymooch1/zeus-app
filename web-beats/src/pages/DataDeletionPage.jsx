import { BeatsNavbar } from '../components/BeatsNavbar';

export default function DataDeletionPage() {
  return (
    <div className="content-page-wrap">
      <BeatsNavbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Data Deletion Request — Zeus Beats</h1>
        <p className="content-meta">Last updated: 15 May 2026</p>

        <section className="content-section">
          <h2>How to Request Deletion</h2>
          <p>
            You can request the deletion of your account and all associated data in two ways:
          </p>

          <h3 style={{ marginTop: '1.25rem', marginBottom: '0.5rem', fontSize: '1rem', color: '#e2e8f0' }}>
            Option 1 — Delete from your account
          </h3>
          <ol>
            <li>Log in to your account at <a href="https://zeusbeats.com" className="auth-link">zeusbeats.com</a></li>
            <li>Go to <strong>Billing &amp; Account Settings</strong></li>
            <li>Scroll to the bottom and click <strong>"Request Account Deletion"</strong></li>
            <li>Confirm the request in the popup</li>
          </ol>

          <h3 style={{ marginTop: '1.25rem', marginBottom: '0.5rem', fontSize: '1rem', color: '#e2e8f0' }}>
            Option 2 — Email us
          </h3>
          <p>
            Send an email to{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">
              hello@zeusbeats.com
            </a>{' '}
            with the subject line <strong>"Data Deletion Request"</strong> and include your
            registered email address.
          </p>
        </section>

        <section className="content-section">
          <h2>Data That Will Be Deleted</h2>
          <ul>
            <li>Your account and profile information</li>
            <li>All generated songs and audio files</li>
            <li>All cover art and video files</li>
            <li>Payment history references</li>
            <li>Usage logs associated with your account</li>
          </ul>
        </section>

        <section className="content-section">
          <h2>Data Retention</h2>
          <ul>
            <li>Deletion is processed within <strong>30 days</strong> of your request</li>
            <li>
              Stripe payment records may be retained for up to <strong>7 years</strong> for
              legal and tax compliance purposes
            </li>
            <li>Anonymised usage statistics may be retained</li>
          </ul>
        </section>

        <section className="content-section">
          <h2>Contact</h2>
          <p>
            If you have any questions about data deletion, contact us at{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">
              hello@zeusbeats.com
            </a>.
          </p>
        </section>
      </main>
    </div>
  );
}
