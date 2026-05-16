import { BeatsNavbar } from '../components/BeatsNavbar';

export default function RefundPolicyPage() {
  return (
    <div className="content-page-wrap">
      <BeatsNavbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Refund Policy</h1>
        <p className="content-meta">Last updated: 15 May 2026</p>

        <section className="content-section">
          <h2>1. 14-Day Refund Window</h2>
          <p>
            New subscribers are entitled to a full refund within <strong>14 days</strong> of
            their initial subscription payment, provided <strong>no songs have been
            generated</strong> using the Service during that period.
          </p>
          <p>
            This applies to first-time payments only. The 14-day window begins on the date of
            your initial charge, not the date of account creation.
          </p>
        </section>

        <section className="content-section">
          <h2>2. No Refund After Songs Generated</h2>
          <p>
            If you have generated one or more songs during your subscription period, you are{' '}
            <strong>not eligible for a refund</strong>, regardless of the time elapsed since your
            initial payment. Generating a song constitutes use of the core paid Service.
          </p>
          <p>
            We are unable to make exceptions to this policy, as song generation consumes
            computational resources and third-party API credits that cannot be recovered.
          </p>
        </section>

        <section className="content-section">
          <h2>3. Renewals &amp; Subsequent Billing Periods</h2>
          <p>
            Refunds are not available for subscription renewals or subsequent billing periods.
            The 14-day refund window applies to your first payment only. To avoid being charged
            for a renewal, you must cancel your subscription before your next billing date.
          </p>
        </section>

        <section className="content-section">
          <h2>4. How to Request a Refund</h2>
          <p>
            To request a refund, contact us at{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">
              hello@zeusbeats.com
            </a>{' '}
            within 14 days of your initial payment. Please include:
          </p>
          <ul>
            <li>Your registered email address</li>
            <li>The date of your subscription payment</li>
            <li>Confirmation that no songs have been generated on your account</li>
          </ul>
          <p>
            Eligible refunds will be processed within 5–10 business days and returned to your
            original payment method via Stripe.
          </p>
        </section>

        <section className="content-section">
          <h2>5. Statutory Rights</h2>
          <p>
            Nothing in this Refund Policy affects your statutory rights under the Consumer
            Rights Act 2015 or any other applicable UK consumer protection legislation. If you
            are a consumer in the EU, you may have additional rights under EU consumer
            protection law.
          </p>
        </section>
      </main>
    </div>
  );
}
