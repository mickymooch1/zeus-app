# Zeus AI Upgrade — Full Business Assistant Design

## Goal

Expand Zeus from a web-design-focused assistant into a full business writing assistant while keeping web design as its primary identity. Add document export (PDF + Word), grammar check mode, a quick-action toolbar, and word count display.

## Architecture

Four independent change areas, all building on the existing FastAPI + WebSocket + React stack:

1. **System prompt + personality** — `backend/zeus_agent.py`
2. **Export detection + endpoint** — `backend/zeus_agent.py` (stream parser) + `backend/main.py` (new route) + `requirements.txt`
3. **Grammar check mode** — `web/src/components/InputBar.jsx`
4. **UI additions** — `web/src/components/MessageBubble.jsx`, `InputBar.jsx`, new `Toolbar.jsx`

No database changes. No new auth. Stateless export endpoint.

---

## Section 1: System Prompt + Personality

### New capabilities added to `ZEUS_SYSTEM_PROMPT`

```
**Writing & Content**
- Essays: structured arguments with intro, body, conclusion; appropriate academic or casual tone
- Blog posts and articles: engaging hooks, clear sections, strong CTAs
- CVs and cover letters: professional formatting, tailored to role/industry
- Business proposals: executive summary, scope, pricing, timeline
- Grammar checking: proofread user-provided text, return corrected version with list of changes
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
```

### Personality changes

Replace current personality section:

**Before:** "Talk like a sharp, experienced colleague — direct, helpful, no filler"

**After:**
```
## Your personality
- Warm, encouraging, and genuinely invested in the user's success
- Direct and clear — no waffle, but never cold
- Ask ONE clarifying question before starting essays, CVs, proposals, or business plans
  (e.g. "Who is this CV for — what industry and level?")
- Celebrate completions briefly ("Strong proposal — here's what makes it work")
- Remember context within the conversation — refer back to earlier details naturally
- Web design remains your primary strength; present all other capabilities as natural extensions
- Never use filler phrases like "Certainly!", "Of course!", "Great question!"
```

---

## Section 2: Document Export

### Stream parser changes (`zeus_agent.py`)

`run_turn_stream` detects `[ZEUS_EXPORT: ...]` in accumulated text at the end of streaming.

Detection logic (after `content_block_stop`, before emitting `done`):
```python
import re
EXPORT_TAG_RE = re.compile(
    r'\[ZEUS_EXPORT:\s*type=(\w+)\s+title="([^"]+)"\]',
    re.IGNORECASE
)

# After final message assembled:
match = EXPORT_TAG_RE.search(zeus_text)
if match:
    doc_type = match.group(1)
    title = match.group(2)
    # Strip tag from the text sent to history and display
    clean_text = EXPORT_TAG_RE.sub('', zeus_text).rstrip()
    await on_message({
        "type": "export_ready",
        "doc_type": doc_type,
        "title": title,
    })
```

The `text` deltas sent during streaming may include the tag characters — the frontend strips them from display using the same regex client-side.

### New endpoint (`main.py`)

```python
class ExportRequest(BaseModel):
    text: str
    format: str          # "pdf" or "docx"
    title: str
    doc_type: str

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

`slugify`: replaces spaces/special chars with hyphens, lowercase, max 60 chars.

### PDF generation (`generate_pdf`)

Uses `fpdf2`. Layout:
- A4 page, 20mm margins
- Title: bold, 18pt, centred, top of page
- Horizontal rule below title
- Body: 11pt, auto line-wrap, paragraph spacing
- Footer: "Generated by Zeus · zeusaidesign.com" in grey 8pt

### Word generation (`generate_docx`)

Uses `python-docx`. Layout:
- Title paragraph using `Heading 1` style
- Body text split on double-newlines into separate `Normal` paragraphs
- Single-newlines within a paragraph become line breaks within that paragraph

### New dependencies

```
fpdf2>=2.7.0
python-docx>=1.1.0
```

---

## Section 3: Grammar Check Mode

Changes only in `web/src/components/InputBar.jsx`.

```jsx
const [grammarMode, setGrammarMode] = useState(false);

const handleSend = () => {
  const text = value.trim();
  if (!text || disabled) return;
  const prompt = grammarMode
    ? `Please proofread and correct the following text. Return the corrected version with a brief list of changes made:\n\n${text}`
    : text;
  onSend(prompt);
  setValue('');
  setGrammarMode(false);  // one-shot: resets after send
};
```

Toggle button renders as a pill `GC` next to the send button:
- Off: muted grey styling
- On: purple/active styling, placeholder changes to "Paste your text here for proofreading..."

---

## Section 4: UI Additions

### Toolbar (`web/src/components/Toolbar.jsx`) — new file

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
        <button key={c.label} className="chip" onClick={() => onChipClick(c.starter)}>
          {c.label}
        </button>
      ))}
    </div>
  );
}
```

`onChipClick` sets the textarea value in `InputBar` and focuses it. Toolbar renders above `InputBar` inside `ChatWindow`.

`InputBar` receives an optional `initialValue` prop (or `ChatWindow` lifts state so Toolbar and InputBar share it). Cleanest: lift textarea value state to `ChatWindow`, pass `value`/`setValue` down to both `Toolbar` and `InputBar`.

### Word count display (`MessageBubble.jsx`)

```jsx
function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

// Inside Zeus bubble, after text renders, when not streaming:
{!isStreaming && message.text && wordCount(message.text) >= 50 && (
  <div className="word-count">~{wordCount(message.text)} words</div>
)}
```

### Export button (`MessageBubble.jsx`)

```jsx
{message.exportReady && (
  <div className="export-bar">
    <span className="export-label">Export as:</span>
    <button onClick={() => handleExport('pdf')} className="export-btn">⬇ PDF</button>
    <button onClick={() => handleExport('docx')} className="export-btn">⬇ Word</button>
  </div>
)}
```

`handleExport(format)`:
```js
async function handleExport(format) {
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
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = message.exportReady.title + (format === 'pdf' ? '.pdf' : '.docx');
  a.click();
  URL.revokeObjectURL(url);
}
```

### WebSocket hook changes (`useZeusSocket.js`)

Handle new `export_ready` event type:
```js
} else if (data.type === 'export_ready') {
  setMessages(prev => prev.map(m =>
    m.id === zeusMsgId
      ? { ...m, exportReady: { doc_type: data.doc_type, title: data.title } }
      : m
  ));
}
```

Strip `[ZEUS_EXPORT: ...]` from text deltas client-side:
```js
// In text delta handler:
const EXPORT_TAG_RE = /\[ZEUS_EXPORT:[^\]]+\]/gi;
const cleanDelta = data.delta.replace(EXPORT_TAG_RE, '');
if (cleanDelta) {
  setMessages(prev => prev.map(m =>
    m.id === zeusMsgId ? { ...m, text: m.text + cleanDelta } : m
  ));
}
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `backend/zeus_agent.py` | New system prompt, personality, export tag detection, `export_ready` event |
| `backend/main.py` | New `POST /export` endpoint, `ExportRequest` model, `generate_pdf`, `generate_docx`, `slugify` |
| `backend/requirements.txt` | Add `fpdf2>=2.7.0`, `python-docx>=1.1.0` |
| `web/src/hooks/useZeusSocket.js` | Handle `export_ready` event, strip export tag from text deltas |
| `web/src/components/MessageBubble.jsx` | Word count display, export button + handler |
| `web/src/components/InputBar.jsx` | Grammar check toggle, `initialValue` prop |
| `web/src/components/ChatWindow.jsx` | Lift textarea state, render `Toolbar` |
| `web/src/components/Toolbar.jsx` | New file — quick-action chips |

## Error Handling

- `/export` returns 400 for invalid format, 500 with generic message for generation failure
- Export button shows "Export failed — try again" toast on fetch error (no crash)
- Grammar mode sends the full prefixed prompt — if Zeus produces a long corrected document, export tag will appear and the Export button shows automatically

## Testing

- Unit test `generate_pdf` and `generate_docx` produce non-empty bytes
- Unit test export tag regex matches correctly and strips cleanly
- Unit test `/export` endpoint returns correct Content-Type and Content-Disposition headers
- Manual: send "Write an essay about climate change" → verify Export button appears, PDF downloads, Word downloads
- Manual: toggle grammar mode, paste text → verify prefix is sent, toggle resets
- Manual: click Essay chip → verify textarea fills with starter, focus lands in textarea
