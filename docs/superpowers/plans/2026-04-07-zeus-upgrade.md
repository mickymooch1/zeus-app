# Zeus AI Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Zeus from a web-design assistant into a full business writing assistant with document export (PDF + Word), grammar check mode, a quick-action toolbar, and word count display.

**Architecture:** Four independent change areas built on the existing FastAPI + WebSocket + React stack. Zeus signals exportable documents with an inline `[ZEUS_EXPORT: type=X title="Y"]` tag that is stripped client-side and converted to a download button. Export uses a stateless `POST /export` endpoint; no database changes.

**Tech Stack:** FastAPI, anthropic SDK, fpdf2, python-docx, React, useZeusSocket hook, ReactMarkdown

---

## File Changes

| File | Change |
|------|--------|
| `backend/requirements.txt` | Add `fpdf2>=2.7.0`, `python-docx>=1.1.0` |
| `backend/main.py` | Add `generate_pdf`, `generate_docx`, `slugify`, `ExportRequest`, `POST /export` |
| `backend/zeus_agent.py` | Update system prompt + personality, add `EXPORT_TAG_RE`, export detection in `run_turn_stream` |
| `web/src/hooks/useZeusSocket.js` | Handle `export_ready` event; strip export tag from text deltas |
| `web/src/components/Toolbar.jsx` | New file — quick-action chip buttons |
| `web/src/components/ChatWindow.jsx` | Lift textarea state; render `<Toolbar>` |
| `web/src/components/InputBar.jsx` | Accept `value`/`setValue` props; add grammar check toggle |
| `web/src/components/MessageBubble.jsx` | Word count display; export button + fetch handler |
| `backend/tests/test_export.py` | New test file for export utilities and endpoint |

---

### Task 1: Add dependencies to requirements.txt

**Files:**
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_export.py` (create)

- [ ] **Step 1: Write the failing import test**

Create `backend/tests/test_export.py`:

```python
def test_fpdf2_importable():
    import fpdf  # fpdf2 installs as 'fpdf'
    assert hasattr(fpdf, 'FPDF')


def test_python_docx_importable():
    import docx
    assert hasattr(docx, 'Document')
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_export.py -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'fpdf'`

- [ ] **Step 3: Add dependencies to requirements.txt**

Append to `backend/requirements.txt` after the existing lines:

```
fpdf2>=2.7.0
python-docx>=1.1.0
```

- [ ] **Step 4: Install the new dependencies**

```
cd C:\Users\Student\zeus-app\backend
pip install fpdf2>=2.7.0 "python-docx>=1.1.0"
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_export.py::test_fpdf2_importable tests/test_export.py::test_python_docx_importable -v
```

Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/tests/test_export.py
git commit -m "feat: add fpdf2 and python-docx dependencies for document export"
```

---

### Task 2: Add export utilities to main.py (generate_pdf, generate_docx, slugify)

**Files:**
- Modify: `backend/main.py` (add imports + three functions near top, after existing imports)
- Test: `backend/tests/test_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_export.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_slugify_basic():
    from main import slugify
    assert slugify("My Great Document") == "my-great-document"


def test_slugify_special_chars():
    from main import slugify
    assert slugify("Hello, World! 2024") == "hello-world-2024"


def test_slugify_max_length():
    from main import slugify
    long = "a" * 100
    assert len(slugify(long)) <= 60


def test_generate_pdf_returns_bytes():
    from main import generate_pdf
    result = generate_pdf("Hello world.\n\nSecond paragraph.", "Test Title")
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b'%PDF'


def test_generate_docx_returns_bytes():
    from main import generate_docx
    result = generate_docx("Hello world.\n\nSecond paragraph.", "Test Title")
    assert isinstance(result, bytes)
    assert len(result) > 100
    # docx files are ZIP archives starting with PK
    assert result[:2] == b'PK'
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_export.py::test_slugify_basic tests/test_export.py::test_generate_pdf_returns_bytes tests/test_export.py::test_generate_docx_returns_bytes -v
```

Expected: FAILED — `ImportError: cannot import name 'slugify' from 'main'`

- [ ] **Step 3: Add imports and utility functions to main.py**

In `backend/main.py`, after the existing imports block (after `import billing`), add:

```python
import io
import re as _re

from fpdf import FPDF
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def slugify(text: str) -> str:
    text = text.lower()
    text = _re.sub(r'[^a-z0-9\s-]', '', text)
    text = _re.sub(r'[\s-]+', '-', text).strip('-')
    return text[:60]


def generate_pdf(text: str, title: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Title
    pdf.set_font("Helvetica", style="B", size=18)
    pdf.cell(0, 12, title, align="C", new_x="LMARGIN", new_y="NEXT")

    # Horizontal rule
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    # Body
    pdf.set_font("Helvetica", size=11)
    pdf.set_text_color(30, 30, 30)
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        pdf.multi_cell(0, 6, para)
        pdf.ln(4)

    # Footer
    pdf.set_y(-15)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Generated by Zeus \u00b7 zeusaidesign.com", align="C")

    return bytes(pdf.output())


def generate_docx(text: str, title: str) -> bytes:
    doc = DocxDocument()

    # Title as Heading 1
    doc.add_heading(title, level=1)

    # Body — double-newline = paragraph, single-newline = line break within paragraph
    for para_text in text.split("\n\n"):
        para_text = para_text.strip()
        if not para_text:
            continue
        lines = para_text.split("\n")
        para = doc.add_paragraph(lines[0])
        for line in lines[1:]:
            run = para.add_run()
            br = OxmlElement("w:br")
            run._r.append(br)
            para.add_run(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_export.py::test_slugify_basic tests/test_export.py::test_slugify_special_chars tests/test_export.py::test_slugify_max_length tests/test_export.py::test_generate_pdf_returns_bytes tests/test_export.py::test_generate_docx_returns_bytes -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_export.py
git commit -m "feat: add generate_pdf, generate_docx, slugify utilities"
```

---

### Task 3: Add POST /export endpoint to main.py

**Files:**
- Modify: `backend/main.py` (add `ExportRequest` model + `/export` route)
- Test: `backend/tests/test_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_export.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Set a dummy API key so lifespan doesn't fail
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    from main import app
    return TestClient(app, raise_server_exceptions=True)


def test_export_pdf_content_type(client):
    resp = client.post("/export", json={
        "text": "Hello world.",
        "format": "pdf",
        "title": "Test Doc",
        "doc_type": "essay",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "test-doc.pdf" in resp.headers["content-disposition"]


def test_export_docx_content_type(client):
    resp = client.post("/export", json={
        "text": "Hello world.",
        "format": "docx",
        "title": "Test Doc",
        "doc_type": "essay",
    })
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert "test-doc.docx" in resp.headers["content-disposition"]


def test_export_invalid_format(client):
    resp = client.post("/export", json={
        "text": "Hello.",
        "format": "txt",
        "title": "Bad",
        "doc_type": "essay",
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_export.py::test_export_pdf_content_type -v
```

Expected: FAILED — `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add ExportRequest model and /export route to main.py**

In `backend/main.py`, in the "Pydantic request models" section, add after `CheckoutRequest`:

```python
class ExportRequest(BaseModel):
    text: str
    format: str   # "pdf" or "docx"
    title: str
    doc_type: str
```

In `backend/main.py`, after the `/tunnel-url` route, add:

```python
@app.post("/export")
async def export_document(body: ExportRequest):
    if body.format == "pdf":
        file_bytes = generate_pdf(body.text, body.title)
        media_type = "application/pdf"
        filename = f"{slugify(body.title)}.pdf"
    elif body.format == "docx":
        file_bytes = generate_docx(body.text, body.title)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{slugify(body.title)}.docx"
    else:
        raise HTTPException(status_code=400, detail="format must be pdf or docx")
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_export.py::test_export_pdf_content_type tests/test_export.py::test_export_docx_content_type tests/test_export.py::test_export_invalid_format -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add POST /export endpoint for PDF and Word document download"
```

---

### Task 4: Update ZEUS_SYSTEM_PROMPT and personality in zeus_agent.py

**Files:**
- Modify: `backend/zeus_agent.py` (lines 38–117: `ZEUS_SYSTEM_PROMPT`)

No automated test for the prompt text itself — correctness is validated via manual chat testing. This task is a direct edit.

- [ ] **Step 1: Replace the capabilities section**

In `backend/zeus_agent.py`, find the `**Content & Copywriting**` section and replace everything from it through `**Business Operations**` and `## Your personality` with the new content.

The full replacement (find `**Content & Copywriting**` through `The goal is to get smarter with every conversation. Save learnings freely.\n"""`):

Replace:
```
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
```

With:
```
**Writing & Content**
- Essays: structured arguments with intro, body, conclusion; appropriate academic or casual tone
- Blog posts and articles: engaging hooks, clear sections, strong CTAs
- CVs and cover letters: professional formatting, tailored to role/industry
- Business proposals: executive summary, scope, pricing, timeline
- Website copy: headlines, taglines, about pages, service descriptions, CTAs
- Email drafting: professional client emails, cold outreach, templates for common scenarios

**Grammar & Language**
- Grammar checking: proofread user-provided text, return corrected version with a brief list of changes made
- Tone adjustment: rewrite any text as formal, casual, or persuasive on request
- Translation: translate text to any requested language, preserving meaning and tone
- Word count: state approximate word count when producing long documents (>200 words)

**Export signalling**
When Zeus produces an exportable document (essay, blog post, CV, cover letter, proposal, business plan,
proofread text), it MUST end its response with this exact tag on its own line:
[ZEUS_EXPORT: type=<type> title="<descriptive title>"]

Valid types: essay, blog, cv, cover_letter, proposal, business_plan, document
The tag is stripped from display by the frontend — users never see it.
Do NOT include the tag for conversational replies, short answers, website builds, or research summaries.

**Business Operations**
- Help price projects and write proposals
- Track what needs doing and suggest next steps
- Advise on tools, workflows, and how to grow a web design business
- Answer questions about freelancing, client management, and contracts

## Your personality
- Warm, encouraging, and genuinely invested in the user's success
- Direct and clear — no waffle, but never cold
- Ask ONE clarifying question before starting essays, CVs, proposals, or business plans
  (e.g. "Who is this CV for — what industry and level?")
- Celebrate completions briefly ("Strong proposal — here's what makes it work")
- Remember context within the conversation — refer back to earlier details naturally
- Web design remains your primary strength; present all other capabilities as natural extensions
- Never use filler phrases like "Certainly!", "Of course!", "Great question!"

## Working style
- Brief plan → execute → summary of what was done
- Always save website files into a named project folder under the working directory
- Use real-world best practices: mobile-first, accessible markup, optimised assets
- When writing copy or emails, match the user's voice if examples are provided
```

- [ ] **Step 2: Verify the file still parses**

```
python -c "import zeus_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/zeus_agent.py
git commit -m "feat: expand Zeus system prompt with writing, grammar, and export signalling capabilities"
```

---

### Task 5: Add EXPORT_TAG_RE and export_ready detection to zeus_agent.py

**Files:**
- Modify: `backend/zeus_agent.py` (add `import re`, module-level `EXPORT_TAG_RE`, modify `run_turn_stream`)
- Test: `backend/tests/test_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_export.py`:

```python
def test_export_tag_regex_matches():
    import re
    from zeus_agent import EXPORT_TAG_RE
    text = 'Some content.\n\n[ZEUS_EXPORT: type=essay title="Climate Change Essay"]'
    m = EXPORT_TAG_RE.search(text)
    assert m is not None
    assert m.group(1) == "essay"
    assert m.group(2) == "Climate Change Essay"


def test_export_tag_regex_strips_cleanly():
    from zeus_agent import EXPORT_TAG_RE
    text = 'Body text.\n\n[ZEUS_EXPORT: type=cv title="My CV"]\n'
    clean = EXPORT_TAG_RE.sub('', text).rstrip()
    assert clean == 'Body text.'
    assert '[ZEUS_EXPORT' not in clean


def test_export_tag_regex_no_match_conversational():
    from zeus_agent import EXPORT_TAG_RE
    text = "Sure, I can help you with that website."
    assert EXPORT_TAG_RE.search(text) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_export.py::test_export_tag_regex_matches -v
```

Expected: FAILED — `ImportError: cannot import name 'EXPORT_TAG_RE' from 'zeus_agent'`

- [ ] **Step 3: Add import re and EXPORT_TAG_RE to zeus_agent.py**

In `backend/zeus_agent.py`, find the existing imports block at the top (around line 1). After `import uuid`, add:

```python
import re
```

Then after the `import httpx` line and before `log = logging.getLogger`, add:

```python
EXPORT_TAG_RE = re.compile(
    r'\[ZEUS_EXPORT:\s*type=(\w+)\s+title="([^"]+)"\]',
    re.IGNORECASE,
)
```

- [ ] **Step 4: Modify run_turn_stream to detect and emit export_ready**

In `backend/zeus_agent.py`, find the `finally:` block in `run_turn_stream` (around line 1196). The current finally block is:

```python
    finally:
        # Always persist whatever was exchanged — even if the loop threw
        if len(messages) > 1:  # more than just the user prompt
            try:
                history.save_messages(session_id, messages)
                turn_count = sum(1 for m in messages if m["role"] == "user")
                history.log_turn(session_id, turn_count, "user", prompt)
                zeus_text = "".join(zeus_text_parts).strip()
                if zeus_text:
                    history.log_turn(session_id, turn_count, "zeus", zeus_text)
                history.save_session(session_id, session_start, turn_count, prompt)
            except Exception:
                log.exception("Failed to persist session %s", session_id)

    await on_message({"type": "done"})
```

Replace with:

```python
    _export_payload: dict | None = None

    finally:
        # Always persist whatever was exchanged — even if the loop threw
        if len(messages) > 1:  # more than just the user prompt
            try:
                history.save_messages(session_id, messages)
                turn_count = sum(1 for m in messages if m["role"] == "user")
                history.log_turn(session_id, turn_count, "user", prompt)
                zeus_text = "".join(zeus_text_parts).strip()
                # Detect and strip export tag before persisting
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
                history.save_session(session_id, session_start, turn_count, prompt)
            except Exception:
                log.exception("Failed to persist session %s", session_id)

    if _export_payload:
        await on_message(_export_payload)
    await on_message({"type": "done"})
```

**Note:** `_export_payload` must be declared BEFORE the `try:` block (not inside `finally:`), so it is in scope after the `finally` ends. Move the declaration to just before `try:` at line 1100. The existing code has `zeus_text_parts: list[str] = []` there — add `_export_payload` beside it:

Find in `run_turn_stream`:
```python
    session_start = datetime.now()
    zeus_text_parts: list[str] = []

    try:
```

Replace with:
```python
    session_start = datetime.now()
    zeus_text_parts: list[str] = []
    _export_payload: dict | None = None

    try:
```

And in the `finally:` block, remove the `_export_payload: dict | None = None` line that was incorrectly placed before `finally:` in the previous step.

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_export.py::test_export_tag_regex_matches tests/test_export.py::test_export_tag_regex_strips_cleanly tests/test_export.py::test_export_tag_regex_no_match_conversational -v
```

Expected: 3 PASSED

- [ ] **Step 6: Verify the file still parses**

```
python -c "import zeus_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/zeus_agent.py backend/tests/test_export.py
git commit -m "feat: detect ZEUS_EXPORT tag in stream and emit export_ready WebSocket event"
```

---

### Task 6: Update useZeusSocket.js — handle export_ready and strip tag from text deltas

**Files:**
- Modify: `web/src/hooks/useZeusSocket.js`

No automated JS test — verified manually via chat. The changes are mechanical.

- [ ] **Step 1: Add EXPORT_TAG_RE constant and strip from text deltas**

In `web/src/hooks/useZeusSocket.js`, after the `const BACKEND_URL` line, add:

```js
const EXPORT_TAG_RE = /\[ZEUS_EXPORT:[^\]]+\]/gi;
```

In the `ws.onmessage` handler, find the `text` case:

```js
      if (data.type === 'text') {
        setMessages(prev => prev.map(m =>
          m.id === zeusMsgId ? { ...m, text: m.text + data.delta } : m
        ));
```

Replace with:

```js
      if (data.type === 'text') {
        const cleanDelta = data.delta.replace(EXPORT_TAG_RE, '');
        if (cleanDelta) {
          setMessages(prev => prev.map(m =>
            m.id === zeusMsgId ? { ...m, text: m.text + cleanDelta } : m
          ));
        }
```

- [ ] **Step 2: Add export_ready event handler**

In `ws.onmessage`, find the `} else if (data.type === 'done') {` block:

```js
      } else if (data.type === 'done') {
        setStreaming(false);
        streamingRef.current = false;
        ws.close();
      }
```

Insert before it:

```js
      } else if (data.type === 'export_ready') {
        setMessages(prev => prev.map(m =>
          m.id === zeusMsgId
            ? { ...m, exportReady: { doc_type: data.doc_type, title: data.title } }
            : m
        ));
      } else if (data.type === 'done') {
```

(Remove the original `} else if (data.type === 'done')` since it's now part of the replacement.)

- [ ] **Step 3: Verify no syntax errors**

```
cd C:\Users\Student\zeus-app\web
npm run build 2>&1 | head -30
```

Expected: build completes without errors (or only the existing warnings)

- [ ] **Step 4: Commit**

```bash
git add web/src/hooks/useZeusSocket.js
git commit -m "feat: handle export_ready WebSocket event and strip export tag from text deltas"
```

---

### Task 7: Create Toolbar.jsx

**Files:**
- Create: `web/src/components/Toolbar.jsx`

- [ ] **Step 1: Create the file**

Create `web/src/components/Toolbar.jsx`:

```jsx
const CHIPS = [
  { label: '✍️ Essay',    starter: 'Write an essay about ' },
  { label: '📝 Blog Post', starter: 'Write a blog post about ' },
  { label: '📄 CV',        starter: 'Write a CV for ' },
  { label: '📧 Email',     starter: 'Draft an email to ' },
  { label: '📋 Proposal',  starter: 'Write a business proposal for ' },
  { label: '🌐 Website',   starter: 'Build a website for ' },
];

export function Toolbar({ onChipClick }) {
  return (
    <div className="toolbar">
      {CHIPS.map(c => (
        <button
          key={c.label}
          className="chip"
          onClick={() => onChipClick(c.starter)}
          type="button"
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify no syntax errors**

```
cd C:\Users\Student\zeus-app\web
npm run build 2>&1 | head -30
```

Expected: build completes without errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/Toolbar.jsx
git commit -m "feat: add Toolbar component with quick-action chips"
```

---

### Task 8: Lift textarea state to ChatWindow and integrate Toolbar

**Files:**
- Modify: `web/src/components/ChatWindow.jsx`
- Modify: `web/src/components/InputBar.jsx`

The textarea `value`/`setValue` state moves from `InputBar` to `ChatWindow`. `Toolbar` chips call `setValue` on `ChatWindow`'s state, which flows down to `InputBar`. This allows chips to pre-fill the textarea.

- [ ] **Step 1: Update InputBar.jsx to accept value/setValue as props**

Replace the entire content of `web/src/components/InputBar.jsx`:

```jsx
import { useState } from 'react';

export function InputBar({ onSend, disabled, value, setValue, grammarMode, setGrammarMode }) {
  // If value/setValue not provided (legacy usage), manage state locally
  const [localValue, setLocalValue] = useState('');
  const inputValue = value !== undefined ? value : localValue;
  const setInputValue = setValue !== undefined ? setValue : setLocalValue;

  const [localGrammarMode, setLocalGrammarMode] = useState(false);
  const activeGrammarMode = grammarMode !== undefined ? grammarMode : localGrammarMode;
  const setActiveGrammarMode = setGrammarMode !== undefined ? setGrammarMode : setLocalGrammarMode;

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text || disabled) return;
    const prompt = activeGrammarMode
      ? `Please proofread and correct the following text. Return the corrected version with a brief list of changes made:\n\n${text}`
      : text;
    onSend(prompt);
    setInputValue('');
    setActiveGrammarMode(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-bar">
      <textarea
        className="input-field"
        value={inputValue}
        onChange={e => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={activeGrammarMode ? 'Paste your text here for proofreading...' : 'Ask Zeus anything...'}
        rows={1}
        disabled={disabled}
      />
      <button
        className={`grammar-btn${activeGrammarMode ? ' grammar-btn--active' : ''}`}
        onClick={() => setActiveGrammarMode(g => !g)}
        disabled={disabled}
        type="button"
        title="Grammar check mode"
        aria-pressed={activeGrammarMode}
      >
        GC
      </button>
      <button
        className="send-btn"
        onClick={handleSend}
        disabled={disabled || !inputValue.trim()}
        aria-label="Send"
      >
        ⚡
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Update ChatWindow.jsx to lift state and render Toolbar**

Replace the entire content of `web/src/components/ChatWindow.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';
import { Toolbar } from './Toolbar';

export function ChatWindow({ messages, streaming, onSend }) {
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const [inputValue, setInputValue] = useState('');
  const [grammarMode, setGrammarMode] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleChipClick = (starter) => {
    setInputValue(starter);
    textareaRef.current?.focus();
  };

  return (
    <main className="chat-window">
      <div className="message-list">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <div className="empty-title">Ask Zeus anything.</div>
            <div className="empty-sub">Websites · Writing · Research · Business</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={
              streaming &&
              i === messages.length - 1 &&
              msg.role === 'zeus'
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>
      <Toolbar onChipClick={handleChipClick} />
      <InputBar
        onSend={onSend}
        disabled={streaming}
        value={inputValue}
        setValue={setInputValue}
        grammarMode={grammarMode}
        setGrammarMode={setGrammarMode}
        textareaRef={textareaRef}
      />
    </main>
  );
}
```

- [ ] **Step 3: Update InputBar to accept and use textareaRef**

In `web/src/components/InputBar.jsx`, update the function signature to accept `textareaRef`:

```jsx
export function InputBar({ onSend, disabled, value, setValue, grammarMode, setGrammarMode, textareaRef }) {
```

And add `ref={textareaRef}` to the `<textarea>` element:

```jsx
      <textarea
        ref={textareaRef}
        className="input-field"
        ...
```

- [ ] **Step 4: Verify build succeeds**

```
cd C:\Users\Student\zeus-app\web
npm run build 2>&1 | head -30
```

Expected: build completes without errors

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ChatWindow.jsx web/src/components/InputBar.jsx
git commit -m "feat: lift textarea state to ChatWindow, integrate Toolbar chips, add grammar check toggle"
```

---

### Task 9: Update MessageBubble.jsx — word count and export button

**Files:**
- Modify: `web/src/components/MessageBubble.jsx`

- [ ] **Step 1: Add word count helper and export handler**

Replace the entire content of `web/src/components/MessageBubble.jsx`:

```jsx
import ReactMarkdown from 'react-markdown';

const DOWNLOAD_URL_RE = /https?:\/\/\S+\/download\/[^\s)]+\.zip/gi;

function linkRenderer({ href, children }) {
  const isDownload = href && /\/download\/.+\.zip$/i.test(href);
  const filename = isDownload
    ? href.split('/').pop().replace(/^[0-9a-f]{8}_/, '')
    : null;
  if (isDownload) {
    return (
      <a
        href={href}
        download={filename}
        target="_blank"
        rel="noopener noreferrer"
        className="download-btn"
      >
        ⬇ {children || `Download ${filename}`}
      </a>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

async function handleExport(message, format) {
  try {
    const res = await fetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: message.text,
        format,
        title: message.exportReady.title,
        doc_type: message.exportReady.doc_type,
      }),
    });
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = message.exportReady.title + (format === 'pdf' ? '.pdf' : '.docx');
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert('Export failed — please try again.');
  }
}

export function MessageBubble({ message, isStreaming }) {
  if (message.role === 'user') {
    return (
      <div className="message-user">
        <div className="bubble-user">{message.text}</div>
      </div>
    );
  }

  const showCursor = isStreaming && !message.error;
  const wc = message.text ? wordCount(message.text) : 0;

  return (
    <div className="message-zeus">
      <div className="zeus-avatar">⚡</div>
      <div className="bubble-zeus">
        <div className="zeus-label">ZEUS</div>

        {(message.text || showCursor) && (
          <div className="zeus-text">
            <ReactMarkdown
              components={{ a: linkRenderer }}
            >
              {message.text || ''}
            </ReactMarkdown>
            {showCursor && <span className="cursor">▍</span>}
          </div>
        )}

        {!isStreaming && wc >= 50 && (
          <div className="word-count">~{wc} words</div>
        )}

        {message.tools?.length > 0 && (
          <div className="tool-log">
            {message.tools.map((t, i) => (
              <div key={i} className={`tool-item ${t.status}`}>
                {t.status === 'done' ? '✓' : '⟳'} {t.name}
                {t.path ? `: ${t.path}` : ''}
              </div>
            ))}
          </div>
        )}

        {message.downloads?.length > 0 && (
          <div className="download-list">
            {message.downloads.map((d, i) => (
              <a
                key={i}
                href={d.url}
                download={d.filename}
                target="_blank"
                rel="noopener noreferrer"
                className="download-btn"
              >
                ⬇ Download {d.filename}
              </a>
            ))}
          </div>
        )}

        {message.exportReady && (
          <div className="export-bar">
            <span className="export-label">Export as:</span>
            <button
              className="export-btn"
              onClick={() => handleExport(message, 'pdf')}
              type="button"
            >
              ⬇ PDF
            </button>
            <button
              className="export-btn"
              onClick={() => handleExport(message, 'docx')}
              type="button"
            >
              ⬇ Word
            </button>
          </div>
        )}

        {message.error && (
          <div className="error-banner">{message.error}</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build succeeds**

```
cd C:\Users\Student\zeus-app\web
npm run build 2>&1 | head -30
```

Expected: build completes without errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MessageBubble.jsx
git commit -m "feat: add word count display and export button to MessageBubble"
```

---

### Task 10: Add CSS for new UI elements

**Files:**
- Modify: `web/src/index.css` (or wherever the main stylesheet lives)

- [ ] **Step 1: Find the main stylesheet**

```
find C:/Users/Student/zeus-app/web/src -name "*.css" | head -10
```

- [ ] **Step 2: Add styles for toolbar, grammar button, word count, and export bar**

Append to the main CSS file:

```css
/* ── Toolbar chips ─────────────────────────────────────────────────────────── */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px 0;
}

.chip {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  font-size: 13px;
  padding: 4px 12px;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
  white-space: nowrap;
}

.chip:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.4);
  color: #fff;
}

/* ── Grammar check button ──────────────────────────────────────────────────── */
.grammar-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 4px 8px;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.grammar-btn--active {
  background: rgba(139, 92, 246, 0.25);
  border-color: rgba(139, 92, 246, 0.7);
  color: #a78bfa;
}

.grammar-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.35);
  color: rgba(255, 255, 255, 0.85);
}

/* ── Word count ────────────────────────────────────────────────────────────── */
.word-count {
  color: rgba(255, 255, 255, 0.35);
  font-size: 11px;
  margin-top: 6px;
  text-align: right;
}

/* ── Export bar ────────────────────────────────────────────────────────────── */
.export-bar {
  align-items: center;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
}

.export-label {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.export-btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  font-size: 12px;
  padding: 4px 12px;
  transition: background 0.15s, border-color 0.15s;
}

.export-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.3);
}
```

- [ ] **Step 3: Verify build succeeds**

```
cd C:\Users\Student\zeus-app\web
npm run build 2>&1 | head -30
```

Expected: build completes without errors

- [ ] **Step 4: Commit**

```bash
git add web/src/index.css
git commit -m "feat: add CSS for toolbar chips, grammar button, word count, and export bar"
```

---

### Task 11: Run all backend tests and verify

**Files:** No changes — verification only

- [ ] **Step 1: Run the full test suite**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_export.py -v
```

Expected output:
```
tests/test_export.py::test_fpdf2_importable PASSED
tests/test_export.py::test_python_docx_importable PASSED
tests/test_export.py::test_slugify_basic PASSED
tests/test_export.py::test_slugify_special_chars PASSED
tests/test_export.py::test_slugify_max_length PASSED
tests/test_export.py::test_generate_pdf_returns_bytes PASSED
tests/test_export.py::test_generate_docx_returns_bytes PASSED
tests/test_export.py::test_export_pdf_content_type PASSED
tests/test_export.py::test_export_docx_content_type PASSED
tests/test_export.py::test_export_invalid_format PASSED
tests/test_export.py::test_export_tag_regex_matches PASSED
tests/test_export.py::test_export_tag_regex_strips_cleanly PASSED
tests/test_export.py::test_export_tag_regex_no_match_conversational PASSED
13 passed
```

- [ ] **Step 2: Verify Docker build succeeds**

```
cd C:\Users\Student\zeus-app
docker build -t zeus-upgrade-test . 2>&1 | tail -5
```

Expected: `Successfully built <image-id>` (or equivalent)

- [ ] **Step 3: Final commit if any fixes were needed, then confirm done**

If all tests pass with no additional fixes needed, the implementation is complete. Deploy to Railway by pushing to the repo.

---

## Manual Testing Checklist

After deploying, verify these scenarios in the live app:

- [ ] Send "Write an essay about climate change" → Zeus asks one clarifying question → after answering, Zeus writes essay → Export button appears → PDF downloads → Word downloads
- [ ] Click the "✍️ Essay" chip → textarea fills with "Write an essay about " → cursor lands in textarea
- [ ] Click the "🌐 Website" chip → textarea fills with "Build a website for "
- [ ] Toggle the GC button → it turns purple → placeholder changes to proofreading text → paste text and send → Zeus returns corrected version → GC button resets to off
- [ ] Ask a conversational question → no export button appears → no word count shown for short replies
- [ ] Send a long message → Zeus reply shows word count when ≥50 words
- [ ] Click "📄 CV" chip → textarea fills → send → Zeus asks clarifying question (industry/level) → reply back → CV produced → export button appears
