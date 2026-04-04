import anyio
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import json
import pathlib
from datetime import datetime

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

# ── Colour helpers ─────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
GOLD   = "\033[93m"

def c(text: str, *codes: str) -> str:
    return "".join(codes) + text + RESET

# ── System prompt ──────────────────────────────────────────────────────────────

ZEUS_SYSTEM_PROMPT = """You are Zeus, a powerful AI assistant built to help run a web design business. You are resourceful, confident, and genuinely invested in the success of the business.

## Your capabilities

**Website Building & Live Deployment**
- Build complete, modern, responsive websites from scratch
- Write clean HTML, CSS, and JavaScript — semantic markup, flexbox/grid, smooth animations
- Create landing pages, portfolios, business sites, e-commerce layouts
- Use vanilla HTML/CSS/JS by default; use frameworks when asked
- Deploy finished sites live to Netlify and hand back the URL (see workflow below)

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

## Live Website Builder — Full Workflow

When a user asks you to build them a website (phrases like "build me a site", "make a website for my business", "I need a website"), follow this exact workflow:

### Step 1 — Intake (use AskUserQuestion for each question, one at a time)
1. "What's the name of your business or project?"
2. "Where are you based? (city/country — or 'online only' if that fits)"
3. "What do you do — what services or products do you offer?"
4. "Who are your customers? Describe your typical client or visitor."
5. "What style do you want? (e.g. modern & minimal, bold & colourful, elegant & professional, friendly & approachable)"
6. "Which pages do you need? (e.g. Home, About, Services, Portfolio, Contact — or say 'just a one-pager')"
7. "Any colours, fonts, or websites you like the look of? (optional — skip if unsure)"

### Step 2 — Build the site
- Create a project folder: `C:/Users/Student/<business-name-slug>/`
  - Slug = lowercase, hyphens, no spaces (e.g. "Smith Plumbing" → `smith-plumbing`)
- Write a complete, professional website using the answers above:
  - `index.html` — full homepage: hero with headline & CTA, services/features section,
    about snippet, social proof or testimonial placeholder, contact section, footer
  - `style.css` — polished responsive CSS: CSS custom properties for brand colours,
    mobile-first media queries, flexbox/grid layouts, clean typography, hover effects
  - `script.js` — smooth scroll, mobile nav hamburger toggle, subtle fade-in animations
  - Any additional pages requested (about.html, services.html, contact.html, etc.)
- **Write real copy throughout** — use the business name, location, services, and target
  audience from Step 1. Zero placeholder text like "Lorem ipsum" or "Your company name".
- Match the style preference in every design decision (layout, colours, font choices).

### Step 3 — Deploy to Netlify
After all files are saved, run this command via Bash:
```
python C:/Users/Student/netlify_deploy.py "C:/Users/Student/<folder-name>" "<business-name-slug>"
```
Capture the output. The last line will contain the live URL ("✓ Live at: https://…").

### Step 4 — Report back
Tell the user:
- The live URL (clickable)
- A brief list of what was built (pages, key sections)
- How to update content: "Edit the files in C:/Users/Student/<folder>/ and re-run the deploy command to push changes"

---

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

# ── Tools ──────────────────────────────────────────────────────────────────────

ZEUS_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "AskUserQuestion",
]

# ── Session state ──────────────────────────────────────────────────────────────

class Session:
    def __init__(self):
        self.session_id: str | None = None
        self.turn: int = 0
        self.started_at = datetime.now()

    @property
    def label(self) -> str:
        if self.session_id:
            return self.session_id[:8] + "…"
        return "new"

# ── History store ─────────────────────────────────────────────────────────────

class HistoryStore:
    def __init__(self):
        self.dir = pathlib.Path.home() / ".zeus"
        self.dir.mkdir(exist_ok=True)
        self.sessions_file = self.dir / "sessions.json"
        self.history_file  = self.dir / "history.json"

    def log_turn(self, session_id: str, turn: int, role: str, text: str) -> None:
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"session_id": session_id, "turn": turn,
                                "role": role, "text": text}) + "\n")

    def save_session(self, session_id: str, started: datetime,
                     turns: int, preview: str) -> None:
        sessions = self._read_sessions()
        entry = {"id": session_id, "started": started.isoformat(),
                 "turns": turns, "preview": preview[:80]}
        for i, s in enumerate(sessions):
            if s["id"] == session_id:
                sessions[i] = entry
                break
        else:
            sessions.append(entry)
        self.sessions_file.write_text(
            json.dumps(sessions, indent=2), encoding="utf-8")

    def list_sessions(self) -> list:
        sessions = self._read_sessions()
        return list(reversed(sessions))

    def get_transcript(self, session_id: str) -> list:
        if not self.history_file.exists():
            return []
        lines = []
        with self.history_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("session_id") == session_id:
                        lines.append(entry)
                except json.JSONDecodeError:
                    pass
        return lines

    def _read_sessions(self) -> list:
        if not self.sessions_file.exists():
            return []
        try:
            return json.loads(self.sessions_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

# ── Help text ──────────────────────────────────────────────────────────────────

HELP = f"""
{c("What Zeus can do", BOLD, GOLD)}
  • Build complete websites and save them to project folders
  • Manage files, search codebases, organise project assets
  • Search the web for trends, references, tools, and pricing
  • Write website copy, blog posts, case studies, SEO content
  • Draft client emails — proposals, follow-ups, cold outreach
  • Help price projects, write proposals, grow the business

{c("Commands", BOLD, CYAN)}
  {c("/help", BOLD)}          Show this help
  {c("/new", BOLD)}           Start a fresh session
  {c("/session", BOLD)}       Show current session ID
  {c("/history", BOLD)}       List past sessions
  {c("/history <n>", BOLD)}   Show transcript for session n
  {c("/resume <n|id>", BOLD)} Resume session by number or ID
  {c("/exit", BOLD)}          Quit  (also: exit, quit, q)
"""

# ── Core agent runner ──────────────────────────────────────────────────────────

async def stream_turn(prompt: str, session: Session, history: HistoryStore):
    """Async generator — yields text chunks as Zeus responds."""
    opts = ClaudeAgentOptions(
        system_prompt=ZEUS_SYSTEM_PROMPT,
        allowed_tools=ZEUS_TOOLS,
        permission_mode="acceptEdits",
        model="claude-opus-4-6",
        max_turns=60,
        cwd="C:/Users/Student",
        **({"resume": session.session_id} if session.session_id else {}),
    )

    zeus_text_parts: list[str] = []
    user_logged = False
    error_occurred = False

    # If resuming an existing session, log the user turn immediately
    if session.session_id:
        history.log_turn(session.session_id, session.turn + 1, "user", prompt)
        user_logged = True

    try:
        async for message in query(prompt=prompt, options=opts):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                new_id = message.data.get("session_id")
                if new_id and new_id != session.session_id:
                    session.session_id = new_id
                if session.session_id and not user_logged:
                    history.log_turn(session.session_id, session.turn + 1, "user", prompt)
                    user_logged = True

            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        zeus_text_parts.append(block.text)
                        yield block.text

            elif isinstance(message, ResultMessage):
                reason = message.stop_reason
                if reason and reason not in ("end_turn", "max_turns"):
                    yield f"\n[stopped: {reason}]"

    except CLINotFoundError:
        yield "\n✗ Claude Code CLI not found. Ensure `claude` is on your PATH."
        error_occurred = True
    except CLIConnectionError as exc:
        yield f"\n✗ Connection error: {exc}"
        error_occurred = True
    finally:
        session.turn += 1
        if session.session_id and not error_occurred:
            zeus_text = "".join(zeus_text_parts).strip()
            if zeus_text:
                history.log_turn(session.session_id, session.turn, "zeus", zeus_text)
            history.save_session(session.session_id, session.started_at,
                                 session.turn, prompt)


async def run_turn(prompt: str, session: Session, history: HistoryStore) -> None:
    """CLI wrapper: streams stream_turn() output to the terminal."""
    print(c("\n Zeus  ", BOLD, GOLD), end="", flush=True)
    try:
        async for chunk in stream_turn(prompt, session, history):
            print(chunk, end="", flush=True)
    except KeyboardInterrupt:
        print(c("\n[interrupted]", DIM, YELLOW))
    print("\n")

# ── Command handling ───────────────────────────────────────────────────────────

def handle_command(text: str, session: Session, history: HistoryStore) -> bool:
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower()

    if cmd in ("/exit", "/quit", "exit", "quit", "q"):
        print(c("Later. ⚡", GOLD))
        sys.exit(0)

    if cmd == "/help":
        print(HELP)
        return True

    if cmd == "/new":
        session.session_id = None
        session.turn = 0
        session.started_at = datetime.now()
        print(c("✓ Fresh session started.", GREEN))
        return True

    if cmd == "/session":
        if session.session_id:
            print(c(f"Session ID: {session.session_id}", CYAN))
            print(c(f"Turns:      {session.turn}", DIM))
        else:
            print(c("No active session yet — send your first message to start one.", DIM))
        return True

    if cmd == "/history":
        arg = arg.strip()
        if arg:
            # Show transcript for session n
            try:
                n = int(arg)
            except ValueError:
                print(c("Usage: /history <number>", YELLOW))
                return True
            sessions = history.list_sessions()
            if n < 1 or n > len(sessions):
                print(c(f"No session {n}. Use /history to list sessions.", YELLOW))
                return True
            sid = sessions[n - 1]["id"]
            turns = history.get_transcript(sid)
            if not turns:
                print(c("No transcript found for that session.", DIM))
                return True
            print()
            for entry in turns:
                if entry["role"] == "user":
                    label = c("You", BOLD, GREEN) + c(f" [{entry['turn']}] › ", DIM)
                    print(label + entry["text"])
                else:
                    label = c("Zeus", BOLD, GOLD) + c(f" [{entry['turn']}]  ", DIM)
                    print(label + entry["text"])
                print()
        else:
            # List all sessions
            sessions = history.list_sessions()
            if not sessions:
                print(c("No history yet.", DIM))
                return True
            print()
            for i, s in enumerate(sessions, 1):
                dt = datetime.fromisoformat(s["started"]).strftime("%Y-%m-%d %H:%M")
                turns = s.get("turns", 0)
                preview = s.get("preview", "")
                num    = c(f"[{i}]", BOLD, CYAN)
                meta   = c(f"  {dt}  {turns} turn{'s' if turns != 1 else ''}  ", DIM)
                print(f"{num}{meta}\"{preview}\"")
            print()
        return True

    if cmd == "/resume":
        sid = arg.strip()
        if not sid:
            print(c("Usage: /resume <n> or /resume <session-id>", YELLOW))
            return True
        # Numeric shortcut
        if sid.isdigit():
            sessions = history.list_sessions()
            n = int(sid)
            if n < 1 or n > len(sessions):
                print(c(f"No session {n}. Use /history to list sessions.", YELLOW))
                return True
            sid = sessions[n - 1]["id"]
        session.session_id = sid
        session.turn = 0
        print(c(f"✓ Resuming session {sid[:16]}…", GREEN))
        return True

    return False

# ── Main REPL ──────────────────────────────────────────────────────────────────

async def main() -> None:
    # Support single-shot mode: python zeus.py "build me a landing page"
    history = HistoryStore()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        session = Session()
        await run_turn(prompt, session, history)
        return

    session = Session()

    print(c(r"""
  ╔════════════════════════════════════════╗
  ║   ⚡  Z E U S  —  Web Design AI  ⚡   ║
  ╚════════════════════════════════════════╝""", BOLD, GOLD))
    print(c("  Websites · Files · Research · Copy · Emails · Business", DIM))
    print(c("  Type /help for commands, /exit to quit\n", DIM))

    while True:
        turn_label = c(f"[{session.turn}]", DIM) if session.turn else ""
        try:
            user_input = input(c("You", BOLD, GREEN) + turn_label + c(" › ", DIM)).strip()
        except (EOFError, KeyboardInterrupt):
            print(c("\nLater. ⚡", GOLD))
            break

        if not user_input:
            continue

        if handle_command(user_input, session, history):
            continue

        await run_turn(user_input, session, history)


if __name__ == "__main__":
    anyio.run(main)
