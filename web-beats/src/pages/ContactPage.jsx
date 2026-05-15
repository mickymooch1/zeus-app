import { useState } from 'react';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';

const PAGE_CSS = `
.contact-page {
  min-height: 100vh;
  background: #0b0b14;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
}
.contact-main {
  flex: 1;
  max-width: 580px;
  margin: 0 auto;
  padding: 48px 20px 80px;
  width: 100%;
}
.contact-title {
  font-size: clamp(1.8rem, 5vw, 2.4rem);
  font-weight: 800;
  background: linear-gradient(135deg, #00f0ff, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 6px;
}
.contact-meta {
  color: #94a3b8;
  margin: 0 0 36px;
  font-size: 0.95rem;
}
.contact-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.contact-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.contact-label {
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #94a3b8;
}
.contact-input {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(0,240,255,0.15);
  border-radius: 8px;
  padding: 11px 14px;
  color: #e2e8f0;
  font-size: 0.95rem;
  transition: border-color 0.2s;
  outline: none;
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}
.contact-input:focus {
  border-color: rgba(0,240,255,0.5);
  box-shadow: 0 0 0 2px rgba(0,240,255,0.08);
}
.contact-input::placeholder { color: #475569; }
.contact-submit {
  margin-top: 6px;
  padding: 12px 28px;
  background: linear-gradient(135deg, #00f0ff, #7c3aed);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
  align-self: flex-start;
}
.contact-submit:hover:not(:disabled) { opacity: 0.88; transform: translateY(-1px); }
.contact-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.contact-success {
  font-size: 1.1rem;
  color: #00f0ff;
  padding: 24px 0;
}
.contact-error {
  font-size: 0.875rem;
  color: #f87171;
  padding: 8px 12px;
  background: rgba(248,113,113,0.08);
  border: 1px solid rgba(248,113,113,0.2);
  border-radius: 6px;
}
`;

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
    <div className="contact-page">
      <style>{PAGE_CSS}</style>
      <BeatsDashboardHeader />
      <main className="contact-main">
        <h1 className="contact-title">Contact Us</h1>
        <p className="contact-meta">We aim to respond to all enquiries within 24 hours.</p>

        {status === 'success' ? (
          <p className="contact-success">Thanks! We'll be in touch within 24 hours.</p>
        ) : (
          <form className="contact-form" onSubmit={handleSubmit}>
            <div className="contact-field">
              <label className="contact-label" htmlFor="contact-name">Name</label>
              <input
                id="contact-name"
                name="name"
                type="text"
                className="contact-input"
                placeholder="Your name"
                required
                value={form.name}
                onChange={handleChange}
              />
            </div>
            <div className="contact-field">
              <label className="contact-label" htmlFor="contact-email">Email</label>
              <input
                id="contact-email"
                name="email"
                type="email"
                className="contact-input"
                placeholder="you@example.com"
                required
                value={form.email}
                onChange={handleChange}
              />
            </div>
            <div className="contact-field">
              <label className="contact-label" htmlFor="contact-subject">Subject</label>
              <input
                id="contact-subject"
                name="subject"
                type="text"
                className="contact-input"
                placeholder="How can we help?"
                required
                value={form.subject}
                onChange={handleChange}
              />
            </div>
            <div className="contact-field">
              <label className="contact-label" htmlFor="contact-message">Message</label>
              <textarea
                id="contact-message"
                name="message"
                className="contact-input"
                rows={6}
                placeholder="Tell us more…"
                required
                value={form.message}
                onChange={handleChange}
                style={{ resize: 'vertical' }}
              />
            </div>
            {status === 'error' && (
              <div className="contact-error">{errorMsg}</div>
            )}
            <button type="submit" className="contact-submit" disabled={status === 'loading'}>
              {status === 'loading' ? 'Sending…' : 'Send Message'}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
