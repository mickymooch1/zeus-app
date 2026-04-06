import { Navbar } from '../components/Navbar';

export default function TermsPage() {
  return (
    <div className="content-page-wrap">
      <Navbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Terms &amp; Conditions</h1>
        <p className="content-meta">Last updated: 3 April 2026</p>

        <section className="content-section">
          <h2>1. Acceptance of Terms</h2>
          <p>
            By accessing or using Zeus ("the Service"), you agree to be bound by these Terms &
            Conditions ("Terms"). If you do not agree to these Terms, you must not use the Service.
            These Terms constitute a legally binding agreement between you and Zeus ("we", "us",
            "our"). We reserve the right to update these Terms at any time. Continued use of the
            Service after changes constitutes acceptance of the new Terms.
          </p>
        </section>

        <section className="content-section">
          <h2>2. Service Description</h2>
          <p>
            Zeus is an AI-powered business assistant designed to help web designers and digital
            agencies with tasks including, but not limited to: website design and code generation,
            client communications, content writing, project management advice, and business
            operations support. The Service is provided "as is" and we make no warranties that
            outputs will be error-free, complete, or suitable for any particular purpose.
          </p>
          <p>
            AI-generated content should always be reviewed by a qualified professional before use
            in commercial or client-facing work. Zeus does not provide legal, financial, tax, or
            professional advice, and nothing in the Service should be construed as such.
          </p>
        </section>

        <section className="content-section">
          <h2>3. Account Registration</h2>
          <p>
            To access the full Service, you must create an account by providing accurate and
            complete information. You are responsible for:
          </p>
          <ul>
            <li>Maintaining the confidentiality of your password and account credentials</li>
            <li>All activity that occurs under your account</li>
            <li>Notifying us immediately of any unauthorised use of your account</li>
            <li>Ensuring all registration information is kept accurate and up to date</li>
          </ul>
          <p>
            You must be at least 18 years of age to create an account. By registering, you
            confirm that you meet this requirement and that you are not prohibited from using the
            Service under any applicable law.
          </p>
        </section>

        <section className="content-section">
          <h2>4. Subscriptions &amp; Billing</h2>
          <p>
            Zeus offers a free tier and paid subscription plans (Professional at £29/month and
            Agency at £79/month). All prices are shown in British Pounds (GBP) and are exclusive
            of applicable taxes (including VAT where required by law).
          </p>
          <p>
            Paid subscriptions are billed monthly in advance. By subscribing, you authorise us
            to charge your payment method on a recurring basis until you cancel. Subscription
            fees are non-refundable except where required by law. You may cancel your subscription
            at any time through the billing portal; cancellation will take effect at the end of
            the current billing period.
          </p>
          <p>
            We use Stripe to process payments. Your payment information is collected and stored
            by Stripe and is subject to Stripe's privacy policy and terms of service. We do not
            store your full card details on our servers.
          </p>
          <p>
            We reserve the right to change subscription prices with 30 days' notice. Price
            changes will not affect your current subscription period.
          </p>
        </section>

        <section className="content-section">
          <h2>5. Acceptable Use</h2>
          <p>You agree not to use the Service to:</p>
          <ul>
            <li>Generate, distribute, or store illegal content of any kind</li>
            <li>Infringe upon the intellectual property rights of any third party</li>
            <li>Create malware, phishing material, or any content intended to deceive</li>
            <li>Harass, threaten, or harm any individual or group</li>
            <li>Attempt to reverse-engineer or extract the underlying AI model</li>
            <li>Resell or sublicense access to the Service without our written consent</li>
            <li>Use automated scripts or bots to access the Service beyond normal usage</li>
            <li>Upload or transmit content that violates any applicable law or regulation</li>
          </ul>
          <p>
            We reserve the right to suspend or terminate accounts that violate these acceptable
            use policies, without notice and without refund.
          </p>
        </section>

        <section className="content-section">
          <h2>6. Intellectual Property</h2>
          <p>
            <strong>Our IP:</strong> The Zeus platform, its software, design, and branding are
            owned by us and protected by copyright, trademark, and other intellectual property
            laws. You may not copy, modify, distribute, or create derivative works from our
            platform without express written permission.
          </p>
          <p>
            <strong>Your content:</strong> You retain ownership of any content you submit to
            the Service (your prompts, client data, uploaded files). By using the Service, you
            grant us a limited, non-exclusive licence to process your content solely for the
            purpose of delivering the Service.
          </p>
          <p>
            <strong>AI outputs:</strong> Content generated by Zeus in response to your prompts
            is provided for your use. You are responsible for ensuring that AI-generated outputs
            do not infringe third-party rights before commercial use. We make no representation
            as to the originality of AI-generated content.
          </p>
        </section>

        <section className="content-section">
          <h2>7. Limitation of Liability</h2>
          <p>
            To the maximum extent permitted by applicable law, Zeus and its affiliates, directors,
            employees, and agents shall not be liable for any:
          </p>
          <ul>
            <li>Indirect, incidental, special, consequential, or punitive damages</li>
            <li>Loss of profits, revenue, data, or business opportunities</li>
            <li>Errors, inaccuracies, or omissions in AI-generated content</li>
            <li>Interruption or cessation of the Service</li>
          </ul>
          <p>
            In no event shall our total aggregate liability exceed the greater of (a) the amount
            you paid to us in the 12 months preceding the claim or (b) £100. Nothing in these
            Terms limits liability for death, personal injury caused by negligence, fraud, or any
            other liability that cannot be excluded under English law.
          </p>
        </section>

        <section className="content-section">
          <h2>8. Termination</h2>
          <p>
            We may terminate or suspend your access to the Service immediately, without notice,
            for any reason, including breach of these Terms. Upon termination, your right to use
            the Service ceases immediately. You may request deletion of your account data in
            accordance with our Privacy Policy.
          </p>
          <p>
            You may terminate your account at any time by contacting us at
            support@zeusai.co.uk or through the account settings. Termination does not entitle
            you to a refund of any prepaid subscription fees.
          </p>
        </section>

        <section className="content-section">
          <h2>9. Governing Law</h2>
          <p>
            These Terms are governed by and construed in accordance with the laws of England and
            Wales. Any disputes arising under these Terms shall be subject to the exclusive
            jurisdiction of the courts of England and Wales.
          </p>
        </section>

        <section className="content-section">
          <h2>10. Contact</h2>
          <p>
            If you have any questions about these Terms, please contact us at:
          </p>
          <address className="content-address">
            Zeus<br />
            Email: <a href="mailto:legal@zeusai.co.uk" className="auth-link">legal@zeusai.co.uk</a><br />
            Website: <a href="https://zeusai.co.uk" className="auth-link">zeusai.co.uk</a>
          </address>
        </section>
      </main>
    </div>
  );
}
