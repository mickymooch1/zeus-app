# Self-Healing Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add retry and self-heal logic to the Zeus multi-agent pipeline so transient failures are recovered automatically, raw tracebacks never reach the user, and a failed Netlify deploy falls back to a zip download of the built site.

**Architecture:** Four additions to `zeus_agent.py`: `StageFailure` exception class, `_add_tool_error_hint` pure helper, `_run_stage_with_retry` async wrapper, and `_emit_stage_failure` async formatter. `_run_agent_loop` gets a one-line change to call `_add_tool_error_hint` on every tool result. `run_multi_agent`'s four `try/except` blocks are replaced with `_run_stage_with_retry` calls and `StageFailure` handlers.

**Tech Stack:** Python asyncio, `unittest.mock.AsyncMock`, `pytest-asyncio` (already installed).

---

## Task 1: `StageFailure` exception class

**Files:**
- Modify: `zeus-app/backend/zeus_agent.py` — insert before `_run_agent_loop` (~line 1399)
- Create: `zeus-app/backend/tests/test_agent_self_heal.py`

---

- [ ] **Step 1: Write the failing tests**

Create `zeus-app/backend/tests/test_agent_self_heal.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestStageFailure -v
```

Expected: `AttributeError: module 'zeus_agent' has no attribute 'StageFailure'`

- [ ] **Step 3: Add `StageFailure` to `zeus_agent.py`**

In `zeus-app/backend/zeus_agent.py`, find this line (it's the `def _build_memory_context` line just above `_run_agent_loop`):

```python
async def _run_agent_loop(
```

Insert the following block immediately before that line:

```python
class StageFailure(Exception):
    """Raised when a pipeline stage fails all retry attempts."""

    def __init__(self, stage: str, attempts: list[str]) -> None:
        self.stage = stage
        self.attempts = attempts  # one error string per attempt, truncated to 120 chars
        super().__init__(f"{stage} failed after {len(attempts)} attempt(s)")


```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestStageFailure -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd zeus-app/backend && git add zeus_agent.py tests/test_agent_self_heal.py && git commit -m "feat: add StageFailure exception class"
```

---

## Task 2: `_add_tool_error_hint` helper + wire into `_run_agent_loop`

**Files:**
- Modify: `zeus-app/backend/zeus_agent.py` — insert helper before `_run_agent_loop`; update tool-result append inside `_run_agent_loop` (~line 1507)
- Modify: `zeus-app/backend/tests/test_agent_self_heal.py`

---

- [ ] **Step 1: Write the failing tests**

Append to `test_agent_self_heal.py`:

```python
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
        # Only exact prefix "Error:" triggers the hint
        result = zeus_agent._add_tool_error_hint("Warning: something odd happened")
        assert "alternative approach" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestAddToolErrorHint -v
```

Expected: `AttributeError: module 'zeus_agent' has no attribute '_add_tool_error_hint'`

- [ ] **Step 3: Add `_add_tool_error_hint` to `zeus_agent.py`**

In `zeus-app/backend/zeus_agent.py`, find the `StageFailure` class you just added and insert the following immediately after it (before `async def _run_agent_loop`):

```python
def _add_tool_error_hint(result: str) -> str:
    """Append a retry hint to tool error results so Claude tries a different approach."""
    if isinstance(result, str) and result.startswith("Error:"):
        return (
            result
            + "\n\n[This tool call failed. Consider an alternative approach — "
            "different parameters, a different tool, or a different strategy "
            "to achieve the same goal.]"
        )
    return result


```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestAddToolErrorHint -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Wire `_add_tool_error_hint` into `_run_agent_loop`**

In `zeus-app/backend/zeus_agent.py`, inside `_run_agent_loop`, find this exact block in the tool-results loop (it's in the `for idx in sorted(tool_blocks):` loop):

```python
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb["id"],
                "content": result,
            })
```

Replace it with:

```python
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb["id"],
                "content": _add_tool_error_hint(result),
            })
```

- [ ] **Step 6: Run all self-heal tests to confirm no regressions**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py -v
```

Expected: 7 tests pass.

- [ ] **Step 7: Commit**

```bash
cd zeus-app/backend && git add zeus_agent.py tests/test_agent_self_heal.py && git commit -m "feat: add _add_tool_error_hint and wire into _run_agent_loop"
```

---

## Task 3: `_run_stage_with_retry` helper

**Files:**
- Modify: `zeus-app/backend/zeus_agent.py` — insert after `_run_agent_loop` (~line 1516), before `run_multi_agent`
- Modify: `zeus-app/backend/tests/test_agent_self_heal.py`

---

- [ ] **Step 1: Write the failing tests**

Append to `test_agent_self_heal.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestRunStageWithRetry -v
```

Expected: `AttributeError: module 'zeus_agent' has no attribute '_run_stage_with_retry'`

- [ ] **Step 3: Add `_run_stage_with_retry` to `zeus_agent.py`**

In `zeus-app/backend/zeus_agent.py`, find the line:

```python
async def run_multi_agent(
```

Insert the following block immediately before it:

```python
async def _run_stage_with_retry(
    stage_label: str,
    prompt: str,
    system_prompt: str,
    tools: list,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: "HistoryStore",
    max_turns: int = 30,
    max_tokens: int = 8000,
    collect_tool_results: bool = False,
    max_attempts: int = 3,
) -> str:
    """
    Run a pipeline stage with automatic retry on exception.

    On each retry, the error from the previous attempt is prepended to the
    prompt so the model can adjust its approach. Raw tracebacks are written
    to the log only — never stored in the attempts list.

    Raises StageFailure if all attempts fail.
    """
    errors: list[str] = []
    for attempt in range(max_attempts):
        if attempt > 0:
            truncated = errors[-1]
            current_prompt = (
                f"[Previous attempt failed: {truncated}. Try a different approach.]\n\n"
                + prompt
            )
            await on_message({
                "type": "text",
                "delta": (
                    f"\n\n⚠️ {stage_label} — attempt {attempt} failed, "
                    f"retrying ({attempt + 1}/{max_attempts})...\n"
                ),
            })
        else:
            current_prompt = prompt
        try:
            return await _run_agent_loop(
                prompt=current_prompt,
                system_prompt=system_prompt,
                tools=tools,
                on_message=on_message,
                history=history,
                stage_label=stage_label,
                max_turns=max_turns,
                max_tokens=max_tokens,
                collect_tool_results=collect_tool_results,
            )
        except Exception as exc:
            log.error(
                "%s attempt %d/%d failed: %s",
                stage_label, attempt + 1, max_attempts, exc,
                exc_info=True,
            )
            errors.append(str(exc)[:120])
    raise StageFailure(stage_label, errors)


```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestRunStageWithRetry -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run all self-heal tests**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py -v
```

Expected: 12 tests pass.

- [ ] **Step 6: Commit**

```bash
cd zeus-app/backend && git add zeus_agent.py tests/test_agent_self_heal.py && git commit -m "feat: add _run_stage_with_retry with error-context injection"
```

---

## Task 4: `_emit_stage_failure` helper

**Files:**
- Modify: `zeus-app/backend/zeus_agent.py` — insert `_STAGE_HINTS` dict and `_emit_stage_failure` immediately before `_run_stage_with_retry`
- Modify: `zeus-app/backend/tests/test_agent_self_heal.py`

---

- [ ] **Step 1: Write the failing tests**

Append to `test_agent_self_heal.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestEmitStageFailure -v
```

Expected: `AttributeError: module 'zeus_agent' has no attribute '_emit_stage_failure'`

- [ ] **Step 3: Add `_STAGE_HINTS` and `_emit_stage_failure` to `zeus_agent.py`**

In `zeus-app/backend/zeus_agent.py`, find the line:

```python
async def _run_stage_with_retry(
```

Insert the following block immediately before it:

```python
_STAGE_HINTS: dict[str, str] = {
    "planner": (
        "Try rephrasing the request with more specific details about the "
        "business type and location."
    ),
    "researcher": (
        "The sites Zeus tried to fetch may be unreachable. "
        "Retry in a moment, or simplify the research brief."
    ),
    "builder": (
        "Check that the build directory is writable and retry. "
        "Try simplifying the request — e.g. 'a basic 3-section site for [business]'."
    ),
}


async def _emit_stage_failure(
    exc: StageFailure,
    stage_key: str,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Stream a clean, structured failure message to the user."""
    hint = _STAGE_HINTS.get(
        stage_key,
        "Retry the task. If it keeps failing, try simplifying the request.",
    )
    attempts_text = "\n".join(
        f"• Attempt {i + 1}: {err}" for i, err in enumerate(exc.attempts)
    )
    msg = (
        f"\n\n❌ **{exc.stage} failed after {len(exc.attempts)} attempt(s).**\n\n"
        f"**What Zeus tried:**\n{attempts_text}\n\n"
        f"**What to do next:** {hint}\n"
    )
    await on_message({"type": "text", "delta": msg})


```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestEmitStageFailure -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run all self-heal tests**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py -v
```

Expected: 16 tests pass.

- [ ] **Step 6: Commit**

```bash
cd zeus-app/backend && git add zeus_agent.py tests/test_agent_self_heal.py && git commit -m "feat: add _emit_stage_failure with per-stage user-facing hints"
```

---

## Task 5: Refactor `run_multi_agent` — retry all stages + Deployer zip fallback

**Files:**
- Modify: `zeus-app/backend/zeus_agent.py` — rewrite the 4 stage blocks inside `run_multi_agent` (~lines 1608–1769)
- Modify: `zeus-app/backend/tests/test_agent_self_heal.py`

Context: the current `run_multi_agent` has 4 `try/except Exception` blocks — one per stage. Each is replaced with `_run_stage_with_retry`. The Deployer block gets additional logic: on `StageFailure`, call `_run_tool("ZipProject", ...)` directly and stream a download link.

---

- [ ] **Step 1: Write the failing tests**

Append to `test_agent_self_heal.py`:

```python
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

        # Pipeline should not crash — returns an error string
        assert isinstance(result, str)
        full_text = "".join(m.get("delta", "") for m in messages)
        assert "Deployment failed" in full_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestRunMultiAgentSelfHeal -v
```

Expected: tests fail because `run_multi_agent` still uses the old `try/except Exception` blocks, not `_run_stage_with_retry`.

- [ ] **Step 3: Replace Stage 1 (Planner) block in `run_multi_agent`**

In `zeus-app/backend/zeus_agent.py`, find and replace the entire Planner try/except block:

```python
    try:
        planner_output = await _run_agent_loop(
            prompt=f"Create a website brief for: {request}",
            system_prompt=planner_system,
            tools=[],
            on_message=on_message,
            history=history,
            stage_label="🧠 Planner Agent",
        )
    except Exception as exc:
        await on_message({"type": "text", "delta": f"\n\n❌ **Planner failed:** {exc}\n"})
        return f"Pipeline aborted: Planner failed — {exc}"
```

Replace with:

```python
    try:
        planner_output = await _run_stage_with_retry(
            stage_label="🧠 Planner Agent",
            prompt=f"Create a website brief for: {request}",
            system_prompt=planner_system,
            tools=[],
            on_message=on_message,
            history=history,
        )
    except StageFailure as exc:
        await _emit_stage_failure(exc, "planner", on_message)
        return f"Pipeline aborted: {exc}"
```

- [ ] **Step 4: Replace Stage 2 (Researcher) block in `run_multi_agent`**

Find and replace the entire Researcher try/except block:

```python
    try:
        researcher_output = await _run_agent_loop(
            prompt=researcher_prompt,
            system_prompt=researcher_system,
            tools=_RESEARCHER_TOOLS,
            on_message=on_message,
            history=history,
            stage_label="🔍 Researcher Agent",
        )
    except Exception as exc:
        await on_message({"type": "text", "delta": f"\n\n❌ **Researcher failed:** {exc}\n"})
        return f"Pipeline aborted: Researcher failed — {exc}"
```

Replace with:

```python
    try:
        researcher_output = await _run_stage_with_retry(
            stage_label="🔍 Researcher Agent",
            prompt=researcher_prompt,
            system_prompt=researcher_system,
            tools=_RESEARCHER_TOOLS,
            on_message=on_message,
            history=history,
        )
    except StageFailure as exc:
        await _emit_stage_failure(exc, "researcher", on_message)
        return f"Pipeline aborted: {exc}"
```

- [ ] **Step 5: Replace Stage 3 (Builder) block in `run_multi_agent`**

Find and replace the entire Builder try/except block:

```python
    try:
        builder_output = await _run_agent_loop(
            prompt=builder_prompt,
            system_prompt=builder_system,
            tools=_BUILDER_TOOLS,
            on_message=on_message,
            history=history,
            stage_label="🏗️ Builder Agent",
            max_tokens=32000,
            max_turns=40,
        )
    except Exception as exc:
        await on_message({"type": "text", "delta": f"\n\n❌ **Builder failed:** {exc}\n"})
        return f"Pipeline aborted: Builder failed — {exc}"
```

Replace with:

```python
    try:
        builder_output = await _run_stage_with_retry(
            stage_label="🏗️ Builder Agent",
            prompt=builder_prompt,
            system_prompt=builder_system,
            tools=_BUILDER_TOOLS,
            on_message=on_message,
            history=history,
            max_tokens=32000,
            max_turns=40,
        )
    except StageFailure as exc:
        await _emit_stage_failure(exc, "builder", on_message)
        return f"Pipeline aborted: {exc}"
```

- [ ] **Step 6: Replace Stage 4 (Deployer) block in `run_multi_agent`**

Find and replace the entire Deployer try/except block:

```python
    try:
        deployer_output = await _run_agent_loop(
            prompt=deployer_prompt,
            system_prompt=deployer_system,
            tools=_DEPLOYER_TOOLS,
            on_message=on_message,
            history=history,
            stage_label="🚀 Deployer Agent",
            collect_tool_results=True,
        )
    except Exception as exc:
        await on_message({"type": "text", "delta": f"\n\n❌ **Deployer failed:** {exc}\n"})
        return (
            f"Website built at /data/projects/{site_name}/ but deployment failed — {exc}\n"
            "You can deploy manually from the Builder's output."
        )
```

Replace with:

```python
    try:
        deployer_output = await _run_stage_with_retry(
            stage_label="🚀 Deployer Agent",
            prompt=deployer_prompt,
            system_prompt=deployer_system,
            tools=_DEPLOYER_TOOLS,
            on_message=on_message,
            history=history,
            collect_tool_results=True,
        )
    except StageFailure as exc:
        # Deployment failed — zip the built files as a fallback
        attempts_text = "\n".join(
            f"• Attempt {i + 1}: {err}" for i, err in enumerate(exc.attempts)
        )
        zip_result = _run_tool(
            "ZipProject",
            {"folder": _build_dir, "zip_name": f"{site_name}.zip"},
            history,
        )
        if isinstance(zip_result, str) and zip_result.startswith("DOWNLOAD_READY:"):
            filename = zip_result.split("\n", 1)[0].split(":", 1)[1].strip()
            download_url = f"/downloads/{filename}"
            msg = (
                f"\n\n⚠️ **Deployment failed after {len(exc.attempts)} attempts — "
                f"but your site was built successfully.**\n\n"
                f"**What Zeus tried:**\n{attempts_text}\n\n"
                f"Your files are ready to download: "
                f"[Download {site_name}.zip]({download_url})\n\n"
                f"To deploy manually: extract the zip and drag the folder into "
                f"[netlify.com/drop](https://app.netlify.com/drop).\n"
            )
            await on_message({"type": "text", "delta": msg})
            return download_url
        else:
            # Zip also failed
            msg = (
                f"\n\n❌ **Deployment failed after {len(exc.attempts)} attempts "
                f"and the zip fallback also failed.**\n\n"
                f"**What Zeus tried:**\n{attempts_text}\n\n"
                f"Your built files are at `{_build_dir}/` on the server.\n"
            )
            await on_message({"type": "text", "delta": msg})
            return f"Pipeline aborted: {exc}"
```

- [ ] **Step 7: Run the new tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_agent_self_heal.py::TestRunMultiAgentSelfHeal -v
```

Expected: 4 tests pass.

- [ ] **Step 8: Run the full test suite to confirm no regressions**

```bash
cd zeus-app/backend && python -m pytest tests/ -v
```

Expected: all tests pass (84 existing + 20 new = 104 total).

- [ ] **Step 9: Commit**

```bash
cd zeus-app/backend && git add zeus_agent.py tests/test_agent_self_heal.py && git commit -m "feat: wire self-heal retries into run_multi_agent with Deployer zip fallback"
```
