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


from unittest.mock import AsyncMock, MagicMock, patch


class TestRunStageWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        messages = []
        async def on_msg(m): messages.append(m)

        with patch("zeus_agent._run_agent_loop", new=AsyncMock(return_value="planner output")):
            result = await zeus_agent._run_stage_with_retry(
                stage_label="🧠 Planner Agent",
                prompt="build a site",
                system_prompt="you are planner",
                tools=[],
                on_message=on_msg,
                history=MagicMock(),
            )

        assert result == "planner output"
        assert not any("retrying" in str(m.get("delta", "")) for m in messages)

    @pytest.mark.asyncio
    async def test_injects_error_context_on_retry(self):
        call_prompts = []

        async def fake_loop(prompt, **kwargs):
            call_prompts.append(prompt)
            if len(call_prompts) == 1:
                raise RuntimeError("API overloaded")
            return "success on retry"

        messages = []
        async def on_msg(m): messages.append(m)

        with patch("zeus_agent._run_agent_loop", side_effect=fake_loop):
            result = await zeus_agent._run_stage_with_retry(
                stage_label="🧠 Planner Agent",
                prompt="build a site",
                system_prompt="",
                tools=[],
                on_message=on_msg,
                history=MagicMock(),
            )

        assert result == "success on retry"
        assert "Previous attempt failed" in call_prompts[1]
        assert "API overloaded" in call_prompts[1]
        assert any("retrying" in str(m.get("delta", "")) for m in messages)

    @pytest.mark.asyncio
    async def test_raises_stage_failure_after_all_attempts(self):
        async def always_fails(prompt, **kwargs):
            raise RuntimeError("timeout")

        async def on_msg(m): pass

        with patch("zeus_agent._run_agent_loop", side_effect=always_fails):
            with pytest.raises(zeus_agent.StageFailure) as exc_info:
                await zeus_agent._run_stage_with_retry(
                    stage_label="🏗️ Builder Agent",
                    prompt="build",
                    system_prompt="",
                    tools=[],
                    on_message=on_msg,
                    history=MagicMock(),
                    max_attempts=3,
                )

        exc = exc_info.value
        assert exc.stage == "🏗️ Builder Agent"
        assert len(exc.attempts) == 3
        assert all("timeout" in e for e in exc.attempts)

    @pytest.mark.asyncio
    async def test_errors_truncated_to_120_chars(self):
        long_error = "x" * 300

        async def always_fails(prompt, **kwargs):
            raise RuntimeError(long_error)

        async def on_msg(m): pass

        with patch("zeus_agent._run_agent_loop", side_effect=always_fails):
            with pytest.raises(zeus_agent.StageFailure) as exc_info:
                await zeus_agent._run_stage_with_retry(
                    stage_label="stage",
                    prompt="p",
                    system_prompt="",
                    tools=[],
                    on_message=on_msg,
                    history=MagicMock(),
                    max_attempts=1,
                )

        assert len(exc_info.value.attempts[0]) <= 120

    @pytest.mark.asyncio
    async def test_retry_notice_streamed_between_attempts(self):
        call_count = 0

        async def fails_twice(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("err")
            return "ok"

        messages = []
        async def on_msg(m): messages.append(m)

        with patch("zeus_agent._run_agent_loop", side_effect=fails_twice):
            await zeus_agent._run_stage_with_retry(
                stage_label="🔍 Researcher Agent",
                prompt="research",
                system_prompt="",
                tools=[],
                on_message=on_msg,
                history=MagicMock(),
                max_attempts=3,
            )

        retry_messages = [m for m in messages if "retrying" in str(m.get("delta", ""))]
        assert len(retry_messages) == 2  # one per failed attempt


class TestEmitStageFailure:
    @pytest.mark.asyncio
    async def test_planner_failure_includes_hint(self):
        exc = zeus_agent.StageFailure("🧠 Planner Agent", ["timeout", "API error", "max_tokens hit"])
        messages = []
        async def on_msg(m): messages.append(m)

        await zeus_agent._emit_stage_failure(exc, "planner", on_msg)

        full_text = "".join(m.get("delta", "") for m in messages)
        assert "Planner Agent" in full_text
        assert "3 attempt" in full_text
        assert "• Attempt 1: timeout" in full_text
        assert "• Attempt 2: API error" in full_text
        assert "• Attempt 3: max_tokens hit" in full_text
        assert "rephrasing" in full_text  # planner-specific hint

    @pytest.mark.asyncio
    async def test_researcher_failure_includes_hint(self):
        exc = zeus_agent.StageFailure("🔍 Researcher Agent", ["connection refused"])
        messages = []
        async def on_msg(m): messages.append(m)

        await zeus_agent._emit_stage_failure(exc, "researcher", on_msg)

        full_text = "".join(m.get("delta", "") for m in messages)
        assert "unreachable" in full_text  # researcher-specific hint

    @pytest.mark.asyncio
    async def test_builder_failure_includes_hint(self):
        exc = zeus_agent.StageFailure("🏗️ Builder Agent", ["permission denied"])
        messages = []
        async def on_msg(m): messages.append(m)

        await zeus_agent._emit_stage_failure(exc, "builder", on_msg)

        full_text = "".join(m.get("delta", "") for m in messages)
        assert "writable" in full_text  # builder-specific hint

    @pytest.mark.asyncio
    async def test_unknown_stage_key_uses_fallback_hint(self):
        exc = zeus_agent.StageFailure("Unknown Stage", ["err"])
        messages = []
        async def on_msg(m): messages.append(m)

        await zeus_agent._emit_stage_failure(exc, "unknown_key", on_msg)

        full_text = "".join(m.get("delta", "") for m in messages)
        assert "Retry" in full_text  # fallback hint


import pathlib


class TestRunMultiAgentSelfHeal:
    @pytest.mark.asyncio
    async def test_planner_failure_returns_pipeline_aborted(self):
        messages = []
        async def on_msg(m): messages.append(m)

        stage_failure = zeus_agent.StageFailure(
            "🧠 Planner Agent", ["err1", "err2", "err3"]
        )

        with patch("zeus_agent._run_stage_with_retry", new=AsyncMock(side_effect=stage_failure)):
            result = await zeus_agent.run_multi_agent("build a site", on_msg, MagicMock())

        assert result.startswith("Pipeline aborted:")
        full_text = "".join(m.get("delta", "") for m in messages)
        assert "failed after 3" in full_text

    @pytest.mark.asyncio
    async def test_researcher_failure_returns_pipeline_aborted(self):
        messages = []
        async def on_msg(m): messages.append(m)

        planner_out = "SITE_NAME: test-biz\nBusiness: Test business\n"
        researcher_failure = zeus_agent.StageFailure(
            "🔍 Researcher Agent", ["connection refused"]
        )

        call_count = 0
        async def fake_retry(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return planner_out
            raise researcher_failure

        with patch("zeus_agent._run_stage_with_retry", side_effect=fake_retry):
            result = await zeus_agent.run_multi_agent("build a site", on_msg, MagicMock())

        assert result.startswith("Pipeline aborted:")

    @pytest.mark.asyncio
    async def test_deployer_failure_triggers_zip_fallback(self):
        messages = []
        async def on_msg(m): messages.append(m)

        planner_out = "SITE_NAME: my-bakery\nBusiness: Bakery in Leeds\n"
        deployer_failure = zeus_agent.StageFailure(
            "🚀 Deployer Agent", ["HTTP 503", "connection reset", "timeout"]
        )

        call_count = 0
        async def fake_retry(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return planner_out       # Planner
            if call_count == 2:
                return "research output" # Researcher
            if call_count == 3:
                return "builder output"  # Builder
            raise deployer_failure       # Deployer

        zip_result = "DOWNLOAD_READY:abc123_my-bakery.zip\nZipped 3 files from 'my-bakery'"

        with patch("zeus_agent._run_stage_with_retry", side_effect=fake_retry), \
             patch("zeus_agent._run_tool", return_value=zip_result), \
             patch.object(pathlib.Path, "exists", return_value=True):
            result = await zeus_agent.run_multi_agent("build a bakery site", on_msg, MagicMock())

        full_text = "".join(m.get("delta", "") for m in messages)
        assert "Deployment failed after 3 attempts" in full_text
        assert "built successfully" in full_text
        assert "HTTP 503" in full_text
        assert "Download" in full_text
        assert "abc123_my-bakery.zip" in full_text

    @pytest.mark.asyncio
    async def test_deployer_failure_zip_also_fails_returns_error(self):
        messages = []
        async def on_msg(m): messages.append(m)

        planner_out = "SITE_NAME: my-shop\nBusiness: Shop\n"
        deployer_failure = zeus_agent.StageFailure(
            "🚀 Deployer Agent", ["err"]
        )

        call_count = 0
        async def fake_retry(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return planner_out
            if call_count == 2:
                return "research output"
            if call_count == 3:
                return "builder output"
            raise deployer_failure

        with patch("zeus_agent._run_stage_with_retry", side_effect=fake_retry), \
             patch("zeus_agent._run_tool", return_value="Error: folder does not exist"), \
             patch.object(pathlib.Path, "exists", return_value=True):
            result = await zeus_agent.run_multi_agent("build a shop site", on_msg, MagicMock())

        assert isinstance(result, str)
        full_text = "".join(m.get("delta", "") for m in messages)
        assert "Deployment failed" in full_text
