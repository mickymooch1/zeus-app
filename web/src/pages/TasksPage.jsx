import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ScheduledTasksTab } from '../components/ScheduledTasksTab';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const STATUS_BADGE = {
  pending: { label: '⏳ Pending',  className: 'badge-status badge-status--pending'  },
  running: { label: '🔄 Running',  className: 'badge-status badge-status--running'  },
  done:    { label: '✅ Done',     className: 'badge-status badge-status--done'     },
  failed:  { label: '❌ Failed',   className: 'badge-status badge-status--failed'   },
};

function TaskCard({ task, onDelete }) {
  const badge = STATUS_BADGE[task.status] || STATUS_BADGE.pending;
  const createdAt = new Date(task.created_at).toLocaleString();

  return (
    <div className={`task-card task-card--${task.status}`}>
      <div className="task-card-header">
        <span className="task-description">{task.description}</span>
        <span className={badge.className}>{badge.label}</span>
        <button className="task-delete-btn" onClick={() => onDelete(task.id)} title="Delete task">✕</button>
      </div>
      <div className="task-card-meta">Started {createdAt}</div>
      {task.status === 'done' && task.live_url && (
        <a
          href={task.live_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary btn-sm task-url-btn"
        >
          View Live Site →
        </a>
      )}
      {task.status === 'failed' && task.result && (
        <p className="task-error-note">{task.result.slice(0, 300)}</p>
      )}
    </div>
  );
}

function BackgroundTasksTab({ token }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const handleDelete = useCallback(async (taskId) => {
    try {
      await fetch(`${BACKEND_URL}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch {
      // silently ignore — task will reappear on next poll
    }
  }, [token]);

  const fetchTasks = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setError('enterprise');
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to load tasks');
      const data = await res.json();
      setTasks(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    const hasActive = tasks.some(
      (t) => t.status === 'pending' || t.status === 'running'
    );
    if (!hasActive) return;
    const id = setInterval(fetchTasks, 10_000);
    return () => clearInterval(id);
  }, [tasks, fetchTasks]);

  if (error === 'enterprise') {
    return (
      <div className="upgrade-gate">
        <p>Background tasks require an <strong>Enterprise</strong> plan.</p>
        <Link to="/pricing" className="btn btn-primary">Upgrade to Enterprise</Link>
      </div>
    );
  }

  if (error && error !== 'enterprise') {
    return <div className="form-error form-error--banner">{error}</div>;
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem' }}>
        <span className="spinner" />
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="tasks-empty">
        <p className="tasks-empty-icon">⚡</p>
        <p className="tasks-empty-title">No background tasks yet.</p>
        <p className="tasks-empty-sub">Ask Zeus to build a website and it will appear here.</p>
      </div>
    );
  }

  return (
    <div className="tasks-list">
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} onDelete={handleDelete} />
      ))}
    </div>
  );
}

export default function TasksPage() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState('background');

  return (
    <div className="tasks-page">
      <Navbar />
      <div className="page tasks-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" />
          <div className="orb orb-2" />
        </div>

        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          Tasks
        </h1>

        <div className="tasks-tab-bar">
          <button
            className={`tasks-tab-btn${activeTab === 'background' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('background')}
          >
            Background Tasks
          </button>
          <button
            className={`tasks-tab-btn${activeTab === 'scheduled' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('scheduled')}
          >
            Scheduled Tasks
          </button>
        </div>

        {activeTab === 'background' && <BackgroundTasksTab token={token} />}
        {activeTab === 'scheduled' && <ScheduledTasksTab token={token} />}
      </div>
    </div>
  );
}
