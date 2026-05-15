import { useState } from 'react';
import { Navbar } from '../components/Navbar';

export default function ContactPage() {
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' });
  const [status, setStatus] = useState('idle');
  const [errorMsg, setErrorMsg] = useState('');

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus('loading');
    setErrorMsg('');
    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send message');
      setStatus('success');
    } catch (err) {
      setErrorMsg(err.message);
      setStatus('error');
    }
  }

  return (
    <div className="content-page-wrap">
      <Navbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" style={{ opacity: 0.3 }} />
      </div>
      <main className="content-page page">
        <h1 className="content-title">Contact Us</h1>
        <p className="content-meta">We aim to respond to all enquiries within 24 hours.</p>

        <section className="content-section">
          {status === 'success' ? (
            <p style={{ fontSize: '1.1rem', color: 'var(--accent, #7c3aed)' }}>
              Thanks! We'll be in touch within 24 hours.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="auth-form" style={{ maxWidth: 520 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="contact-name">Name</label>
                <input
                  id="contact-name"
                  name="name"
                  type="text"
                  className="form-input"
                  placeholder="Your name"
                  required
                  value={form.name}
                  onChange={handleChange}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="contact-email">Email</label>
                <input
                  id="contact-email"
                  name="email"
                  type="email"
                  className="form-input"
                  placeholder="you@example.com"
                  required
                  value={form.email}
                  onChange={handleChange}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="contact-subject">Subject</label>
                <input
                  id="contact-subject"
                  name="subject"
                  type="text"
                  className="form-input"
                  placeholder="How can we help?"
                  required
                  value={form.subject}
                  onChange={handleChange}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="contact-message">Message</label>
                <textarea
                  id="contact-message"
                  name="message"
                  className="form-input"
                  rows={6}
                  placeholder="Tell us more…"
                  required
                  value={form.message}
                  onChange={handleChange}
                  style={{ resize: 'vertical' }}
                />
              </div>
              {status === 'error' && (
                <div className="form-error form-error--banner">{errorMsg}</div>
              )}
              <button
                type="submit"
                className="btn btn-primary"
                disabled={status === 'loading'}
                style={{ marginTop: 8 }}
              >
                {status === 'loading' ? 'Sending…' : 'Send Message'}
              </button>
            </form>
          )}
        </section>
      </main>
    </div>
  );
}
