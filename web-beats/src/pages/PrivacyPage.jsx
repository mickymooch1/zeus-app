import { BeatsNavbar } from '../components/BeatsNavbar';

export default function PrivacyPage() {
  return (
    <div className="content-page-wrap">
      <BeatsNavbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Privacy Policy</h1>
        <p className="content-meta">Last updated: 17 July 2026</p>

        <section className="content-section">
          <h2>1. Introduction</h2>
          <p>
            Zeus Beats ("we", "us", "our") is committed to protecting your personal data and
            respecting your privacy. This Privacy Policy explains how we collect, use, store, and
            protect your personal information when you use our Service. It applies to all users of
            zeusbeats.com and the Zeus Beats application.
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
              <strong>Usage data:</strong> Song generation counts, session IDs, and timestamps of
              your interactions with Zeus Beats
            </li>
            <li>
              <strong>Generated content:</strong> Songs, lyrics, cover art, and videos you create
              — stored to provide your song library and history
            </li>
            <li>
              <strong>Payment information:</strong> Billing name, email, and payment method
              details (processed by Stripe — we do not store full card details)
            </li>
            <li>
              <strong>Connected accounts:</strong> YouTube OAuth tokens (if you connect your
              channel) stored to enable direct uploads
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
            <li>Create and manage your Zeus Beats account</li>
            <li>Provide, operate, and improve the Service</li>
            <li>Process payments and manage subscriptions</li>
            <li>Store and serve your generated songs and media</li>
            <li>Upload content to your connected YouTube channel (with your consent)</li>
            <li>Post to Facebook via Make.com automation (Music Agency plan only)</li>
            <li>Send transactional emails (account confirmation, billing receipts)</li>
            <li>Monitor for abuse, fraud, and security incidents</li>
            <li>Comply with legal obligations</li>
          </ul>
          <p>
            We do not use your generated content to train AI models, sell to third parties,
            or use for advertising purposes.
          </p>
        </section>

        <section className="content-section">
          <h2>4. Data Storage &amp; Security</h2>
          <p>
            Your data is stored in a database hosted on Railway's infrastructure. Railway
            maintains servers in the United States and European Union. We use Railway's persistent
            volume storage to ensure data durability.
          </p>
          <p>
            We implement appropriate technical and organisational security measures including:
          </p>
          <ul>
            <li>Passwords stored using bcrypt hashing (never in plain text)</li>
            <li>JWT authentication tokens with 7-day expiry</li>
            <li>HTTPS encryption for all data in transit</li>
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
          <p>
            The third-party AI providers that process your creative inputs are described
            separately in Section 6 (AI Processing &amp; Third-Party AI Services).
          </p>
          <ul>
            <li>
              <strong>Stripe:</strong> Processes all payment transactions. Stripe collects and
              stores payment details directly. We receive only non-sensitive billing identifiers.
              See stripe.com/privacy.
            </li>
            <li>
              <strong>Railway:</strong> Cloud hosting provider for the Zeus Beats application and
              database. See railway.app/legal/privacy.
            </li>
            <li>
              <strong>YouTube (Google):</strong> If you connect your YouTube channel, we use the
              YouTube Data API to upload songs on your behalf. This is governed by Google's
              Privacy Policy and YouTube Terms of Service. You may revoke access at any time
              through your Google account settings.
            </li>
            <li>
              <strong>Make.com:</strong> Used for automated Facebook posting on the Music Agency
              plan. Posts are triggered by our server; no direct Facebook OAuth is required from
              you.
            </li>
          </ul>
          <p>
            We do not sell, rent, or share your personal data with any third party for marketing
            or advertising purposes.
          </p>
        </section>

        <section className="content-section">
          <h2>6. AI Processing &amp; Third-Party AI Services</h2>
          <p>
            Zeus Beats is an AI-powered creative tool. To generate the music, lyrics, cover art,
            and voice content you request, the information you provide — including your song
            descriptions and style prompts, lyric ideas, and any voice recordings you upload for
            voice cloning — is transmitted to and processed by the third-party
            artificial-intelligence providers listed below. This processing is essential to
            deliver the features you ask for, and it only happens when you choose to use those
            features.
          </p>
          <ul>
            <li>
              <strong>Suno (via Apiframe):</strong> Your song descriptions, style selections, and
              generated lyrics are sent to generate the music audio for your tracks. Processed
              under Suno's and Apiframe's own terms (suno.com, apiframe.ai).
            </li>
            <li>
              <strong>ElevenLabs:</strong> Text you provide is sent to generate voice narration
              and sound effects. For the optional voice-cloning feature, any voice recording you
              record or upload is sent to create a synthetic version of that voice. Processed
              under ElevenLabs' own terms (elevenlabs.io).
            </li>
            <li>
              <strong>Anthropic (Claude):</strong> Your song descriptions, themes, and prompts are
              sent to generate and refine song lyrics and text. Processed under Anthropic's own
              terms (anthropic.com).
            </li>
            <li>
              <strong>fal.ai:</strong> Your prompts and style selections are sent to generate
              cover art and image content for your songs. Processed under fal.ai's own terms
              (fal.ai).
            </li>
          </ul>
          <p>
            <strong>Limited use.</strong> We use the data sent to these AI providers solely to
            provide the generation features you request. We do not use your prompts, uploads, or
            generated content to train our own AI models, we do not sell or rent this data, and we
            do not use it for advertising. Each provider processes your data only to return the
            requested result to us, under its own privacy policy and terms.
          </p>
          <p>
            <strong>Voice cloning and biometric data.</strong> The optional voice-cloning feature
            processes a recording of your voice, which may constitute biometric data. We capture
            and transmit a voice recording to ElevenLabs only when you actively choose to use voice
            cloning and give your explicit consent at the point of recording or upload. Your voice
            recording is used solely to create the synthetic voice you request — it is never used
            for identification, sold, or shared for any other purpose. You may decline by not using
            the feature, and you may request deletion of your voice data at any time by contacting
            us at{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">hello@zeusbeats.com</a>.
          </p>
          <p>
            <strong>Your consent.</strong> By using Zeus Beats' AI generation features, you consent
            to your inputs being processed by these third-party AI providers as described above. If
            you do not wish your data to be processed by them, please do not use the relevant AI
            generation features. We recommend you do not include sensitive personal information in
            your prompts, descriptions, or uploads.
          </p>
        </section>

        <section className="content-section">
          <h2>7. Your Rights Under UK GDPR</h2>
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
            To exercise any of these rights, contact us at{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">hello@zeusbeats.com</a>.
            We will respond within one month. You also have the right to lodge a complaint with
            the Information Commissioner's Office (ICO) at{' '}
            <a href="https://ico.org.uk" target="_blank" rel="noopener noreferrer" className="auth-link">
              ico.org.uk
            </a>.
          </p>
        </section>

        <section className="content-section">
          <h2>8. Data Retention</h2>
          <p>
            We retain your personal data for as long as your account is active or as needed to
            provide the Service. If you delete your account, we will delete your personal data
            within 30 days, except where we are required to retain it by law (e.g. for tax and
            accounting purposes, typically 7 years for transaction records).
          </p>
          <p>
            Generated songs and media are retained while your account is active. You may delete
            individual songs or all your content at any time from your Songs library.
          </p>
        </section>

        <section className="content-section">
          <h2>9. Cookies</h2>
          <p>
            Zeus Beats uses minimal cookies and local storage:
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
          <h2>10. Children's Privacy</h2>
          <p>
            The Service is not directed at children under the age of 18. We do not knowingly
            collect personal data from children. If you believe we have inadvertently collected
            data from a child, please contact us immediately and we will delete it.
          </p>
        </section>

        <section className="content-section">
          <h2>11. Right to Erasure &amp; Data Deletion</h2>
          <p>
            You have the right to request deletion of your personal data at any time. To request
            deletion, visit your{' '}
            <a href="/billing" className="auth-link">account settings</a> and use the
            "Request Account Deletion" option, or contact us at{' '}
            <a href="mailto:hello@zeusbeats.com" className="auth-link">hello@zeusbeats.com</a>.
            Requests will be processed within 30 days.
          </p>
          <p>
            Upon deletion, we will remove your account, all songs, generated content, and personal
            data from our systems. Some data may be retained for a limited period where required by
            law (for example, billing records for tax compliance purposes).
          </p>
        </section>

        <section className="content-section">
          <h2>12. Children's Data (Zeus Kids Beats)</h2>
          <p>Zeus Kids Beats is our child-safe music and storytelling mode designed for use in schools and family settings. We take children's privacy extremely seriously.</p>
          <p><strong>No individual child data is collected.</strong> Zeus Kids Beats school accounts are managed by adult teachers. Children do not have individual logins or personal profiles. All songs and stories created belong to the teacher's account, not to any individual child.</p>
          <p>School accounts store only: the teacher's name, school name, email address, and year group. No child names, ages, or personal identifiers are stored.</p>
          <p>Zeus Beats is not directed at children under 13 for individual account registration. School accounts are operated by adult teachers who are responsible for their class's use of the platform under their own consent.</p>
          <p>If you have questions about children's data, contact us at <a href="mailto:privacy@zeusbeats.com" className="auth-link">privacy@zeusbeats.com</a>.</p>
        </section>

        <section className="content-section">
          <h2>13. Contact &amp; Data Controller</h2>
          <p>
            Zeus Beats Ltd is the data controller for personal
            data processed through the Service. Zeus Beats Ltd is registered with the
            Information Commissioner's Office (ICO), registration number CSN5305083.
          </p>
          <address className="content-address">
            Zeus Beats Ltd<br />
            Company number: 17230535<br />
            Registered address: 79 Brookway Court, Wythenshawe, Manchester, M23 0GL<br />
            Registered in England and Wales<br />
            Data Protection Enquiries:<br />
            Email: <a href="mailto:hello@zeusbeats.com" className="auth-link">hello@zeusbeats.com</a><br />
            Website: <a href="https://zeusbeats.com" className="auth-link">zeusbeats.com</a>
          </address>
        </section>
      </main>
    </div>
  );
}
