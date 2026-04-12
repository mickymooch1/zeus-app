import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

function ScheduledTaskRow({ task, token, onToggle, onDelete }) {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/${task.id}/toggle`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = await res.json();
      onToggle(updated);
    } catch {
      // revert optimistic update on error — parent handles state
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    onDelete(task.id); // optimistic
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/${task.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch {
      // revert: parent would need to re-fetch; for simplicity leave as deleted
    }
  };

  return (
    <div className={`scheduled-task-card${task.is_active ? '' : ' scheduled-task-card--paused'}`}>
      <div className="scheduled-task-card-header">
        <div className="scheduled-task-card-labels">
          <span className="scheduled-task-schedule-label">{task.schedule_label}</span>
          <span className={`scheduled-task-badge${task.is_active ? ' scheduled-task-badge--active' : ' scheduled-task-badge--paused'}`}>
            {task.is_active ? 'Active' : 'Paused'}
          </span>
        </div>
        <div className="scheduled-task-card-actions">
          <label className="scheduled-task-toggle" title={task.is_active ? 'Pause' : 'Activate'}>
            <input
              type="checkbox"
              checked={!!task.is_active}
              onChange={handleToggle}
              disabled={toggling}
            />
            <span className="scheduled-task-toggle-slider" />
          </label>
          <button
            className="task-delete-btn"
            onClick={handleDelete}
            disabled={deleting}
            title="Delete scheduled task"
          >
            ✕
          </button>
        </div>
      </div>
      <p className="scheduled-task-description">{task.task_description}</p>
      <div className="scheduled-task-meta">
        <span>Next run: {task.is_active ? formatDateTime(task.next_run) : '—'}</span>
        <span>Last run: {task.last_run ? formatDateTime(task.last_run) : 'Never'}</span>
      </div>
    </div>
  );
}

export function ScheduledTasksTab({ token }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [planError, setPlanError] = useState(false);
  const [fetchError, setFetchError] = useState('');

  // Create form state
  const [taskDesc, setTaskDesc] = useState('');
  const [scheduleInput, setScheduleInput] = useState('');
  const [parsedCron, setParsedCron] = useState(null); // {cron_expression, schedule_label}
  const [lastParsedInput, setLastParsedInput] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const fetchTasks = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setPlanError(true);
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to load scheduled tasks');
      const data = await res.json();
      setTasks(data);
    } catch (err) {
      setFetchError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Clear parse result if user edits the schedule input after parsing
  useEffect(() => {
    if (parsedCron && scheduleInput !== lastParsedInput) {
      setParsedCron(null);
    }
  }, [scheduleInput, parsedCron, lastParsedInput]);

  const handleParse = async () => {
    if (!scheduleInput.trim()) return;
    setParsing(true);
    setParseError('');
    setParsedCron(null);
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/parse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ natural_language: scheduleInput }),
      });
      const data = await res.json();
      if (!res.ok) {
        setParseError(data.detail || 'Could not parse schedule');
        return;
      }
      setParsedCron(data);
      setLastParsedInput(scheduleInput);
    } catch {
      setParseError('Could not parse schedule — try again');
    } finally {
      setParsing(false);
    }
  };

  const handleCreate = async () => {
    if (!parsedCron || !taskDesc.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          task_description: taskDesc,
          cron_expression: parsedCron.cron_expression,
          schedule_label: parsedCron.schedule_label,
          timezone: 'UTC',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 403) {
          setCreateError(data.detail || 'Scheduled tasks require a Pro plan or above — upgrade at zeusaidesign.com/pricing.');
        } else {
          setCreateError(data.detail || 'Failed to create task');
        }
        return;
      }
      // Reset form and add new task at top
      setTaskDesc('');
      setScheduleInput('');
      setParsedCron(null);
      setLastParsedInput('');
      setTasks((prev) => [data, ...prev]);
    } catch {
      setCreateError('Failed to create task — try again');
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = useCallback((updated) => {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }, []);

  const handleDelete = useCallback((taskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  }, []);

  if (planError) {
    return (
      <div className="upgrade-gate">
        <p>Scheduled tasks require a <strong>Pro plan</strong> or above.</p>
        <Link to="/pricing" className="btn btn-primary">Upgrade</Link>
      </div>
    );
  }

  return (
    <div className="scheduled-tasks-tab">
      {/* ── Create form ── */}
      <div className="scheduled-task-create-form">
        <h2 className="scheduled-task-create-title">Create Scheduled Task</h2>

        <textarea
          className="scheduled-task-textarea"
          placeholder="What should Zeus do? (e.g. Rebuild my bakery website)"
          value={taskDesc}
          onChange={(e) => setTaskDesc(e.target.value)}
          rows={3}
        />

        <div className="scheduled-task-parse-row">
          <input
            type="text"
            className="scheduled-task-schedule-input"
            placeholder="Describe your schedule (e.g. every Monday at 9am)"
            value={scheduleInput}
            onChange={(e) => setScheduleInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleParse()}
          />
          <button
            className="btn btn-secondary scheduled-task-parse-btn"
            onClick={handleParse}
            disabled={parsing || !scheduleInput.trim()}
          >
            {parsing ? <span className="spinner spinner--sm" /> : 'Parse ↺'}
          </button>
        </div>

        {parseError && (
          <div className="form-error">{parseError}</div>
        )}

        {parsedCron && (
          <div className="scheduled-task-parse-result">
            ✓ {parsedCron.schedule_label}
          </div>
        )}

        {parsedCron && (
          <button
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={creating || !taskDesc.trim()}
          >
            {creating ? <span className="spinner spinner--sm" /> : 'Create Task'}
          </button>
        )}

        {createError && (
          <div className="form-error form-error--banner">{createError}</div>
        )}
      </div>

      {/* ── Task list ── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <span className="spinner" />
        </div>
      ) : fetchError ? (
        <div className="form-error form-error--banner">{fetchError}</div>
      ) : tasks.length === 0 ? (
        <div className="tasks-empty">
          <p className="tasks-empty-icon">🗓</p>
          <p className="tasks-empty-title">No scheduled tasks yet.</p>
          <p className="tasks-empty-sub">Create one above.</p>
        </div>
      ) : (
        <div className="scheduled-tasks-list">
          {tasks.map((task) => (
            <ScheduledTaskRow
              key={task.id}
              task={task}
              token={token}
              onToggle={handleToggle}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
