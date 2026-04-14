# Monthly Build Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce per-plan monthly website build limits (Free=0, Pro=5, Agency=10, Enterprise=20) tracked in SQLite, with admins bypassing all limits.

**Architecture:** Add a `builds` column to the existing `monthly_usage` table via a zero-downtime ALTER TABLE migration. Two new db.py functions read and increment the build count. `run_multi_agent()` in zeus_agent.py checks the limit before starting the pipeline (so failed builds count against the quota too — prevents gaming), and the existing enterprise-only gate is replaced by the new plan-aware gate that allows Pro/Agency/Enterprise with their respective limits.

**Tech Stack:** Python stdlib, SQLite (via existing `db.py` helpers), FastAPI (no new endpoints needed).

---

## Files changed

| Action | File | What changes |
|---|---|---|
| Modify | `backend/db.py` | Add `builds` column migration in `init_user_tables`; add `get_monthly_builds()` and `increment_builds_count()` |
| Modify | `backend/zeus_agent.py` | Add `_BUILD_LIMITS` dict; replace enterprise-only gate with plan+limit gate; increment builds at pipeline entry |
| Create | `backend/tests/test_build_limits.py` | 11 tests covering DB layer and pipeline gate |

---

## Task 1: DB layer — `builds` column and helper functions

**Files:**
- Modify: `backend/db.py` (inside `init_user_tables` and after `reset_monthly_usage`)
- Create: `backend/tests/test_build_limits.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_build_limits.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_build_limits.py -v
```

Expected: `AttributeError: module 'db' has no attribute 'get_monthly_builds'`

- [ ] **Step 3: Add the `builds` column migration and two helper functions to `db.py`**

**3a.** In `init_user_tables`, find the existing migration block:
```python
        # Migrate existing tables — ignore error if column already exists
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        except Exception:
            pass
```

Replace it with:
```python
        # Migrate existing tables — ignore error if column already exists
        for _migration in [
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE monthly_usage ADD COLUMN builds INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(_migration)
                conn.commit()
            except Exception:
                pass
```

**3b.** After the `reset_monthly_usage` function (around line 246), add:

```python
def get_monthly_builds(db_path: pathlib.Path, user_id: str, month: str) -> int:
    """Return build count for user in given month (YYYY-MM)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT builds FROM monthly_usage WHERE user_id = ? AND month = ?",
            (user_id, month),
        ).fetchone()
        return row["builds"] if row else 0
    finally:
        conn.close()


def increment_builds_count(db_path: pathlib.Path, user_id: str, month: str) -> None:
    """Upsert monthly_usage, incrementing builds by 1."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO monthly_usage (user_id, month, messages, builds)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(user_id, month) DO UPDATE SET builds = builds + 1
            """,
            (user_id, month),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_build_limits.py::TestGetMonthlyBuilds -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Student/zeus-app
git add backend/db.py backend/tests/test_build_limits.py
git commit -m "feat: add monthly build tracking to db — builds column and helpers"
```

---

## Task 2: Pipeline gate — enforce limits in `run_multi_agent`

**Files:**
- Modify: `backend/zeus_agent.py` (top of file for constants; inside `run_multi_agent`)
- Modify: `backend/tests/test_build_limits.py` (append new test class)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_build_limits.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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

        # If it reached _run_stage_with_retry, the gate passed
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

        # Gate must not have blocked — pipeline reached _run_stage_with_retry
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_build_limits.py::TestBuildLimitGate -v
```

Expected: various failures — `_BUILD_LIMITS` not defined, gate logic missing, free user not blocked.

- [ ] **Step 3: Add `_BUILD_LIMITS` constant near the top of `zeus_agent.py`**

Find `def _is_enterprise_or_admin(user: dict) -> bool:` (line ~47) and insert ABOVE it:

```python
# Monthly build limits per plan. Admins are always unlimited.
_BUILD_LIMITS: dict[str, int] = {
    "free":       0,
    "pro":        5,
    "agency":    10,
    "enterprise": 20,
}

_UPGRADE_HINT: dict[str, str] = {
    "free":       "Upgrade to Pro (£29/mo) for 5 builds/month",
    "pro":        "Upgrade to Agency (£79/mo) for 10 builds/month",
    "agency":     "Upgrade to Enterprise (£150/mo) for 20 builds/month",
    "enterprise": "Contact support to discuss higher limits",
}
```

- [ ] **Step 4: Replace the enterprise gate in `run_multi_agent` with the plan+limit gate**

Find this block in `run_multi_agent` (around line 1840):

```python
    # ── Enterprise gating ─────────────────────────────────────────────────────
    if user_id:
        try:
            import db as _db
            _db_path = _db.get_db_path()
            _user = _db.get_user_by_id(_db_path, user_id)
            if _user:
                if not _is_enterprise_or_admin(_user):
                    msg = (
                        "❌ **MultiAgentBuild requires an Enterprise plan.** "
                        "Upgrade at zeusaidesign.com/pricing to unlock this feature."
                    )
                    await on_message({"type": "text", "delta": msg})
                    return "Enterprise plan required."
        except Exception:
            log.warning("run_multi_agent: could not verify enterprise plan for user %s", user_id)
```

Replace it with:

```python
    # ── Build limit gate ──────────────────────────────────────────────────────
    if user_id:
        try:
            import db as _db
            from datetime import timezone as _tz
            _db_path = _db.get_db_path()
            _user = _db.get_user_by_id(_db_path, user_id)
            if _user:
                _is_admin = bool(_user.get("is_admin", 0))
                if not _is_admin:
                    _plan = _user.get("subscription_plan") or "free"
                    _limit = _BUILD_LIMITS.get(_plan, 0)
                    _month = datetime.now(_tz.utc).strftime("%Y-%m")
                    _builds_used = _db.get_monthly_builds(_db_path, user_id, _month)
                    if _builds_used >= _limit:
                        _hint = _UPGRADE_HINT.get(_plan, "")
                        if _limit == 0:
                            _msg = (
                                f"❌ **Website builds aren't included in the Free plan.** "
                                f"{_hint} at zeusaidesign.com/pricing."
                            )
                        else:
                            _msg = (
                                f"❌ **You've used all {_limit} of your monthly website builds** "
                                f"on the {_plan.capitalize()} plan. "
                                f"{_hint} at zeusaidesign.com/pricing."
                            )
                        await on_message({"type": "text", "delta": _msg})
                        return "Monthly build limit reached."
                    _db.increment_builds_count(_db_path, user_id, _month)
        except Exception:
            log.warning("run_multi_agent: could not verify build limit for user %s", user_id)
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_build_limits.py -v
```

Expected: `12 passed`

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/ --tb=short -q 2>&1 | tail -5
```

Expected: all 120 previously passing tests still pass (total now 132).

- [ ] **Step 7: Commit and push**

```bash
cd C:/Users/Student/zeus-app
git add backend/zeus_agent.py backend/tests/test_build_limits.py
git commit -m "feat: enforce monthly build limits per plan (Free=0, Pro=5, Agency=10, Enterprise=20)"
git push origin master
```

---

## Self-review

**Spec coverage:**

| Requirement | Covered by |
|---|---|
| Free = 0 builds | `_BUILD_LIMITS["free"] = 0` → blocked before pipeline |
| Pro = 5 builds/month | `_BUILD_LIMITS["pro"] = 5` + `get_monthly_builds` check |
| Agency = 10 builds/month | `_BUILD_LIMITS["agency"] = 10` |
| Enterprise = 20 builds/month | `_BUILD_LIMITS["enterprise"] = 20` |
| Track in DB per user per month | `increment_builds_count` + `builds` column in `monthly_usage` |
| Tell user when limit hit + suggest upgrade | `_msg` with `_UPGRADE_HINT` per plan |
| Admins unlimited | `_is_admin` check bypasses gate entirely |

**Placeholder scan:** None. All code blocks are complete.

**Type consistency:** `get_monthly_builds(db_path, user_id, month) -> int` and `increment_builds_count(db_path, user_id, month) -> None` used identically in tasks 1 and 2.

**Edge cases handled:**
- `user_id=None` (unauthenticated): gate skipped entirely (same as before)
- DB unreachable: `except Exception` catches it, logs warning, pipeline continues (fail open — same pattern as existing enterprise gate)
- Plan not in `_BUILD_LIMITS` (e.g. unexpected value): `.get(_plan, 0)` → treated as Free (0 builds)
- Existing `monthly_usage` rows without `builds` column: migration adds `DEFAULT 0`, so all existing rows read as 0
