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


class TestAddToolErrorHint:
    def test_error_string_gets_hint_appended(self):
        result = zeus_agent._add_tool_error_hint("Error: folder not found")
        assert result.startswith("Error: folder not found")
        assert "alternative approach" in result

    def test_non_error_string_unchanged(self):
        result = zeus_agent._add_tool_error_hint("Written 1234 chars to /data/projects/foo/index.html")
        assert "alternative approach" not in result
        assert result == "Written 1234 chars to /data/projects/foo/index.html"

    def test_empty_string_unchanged(self):
        assert zeus_agent._add_tool_error_hint("") == ""

    def test_warning_string_unchanged(self):
        result = zeus_agent._add_tool_error_hint("Warning: something odd happened")
        assert "alternative approach" not in result
