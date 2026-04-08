import { Navbar } from '../components/Navbar';

export default function PrivacyPage() {
  return (
    <div className="content-page-wrap">
      <Navbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Privacy Policy</h1>
        <p className="content-meta">Last updated: 3 April 2026</p>

        <section className="content-section">
          <h2>1. Introduction</h2>
          <p>
            Zeus ("we", "us", "our") is committed to protecting your personal data and respecting
            your privacy. This Privacy Policy explains how we collect, use, store, and protect your
            personal information when you use our Service. It applies to all users of
            zeusai.co.uk and the Zeus application.
          </p>
          <p>
            We process personal data in accordance with the UK General Data Protection Regulation
            (UK GDPR), the Data Protection Act 2018, and applicable EU GDPR requirements. Our
            lawful basis for processing is primarily (a) performance of contract and (b) legitimate
            interests, with your consent where required.
          </p>
        </section>

        <section className="content-section">
          <h2>2. Data We Collect</h2>
          <p>We collect the following categories of personal data:</p>
          <ul>
            <li>
              <strong>Account information:</strong> Name, email address, and encrypted password
              when you register
            </li>
            <li>
              <strong>Usage data:</strong> Message counts, session IDs, and timestamps of your
              interactions with Zeus
            </li>
            <li>
              <strong>Conversation content:</strong> The prompts you send to Zeus and the
              responses generated — stored to provide conversation history and context
            </li>
            <li>
              <strong>Payment information:</strong> Billing name, email, and payment method
              details (processed by Stripe — we do not store full card details)
            </li>
            <li>
              <strong>Technical data:</strong> IP addresses, browser type, and device information
              collected automatically for security and performance monitoring
            </li>
          </ul>
        </section>

        <section className="content-section">
          <h2>3. How We Use Your Data</h2>
          <p>Your personal data is used to:</p>
          <ul>
            <li>Create and manage your Zeus account</li>
            <li>Provide, operate, and improve the Service</li>
            <li>Process payments and manage subscriptions</li>
            <li>Maintain your conversation history and AI memory across sessions</li>
            <li>Send transactional emails (account confirmation, billing receipts)</li>
            <li>Monitor for abuse, fraud, and security incidents</li>
            <li>Comply with legal obligations</li>
          </ul>
          <p>
            We do not use your conversation content to train AI models, sell to third parties,
            or use for advertising purposes.
          </p>
        </section>

        <section className="content-section">
          <h2>4. Data Storage &amp; Security</h2>
          <p>
            Your data is stored in a SQLite database hosted on Railway's infrastructure. Railway
            maintains servers in the United States and European Union. We use Railway's persistent
            volume storage to ensure data durability.
          </p>
          <p>
            We implement appropriate technical and organisational security measures including:
          </p>
          <ul>
            <li>Passwords stored using bcrypt hashing (never in plain text)</li>
            <li>JWT authentication tokens with 7-day expiry</li>
            <li>HTTPS/WSS encryption for all data in transit</li>
            <li>Environment variable management for sensitive credentials</li>
            <li>Access controls limiting who can access production infrastructure</li>
          </ul>
          <p>
            No system is 100% secure. In the event of a data breach that is likely to result in
            a high risk to your rights and freedoms, we will notify you within 72 hours as
            required by UK GDPR.
          </p>
        </section>

        <section className="content-section">
          <h2>5. Third-Party Services</h2>
          <p>We use the following third-party processors:</p>
          <ul>
            <li>
              <strong>Anthropic (Claude API):</strong> Your conversation prompts are transmitted
              to Anthropic's API to generate AI responses. Anthropic processes this data under
              their API terms. We recommend not including sensitive personal information in
              prompts. See Anthropic's privacy policy at anthropic.com/privacy.
            </li>
            <li>
              <strong>Stripe:</strong> Processes all payment transactions. Stripe collects and
              stores payment details directly. We receive only non-sensitive billing identifiers.
              See stripe.com/privacy.
            </li>
            <li>
              <strong>Railway:</strong> Cloud hosting provider for the Zeus application and
              database. See railway.app/legal/privacy.
            </li>
          </ul>
          <p>
            We do not sell, rent, or share your personal data with any third party for marketing
            or advertising purposes.
          </p>
        </section>

        <section className="content-section">
          <h2>6. Your Rights Under UK GDPR</h2>
          <p>You have the following rights regarding your personal data:</p>
          <ul>
            <li>
              <strong>Right of access:</strong> Request a copy of all personal data we hold
              about you
            </li>
            <li>
              <strong>Right to rectification:</strong> Request correction of inaccurate or
              incomplete data
            </li>
            <li>
              <strong>Right to erasure:</strong> Request deletion of your personal data
              ("right to be forgotten")
            </li>
            <li>
              <strong>Right to portability:</strong> Request your data in a structured,
              machine-readable format
            </li>
            <li>
              <strong>Right to restriction:</strong> Request that we restrict processing of
              your data
            </li>
            <li>
              <strong>Right to object:</strong> Object to processing based on legitimate
              interests
            </li>
            <li>
              <strong>Rights related to automated decision-making:</strong> We do not make
              automated decisions with legal or similarly significant effects about you
            </li>
          </ul>
          <p>
            To exercise any of these rights, contact us at rowlemichael1@gmail.com. We will
            respond within one month. You also have the right to lodge a complaint with the
            Information Commissioner's Office (ICO) at ico.org.uk.
          </p>
        </section>

        <section className="content-section">
          <h2>7. Data Retention</h2>
          <p>
            We retain your personal data for as long as your account is active or as needed to
            provide the Service. If you delete your account, we will delete your personal data
            within 30 days, except where we are required to retain it by law (e.g. for tax and
            accounting purposes, typically 7 years for transaction records).
          </p>
          <p>
            Conversation history is retained to provide the AI memory feature. You may request
            deletion of specific conversations or all conversation data at any time.
          </p>
        </section>

        <section className="content-section">
          <h2>8. Cookies</h2>
          <p>
            Zeus uses minimal cookies and local storage:
          </p>
          <ul>
            <li>
              <strong>Authentication token:</strong> Stored in browser localStorage to keep you
              signed in. This is strictly necessary for the Service to function.
            </li>
            <li>
              <strong>Session preferences:</strong> Lightweight data to remember your UI
              preferences.
            </li>
          </ul>
          <p>
            We do not use tracking cookies, advertising cookies, or third-party analytics cookies.
          </p>
        </section>

        <section className="content-section">
          <h2>9. Children's Privacy</h2>
          <p>
            The Service is not directed at children under the age of 18. We do not knowingly
            collect personal data from children. If you believe we have inadvertently collected
            data from a child, please contact us immediately and we will delete it.
          </p>
        </section>

        <section className="content-section">
          <h2>10. Contact &amp; Data Controller</h2>
          <p>
            Aero Space Parking Ltd (trading as Zeus AI Design) is the data controller for
            personal data processed through the Service. Aero Space Parking Ltd (trading as
            Zeus AI Design) is registered with the Information Commissioner's Office (ICO),
            registration number C1903581.
          </p>
          <address className="content-address">
            Aero Space Parking Ltd<br />
            Trading as: Zeus AI Design<br />
            Company number: 17141941<br />
            Registered in England and Wales<br />
            Data Protection Enquiries:<br />
            Email: <a href="mailto:rowlemichael1@gmail.com" className="auth-link">rowlemichael1@gmail.com</a><br />
            Website: <a href="https://zeusaidesign.com" className="auth-link">zeusaidesign.com</a>
          </address>
        </section>
      </main>
    </div>
  );
}
