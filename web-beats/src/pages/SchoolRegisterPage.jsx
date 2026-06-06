import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BACKEND_URL } from '../brand';
import KidsShell from '../components/KidsShell';

const YEAR_GROUPS = [
  'Nursery / Pre-school (ages 3–4)',
  'Reception (age 4–5)',
  'Year 1–2 (ages 5–7)',
  'Year 3–4 (ages 7–9)',
  'Year 5–6 (ages 9–11)',
  'Mixed age class',
];

export default function SchoolRegisterPage() {
  const [form, setForm] = useState({ school_name: '', teacher_name: '', email: '', password: '', year_group: '', country: 'UK' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.school_name || !form.teacher_name || !form.email || !form.password || !form.year_group) {
      setError('Please fill in all fields');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/auth/register/school`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');

      localStorage.setItem('zeus_token', data.token);
      window.location.href = '/kids';
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KidsShell>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 20px' }}>
        <div className="kids-card" style={{ maxWidth: 440, width: '100%' }}>
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>🏫</div>
            <h2 style={{ margin: '0 0 4px', fontSize: 22 }}>School Sign Up</h2>
            <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
              Safe AI music and stories for your class
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>School name</label>
              <input className="kids-input" placeholder="e.g. Sunflower Primary School" value={form.school_name} onChange={set('school_name')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Your name (teacher)</label>
              <input className="kids-input" placeholder="e.g. Ms Johnson" value={form.teacher_name} onChange={set('teacher_name')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>School email</label>
              <input className="kids-input" type="email" placeholder="you@school.sch.uk" value={form.email} onChange={set('email')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Year group</label>
              <select className="kids-select" value={form.year_group} onChange={set('year_group')}>
                <option value="">Select year group...</option>
                {YEAR_GROUPS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Password</label>
              <input className="kids-input" type="password" placeholder="At least 8 characters" value={form.password} onChange={set('password')} />
            </div>

            {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 13, margin: 0 }}>{error}</p>}

            <button type="submit" className="kids-btn kids-btn-primary" style={{ width: '100%', marginTop: 8 }} disabled={loading}>
              {loading ? '✨ Creating your account...' : '🏫 Create School Account'}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: 12, color: '#94a3b8', marginTop: 16, marginBottom: 0 }}>
            Already have an account? <Link to="/login" style={{ color: '#45b7d1', fontWeight: 700 }}>Log in</Link>
          </p>
          <p style={{ textAlign: 'center', fontSize: 11, color: '#cbd5e1', marginTop: 8, marginBottom: 0 }}>
            No individual child data is collected. <Link to="/privacy" style={{ color: '#94a3b8' }}>Privacy Policy</Link>
          </p>
        </div>
      </div>
    </KidsShell>
  );
}
