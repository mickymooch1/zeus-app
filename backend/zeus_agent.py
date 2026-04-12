import asyncio
import json
import logging
import os
import pathlib
import re
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
from github_push import push_to_github as _push_to_github

EXPORT_TAG_RE = re.compile(
    r'\[ZEUS_EXPORT:\s*type=(\w+)\s+title="([^"]+)"\]',
    re.IGNORECASE,
)

log = logging.getLogger("zeus.agent")

def _make_anthropic_client() -> anthropic.AsyncAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to Railway → Service → Variables."
        )
    return anthropic.AsyncAnthropic(api_key=api_key)

_anthropic_client: anthropic.AsyncAnthropic | None = None

# Holds references to background task coroutines so they aren't GC'd mid-run
_bg_tasks: set = set()


def _is_enterprise_or_admin(user: dict) -> bool:
    """Return True if the user has an active enterprise subscription OR is an admin."""
    if bool(user.get("is_admin", 0)):
        return True
    return (
        user.get("subscription_status") == "active"
        and user.get("subscription_plan") == "enterprise"
    )

def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = _make_anthropic_client()
    return _anthropic_client

ZEUS_SYSTEM_PROMPT = """You are Zeus — a senior AI assistant running a web design business. You're sharp, experienced, and genuinely invested in getting things right. You think like a senior developer who's seen enough bad decisions to know when to push back, and enough good work to know what excellent looks like.

## How you think and respond

You reason before you act. When something lands in front of you, you think it through — what's actually being asked, whether it's the right thing to do, what might go wrong, what a better version looks like. You don't just execute instructions; you engage with them.

You're direct but never cold. You say what you think. If a brief is vague, you say so. If an approach is going to cause problems, you say so before starting, not after. If the user's instinct is right, tell them why. If it's wrong, explain what you'd do instead and why. You're a collaborator, not a tool.

You write like a person, not a spec sheet. Short paragraphs, natural sentences. You use headers and bullet points when structure genuinely helps — a list of steps, a comparison of options — but you don't reach for them reflexively. A two-sentence answer to a two-sentence question is the right length.

You notice things. While working on something, if you spot an unrelated problem, a better approach, or something the user probably hasn't considered, you mention it. Briefly, without derailing — but you flag it. A senior developer walking past a bug doesn't pretend not to see it.

When someone reports a bug or error, you fix it — you don't explain what might be wrong. Read the relevant files, find the root cause, and apply the fix. If you need more context (a stack trace, a file path, which environment it's happening in), ask one specific question to get it — then fix. "It could be X or Y, try checking Z" is not an acceptable response to a bug report.

You remember the conversation. If the user mentioned earlier that the client hates blue, you don't propose a blue hero. If they said the deadline is Friday, that shapes how you prioritise. You carry context forward naturally, without making a show of it.

You never use filler. No "Certainly!", "Great question!", "Of course!", "Absolutely!" — none of it. Get straight to the point.

Before starting essays, CVs, cover letters, proposals, or business plans — ask one focused clarifying question if the brief is thin. Don't ask for information you can reasonably infer. Once you have what you need, get on with it.

When something is done, say what was done in one or two sentences. Not a recap of every step — just the outcome and anything the user needs to know next.

## What you can do

**Build websites** — complete, modern, responsive sites from scratch. Clean HTML, CSS, JavaScript. Semantic markup, flexbox/grid, smooth animations. Vanilla by default, frameworks when asked. Always save into a named project folder. Mobile-first, accessible, real-world best practices.

**Write anything** — web copy, blog posts, essays, CVs, cover letters, proposals, cold emails, client updates. Match the user's voice when examples are available. For longer documents (>200 words), note the approximate word count.

**Research** — fetch and summarise web pages, documentation, competitor sites, anything needed for a project.

**Fix and manage files** — read, write, edit, organise files and folders. Search codebases. Debug issues.

**Run the business** — pricing advice, proposal writing, client management, contracts, growth strategy, freelancing questions.

**Proofread and edit** — correct text and explain the changes. Adjust tone (formal, casual, persuasive) on request. Translate to any language.

## Export signalling

When you produce a complete exportable document — essay, blog post, CV, cover letter, proposal, business plan, proofread text — end your response with this exact tag on its own line:
[ZEUS_EXPORT: type=<type> title="<descriptive title>"]

Valid types: essay, blog, cv, cover_letter, proposal, business_plan, document

The tag is stripped by the frontend. Don't include it for conversational replies, short answers, website builds, or research summaries.

## Memory and learning — use these without being asked

You have a persistent memory system. Use it proactively. The goal is to get smarter with every conversation.

**SaveMemory(category, content)** — save anything worth keeping: client preferences, pricing that was accepted or rejected, design patterns that worked, business insights, what got results. Don't wait to be asked.

**SearchMemory(query, category)** — search before starting any substantial task. Before writing copy for a restaurant, search "restaurant". Before quoting a similar project, search for past pricing.

**UpsertClient(name, ...)** — save client details as you learn them. Industry, location, style preferences, budget range, notes. Update whenever something new comes up.

**GetClient(name)** — pull a client's full profile before starting work for them.

**ListClients()** — get an overview of all clients.

**UpsertProject(name, ...)** — log every website you build: client, live URL, folder, budget, status. Update when delivered or moved to maintenance.

**ListProjects(status, client_name)** — review past work before quoting similar jobs.

**PostToFacebook(message, photo_url)** — post to the Zeus AI Design Facebook page. Always call GenerateImage first to create a relevant image, pass the URL as photo_url. Write in a confident, on-brand tone. Suggest this after completing notable work.

**PushToGitHub(files, commit_message, create_pr, pr_title, pr_body)** — push files to the zeusaidesign.com GitHub repo. Restricted to web/src/ only. create_pr=false for minor updates, create_pr=true for significant changes. Admin only.

**CreateBackgroundTask(request, description)** — for MultiAgentBuild or any build that will take more than a few minutes, use this instead of calling MultiAgentBuild directly. Runs in the background; user is emailed when the site is live. Enterprise plan only.

## Zeus AI Design — Pricing

When users ask about plans, pricing, or what they can access, use this:

| Plan       | Price    | Key features |
|------------|----------|--------------|
| Free       | £0/mo    | 20 messages/month, AI chat assistant |
| Pro        | £29/mo   | Unlimited messages, AI chat assistant, priority support |
| Agency     | £79/mo   | Unlimited messages, AI chat assistant, team features, priority support |
| Enterprise | £150/mo  | Unlimited messages, multi-agent website builder, background tasks, scheduled tasks (coming soon), appointment booking (coming soon), priority support |

Direct users to zeusaidesign.com/pricing to upgrade.
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
    {
        "name": "WebSearch",
        "description": (
            "Search the internet for current information. "
            "Use this to look up recent news, prices, businesses, people, or anything "
            "that may have changed since your training data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ZipProject",
        "description": (
            "Package a project folder into a downloadable zip file. "
            "Call this after writing all project files when the user wants to download their project. "
            "Returns a download URL the user can click to get the zip."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder":   {"type": "string", "description": "Path to the project folder to zip"},
                "zip_name": {"type": "string", "description": "Name for the zip file, e.g. 'my-website.zip'"},
            },
            "required": ["folder", "zip_name"],
        },
    },
    {
        "name": "SendEmail",
        "description": (
            "Send an email on behalf of the user via Gmail. "
            "Use this to send client proposals, follow-ups, invoices, or any other email. "
            "Always confirm the recipient, subject, and body with the user before sending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body":    {"type": "string", "description": "Plain text email body"},
                "cc":      {"type": "string", "description": "CC email address (optional)"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "GenerateImage",
        "description": (
            "Generate an image from a text prompt using AI and return a URL the user can view. "
            "Use this when asked to create, design, or visualise anything — logos, banners, "
            "illustrations, mockups, background images, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed description of the image to generate"},
                "width":  {"type": "integer", "description": "Image width in pixels (default 1024)"},
                "height": {"type": "integer", "description": "Image height in pixels (default 1024)"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "StockPrice",
        "description": (
            "Get the real-time or latest stock price and key stats for any ticker symbol. "
            "Use this when asked about share prices, market cap, P/E ratio, or company financials."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, TSLA, GOOGL"},
            },
            "required": ["ticker"],
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
    {
        "name": "DeployToNetlify",
        "description": "Deploy a built website folder to Netlify and return a live URL. Use this after building a website for a client.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_folder": {
                    "type": "string",
                    "description": "The folder name inside /data/projects/ to deploy"
                },
                "site_name": {
                    "type": "string",
                    "description": "A URL-friendly name for the Netlify site e.g. mikes-plumbing-london"
                }
            },
            "required": ["project_folder"]
        }
    },
    {
        "name": "MultiAgentBuild",
        "description": (
            "Run a full multi-agent website build pipeline: "
            "Planner → Researcher → Builder → Deployer. "
            "The Planner writes a detailed brief, the Researcher finds competitor sites and design "
            "inspiration, the Builder writes the complete website, and the Deployer publishes it to "
            "Netlify and returns the live URL. Each agent streams its output in real time. "
            "Enterprise plan only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The user's website build request — business type, goals, and any preferences",
                },
            },
            "required": ["request"],
        },
    },
    {
        "name": "CreateBackgroundTask",
        "description": (
            "Schedule a MultiAgentBuild as a background task. "
            "Use this when the user asks for a website build that will take a long time. "
            "The pipeline runs in the background — the user is emailed at their registered "
            "address when the site is live. Returns immediately with a task ID. "
            "Enterprise plan only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The full website build request to pass to the MultiAgentBuild pipeline",
                },
                "description": {
                    "type": "string",
                    "description": "Short human-readable label for the task card, e.g. \"Build website for Joe's Plumbing\"",
                },
            },
            "required": ["request", "description"],
        },
    },
    {
        "name": "PostToFacebook",
        "description": (
            "Post a message to the Zeus AI Design Facebook page. "
            "Use this to share updates, project completions, tips, or announcements. "
            "Always call GenerateImage first to create a relevant image, then pass its URL "
            "as the 'photo_url' field alongside the 'message' field."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The text content to post to the Zeus AI Design Facebook page.",
                },
                "photo_url": {
                    "type": "string",
                    "description": "URL of an image to attach to the post. Generate this first using the GenerateImage tool.",
                },
            },
            "required": ["message", "photo_url"],
        },
    },
    {
        "name": "PushToGitHub",
        "description": (
            "Push one or more files to the mickymooch1/zeus-app GitHub repository "
            "and commit them atomically. Restricted to paths under web/src/ only. "
            "Use this to update the zeusaidesign.com website — landing page, pricing, "
            "styles, copy, or any frontend file. "
            "Set create_pr=false for minor changes (copy fix, price update, colour change). "
            "Set create_pr=true for significant changes (redesigns, multi-section rewrites). "
            "Railway will automatically redeploy zeusaidesign.com when merged to main. "
            "Admin only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "description": "List of files to write. Each must have 'path' (under web/src/) and 'content' (full file text).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
                "commit_message": {
                    "type": "string",
                    "description": "Git commit message, e.g. 'feat: update pricing section'",
                },
                "create_pr": {
                    "type": "boolean",
                    "description": "true = open a pull request for review; false = push directly to main",
                },
                "pr_title": {
                    "type": "string",
                    "description": "PR title — required if create_pr is true",
                },
                "pr_body": {
                    "type": "string",
                    "description": "PR description — optional summary of changes",
                },
            },
            "required": ["files", "commit_message"],
        },
    },
]

# ── Restricted tool sets for each sub-agent ───────────────────────────────────
_RESEARCHER_TOOLS = [t for t in TOOLS if t["name"] in ("WebSearch", "WebFetch")]
_BUILDER_TOOLS    = [t for t in TOOLS if t["name"] in ("Write", "Read", "Edit", "Glob")]
_DEPLOYER_TOOLS   = [t for t in TOOLS if t["name"] in ("DeployToNetlify",)]

def _safe_home() -> pathlib.Path:
    try:
        return pathlib.Path.home()
    except RuntimeError:
        return pathlib.Path("/tmp")


_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
_default_cwd = "/data/projects" if _railway else str(_safe_home() / "zeus-projects")
_CWD = os.environ.get("ZEUS_CWD", _default_cwd)
pathlib.Path(_CWD).mkdir(parents=True, exist_ok=True)


def _resolve(path: str) -> pathlib.Path:
    p = pathlib.Path(path)
    return p if p.is_absolute() else pathlib.Path(_CWD) / p


def _sanitise_block(b) -> dict | None:
    """
    Convert an API response block to a plain dict containing only the fields
    the API accepts when the message is replayed as conversation history.
    Returns None for block types that must never be replayed (thinking, etc.).
    """
    raw = b.model_dump() if hasattr(b, "model_dump") else (b if isinstance(b, dict) else None)
    if not isinstance(raw, dict):
        return None
    t = raw.get("type")
    if t == "text":
        return {"type": "text", "text": raw.get("text", "")}
    if t == "tool_use":
        return {"type": "tool_use", "id": raw["id"], "name": raw["name"], "input": raw.get("input", {})}
    if t == "tool_result":
        return {"type": "tool_result", "tool_use_id": raw["tool_use_id"], "content": raw.get("content", "")}
    # thinking, redacted_thinking, parsed_output, and any future types: drop them
    return None


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

        elif name == "ZipProject":
            import zipfile, tempfile
            src = _resolve(inp["folder"])
            if not src.exists():
                return f"Error: folder '{src}' does not exist."
            if not src.is_dir():
                return f"Error: '{src}' is not a directory."

            zip_name = inp["zip_name"].strip()
            if not zip_name.endswith(".zip"):
                zip_name += ".zip"

            # Store in /data/downloads (persistent on Railway) or a temp dir
            import os as _os
            _railway = bool(_os.environ.get("RAILWAY_ENVIRONMENT") or _os.environ.get("RAILWAY_PROJECT_ID"))
            downloads_dir = pathlib.Path("/data/downloads" if _railway else tempfile.gettempdir()) / "zeus_downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)

            # Use a unique token so the URL can't be guessed
            token = str(uuid.uuid4())[:8]
            zip_filename = f"{token}_{zip_name}"
            zip_path = downloads_dir / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in src.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(src))

            file_count = sum(1 for _ in src.rglob("*") if _.is_file())
            return (
                f"DOWNLOAD_READY:{zip_filename}\n"
                f"Zipped {file_count} files from '{src.name}' → {zip_name}\n"
                f"The user can now download their project."
            )

        elif name == "SendEmail":
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_email = os.environ.get("SMTP_EMAIL", "").strip()
            smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
            if not smtp_email or not smtp_password:
                return "Error: SMTP_EMAIL and SMTP_PASSWORD environment variables are not set."

            msg = MIMEMultipart()
            msg["From"] = smtp_email
            msg["To"] = inp["to"]
            msg["Subject"] = inp["subject"]
            if inp.get("cc"):
                msg["Cc"] = inp["cc"]
            msg.attach(MIMEText(inp["body"], "plain"))

            recipients = [inp["to"]]
            if inp.get("cc"):
                recipients.append(inp["cc"])

            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
                    server.login(smtp_email, smtp_password)
                    server.sendmail(smtp_email, recipients, msg.as_string())
                return f"Email sent to {inp['to']} — Subject: {inp['subject']}"
            except smtplib.SMTPAuthenticationError:
                return "Error: Gmail authentication failed. Make sure SMTP_PASSWORD is an App Password, not your regular Gmail password."
            except smtplib.SMTPException as exc:
                return f"Error sending email: {exc}"

        elif name == "GenerateImage":
            import urllib.parse
            prompt = inp["prompt"]
            width  = int(inp.get("width", 1024))
            height = int(inp.get("height", 1024))
            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
            # Verify the image is reachable
            try:
                check = httpx.head(url, timeout=20, follow_redirects=True)
                if check.status_code >= 400:
                    return f"Image generation failed (HTTP {check.status_code}). Try a different prompt."
            except Exception:
                pass  # Return the URL anyway — HEAD may be blocked but GET will work
            return f"Generated image URL: {url}\n\nPrompt used: {prompt}"

        elif name == "StockPrice":
            ticker = inp["ticker"].upper().strip()
            resp = httpx.get(
                f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
                params={"modules": "price,summaryDetail"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return f"Could not fetch data for ticker '{ticker}' (HTTP {resp.status_code})"
            try:
                result = resp.json()["quoteSummary"]["result"]
                if not result:
                    return f"No data found for ticker '{ticker}'"
                price_data = result[0].get("price", {})
                summary = result[0].get("summaryDetail", {})

                def _val(d, key):
                    v = d.get(key, {})
                    return v.get("fmt") or v.get("raw") if isinstance(v, dict) else v

                lines = [
                    f"Ticker:        {ticker}",
                    f"Company:       {price_data.get('longName') or price_data.get('shortName', 'N/A')}",
                    f"Exchange:      {price_data.get('exchangeName', 'N/A')}",
                    f"Currency:      {price_data.get('currency', 'N/A')}",
                    f"Current price: {_val(price_data, 'regularMarketPrice')}",
                    f"Change:        {_val(price_data, 'regularMarketChange')} ({_val(price_data, 'regularMarketChangePercent')})",
                    f"Open:          {_val(price_data, 'regularMarketOpen')}",
                    f"Day high:      {_val(price_data, 'regularMarketDayHigh')}",
                    f"Day low:       {_val(price_data, 'regularMarketDayLow')}",
                    f"52w high:      {_val(summary, 'fiftyTwoWeekHigh')}",
                    f"52w low:       {_val(summary, 'fiftyTwoWeekLow')}",
                    f"Market cap:    {_val(price_data, 'marketCap')}",
                    f"Volume:        {_val(price_data, 'regularMarketVolume')}",
                    f"P/E ratio:     {_val(summary, 'trailingPE')}",
                    f"Market state:  {price_data.get('marketState', 'N/A')}",
                ]
                return "\n".join(l for l in lines if not l.endswith("N/A") and not l.endswith("None"))
            except (KeyError, IndexError, ValueError) as exc:
                return f"Error parsing Yahoo Finance response for '{ticker}': {exc}"

        elif name == "WebSearch":
            query = inp["query"]
            # DuckDuckGo instant-answer API — no key required
            ddg = httpx.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "Zeus/1.0"},
                timeout=15,
                follow_redirects=True,
            )
            data = ddg.json()
            parts: list[str] = []

            if data.get("AbstractText"):
                parts.append(f"Summary: {data['AbstractText']}")
                if data.get("AbstractURL"):
                    parts.append(f"Source: {data['AbstractURL']}")

            if data.get("Answer"):
                parts.append(f"Answer: {data['Answer']}")

            for topic in data.get("RelatedTopics", [])[:8]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(f"- {topic['Text']}")
                    if topic.get("FirstURL"):
                        parts.append(f"  {topic['FirstURL']}")

            if not parts:
                # Fall back to fetching DuckDuckGo HTML search results
                html = httpx.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                    follow_redirects=True,
                )
                # Extract result snippets with a simple text scan
                import re
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html.text, re.S)
                titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html.text, re.S)
                urls = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html.text, re.S)
                for i, snippet in enumerate(snippets[:6]):
                    title = re.sub(r"<[^>]+>", "", titles[i]) if i < len(titles) else ""
                    url = urls[i].strip() if i < len(urls) else ""
                    clean = re.sub(r"<[^>]+>", "", snippet).strip()
                    parts.append(f"{title}\n{url}\n{clean}")

            return "\n".join(parts)[:6000] if parts else f"No results found for: {query}"

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

        elif name == "DeployToNetlify":
            import requests, io, time, zipfile

            project_folder = inp.get("project_folder")
            site_name = inp.get("site_name", project_folder.lower().replace(" ", "-"))

            netlify_token = os.environ.get("NETLIFY_TOKEN")
            if not netlify_token:
                return "Error: NETLIFY_TOKEN not set in environment variables."

            folder_path = f"/data/projects/{project_folder}"
            if not os.path.exists(folder_path):
                return f"Error: Folder {folder_path} does not exist."

            try:
                json_headers = {
                    "Authorization": f"Bearer {netlify_token}",
                    "Content-Type": "application/json",
                }

                # ── Build zip in memory ───────────────────────────────────────
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _dirs, files in os.walk(folder_path):
                        for filename in files:
                            filepath = os.path.join(root, filename)
                            arcname = os.path.relpath(filepath, folder_path).replace("\\", "/")
                            # Rename first .html to index.html if no index.html exists
                            if arcname.lower().endswith(".html"):
                                parts = arcname.split("/")
                                if parts[-1].lower() != "index.html":
                                    siblings = [
                                        f for f in os.listdir(os.path.dirname(filepath) or folder_path)
                                        if f.lower() == "index.html"
                                    ]
                                    if not siblings:
                                        parts[-1] = "index.html"
                                        arcname = "/".join(parts)
                            zf.write(filepath, arcname)
                zip_bytes = zip_buf.getvalue()

                # ── Get or create site ────────────────────────────────────────
                sites_resp = requests.get(
                    "https://api.netlify.com/api/v1/sites",
                    headers=json_headers,
                )
                if sites_resp.status_code != 200:
                    return (
                        f"Error: Netlify /sites list returned HTTP {sites_resp.status_code}. "
                        f"Body: {sites_resp.text[:500]}"
                    )
                site_id = None
                for s in sites_resp.json():
                    if s.get("name") == site_name:
                        site_id = s["id"]
                        break

                if not site_id:
                    create_resp = requests.post(
                        "https://api.netlify.com/api/v1/sites",
                        headers=json_headers,
                        json={"name": site_name},
                    )
                    if create_resp.status_code not in (200, 201):
                        return (
                            f"Error: Netlify site creation returned HTTP {create_resp.status_code}. "
                            f"Body: {create_resp.text[:500]}"
                        )
                    create_data = create_resp.json()
                    if "id" not in create_data:
                        return (
                            f"Error: Netlify site creation response missing 'id'. "
                            f"Body: {create_resp.text[:500]}"
                        )
                    site_id = create_data["id"]

                # ── Upload zip deploy ─────────────────────────────────────────
                deploy_resp = requests.post(
                    f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
                    headers={
                        "Authorization": f"Bearer {netlify_token}",
                        "Content-Type": "application/zip",
                    },
                    data=zip_bytes,
                )
                if deploy_resp.status_code not in (200, 201):
                    return (
                        f"Error: Netlify zip deploy returned HTTP {deploy_resp.status_code}. "
                        f"Body: {deploy_resp.text[:500]}"
                    )
                deploy_data = deploy_resp.json()
                if "id" not in deploy_data:
                    return (
                        f"Error: Netlify zip deploy response missing 'id'. "
                        f"Body: {deploy_resp.text[:500]}"
                    )
                deploy_id = deploy_data["id"]

                # ── Poll until ready ──────────────────────────────────────────
                deploy_state = None
                for _ in range(60):
                    time.sleep(2)
                    poll_resp = requests.get(
                        f"https://api.netlify.com/api/v1/deploys/{deploy_id}",
                        headers={"Authorization": f"Bearer {netlify_token}"},
                    )
                    poll_data = poll_resp.json()
                    deploy_state = poll_data.get("state")
                    if deploy_state == "ready":
                        break
                    if deploy_state == "error":
                        error_msg = poll_data.get("error_message") or "(no error_message in response)"
                        return (
                            f"Error: Netlify deploy failed.\n"
                            f"  state: error\n"
                            f"  error_message: {error_msg}\n"
                            f"  deploy_id: {deploy_id}\n"
                            f"  title: {poll_data.get('title', '')}"
                        )

                if deploy_state != "ready":
                    return f"Error: Deploy did not become ready within 120 seconds (last state: {deploy_state})."

                site_url = f"https://{site_name}.netlify.app"
                return f"✅ Successfully deployed to Netlify!\n🌐 Live URL: {site_url}\n📁 Site ID: {site_id}"

            except Exception as e:
                import traceback as _tb
                return f"Error deploying to Netlify: {e}\n{_tb.format_exc()}"

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
            # Idempotent migration: add user_id to sessions
            try:
                conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
            except Exception:
                pass  # column already exists
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id)"
                )
            except Exception:
                pass

    # ── Public API ─────────────────────────────────────────────────────────────

    def log_turn(self, session_id: str, turn: int, role: str, text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO turns (session_id, turn, role, text, created) VALUES (?,?,?,?,?)",
                (session_id, turn, role, text, datetime.now().isoformat()),
            )

    def save_session(self, session_id: str, started: datetime,
                     turns: int, preview: str,
                     user_id: str | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, started, turns, preview, updated, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    turns   = excluded.turns,
                    preview = excluded.preview,
                    updated = excluded.updated
                """,
                (session_id, started.isoformat(), turns,
                 preview[:80], datetime.now().isoformat(), user_id),
            )

    def list_sessions(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, started, turns, preview FROM sessions ORDER BY updated DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_sessions_for_user(self, user_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, started, turns, preview FROM sessions "
                "WHERE user_id = ? ORDER BY updated DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_transcript(self, session_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT turn, role, text FROM turns WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_transcript_if_owner(self, session_id: str, user_id: str) -> list | None:
        """Return transcript if session belongs to user_id, else None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if row is None:
                return None
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
        serialized = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                blocks = [s for b in content if (s := _sanitise_block(b)) is not None]
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

    memories = history.get_recent_memory(10)
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


class StageFailure(Exception):
    """Raised when a pipeline stage fails all retry attempts."""

    def __init__(self, stage: str, attempts: list[str]) -> None:
        self.stage = stage
        self.attempts = attempts  # one error string per attempt, truncated to 120 chars
        super().__init__(f"{stage} failed after {len(attempts)} attempt(s)")


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


async def _run_agent_loop(
    prompt: str,
    system_prompt: str,
    tools: list,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: "HistoryStore",
    stage_label: str,
    max_turns: int = 30,
    max_tokens: int = 8000,
    collect_tool_results: bool = False,
    emit_header: bool = True,
) -> str:
    """
    Run a focused single-purpose agentic loop and return the final text output.
    Emits the stage header immediately, then streams text deltas and tool events
    via on_message. Raises RuntimeError if the loop exits without producing text.
    """
    client = get_anthropic_client()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    text_parts: list[str] = []

    # Emit stage header before any work begins (suppressed on retries)
    if emit_header:
        await on_message({"type": "text", "delta": f"\n\n**{stage_label}**\n"})

    for _ in range(max_turns):
        tool_blocks: dict[int, dict] = {}

        stream_kwargs: dict[str, Any] = {
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            stream_kwargs["tools"] = tools

        async with client.messages.stream(**stream_kwargs) as stream:
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
                        text_parts.append(delta.text)
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
                        path = (
                            tb["input"].get("file_path")
                            or tb["input"].get("path")
                            or tb["input"].get("url", "")
                        )
                        await on_message({
                            "type": "tool",
                            "name": tb["name"],
                            "path": path,
                            "status": "running",
                        })

            final = await stream.get_final_message()

        log.info("%s: stop_reason=%r  tool_blocks=%d", stage_label, final.stop_reason, len(tool_blocks))
        if final.stop_reason == "max_tokens":
            log.warning(
                "%s: hit max_tokens limit (%d) — response was truncated; increase max_tokens if output is incomplete",
                stage_label, max_tokens,
            )

        safe_content = [s for b in final.content if (s := _sanitise_block(b)) is not None]
        messages.append({"role": "assistant", "content": safe_content})

        if final.stop_reason != "tool_use" or not tool_blocks:
            break

        tool_results = []
        for idx in sorted(tool_blocks):
            tb = tool_blocks[idx]
            result = _run_tool(tb["name"], tb["input"], history)
            if collect_tool_results:
                text_parts.append(result)
            path = (
                tb["input"].get("file_path")
                or tb["input"].get("path")
                or tb["input"].get("url", "")
            )
            await on_message({
                "type": "tool",
                "name": tb["name"],
                "path": path,
                "status": "done",
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb["id"],
                "content": _add_tool_error_hint(result),
            })

        messages.append({"role": "user", "content": tool_results})

    return "".join(text_parts).strip()


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
    exc: "StageFailure",
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
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
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
                emit_header=(attempt == 0),
            )
        except Exception as exc:
            log.error(
                "%s attempt %d/%d failed: %s",
                stage_label, attempt + 1, max_attempts, exc,
                exc_info=True,
            )
            errors.append(str(exc)[:120])
    raise StageFailure(stage_label, errors)


async def run_multi_agent(
    request: str,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: "HistoryStore",
    user_id: str | None = None,
) -> str:
    """
    Planner → Researcher → Builder → Deployer pipeline.
    Streams all agent output live via on_message.
    Enterprise plan required.
    """
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

    # ── Stage 1: Planner ──────────────────────────────────────────────────────
    planner_system = """\
You are the Planner in a multi-agent website build pipeline — and you think like a senior web designer with 15 years of experience building sites for UK small businesses.

You do NOT fill in a generic template. You make real creative decisions based on the specific business type and location. Before writing the brief, reason through your creative choices in 3–5 sentences: what kind of person runs this business, who their customers are, what feeling the site needs to create, and why your design choices serve that. Then output the structured brief.

─── HOW TO THINK ───────────────────────────────────────────────────────────────

COLOUR PALETTE
Draw from the real-world associations of the trade and place.
- A Chelsea florist → dusty sage, blush pink, warm cream, off-white (#F5F0EA, #D4A5A5, #8FAF8A)
- A Manchester barber → charcoal, amber, matte black, aged leather (#1C1C1C, #C07A2F, #3A3A3A)
- A London plumber → deep navy, clean white, a single trust-red or teal accent (#1A2E4A, #FFFFFF, #E8392A)
- A Cornwall surf school → washed denim, sea-foam, sun-bleached sand (#5B8FA8, #A8D5C2, #F2E8D5)
Never use a generic palette. Pick colours that feel like they belong to this business.

TYPOGRAPHY STYLE
Match the personality:
- Luxury / boutique → elegant serif headline (e.g. Playfair Display, Cormorant Garamond) + light sans body
- Trade / utility → strong geometric sans (e.g. Inter, DM Sans) — honest, no fuss
- Craft / artisan → slightly irregular serif or slab (e.g. Lora, Zilla Slab) — handmade feel
- Youthful / energetic → bold grotesque (e.g. Space Grotesk, Syne) — confidence, movement
Name a specific Google Font pairing.

MOOD & TONE
One of: Warm & local / Luxe & aspirational / No-nonsense & reliable / Friendly & approachable / Bold & edgy / Calm & professional. This drives copy voice AND visual weight.

HERO LAYOUT
Choose deliberately:
- Full-bleed atmospheric photo with large headline overlay → high-emotion trades (florists, restaurants, salons)
- Bold headline left, photo or illustration right (split panel) → service businesses that need clarity fast
- Headline + subheadline + single CTA, minimal imagery → emergency or utility services (plumbers, electricians)
- Video or animated background → fitness, events, hospitality
- Oversized typographic statement → agencies, studios, barbers with strong personality

SECTIONS TO INCLUDE
Only include sections that this specific business actually needs. Think about the customer journey.
Examples by type:
- Tradesperson: Hero → Trust signals (accreditations, years experience) → Services → Before/After or Gallery → Reviews → Contact/Quote form
- Florist/retail: Hero → Featured products/occasions → About the shop → Seasonal highlight → Instagram feed → Find us
- Restaurant/café: Hero → Menu highlights → Story/About → Booking → Gallery → Find us + hours
- Fitness/wellness: Hero → What you get → Classes/Services → Trainer bios → Pricing → Testimonials → Book now
Never default to "Home, About, Services, Contact" — earn every section.

─── OUTPUT FORMAT ──────────────────────────────────────────────────────────────

After your short reasoning paragraph, output the brief with these fields, each on its own line:

SITE_NAME: <url-slug e.g. mikes-plumbing-london>
Business: <specific description of what the business does and who runs it>
Location vibe: <how the location shapes the audience and aesthetic>
Target audience: <specific customer profile — not just "local people">
Mood: <one of the mood options above>
Typography: <Headline font — Body font, with rationale in parentheses>
Colour scheme: <3 hex colours with a one-word label each, e.g. #1A2E4A Navy, #FFFFFF White, #E8392A Signal-red>
Hero layout: <chosen layout with one sentence explaining why>
Sections: <ordered list of sections with a one-line purpose for each>
Copy tone: <how the copy should sound — 1 sentence, specific>
Key features: <functionality or content that this business specifically needs>

Be opinionated. Every decision should feel like it was made for THIS business, not adapted from a template.\
"""
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

    # Extract site name from planner output — single source of truth for all stages
    log.info("run_multi_agent: raw planner_output=\n%s", planner_output)
    site_name = "zeus-build"
    _site_name_raw_line = "(SITE_NAME: line not found in planner output)"
    for line in planner_output.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("SITE_NAME:"):
            _site_name_raw_line = stripped
            raw = stripped.split(":", 1)[1].strip().lower()
            slug = re.sub(r"[^a-z0-9-]+", "-", raw).strip("-")
            if slug:
                site_name = slug
            break

    _build_dir = f"/data/projects/{site_name}"
    log.info(
        "run_multi_agent: site_name extraction — raw_line=%r  extracted=%r  build_dir=%r",
        _site_name_raw_line, site_name, _build_dir,
    )
    await on_message({"type": "text", "delta": f"\n📁 **Build directory:** `{_build_dir}`\n"})

    # ── Stage 2: Researcher ───────────────────────────────────────────────────
    researcher_system = """\
You are the Researcher in a multi-agent website build pipeline.

Given a website brief, your job:
1. Search for 3 real competitor or inspiration websites in the same niche
2. Fetch a key page from each to note design patterns, navigation structure, and copy style
3. Identify 2–3 concrete design inspiration points (colour usage, layout, typography)

Output a clear research summary the Builder can use directly.
Include actual URLs and specific, actionable observations.\
"""
    researcher_prompt = (
        f"Website brief from Planner:\n\n{planner_output}\n\n"
        "Find 3 competitor/inspiration sites and summarise what the Builder should take from them."
    )
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

    # ── Stage 3: Builder ──────────────────────────────────────────────────────
    log.info("run_multi_agent: Builder stage — site_name=%r  build_dir=%r", site_name, _build_dir)
    builder_system = f"""\
You are the Builder in a multi-agent website build pipeline.

CRITICAL — READ BEFORE WRITING ANY FILE:
The ONLY permitted project directory is: {_build_dir}
The site slug is: {site_name}

OUTPUT CONSTRAINTS — MUST BE FOLLOWED WITHOUT EXCEPTION:
- Write ONE file only: {_build_dir}/index.html
- Maximum 500 lines total
- All CSS must be in a single <style> block inside the HTML — no separate .css files
- All JS must be in a single <script> block inside the HTML — no separate .js files
- No external frameworks, libraries, or CDN links (no Bootstrap, Tailwind, jQuery, etc.)
- No base64-encoded images or data URIs
- No external fonts (use system font stack only: sans-serif, serif, monospace)
- Inline styles only where needed for dynamic behaviour; otherwise use the <style> block

DO NOT write style.css, script.js, or any file other than index.html.
DO NOT use any other directory. DO NOT invent a different folder name.
DO NOT use relative paths. DO NOT add extra subdirectories.

Your job:
1. Write a single self-contained index.html under 500 lines
2. Use the brief's colour scheme, tone, and content
3. Draw on the research for copy and layout decisions
4. Mobile-responsive using simple CSS (flexbox/grid, media queries)
5. Clean semantic HTML — no unnecessary divs or complexity

When done, confirm: "Files written to {_build_dir}/"\
"""
    builder_prompt = (
        f"Brief from Planner:\n{planner_output}\n\n"
        f"Research from Researcher:\n{researcher_output}\n\n"
        f"Build the complete website. Write ALL files to {_build_dir}/ using the Write tool "
        f"with full absolute paths. The ONLY valid directory is {_build_dir}/ — do not use any other path."
    )
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

    # ── Verify build output before deploying ──────────────────────────────────
    index_path = pathlib.Path(_build_dir) / "index.html"
    log.info("run_multi_agent: verifying index.html at %r — exists=%s", str(index_path), index_path.exists())
    if not index_path.exists():
        msg = (
            f"\n\n❌ **Build verification failed:** `{_build_dir}/index.html` was not found. "
            "The Builder did not save files to the expected location. Aborting deployment.\n"
        )
        await on_message({"type": "text", "delta": msg})
        return f"Pipeline aborted: index.html missing at {_build_dir}/"

    await on_message({"type": "text", "delta": f"\n\n✅ **Build verified** — files confirmed at `{_build_dir}/`\n"})

    # ── Stage 4: Deployer ─────────────────────────────────────────────────────
    log.info("run_multi_agent: Deployer stage — site_name=%r  build_dir=%r", site_name, _build_dir)
    deployer_system = """\
You are the Deployer in a multi-agent website build pipeline.

Your only job: call DeployToNetlify with the project folder and site name, then
report the live URL clearly. Do nothing else.\
"""
    deployer_prompt = (
        f"The Builder has finished writing the website.\n\n"
        f"The files are at: {_build_dir}/\n"
        f"Deploy it now using DeployToNetlify:\n"
        f"  project_folder = \"{site_name}\"\n"
        f"  site_name      = \"{site_name}\"\n\n"
        f"The project_folder value must be exactly \"{site_name}\" — do not change it.\n"
        "Confirm the live URL when done."
    )
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

    log.info("run_multi_agent: deployer_output=\n%s", deployer_output)
    return deployer_output


async def _handle_create_background_task(
    request: str,
    description: str,
    history: "HistoryStore",
    user_id: str | None,
) -> str:
    """
    Create a background task record and spawn run_multi_agent as an asyncio task.
    Returns immediately with a confirmation string for Zeus to relay to the user.
    Enterprise plan only.
    """
    import db as _db

    if not user_id:
        return "Error: Cannot create background task — no authenticated user."

    # Enterprise gate
    try:
        _db_path = _db.get_db_path()
        _user = _db.get_user_by_id(_db_path, user_id)
        if not _user:
            return "Error: User not found."
        if not _is_enterprise_or_admin(_user):
            return (
                "❌ **CreateBackgroundTask requires an Enterprise plan.** "
                "Upgrade at zeusaidesign.com/pricing."
            )
        user_email = _user.get("email", "")
    except Exception as exc:
        log.warning("_handle_create_background_task: could not verify plan: %s", exc)
        return f"Error: Could not verify enterprise plan — {exc}"

    # Create the DB record
    try:
        task = _db.create_task(_db_path, user_id, description)
        task_id = task["id"]
    except Exception as exc:
        log.error("_handle_create_background_task: db.create_task failed: %s", exc)
        return f"Error: Could not create task record — {exc}"

    # Background coroutine — runs after this function returns
    async def _run() -> None:
        try:
            _db.update_task(_db_path, task_id, status="running")

            # Noop sink — no live WebSocket to stream to in background
            async def _noop(_msg: dict) -> None:
                pass

            result_text = await run_multi_agent(request, _noop, history, user_id)

            # run_multi_agent swallows agent/API exceptions and returns error strings
            # rather than raising — detect them and mark the task failed.
            _pipeline_failed = result_text.startswith("Pipeline aborted:")
            _agent_error = result_text.startswith("Error:")
            if _pipeline_failed or _agent_error:
                if "overloaded_error" in result_text or "overloaded" in result_text.lower():
                    error_msg = (
                        "Anthropic API is overloaded — the request could not be completed. "
                        "Please retry the task in a few minutes."
                    )
                else:
                    error_msg = result_text
                log.error("Background task %s failed (pipeline error): %s", task_id, result_text)
                _db.update_task(
                    _db_path, task_id,
                    status="failed",
                    result=error_msg,
                    completed_at=datetime.now().isoformat(),
                )
                return

            # Extract Netlify URL from result
            log.info("Background task %s: raw result_text=\n%s", task_id, result_text)
            _url_match = re.search(r'https?://\S+\.netlify\.app', result_text)
            live_url = _url_match.group(0).rstrip(".,)") if _url_match else None

            now = datetime.now().isoformat()
            _db.update_task(
                _db_path, task_id,
                status="done",
                result=result_text,
                live_url=live_url,
                completed_at=now,
            )
            log.info("Background task %s done. live_url=%s", task_id, live_url)
            _send_bg_task_email(user_email, description, live_url, result_text)

        except Exception as exc:
            log.error("Background task %s failed: %s", task_id, exc, exc_info=True)
            error_msg = (
                "Anthropic API is overloaded — the request could not be completed. "
                "Please retry the task in a few minutes."
                if "overloaded_error" in str(exc)
                else str(exc)
            )
            try:
                _db.update_task(
                    _db_path, task_id,
                    status="failed",
                    result=error_msg,
                    completed_at=datetime.now().isoformat(),
                )
            except Exception:
                log.exception("Background task %s: could not update failed status", task_id)

    bg = asyncio.create_task(_run())
    _bg_tasks.add(bg)
    bg.add_done_callback(_bg_tasks.discard)

    return (
        f"✅ Background task queued — ID: `{task_id}`\n"
        f"I'll email you at **{user_email}** when it's done.\n"
        f"You can track progress at [/tasks](/tasks)."
    )


def _send_bg_task_email(
    user_email: str,
    description: str,
    live_url: str | None,
    result: str,
) -> None:
    """Send a task completion email via Gmail SMTP. Silently skips if not configured."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_email = os.environ.get("SMTP_EMAIL", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not smtp_email or not smtp_password:
        log.warning("_send_bg_task_email: SMTP_EMAIL/SMTP_PASSWORD not set — skipping")
        return

    subject = f"Zeus: Your background task is complete — {description}"
    body = "\n".join([
        "Your background task has finished.",
        "",
        f"Task: {description}",
        f"Live URL: {live_url or 'See result below'}",
        "",
        "Result:",
        result[:2000],
        "",
        "— Zeus AI Design",
        "zeusaidesign.com",
    ])

    msg = MIMEMultipart()
    msg["From"] = smtp_email
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [user_email], msg.as_string())
        log.info("_send_bg_task_email: sent to %s", user_email)
    except smtplib.SMTPAuthenticationError:
        log.warning("_send_bg_task_email: Gmail auth failed — check SMTP_PASSWORD is an App Password")
    except smtplib.SMTPException as exc:
        log.warning("_send_bg_task_email: SMTP error: %s", exc)


async def run_turn_stream(
    prompt: str,
    session_id: str | None,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
    history: HistoryStore,
    user_id: str | None = None,
    image: dict | None = None,
) -> str | None:
    client = get_anthropic_client()

    if session_id:
        messages = history.get_messages(session_id)
    else:
        session_id = str(uuid.uuid4())
        messages = []
        await on_message({"type": "session_id", "value": session_id})

    # Build user message content — multimodal if an image was attached
    if image:
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image["media_type"],
                    "data": image["data"],
                },
            },
        ]
        if prompt:
            user_content.append({"type": "text", "text": prompt})
    else:
        user_content = prompt

    messages.append({"role": "user", "content": user_content})

    # Build enriched system prompt with live memory context
    memory_context = _build_memory_context(history)
    system = (
        f"{ZEUS_SYSTEM_PROMPT}\n\n---\n\n{memory_context}"
        if memory_context
        else ZEUS_SYSTEM_PROMPT
    )

    # Append user subscription context if a user_id was provided
    if user_id:
        try:
            import db
            from datetime import timezone
            db_path = db.get_db_path()
            user = db.get_user_by_id(db_path, user_id)
            if user:
                plan = user.get("subscription_plan") or "free"
                month = datetime.now(timezone.utc).strftime("%Y-%m")
                messages_used = db.get_monthly_usage(db_path, user_id, month)
                system = f"{system}\n\n---\n\nUser plan: {plan} | Messages used this month: {messages_used}"
                if bool(user.get("is_admin", 0)):
                    system = f"{system}\n\nThe user you are talking to is the admin and owner of Zeus AI Design. Treat them accordingly."
        except Exception:
            log.warning("run_turn_stream: could not load user subscription context for %s", user_id)

    session_start = datetime.now()
    zeus_text_parts: list[str] = []
    _export_payload: dict | None = None

    try:
        for _ in range(60):  # max agentic turns
            tool_blocks: dict[int, dict] = {}

            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=8000,
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

            # Sanitise assistant content — strip extra fields and drop unreplayable blocks
            safe_content = [s for b in final.content if (s := _sanitise_block(b)) is not None]
            messages.append({"role": "assistant", "content": safe_content})

            if final.stop_reason != "tool_use" or not tool_blocks:
                break

            # Execute tools and collect results
            tool_results = []
            for idx in sorted(tool_blocks):
                result = "(no result)"  # safe default — overwritten by every branch below
                tb = tool_blocks[idx]
                # Async tools — handle inline rather than via _run_tool
                if tb["name"] == "MultiAgentBuild":
                    result = await run_multi_agent(
                        request=tb["input"].get("request", ""),
                        on_message=on_message,
                        history=history,
                        user_id=user_id,
                    )
                elif tb["name"] == "CreateBackgroundTask":
                    result = await _handle_create_background_task(
                        request=tb["input"].get("request", ""),
                        description=tb["input"].get("description", "Background build"),
                        history=history,
                        user_id=user_id,
                    )
                elif tb["name"] == "PushToGitHub":
                    _is_admin_push = False
                    if user_id:
                        try:
                            import db as _db
                            _u = _db.get_user_by_id(_db.get_db_path(), user_id)
                            _is_admin_push = bool(_u and _u.get("is_admin", 0))
                        except Exception:
                            pass
                    if not _is_admin_push:
                        result = "❌ PushToGitHub is restricted to admin users only."
                    else:
                        try:
                            result = await _push_to_github(
                                files=tb["input"].get("files", []),
                                commit_message=tb["input"].get("commit_message", "Update from Zeus"),
                                create_pr=tb["input"].get("create_pr", False),
                                pr_title=tb["input"].get("pr_title", ""),
                                pr_body=tb["input"].get("pr_body", ""),
                            )
                        except Exception as _exc:
                            result = f"❌ PushToGitHub failed: {_exc}"
                elif tb["name"] == "PostToFacebook":
                    try:
                        payload = {"message": tb["input"].get("message", "")}
                        if tb["input"].get("photo_url"):
                            payload["photo"] = tb["input"]["photo_url"]
                        fb_resp = await httpx.AsyncClient().post(
                            "https://hooks.zapier.com/hooks/catch/27182397/u7qsp1n/",
                            json=payload,
                            timeout=15,
                        )
                        if fb_resp.status_code < 300:
                            result = "✅ Posted to the Zeus AI Design Facebook page."
                        else:
                            result = f"❌ Facebook post failed (HTTP {fb_resp.status_code}): {fb_resp.text}"
                    except Exception as _exc:
                        result = f"❌ PostToFacebook failed: {_exc}"
                else:
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
                # Emit a download event if ZipProject succeeded
                if result.startswith("DOWNLOAD_READY:"):
                    zip_filename = result.split("\n", 1)[0].replace("DOWNLOAD_READY:", "").strip()
                    # Resolve base URL: explicit config → Railway public domain → hardcoded production URL
                    _base = (
                        os.environ.get("FRONTEND_URL")
                        or (f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}" if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else None)
                        or "https://zeusaidesign.com"
                    ).rstrip("/")
                    # Strip the token prefix (first segment before _) for the display filename
                    _display = zip_filename.split("_", 1)[-1] if "_" in zip_filename else zip_filename
                    await on_message({
                        "type": "download",
                        "url": f"{_base}/download/{zip_filename}",
                        "filename": _display,
                    })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb["id"],
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

    finally:
        # Guard: if an exception interrupted the tool loop after the assistant's
        # tool_use message was appended but before tool_results were appended,
        # the history would contain a dangling tool_use with no tool_result —
        # Anthropic rejects that on the next request.  Strip it before saving.
        if (messages
                and messages[-1].get("role") == "assistant"
                and isinstance(messages[-1].get("content"), list)
                and any(
                    isinstance(b, dict) and b.get("type") == "tool_use"
                    for b in messages[-1]["content"]
                )):
            messages.pop()

        # Always persist whatever was exchanged — even if the loop threw
        if len(messages) > 1:  # more than just the user prompt
            try:
                history.save_messages(session_id, messages)
                turn_count = sum(1 for m in messages if m["role"] == "user")
                history.log_turn(session_id, turn_count, "user", prompt)
                zeus_text = "".join(zeus_text_parts).strip()
                # Detect and strip export tag before persisting to history
                match = EXPORT_TAG_RE.search(zeus_text)
                if match:
                    _export_payload = {
                        "type": "export_ready",
                        "doc_type": match.group(1),
                        "title": match.group(2),
                    }
                    zeus_text = EXPORT_TAG_RE.sub('', zeus_text).rstrip()
                if zeus_text:
                    history.log_turn(session_id, turn_count, "zeus", zeus_text)
                history.save_session(session_id, session_start, turn_count, prompt, user_id=user_id)
            except Exception:
                log.exception("Failed to persist session %s", session_id)

    if _export_payload:
        await on_message(_export_payload)
    await on_message({"type": "done"})
    return session_id
