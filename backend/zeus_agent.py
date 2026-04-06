import json
import logging
import os
import pathlib
import sqlite3
import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any

print("zeus_agent.py: importing anthropic", file=sys.stderr, flush=True)
import anthropic
print("zeus_agent.py: anthropic ok", file=sys.stderr, flush=True)

import httpx

log = logging.getLogger("zeus.agent")

def _make_anthropic_client() -> anthropic.AsyncAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to Railway → Service → Variables."
        )
    return anthropic.AsyncAnthropic(api_key=api_key)

_anthropic_client: anthropic.AsyncAnthropic | None = None

def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = _make_anthropic_client()
    return _anthropic_client

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

## Memory & Learning — use these tools proactively

You have a persistent memory system that compounds over time. Use it without being asked.

**SaveMemory(category, content)** — call this whenever you learn something worth keeping:
- Client preferences, budget range, communication style, industry quirks
- Design patterns that worked well ("bold hero + minimal nav suits fitness brands")
- Pricing that was accepted or rejected and why
- Business insights, workflow improvements, what got results

**SearchMemory(query, category)** — search before starting any substantial task.
Example: before writing copy for a restaurant, search "restaurant" to recall past learnings.

**UpsertClient(name, ...)** — save client details as you learn them (industry, location,
style preferences, notes). Update whenever new information comes up.

**GetClient(name)** — pull a client's full profile before starting work for them.

**ListClients()** — get an overview of all clients on the books.

**UpsertProject(name, ...)** — log every website you build: client, live URL, folder,
budget, status. Update status when a project is delivered or goes to maintenance.

**ListProjects(status, client_name)** — review past work before quoting similar jobs.

The goal is to get smarter with every conversation. Save learnings freely.
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
    # ── Memory & intelligence tools ────────────────────────────────────────────
    {
        "name": "SaveMemory",
        "description": (
            "Save a persistent learning or insight to your memory database. "
            "Call proactively whenever you learn something useful: client preferences, "
            "industry insights, pricing outcomes, design decisions, business learnings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["client", "industry", "design", "pricing", "business", "general"],
                    "description": "Category for organisation and filtering",
                },
                "content": {
                    "type": "string",
                    "description": "The learning to store. Be specific and concrete.",
                },
            },
            "required": ["category", "content"],
        },
    },
    {
        "name": "SearchMemory",
        "description": (
            "Search your persistent memory for relevant knowledge. "
            "Use at the start of tasks to recall what you know about a client, "
            "industry, design pattern, or topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
                "category": {
                    "type": "string",
                    "enum": ["client", "industry", "design", "pricing", "business", "general", "all"],
                    "description": "Filter by category, or 'all' for everything (default: all)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "UpsertClient",
        "description": (
            "Create or update a client profile. Call whenever you learn details about "
            "a client — industry, location, contact, style preferences, notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":       {"type": "string", "description": "Client/business name (unique key)"},
                "industry":   {"type": "string"},
                "location":   {"type": "string"},
                "email":      {"type": "string"},
                "style_pref": {"type": "string", "description": "Design style preferences"},
                "notes":      {"type": "string", "description": "Any other relevant notes"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "GetClient",
        "description": "Retrieve a client's full profile. Use before starting any work for a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Client name (partial match supported)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ListClients",
        "description": "List all clients in the database.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "UpsertProject",
        "description": (
            "Create or update a project record. Track every site you build: "
            "client, live URL, local folder, budget, status, notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":        {"type": "string", "description": "Project name (unique key)"},
                "client_name": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["active", "delivered", "maintenance", "cancelled"],
                },
                "url":    {"type": "string", "description": "Live website URL"},
                "folder": {"type": "string", "description": "Local folder path"},
                "budget": {"type": "number", "description": "Budget in GBP"},
                "notes":  {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ListProjects",
        "description": "List tracked projects, optionally filtered by client or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["active", "delivered", "maintenance", "cancelled", "all"],
                },
            },
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


def _run_tool(name: str, inp: dict, history: "HistoryStore | None" = None) -> str:
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

        # ── Memory & intelligence tools ────────────────────────────────────────
        elif name == "SaveMemory":
            if not history:
                return "Error: memory store not available"
            row_id = history.save_memory(inp["category"], inp["content"])
            return f"Memory saved (id={row_id})"

        elif name == "SearchMemory":
            if not history:
                return "Error: memory store not available"
            results = history.search_memory(inp["query"], inp.get("category", "all"))
            if not results:
                return "No matching memories found."
            return "\n".join(
                f"[{r['category']}] {r['content']}  ({r['created'][:10]})"
                for r in results
            )

        elif name == "UpsertClient":
            if not history:
                return "Error: memory store not available"
            name_val = inp.pop("name")
            history.upsert_client(name_val, **inp)
            return f"Client '{name_val}' saved."

        elif name == "GetClient":
            if not history:
                return "Error: memory store not available"
            client = history.get_client(inp["name"])
            if not client:
                return f"No client matching '{inp['name']}' found."
            return json.dumps(client, indent=2)

        elif name == "ListClients":
            if not history:
                return "Error: memory store not available"
            clients = history.list_clients()
            if not clients:
                return "No clients saved yet."
            return "\n".join(
                f"- {c['name']}" + (f" ({c['industry']})" if c.get("industry") else "")
                + (f", {c['location']}" if c.get("location") else "")
                + (f" — {c['notes'][:60]}" if c.get("notes") else "")
                for c in clients
            )

        elif name == "UpsertProject":
            if not history:
                return "Error: memory store not available"
            proj_name = inp.pop("name")
            history.upsert_project(proj_name, **inp)
            return f"Project '{proj_name}' saved."

        elif name == "ListProjects":
            if not history:
                return "Error: memory store not available"
            projects = history.list_projects(
                client_name=inp.get("client_name"),
                status=inp.get("status"),
            )
            if not projects:
                return "No matching projects found."
            return "\n".join(
                f"- {p['name']}"
                + (f" for {p['client_name']}" if p.get("client_name") else "")
                + (f" [{p['status']}]" if p.get("status") else "")
                + (f" → {p['url']}" if p.get("url") else "")
                + (f" £{p['budget']:.0f}" if p.get("budget") else "")
                for p in projects
            )

        else:
            return f"Unknown tool: {name}"

    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except Exception as exc:
        return f"Error: {exc}"


class HistoryStore:
    """
    SQLite-backed storage for Zeus sessions, turn transcripts, and raw Claude
    API message histories.

    Path priority (first match wins):
      1. ZEUS_DATA_DIR env var          — explicit operator override
      2. /data                          — Railway persistent volume mount point
      3. ~/.zeus                        — local dev fallback

    On Railway: add a Volume in the dashboard, mount it at /data.  That's all
    that's needed — the DB file is created automatically on first startup.
    """

    def __init__(self):
        _railway = bool(
            os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID")
        )
        default = (
            os.environ.get("ZEUS_DATA_DIR")
            or ("/data" if _railway else str(_safe_home() / ".zeus"))
        )
        self.dir = pathlib.Path(default)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dir / "zeus.db"
        self._init_db()
        log.info("HistoryStore: SQLite at %s", self.db_path)

    # ── Internal helpers ───────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id      TEXT PRIMARY KEY,
                    started TEXT NOT NULL,
                    turns   INTEGER NOT NULL DEFAULT 0,
                    preview TEXT NOT NULL DEFAULT '',
                    updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn       INTEGER NOT NULL,
                    role       TEXT NOT NULL,
                    text       TEXT NOT NULL,
                    created    TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns (session_id);
                CREATE TABLE IF NOT EXISTS messages (
                    session_id TEXT PRIMARY KEY,
                    data       TEXT NOT NULL,
                    updated    TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'general',
                    content  TEXT NOT NULL,
                    created  TEXT NOT NULL,
                    updated  TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_cat ON memory (category);
                CREATE TABLE IF NOT EXISTS clients (
                    name       TEXT PRIMARY KEY,
                    industry   TEXT,
                    location   TEXT,
                    email      TEXT,
                    style_pref TEXT,
                    notes      TEXT,
                    created    TEXT NOT NULL,
                    updated    TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    name        TEXT PRIMARY KEY,
                    client_name TEXT,
                    status      TEXT NOT NULL DEFAULT 'active',
                    url         TEXT,
                    folder      TEXT,
                    budget      REAL,
                    notes       TEXT,
                    created     TEXT NOT NULL,
                    updated     TEXT NOT NULL
                );
            """)

    # ── Public API ─────────────────────────────────────────────────────────────

    def log_turn(self, session_id: str, turn: int, role: str, text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO turns (session_id, turn, role, text, created) VALUES (?,?,?,?,?)",
                (session_id, turn, role, text, datetime.now().isoformat()),
            )

    def save_session(self, session_id: str, started: datetime,
                     turns: int, preview: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, started, turns, preview, updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    turns   = excluded.turns,
                    preview = excluded.preview,
                    updated = excluded.updated
                """,
                (session_id, started.isoformat(), turns,
                 preview[:80], datetime.now().isoformat()),
            )

    def list_sessions(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, started, turns, preview FROM sessions ORDER BY updated DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_transcript(self, session_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT turn, role, text FROM turns WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_messages(self, session_id: str) -> list:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM messages WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            return []
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return []

    def save_messages(self, session_id: str, messages: list) -> None:
        _STRIP_TYPES = {"thinking", "parsed_output"}
        serialized = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                blocks = []
                for b in content:
                    raw = b.model_dump() if hasattr(b, "model_dump") else b
                    if not isinstance(raw, dict):
                        continue
                    if raw.get("type") in _STRIP_TYPES:
                        continue
                    blocks.append(raw)
                serialized.append({"role": msg["role"], "content": blocks})
            else:
                serialized.append(msg)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, data, updated) VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    data    = excluded.data,
                    updated = excluded.updated
                """,
                (session_id, json.dumps(serialized), datetime.now().isoformat()),
            )

    # ── Memory ─────────────────────────────────────────────────────────────────

    def save_memory(self, category: str, content: str) -> int:
        now = datetime.now().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO memory (category, content, created, updated) VALUES (?,?,?,?)",
                (category, content, now, now),
            )
            return cur.lastrowid

    def search_memory(self, query: str, category: str = "all") -> list:
        terms = [t for t in query.split() if t]
        if not terms:
            terms = [""]
        clauses = " AND ".join("content LIKE ?" for _ in terms)
        params: list = [f"%{t}%" for t in terms]
        if category and category != "all":
            clauses += " AND category = ?"
            params.append(category)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, category, content, created FROM memory WHERE {clauses} "
                f"ORDER BY id DESC LIMIT 20",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_memory(self, limit: int = 40) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT category, content, created FROM memory ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Clients ────────────────────────────────────────────────────────────────

    _CLIENT_COLS = frozenset({"industry", "location", "email", "style_pref", "notes"})

    def upsert_client(self, name: str, **fields: str) -> None:
        now = datetime.now().isoformat()
        safe = {k: v for k, v in fields.items() if k in self._CLIENT_COLS and v is not None}
        with self._conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM clients WHERE name=?", (name,)
            ).fetchone()
            if exists:
                if safe:
                    sets = ", ".join(f"{k}=?" for k in safe)
                    conn.execute(
                        f"UPDATE clients SET {sets}, updated=? WHERE name=?",
                        (*safe.values(), now, name),
                    )
            else:
                cols = ["name", "created", "updated", *safe.keys()]
                vals = [name, now, now, *safe.values()]
                conn.execute(
                    f"INSERT INTO clients ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                    vals,
                )

    def get_client(self, name: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE name LIKE ?", (f"%{name}%",)
            ).fetchone()
        return dict(row) if row else None

    def list_clients(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM clients ORDER BY updated DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Projects ───────────────────────────────────────────────────────────────

    _PROJECT_COLS = frozenset({"client_name", "status", "url", "folder", "budget", "notes"})

    def upsert_project(self, name: str, **fields) -> None:
        now = datetime.now().isoformat()
        safe = {k: v for k, v in fields.items() if k in self._PROJECT_COLS and v is not None}
        with self._conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM projects WHERE name=?", (name,)
            ).fetchone()
            if exists:
                if safe:
                    sets = ", ".join(f"{k}=?" for k in safe)
                    conn.execute(
                        f"UPDATE projects SET {sets}, updated=? WHERE name=?",
                        (*safe.values(), now, name),
                    )
            else:
                cols = ["name", "created", "updated", *safe.keys()]
                vals = [name, now, now, *safe.values()]
                conn.execute(
                    f"INSERT INTO projects ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                    vals,
                )

    def list_projects(self, client_name: str | None = None,
                      status: str | None = None) -> list:
        sql = "SELECT * FROM projects"
        params: list = []
        clauses: list[str] = []
        if client_name:
            clauses.append("client_name LIKE ?")
            params.append(f"%{client_name}%")
        if status and status != "all":
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def _build_memory_context(history: HistoryStore) -> str:
    """
    Assemble a live context block injected before each Claude call so Zeus
    always has its current knowledge, clients, and projects in view.
    """
    parts: list[str] = []

    memories = history.get_recent_memory(40)
    if memories:
        lines = "\n".join(
            f"  [{m['category']}] {m['content']}"
            for m in memories
        )
        parts.append(f"### Recent Learnings ({len(memories)})\n{lines}")

    clients = history.list_clients()
    if clients:
        lines = "\n".join(
            f"  - {c['name']}"
            + (f" ({c['industry']})" if c.get("industry") else "")
            + (f", {c['location']}" if c.get("location") else "")
            + (f" — {c['notes'][:70]}" if c.get("notes") else "")
            for c in clients[:30]
        )
        parts.append(f"### Clients ({len(clients)})\n{lines}")

    active = history.list_projects(status="active")
    if active:
        lines = "\n".join(
            f"  - {p['name']}"
            + (f" for {p['client_name']}" if p.get("client_name") else "")
            + (f" → {p['url']}" if p.get("url") else " (no URL yet)")
            for p in active[:20]
        )
        parts.append(f"### Active Projects ({len(active)})\n{lines}")

    if not parts:
        return ""
    return "## Zeus Live Context\n\n" + "\n\n".join(parts)


async def run_turn_stream(
    prompt: str,
    session_id: str | None,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: HistoryStore,
) -> str | None:
    client = get_anthropic_client()

    if session_id:
        messages = history.get_messages(session_id)
    else:
        session_id = str(uuid.uuid4())
        messages = []
        await on_message({"type": "session_id", "value": session_id})

    messages.append({"role": "user", "content": prompt})

    # Build enriched system prompt with live memory context
    memory_context = _build_memory_context(history)
    system = (
        f"{ZEUS_SYSTEM_PROMPT}\n\n---\n\n{memory_context}"
        if memory_context
        else ZEUS_SYSTEM_PROMPT
    )

    session_start = datetime.now()
    zeus_text_parts: list[str] = []

    for _ in range(60):  # max agentic turns
        # tool_blocks: index -> {id, name, json, input}
        tool_blocks: dict[int, dict] = {}

        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=16000,
            system=system,
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

        # Strip thinking/parsed_output blocks — they cannot be replayed to the API
        _STRIP_TYPES = {"thinking", "parsed_output"}
        safe_content = [
            b for b in final.content
            if (b.type if hasattr(b, "type") else b.get("type")) not in _STRIP_TYPES
        ]
        messages.append({"role": "assistant", "content": safe_content})

        if final.stop_reason != "tool_use" or not tool_blocks:
            break

        # Execute tools and collect results
        tool_results = []
        for idx in sorted(tool_blocks):
            tb = tool_blocks[idx]
            result = _run_tool(tb["name"], tb["input"], history)
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
