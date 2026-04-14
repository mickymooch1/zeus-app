import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import db


def _make_db(tmp_path: pathlib.Path) -> pathlib.Path:
    db_path = tmp_path / "zeus.db"
    db.init_user_tables(db_path)
    return db_path


class TestGetMonthlyBuilds:
    def test_returns_zero_when_no_record(self, tmp_path):
        db_path = _make_db(tmp_path)
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 0

    def test_returns_correct_count_after_increments(self, tmp_path):
        db_path = _make_db(tmp_path)
        db.increment_builds_count(db_path, "user-1", "2026-04")
        db.increment_builds_count(db_path, "user-1", "2026-04")
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 2

    def test_different_users_are_isolated(self, tmp_path):
        db_path = _make_db(tmp_path)
        db.increment_builds_count(db_path, "user-1", "2026-04")
        db.increment_builds_count(db_path, "user-1", "2026-04")
        db.increment_builds_count(db_path, "user-2", "2026-04")
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 2
        assert db.get_monthly_builds(db_path, "user-2", "2026-04") == 1

    def test_different_months_are_isolated(self, tmp_path):
        db_path = _make_db(tmp_path)
        db.increment_builds_count(db_path, "user-1", "2026-03")
        db.increment_builds_count(db_path, "user-1", "2026-03")
        db.increment_builds_count(db_path, "user-1", "2026-04")
        assert db.get_monthly_builds(db_path, "user-1", "2026-03") == 2
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 1

    def test_builds_and_messages_are_independent(self, tmp_path):
        """Incrementing messages must not affect builds, and vice versa."""
        db_path = _make_db(tmp_path)
        db.increment_usage(db_path, "user-1", "2026-04")   # messages
        db.increment_usage(db_path, "user-1", "2026-04")
        db.increment_builds_count(db_path, "user-1", "2026-04")
        assert db.get_monthly_usage(db_path, "user-1", "2026-04") == 2
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 1

    def test_increment_usage_does_not_reset_builds(self, tmp_path):
        """A messages increment on an existing row must not clobber builds."""
        db_path = _make_db(tmp_path)
        db.increment_builds_count(db_path, "user-1", "2026-04")  # builds=1, messages=0
        db.increment_usage(db_path, "user-1", "2026-04")         # messages=1
        assert db.get_monthly_builds(db_path, "user-1", "2026-04") == 1
        assert db.get_monthly_usage(db_path, "user-1", "2026-04") == 1
