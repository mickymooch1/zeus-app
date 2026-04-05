import json
import logging
import os
import pathlib
import subprocess
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import anthropic
import httpx

log = logging.getLogger("zeus.agent")

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

TOOLS = [
    {
        "name": "Bash",
        "description": "Execute a bash command on the server.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "Read",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file, creating it and any parent directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "Edit",
        "description": "Replace an exact string in a file with new content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "old_string": {"type": "string", "description": "Exact string to find (must be unique in the file)"},
                "new_string": {"type": "string", "description": "Replacement string"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.html'"},
                "path": {"type": "string", "description": "Base directory to search (default: cwd)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search file contents with a regex pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "File or directory to search (default: cwd)"},
                "glob": {"type": "string", "description": "File name filter, e.g. '*.py'"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "WebFetch",
        "description": "Fetch the content of a URL and return it as text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
            },
            "required": ["url"],
        },
    },
]

def _safe_home() -> pathlib.Path:
    try:
        return pathlib.Path.home()
    except RuntimeError:
        return pathlib.Path("/tmp")


_CWD = os.environ.get("ZEUS_CWD", str(_safe_home()))


def _resolve(path: str) -> pathlib.Path:
    p = pathlib.Path(path)
    return p if p.is_absolute() else pathlib.Path(_CWD) / p


def _run_tool(name: str, inp: dict) -> str:
    try:
        if name == "Bash":
            r = subprocess.run(
                inp["command"], shell=True, capture_output=True,
                text=True, timeout=60, cwd=_CWD,
            )
            return (r.stdout + r.stderr).strip() or "(no output)"

        elif name == "Read":
            return _resolve(inp["file_path"]).read_text(encoding="utf-8")

        elif name == "Write":
            p = _resolve(inp["file_path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(inp["content"], encoding="utf-8")
            return f"Written {len(inp['content'])} chars to {p}"

        elif name == "Edit":
            p = _resolve(inp["file_path"])
            text = p.read_text(encoding="utf-8")
            old, new = inp["old_string"], inp["new_string"]
            if old not in text:
                return f"Error: old_string not found in {p}"
            p.write_text(text.replace(old, new, 1), encoding="utf-8")
            return f"Edited {p}"

        elif name == "Glob":
            base = _resolve(inp.get("path", "."))
            matches = sorted(base.glob(inp["pattern"]))
            return "\n".join(str(m) for m in matches) or "(no matches)"

        elif name == "Grep":
            path_arg = inp.get("path", ".")
            glob_arg = inp.get("glob", "")
            cmd = ["grep", "-r", "-n", inp["pattern"]]
            if glob_arg:
                cmd.append(f"--include={glob_arg}")
            cmd.append(path_arg)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=_CWD)
            return r.stdout.strip() or "(no matches)"

        elif name == "WebFetch":
            resp = httpx.get(inp["url"], timeout=20, follow_redirects=True)
            return resp.text[:8000]

        else:
            return f"Unknown tool: {name}"

    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except Exception as exc:
        return f"Error: {exc}"


class HistoryStore:
    def __init__(self):
        # ZEUS_DATA_DIR lets Railway/Docker operators override the storage path.
        # Fall back to /tmp/.zeus so it always works in containers where
        # pathlib.Path.home() may raise RuntimeError (no home in /etc/passwd).
        default = os.environ.get("ZEUS_DATA_DIR") or str(_safe_home() / ".zeus")
        self.dir = pathlib.Path(default)
        self.dir.mkdir(exist_ok=True, parents=True)
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

    def get_messages(self, session_id: str) -> list:
        msg_file = self.dir / "messages" / f"{session_id}.json"
        if not msg_file.exists():
            return []
        try:
            return json.loads(msg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def save_messages(self, session_id: str, messages: list) -> None:
        msg_dir = self.dir / "messages"
        msg_dir.mkdir(exist_ok=True)
        serialized = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                blocks = []
                for block in content:
                    if hasattr(block, "model_dump"):
                        blocks.append(block.model_dump())
                    elif isinstance(block, dict):
                        blocks.append(block)
                serialized.append({"role": msg["role"], "content": blocks})
            else:
                serialized.append(msg)
        (msg_dir / f"{session_id}.json").write_text(
            json.dumps(serialized, indent=2), encoding="utf-8")

    def _read_sessions(self) -> list:
        log.info("_read_sessions: sessions_file=%s exists=%s",
                 self.sessions_file, self.sessions_file.exists())
        if not self.sessions_file.exists():
            return []
        try:
            data = json.loads(self.sessions_file.read_text(encoding="utf-8"))
            log.info("_read_sessions: loaded %d entries", len(data) if isinstance(data, list) else -1)
            return data
        except Exception:
            log.exception("_read_sessions: failed to read %s", self.sessions_file)
            return []


async def run_turn_stream(
    prompt: str,
    session_id: str | None,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: HistoryStore,
) -> str | None:
    client = anthropic.AsyncAnthropic()

    if session_id:
        messages = history.get_messages(session_id)
    else:
        session_id = str(uuid.uuid4())
        messages = []
        await on_message({"type": "session_id", "value": session_id})

    messages.append({"role": "user", "content": prompt})

    session_start = datetime.now()
    zeus_text_parts: list[str] = []

    for _ in range(60):  # max agentic turns
        # tool_blocks: index -> {id, name, json, input}
        tool_blocks: dict[int, dict] = {}

        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=8096,
            system=ZEUS_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            async for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_blocks[event.index] = {
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "json": "",
                            "input": {},
                        }

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        zeus_text_parts.append(delta.text)
                        await on_message({"type": "text", "delta": delta.text})
                    elif delta.type == "input_json_delta":
                        if event.index in tool_blocks:
                            tool_blocks[event.index]["json"] += delta.partial_json

                elif etype == "content_block_stop":
                    if event.index in tool_blocks:
                        tb = tool_blocks[event.index]
                        try:
                            tb["input"] = json.loads(tb["json"]) if tb["json"] else {}
                        except json.JSONDecodeError:
                            tb["input"] = {}
                        path = (tb["input"].get("file_path")
                                or tb["input"].get("path")
                                or tb["input"].get("url", ""))
                        await on_message({
                            "type": "tool",
                            "name": tb["name"],
                            "path": path,
                            "status": "running",
                        })

            final = await stream.get_final_message()

        messages.append({"role": "assistant", "content": final.content})

        if final.stop_reason != "tool_use" or not tool_blocks:
            break

        # Execute tools and collect results
        tool_results = []
        for idx in sorted(tool_blocks):
            tb = tool_blocks[idx]
            result = _run_tool(tb["name"], tb["input"])
            path = (tb["input"].get("file_path")
                    or tb["input"].get("path")
                    or tb["input"].get("url", ""))
            await on_message({
                "type": "tool",
                "name": tb["name"],
                "path": path,
                "status": "done",
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb["id"],
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    # Persist conversation history
    history.save_messages(session_id, messages)
    turn_count = sum(1 for m in messages if m["role"] == "user")
    history.log_turn(session_id, turn_count, "user", prompt)
    zeus_text = "".join(zeus_text_parts).strip()
    if zeus_text:
        history.log_turn(session_id, turn_count, "zeus", zeus_text)
    history.save_session(session_id, session_start, turn_count, prompt)

    await on_message({"type": "done"})
    return session_id
