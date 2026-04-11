import os
import pathlib
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


class TestComputeNextRun:
    def test_returns_iso_string_in_future(self):
        import scheduler
        result = scheduler.compute_next_run("0 9 * * 1")
        # Should parse as a valid ISO datetime
        dt = datetime.fromisoformat(result)
        assert dt > datetime.now(timezone.utc)

    def test_daily_schedule(self):
        import scheduler
        result = scheduler.compute_next_run("0 0 * * *")
        dt = datetime.fromisoformat(result)
        assert dt > datetime.now(timezone.utc)

    def test_invalid_cron_raises(self):
        import scheduler
        with pytest.raises(Exception):
            scheduler.compute_next_run("not a cron expression")
