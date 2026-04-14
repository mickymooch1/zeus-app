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


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import zeus_agent


# Build limits by plan (mirrors _BUILD_LIMITS in zeus_agent.py)
_LIMITS = {"free": 0, "pro": 5, "agency": 10, "enterprise": 20}


def _make_user(plan: str, is_admin: bool = False, status: str = "active") -> dict:
    return {
        "id": "user-test",
        "email": "test@example.com",
        "subscription_plan": plan,
        "subscription_status": status,
        "is_admin": 1 if is_admin else 0,
    }


# Patches target zeus_agent.db.* (not db.*) because zeus_agent imports db at
# module level. If that import is ever changed to a local import, the patches
# must be updated to match.
class TestBuildLimitGate:
    @pytest.mark.asyncio
    async def test_free_user_blocked_immediately(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("free")),
            patch("zeus_agent.db.get_monthly_builds", return_value=0),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "Free plan" in combined or "free" in combined.lower()
        assert "upgrade" in combined.lower() or "Upgrade" in combined

    @pytest.mark.asyncio
    async def test_pro_user_blocked_at_limit(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("pro")),
            patch("zeus_agent.db.get_monthly_builds", return_value=5),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "5" in combined
        assert "upgrade" in combined.lower() or "Upgrade" in combined

    @pytest.mark.asyncio
    async def test_pro_user_allowed_below_limit(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("pro")),
            patch("zeus_agent.db.get_monthly_builds", return_value=4),
            patch("zeus_agent.db.increment_builds_count"),
            patch("zeus_agent._run_stage_with_retry", new=AsyncMock(side_effect=Exception("stop"))),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "monthly builds" not in combined.lower()

    @pytest.mark.asyncio
    async def test_agency_user_blocked_at_limit(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("agency")),
            patch("zeus_agent.db.get_monthly_builds", return_value=10),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "10" in combined
        assert "upgrade" in combined.lower() or "Upgrade" in combined

    @pytest.mark.asyncio
    async def test_enterprise_user_blocked_at_limit(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("enterprise")),
            patch("zeus_agent.db.get_monthly_builds", return_value=20),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "20" in combined

    @pytest.mark.asyncio
    async def test_admin_bypasses_limit(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("free", is_admin=True)),
            patch("zeus_agent.db.get_monthly_builds", return_value=999),
            patch("zeus_agent.db.increment_builds_count"),
            patch("zeus_agent._run_stage_with_retry", new=AsyncMock(side_effect=Exception("stop"))),
        ):
            result = await zeus_agent.run_multi_agent(
                "build a site", on_msg, MagicMock(), user_id="user-test"
            )

        combined = " ".join(m.get("delta", "") for m in messages if m.get("type") == "text")
        assert "monthly builds" not in combined.lower()
        assert "upgrade" not in combined.lower()

    @pytest.mark.asyncio
    async def test_increment_called_before_pipeline(self):
        """builds must be incremented before the pipeline starts — not after."""
        increment_calls = []

        with (
            patch("zeus_agent.db.get_db_path", return_value=MagicMock()),
            patch("zeus_agent.db.get_user_by_id", return_value=_make_user("pro")),
            patch("zeus_agent.db.get_monthly_builds", return_value=0),
            patch("zeus_agent.db.increment_builds_count",
                  side_effect=lambda *a, **kw: increment_calls.append(a)),
            patch("zeus_agent._run_stage_with_retry", new=AsyncMock(side_effect=Exception("stop early"))),
        ):
            await zeus_agent.run_multi_agent(
                "build a site", AsyncMock(), MagicMock(), user_id="user-test"
            )

        assert len(increment_calls) == 1, "increment_builds_count must be called exactly once"
