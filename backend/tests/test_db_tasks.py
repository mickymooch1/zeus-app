import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_zeus.db"
    db.init_user_tables(path)
    return path


@pytest.fixture
def user_id():
    return "test-user-123"


class TestCreateTask:
    def test_returns_dict_with_expected_fields(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site for Acme")
        assert task["id"]
        assert task["user_id"] == user_id
        assert task["description"] == "Build site for Acme"
        assert task["status"] == "pending"
        assert task["result"] is None
        assert task["live_url"] is None
        assert task["created_at"]
        assert task["completed_at"] is None

    def test_id_is_unique(self, db_path, user_id):
        t1 = db.create_task(db_path, user_id, "Task A")
        t2 = db.create_task(db_path, user_id, "Task B")
        assert t1["id"] != t2["id"]


class TestUpdateTask:
    def test_updates_status(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site")
        db.update_task(db_path, task["id"], status="running")
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "running"

    def test_updates_result_and_live_url(self, db_path, user_id):
        from datetime import datetime, timezone
        task = db.create_task(db_path, user_id, "Build site")
        now = datetime.now(timezone.utc).isoformat()
        db.update_task(
            db_path, task["id"],
            status="done",
            result="Live at https://acme-corp.netlify.app",
            live_url="https://acme-corp.netlify.app",
            completed_at=now,
        )
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "done"
        assert updated["live_url"] == "https://acme-corp.netlify.app"
        assert updated["completed_at"] == now


class TestGetTask:
    def test_returns_none_for_missing_id(self, db_path):
        assert db.get_task(db_path, "nonexistent-id") is None

    def test_returns_task_by_id(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site")
        fetched = db.get_task(db_path, task["id"])
        assert fetched["id"] == task["id"]


class TestGetTasksForUser:
    def test_returns_empty_list_for_new_user(self, db_path):
        assert db.get_tasks_for_user(db_path, "no-tasks-user") == []

    def test_returns_only_user_tasks(self, db_path):
        db.create_task(db_path, "user-a", "Task for A")
        db.create_task(db_path, "user-b", "Task for B")
        tasks = db.get_tasks_for_user(db_path, "user-a")
        assert len(tasks) == 1
        assert tasks[0]["user_id"] == "user-a"

    def test_returns_newest_first(self, db_path, user_id):
        db.create_task(db_path, user_id, "First task")
        db.create_task(db_path, user_id, "Second task")
        tasks = db.get_tasks_for_user(db_path, user_id)
        assert tasks[0]["description"] == "Second task"


class TestFailStaleTasks:
    def test_marks_running_tasks_as_failed(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Stale task")
        db.update_task(db_path, task["id"], status="running")
        db.fail_stale_tasks(db_path)
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "failed"
        assert updated["completed_at"] is not None

    def test_does_not_touch_pending_or_done_tasks(self, db_path, user_id):
        pending = db.create_task(db_path, user_id, "Pending task")
        done = db.create_task(db_path, user_id, "Done task")
        db.update_task(db_path, done["id"], status="done")
        db.fail_stale_tasks(db_path)
        assert db.get_task(db_path, pending["id"])["status"] == "pending"
        assert db.get_task(db_path, done["id"])["status"] == "done"
