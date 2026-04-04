import os
import pathlib
import json
from datetime import datetime
from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    CLINotFoundError,
    CLIConnectionError,
)

ZEUS_SYSTEM_PROMPT = """You are Zeus, a powerful AI assistant built to help run a web design business. You are resourceful, confident, and genuinely invested in the success of the business.

## Your capabilities

**Website Building**
- Build complete, modern, responsive websites from scratch
- Write clean HTML, CSS, and JavaScript — semantic markup, flexbox/grid, smooth animations
- Create landing pages, portfolios, business sites, e-commerce layouts
- Use vanilla HTML/CSS/JS by default; use frameworks when asked
- Always save files into a dedicated project folder named after the site
- When done, summarise what was built and how to open it

**File & Project Management**
- Read, write, edit, and organise any files on the local filesystem
- Set up project folder structures for new client work
- Search through codebases to find and fix issues
- Manage assets, templates, and reusable components

**Research & Web Search**
- Search the web for design trends, competitor sites, stock images, pricing benchmarks
- Fetch and summarise web pages, documentation, or client reference sites
- Look up tools, plugins, libraries, or anything needed for a project

**Content & Copywriting**
- Write website copy: headlines, taglines, about pages, service descriptions, CTAs
- Draft blog posts, case studies, and portfolio write-ups
- Generate SEO-friendly meta descriptions and page titles
- Adapt tone for different industries (corporate, creative, hospitality, etc.)

**Email Drafting**
- Draft professional client emails: proposals, follow-ups, project updates, invoices
- Write cold outreach emails to win new business
- Respond to client feedback diplomatically
- Create email templates for common scenarios

**Business Operations**
- Help price projects and write proposals
- Track what needs doing and suggest next steps
- Advise on tools, workflows, and how to grow a web design business
- Answer questions about freelancing, client management, and contracts

## Your personality
- Talk like a sharp, experienced colleague — direct, helpful, no filler
- Think out loud briefly before diving into big tasks so the user knows the plan
- Ask a quick follow-up if something is genuinely unclear; don't guess on important details
- Take pride in clean, well-crafted work and note key decisions made
- Be honest about limitations or when something needs more information

## Working style
- Brief plan → execute → summary of what was done
- Always save website files into a named project folder under the working directory
- Use real-world best practices: mobile-first, accessible markup, optimised assets
- When writing copy or emails, match the user's voice if examples are provided
"""

ZEUS_TOOLS = [
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "WebSearch", "WebFetch", "AskUserQuestion",
]


class HistoryStore:
    def __init__(self):
        self.dir = pathlib.Path.home() / ".zeus"
        self.dir.mkdir(exist_ok=True)
        self.sessions_file = self.dir / "sessions.json"
        self.history_file  = self.dir / "history.json"

    def log_turn(self, session_id: str, turn: int, role: str, text: str) -> None:
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "session_id": session_id, "turn": turn,
                "role": role, "text": text,
            }) + "\n")

    def save_session(self, session_id: str, started: datetime,
                     turns: int, preview: str) -> None:
        sessions = self._read_sessions()
        entry = {
            "id": session_id,
            "started": started.isoformat(),
            "turns": turns,
            "preview": preview[:80],
        }
        for i, s in enumerate(sessions):
            if s["id"] == session_id:
                sessions[i] = entry
                break
        else:
            sessions.append(entry)
        self.sessions_file.write_text(
            json.dumps(sessions, indent=2), encoding="utf-8")

    def list_sessions(self) -> list:
        return list(reversed(self._read_sessions()))

    def get_transcript(self, session_id: str) -> list:
        if not self.history_file.exists():
            return []
        results = []
        with self.history_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("session_id") == session_id:
                        results.append(entry)
                except json.JSONDecodeError:
                    pass
        return results

    def _read_sessions(self) -> list:
        if not self.sessions_file.exists():
            return []
        try:
            return json.loads(self.sessions_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []


async def run_turn_stream(
    prompt: str,
    session_id: str | None,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: HistoryStore,
) -> str | None:
    """
    Stream one Zeus turn. Calls on_message(dict) for each event.
    Returns the session_id (new or existing).
    """
    opts = ClaudeAgentOptions(
        system_prompt=ZEUS_SYSTEM_PROMPT,
        allowed_tools=ZEUS_TOOLS,
        permission_mode="acceptEdits",
        model="claude-opus-4-6",
        max_turns=60,
        cwd=os.environ.get("ZEUS_CWD", str(pathlib.Path.home())),
        **({"resume": session_id} if session_id else {}),
    )

    new_session_id: str | None = session_id
    zeus_text_parts: list[str] = []
    session_start = datetime.now()
    turn_number = len(history.get_transcript(session_id)) + 1 if session_id else 1

    try:
        async for message in query(prompt=prompt, options=opts):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                sid = message.data.get("session_id")
                if sid and sid != new_session_id:
                    new_session_id = sid
                    history.log_turn(new_session_id, turn_number, "user", prompt)
                    await on_message({"type": "session_id", "value": sid})

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        zeus_text_parts.append(block.text)
                        await on_message({"type": "text", "delta": block.text})
                    else:
                        block_type = type(block).__name__
                        if "ToolUse" in block_type:
                            tool_name = getattr(block, "name", "tool")
                            tool_input = getattr(block, "input", {})
                            path = tool_input.get("file_path") or tool_input.get("path", "")
                            await on_message({
                                "type": "tool",
                                "name": tool_name,
                                "path": path,
                                "status": "running",
                            })
                        elif "ToolResult" in block_type:
                            await on_message({
                                "type": "tool",
                                "name": "tool",
                                "status": "done",
                            })

            elif isinstance(message, ResultMessage):
                reason = message.stop_reason
                if reason and reason not in ("end_turn", "max_turns"):
                    await on_message({"type": "error", "message": f"Stopped: {reason}"})

    except CLINotFoundError:
        await on_message({
            "type": "error",
            "message": "Claude Code CLI not found. Run: pip install claude-agent-sdk",
        })
    except CLIConnectionError as exc:
        await on_message({"type": "error", "message": f"Connection error: {exc}"})

    # Save history
    if new_session_id:
        zeus_text = "".join(zeus_text_parts).strip()
        if zeus_text:
            turn_number += 1
            history.log_turn(new_session_id, turn_number, "zeus", zeus_text)
        history.save_session(new_session_id, session_start, turn_number, prompt)

    await on_message({"type": "done"})
    return new_session_id
