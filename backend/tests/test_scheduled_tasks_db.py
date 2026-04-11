import os
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


def _db(tmp_path):
    """Return a fresh db_path inside tmp_path."""
    import db
    db._db_initialised = False
    os.environ["ZEUS_DATA_DIR"] = str(tmp_path)
    path = db.get_db_path()
    db._db_initialised = False
    return path


class TestScheduledTasksDb:
    def test_create_and_get(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(
            db_path,
            user_id="user-1",
            task_description="Rebuild my website",
            cron_expression="0 9 * * 1",
            schedule_label="Every Monday at 9am",
            next_run="2026-04-14T09:00:00+00:00",
        )
        assert task["user_id"] == "user-1"
        assert task["task_description"] == "Rebuild my website"
        assert task["cron_expression"] == "0 9 * * 1"
        assert task["schedule_label"] == "Every Monday at 9am"
        assert task["is_active"] == 1
        assert task["last_run"] is None
        assert task["timezone"] == "UTC"
        assert "id" in task
        assert "created_at" in task

    def test_get_scheduled_tasks_for_user(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Mondays 9am", "2026-04-14T09:00:00+00:00")
        db.create_scheduled_task(db_path, "user-1", "Task B", "0 10 * * 2", "Tuesdays 10am", "2026-04-15T10:00:00+00:00")
        db.create_scheduled_task(db_path, "user-2", "Task C", "0 8 * * 3", "Wednesdays 8am", "2026-04-16T08:00:00+00:00")
        tasks = db.get_scheduled_tasks_for_user(db_path, "user-1")
        assert len(tasks) == 2
        # most recent first
        assert tasks[0]["task_description"] == "Task B"

    def test_get_all_active_scheduled_tasks(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        t1 = db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        t2 = db.create_scheduled_task(db_path, "user-2", "Task B", "0 10 * * 2", "Label", "2026-04-15T10:00:00+00:00")
        db.update_scheduled_task(db_path, t1["id"], is_active=0)
        tasks = db.get_all_active_scheduled_tasks(db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == t2["id"]

    def test_update_scheduled_task(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        db.update_scheduled_task(db_path, task["id"], is_active=0, last_run="2026-04-14T09:00:01+00:00")
        updated = db.get_scheduled_task(db_path, task["id"])
        assert updated["is_active"] == 0
        assert updated["last_run"] == "2026-04-14T09:00:01+00:00"

    def test_delete_scheduled_task(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        result = db.delete_scheduled_task(db_path, task["id"], "user-1")
        assert result is True
        assert db.get_scheduled_task(db_path, task["id"]) is None

    def test_delete_wrong_user_returns_false(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        result = db.delete_scheduled_task(db_path, task["id"], "user-2")
        assert result is False
        assert db.get_scheduled_task(db_path, task["id"]) is not None

    def test_count_active_scheduled_tasks(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        t1 = db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        db.create_scheduled_task(db_path, "user-1", "Task B", "0 10 * * 2", "Label", "2026-04-15T10:00:00+00:00")
        db.create_scheduled_task(db_path, "user-2", "Task C", "0 8 * * 3", "Label", "2026-04-16T08:00:00+00:00")
        db.update_scheduled_task(db_path, t1["id"], is_active=0)
        assert db.count_active_scheduled_tasks(db_path, "user-1") == 1
        assert db.count_active_scheduled_tasks(db_path, "user-2") == 1
