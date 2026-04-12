import pytest
import zeus_agent


class TestStageFailure:
    def test_stage_and_attempts_accessible(self):
        exc = zeus_agent.StageFailure("🧠 Planner Agent", ["err1", "err2", "err3"])
        assert exc.stage == "🧠 Planner Agent"
        assert exc.attempts == ["err1", "err2", "err3"]

    def test_str_includes_stage_and_count(self):
        exc = zeus_agent.StageFailure("🏗️ Builder Agent", ["x", "y"])
        assert "Builder Agent" in str(exc)
        assert "2" in str(exc)

    def test_is_exception_subclass(self):
        exc = zeus_agent.StageFailure("stage", ["e"])
        assert isinstance(exc, Exception)
