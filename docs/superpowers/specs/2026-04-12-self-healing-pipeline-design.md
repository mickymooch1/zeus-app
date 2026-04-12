# Self-Healing Agent Pipeline Design Spec

**Goal:** Add retry and self-heal logic to the Zeus multi-agent pipeline so that transient failures in any stage are recovered automatically, the user only hears about a problem after 3 genuine attempts, and a Deployer failure never wastes a completed build.

**Architecture:** A new `_run_stage_with_retry()` helper wraps every call to `_run_agent_loop`. On each retry the error from the previous attempt is prepended to the prompt so Claude can adjust its approach. A lightweight tool-error hint is injected into `_run_agent_loop` when a tool returns an `"Error:"` string, nudging Claude to try differently. The Deployer gets a special fallback: after 3 deploy failures it zips the built files and gives the user a download link. All raw tracebacks stay in logs; users see a clean structured summary.

**Tech Stack:** Python asyncio, existing `_run_agent_loop`, `_run_tool`, `ZipProject` tool, Python `logging`.

---

## 1. New exception class: `StageFailure`

Defined at module level in `zeus_agent.py`, above `_run_stage_with_retry`.

```python
class StageFailure(Exception):
    """Raised when a pipeline stage fails all retry attempts."""

    def __init__(self, stage: str, attempts: list[str]) -> None:
        self.stage = stage
        self.attempts = attempts  # one error string per attempt, max 3
        super().__init__(f"{stage} failed after {len(attempts)} attempt(s)")
```

`attempts` is a list of error strings — one per attempt, truncated to 120 characters each — so the caller can format a clean bullet list without worrying about multi-line tracebacks leaking through.

---

## 2. New helper: `_run_stage_with_retry()`

Added to `zeus_agent.py` immediately before `run_multi_agent`.

### Signature

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
```

### Behaviour

- Attempts the stage up to `max_attempts` times.
- On attempt 1, passes `prompt` unchanged.
- On all subsequent attempts (2, 3, …), prepends a context line to the prompt:
  ```
  [Previous attempt failed: {truncated_error}. Try a different approach.]

  {original_prompt}
  ```
- Between retries, streams a brief notice to the user:
  ```
  ⚠️ {stage_label} — attempt {n} failed, retrying ({attempt+1}/{max_attempts})...
  ```
- Accumulates errors in a local list.
- If all attempts raise, raises `StageFailure(stage_label, errors)`.
- Each attempt error is captured from the exception message and truncated to 120 characters before storing.
- Raw tracebacks are written to `log.error(...)` with `exc_info=True` — never stored in the attempts list.

### Retry trigger

An attempt is considered failed when `_run_agent_loop` raises any `Exception`. Normal completion (including an agent that produced an empty string) is not retried by this helper — that's the existing behaviour.

---

## 3. Change: tool-error hints in `_run_agent_loop`

In the tool-result loop inside `_run_agent_loop` (where `_run_tool` is called and results are appended):

**Before:**
```python
tool_results.append({
    "type": "tool_result",
    "tool_use_id": tb["id"],
    "content": result,
})
```

**After:**
```python
content = result
if isinstance(result, str) and result.startswith("Error:"):
    content = (
        result
        + "\n\n[This tool call failed. Consider an alternative approach — "
        "different parameters, a different tool, or a different strategy "
        "to achieve the same goal.]"
    )
tool_results.append({
    "type": "tool_result",
    "tool_use_id": tb["id"],
    "content": content,
})
```

The hint is invisible to the user (it's in conversation history, not streamed). It applies to all tool calls in all agent loops — not just the pipeline stages.

---

## 4. Changes to `run_multi_agent`

Each of the four `try/except` blocks around stage calls is replaced with a call to `_run_stage_with_retry`. The `except Exception` blocks are replaced with `except StageFailure`.

### Stages 1–3 (Planner, Researcher, Builder)

On `StageFailure`, stream a structured failure message and return early. The message format:

```
❌ **{stage} failed after {n} attempts.**

**What Zeus tried:**
• Attempt 1: {error_1}
• Attempt 2: {error_2}
• Attempt 3: {error_3}

**What to do next:** {stage_specific_hint}
```

Stage-specific hints:

| Stage | Hint |
|---|---|
| Planner | "Try rephrasing the request with more specific details about the business type and location." |
| Researcher | "The sites Zeus tried to fetch may be unreachable. Retry in a moment, or simplify the research brief." |
| Builder | "Check that the build directory is writable and retry. Try simplifying the request — e.g. 'a basic 3-section site for [business]'." |

### Stage 4 (Deployer) — zip fallback

On `StageFailure` from the Deployer:

1. Call `_run_tool("ZipProject", {"folder": _build_dir, "zip_name": f"{site_name}.zip"}, history)` directly.
2. Extract the `DOWNLOAD_READY:{filename}` token to build the download URL: `/downloads/{filename}`.
3. If zip succeeds, stream:

```
⚠️ **Deployment failed after 3 attempts — but your site was built successfully.**

**What Zeus tried:**
• Attempt 1: {error_1}
• Attempt 2: {error_2}
• Attempt 3: {error_3}

Your files are ready to download: [Download {site_name}.zip]({download_url})

To deploy manually: extract the zip and drag the folder into netlify.com/drop.
```

4. If the zip step itself fails, stream a plain error and return the error string.
5. Return the download URL string as the pipeline result (so background task email includes it).

---

## 5. Stage call refactor summary

Each stage in `run_multi_agent` goes from:

```python
try:
    planner_output = await _run_agent_loop(
        prompt=...,
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

To:

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

`_emit_stage_failure(exc, stage_key, on_message)` is a small private async helper that formats and streams the failure message using the stage-specific hint table. It takes a `stage_key` string (`"planner"`, `"researcher"`, `"builder"`) to look up the right hint.

---

## 6. Files changed

| Action | File | Change |
|---|---|---|
| Modify | `zeus-app/backend/zeus_agent.py` | Add `StageFailure`, `_run_stage_with_retry`, `_emit_stage_failure`; update `_run_agent_loop` tool-error hint; refactor 4 stage calls in `run_multi_agent` |

No other files change. No new dependencies.

---

## 7. Error handling summary

| Scenario | Behaviour |
|---|---|
| `_run_agent_loop` raises (API error, timeout, overload) | `_run_stage_with_retry` catches, logs traceback, retries with error context injected |
| Tool returns `"Error: ..."` string | Hint appended to tool result; Claude adapts; no retry at stage level |
| Planner/Researcher/Builder fails 3× | `StageFailure` raised → `_emit_stage_failure` → clean message → pipeline returns |
| Deployer fails 3× | `StageFailure` caught → zip built files → download URL streamed to user |
| Zip step also fails | Plain error message streamed; pipeline returns error string |
| Background task uses `run_multi_agent` | Same retry logic applies — `_handle_create_background_task` is unchanged |
| Scheduled task uses `_handle_create_background_task` | Same retry logic applies transitively |
