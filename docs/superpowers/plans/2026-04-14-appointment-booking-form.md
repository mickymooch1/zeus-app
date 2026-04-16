# Appointment Booking Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Zeus builds a website, he asks the user if they want a booking form; if yes, the Builder embeds a fully functional Formspree-powered appointment form in the built site that emails the business owner on every submission.

**Architecture:** Two self-contained changes to `backend/zeus_agent.py`. (1) A new instruction block added to `ZEUS_SYSTEM_PROMPT` tells the main Zeus agent to ask about booking forms before calling `MultiAgentBuild`, collecting the owner's notification email when the user says yes. (2) Logic added to `run_multi_agent` detects the booking form requirement from the `request` string, extracts the owner email, conditionally raises the Builder's line cap from 500 → 600, and appends a Formspree form template + AJAX JavaScript to the Builder's system prompt. No new files, no backend changes, no database changes — the form is fully client-side via Formspree's free no-account endpoint.

**Tech Stack:** Python (zeus_agent.py), Formspree legacy email endpoint (`https://formspree.io/owner@email.com`), Fetch API for AJAX submission, pytest / pytest-asyncio for tests.

---

## How the booking form works (background for the implementer)

Formspree's legacy free endpoint accepts a `POST` from any HTML form where `action="https://formspree.io/owner@email.com"`. On first submission Formspree sends a one-time confirmation email to the owner; after that, every submission is forwarded immediately. No Formspree account is required. Quota is 50 submissions/month on the free tier.

The Builder is given a complete HTML/JS template in its system prompt. It fills in the service options from the Planner brief and adapts the CSS to the site's palette. AJAX fetch (with `Accept: application/json`) prevents a page redirect on submit.

## File structure

| File | Change |
|------|--------|
| `backend/zeus_agent.py` | Two locations: `ZEUS_SYSTEM_PROMPT` (new `## Booking form` section) and `run_multi_agent` (detection logic + builder_system modifications) |
| `backend/tests/test_booking_form.py` | New test file: prompt text tests + pipeline integration tests |

---

## Task 1 — Update Zeus system prompt to ask about booking forms

**Files:**
- Modify: `backend/zeus_agent.py` — `ZEUS_SYSTEM_PROMPT` (ends around line 161)
- Create: `backend/tests/test_booking_form.py`

### What to add

A `## Booking form` section that tells Zeus to ask two questions before triggering any website build, and how to embed the answers in the `MultiAgentBuild` / `CreateBackgroundTask` request string.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_booking_form.py`:

```python
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import zeus_agent


class TestZeusSystemPromptBookingFormInstruction:
    def test_prompt_contains_booking_form_section(self):
        assert "## Booking form" in zeus_agent.ZEUS_SYSTEM_PROMPT

    def test_prompt_instructs_to_ask_before_build(self):
        # Must tell Zeus to ask BEFORE calling MultiAgentBuild / CreateBackgroundTask
        assert "MultiAgentBuild" in zeus_agent.ZEUS_SYSTEM_PROMPT
        booking_section = zeus_agent.ZEUS_SYSTEM_PROMPT.split("## Booking form", 1)[1]
        assert "before" in booking_section.lower()

    def test_prompt_instructs_to_ask_for_email(self):
        booking_section = zeus_agent.ZEUS_SYSTEM_PROMPT.split("## Booking form", 1)[1]
        assert "email" in booking_section.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_booking_form.py::TestZeusSystemPromptBookingFormInstruction -v
```

Expected: 3 FAILED (ZEUS_SYSTEM_PROMPT doesn't have the section yet)

- [ ] **Step 3: Add the `## Booking form` section to `ZEUS_SYSTEM_PROMPT`**

In `backend/zeus_agent.py`, find the end of `ZEUS_SYSTEM_PROMPT` — the line that reads:

```
Direct users to zeusaidesign.com/pricing to upgrade.
"""
```

Insert the new section **before** the closing `"""`:

```python
## Booking form

Before calling MultiAgentBuild or CreateBackgroundTask for any website build, ask two questions:

1. "Would you like an appointment booking form on your website? Visitors can fill it in to request a booking, and you'll get an email notification with their details." (yes/no)
2. If yes: "What email address should booking enquiries be sent to?"

Once you have the answers, include them in the request you pass to MultiAgentBuild / CreateBackgroundTask. For example:
  request = "Build a website for Joe's Plumbing, London. Include an appointment booking form. Booking notification email: joe@joes-plumbing.co.uk."

If the user says no, do not mention the booking form again and proceed with the build as normal.
If the user does not provide an email when they said yes, ask once more before proceeding.
```

The section sits between the pricing block and the closing `"""`. The full closing of `ZEUS_SYSTEM_PROMPT` should look like:

```python
Direct users to zeusaidesign.com/pricing to upgrade.

## Booking form

Before calling MultiAgentBuild or CreateBackgroundTask for any website build, ask two questions:

1. "Would you like an appointment booking form on your website? Visitors can fill it in to request a booking, and you'll get an email notification with their details." (yes/no)
2. If yes: "What email address should booking enquiries be sent to?"

Once you have the answers, include them in the request you pass to MultiAgentBuild / CreateBackgroundTask. For example:
  request = "Build a website for Joe's Plumbing, London. Include an appointment booking form. Booking notification email: joe@joes-plumbing.co.uk."

If the user says no, do not mention the booking form again and proceed with the build as normal.
If the user does not provide an email when they said yes, ask once more before proceeding.
"""
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_booking_form.py::TestZeusSystemPromptBookingFormInstruction -v
```

Expected: 3 PASSED

- [ ] **Step 5: Run the full test suite to check for regressions**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/zeus_agent.py backend/tests/test_booking_form.py
git commit -m "feat: instruct Zeus to ask about booking forms before website builds"
```

---

## Task 2 — Detect booking form requirement in pipeline and inject Formspree template into Builder

**Files:**
- Modify: `backend/zeus_agent.py` — `run_multi_agent` function (lines ~1786–2111)
- Modify: `backend/tests/test_booking_form.py` — add `TestBookingFormPipeline` class

### What to change in `run_multi_agent`

After the build-limit gate and before Stage 1 (Planner), add:

```python
# ── Booking form detection ────────────────────────────────────────────────────
_wants_booking_form = bool(
    re.search(r'\bbook(?:ing)?\s+(?:form|appointment)', request, re.IGNORECASE)
)
_booking_email = ""
if _wants_booking_form:
    _em = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', request)
    _booking_email = _em.group(0) if _em else ""
```

Set the line cap variable:

```python
_line_limit = 600 if _wants_booking_form else 500
```

Build the conditional booking form instructions string (plain string concatenation, not f-string, to avoid JavaScript curly-brace escaping):

```python
if _wants_booking_form:
    _form_action = (
        "https://formspree.io/" + _booking_email
        if _booking_email
        else "https://formspree.io/REPLACE_WITH_OWNER_EMAIL"
    )
    _booking_form_extra = (
        "\n\nBOOKING FORM REQUIREMENT:\n"
        "The brief requests an appointment booking form. You MUST include it as a dedicated section.\n"
        "Form action (Formspree — no backend needed): " + _form_action + "\n\n"
        "Required fields: Name, Email, Phone, Service (dropdown with 4–6 options from the brief),\n"
        "Preferred Date, Preferred Time, Message.\n\n"
        "Use this HTML structure (adapt all CSS colours and fonts to match the site palette):\n\n"
        "<section id=\"booking\">\n"
        "  <div class=\"container\">\n"
        "    <h2>Book an Appointment</h2>\n"
        "    <form id=\"booking-form\" action=\"" + _form_action + "\" method=\"POST\">\n"
        "      <div class=\"form-row\">\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-name\">Name *</label>\n"
        "          <input type=\"text\" id=\"f-name\" name=\"name\" required placeholder=\"Your full name\">\n"
        "        </div>\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-email\">Email *</label>\n"
        "          <input type=\"email\" id=\"f-email\" name=\"email\" required placeholder=\"your@email.com\">\n"
        "        </div>\n"
        "      </div>\n"
        "      <div class=\"form-row\">\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-phone\">Phone</label>\n"
        "          <input type=\"tel\" id=\"f-phone\" name=\"phone\" placeholder=\"07700 000000\">\n"
        "        </div>\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-service\">Service *</label>\n"
        "          <select id=\"f-service\" name=\"service\" required>\n"
        "            <option value=\"\">Select a service...</option>\n"
        "            <!-- Add 4-6 <option> elements relevant to this business from the brief -->\n"
        "          </select>\n"
        "        </div>\n"
        "      </div>\n"
        "      <div class=\"form-row\">\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-date\">Preferred Date *</label>\n"
        "          <input type=\"date\" id=\"f-date\" name=\"date\" required>\n"
        "        </div>\n"
        "        <div class=\"form-group\">\n"
        "          <label for=\"f-time\">Preferred Time *</label>\n"
        "          <input type=\"time\" id=\"f-time\" name=\"time\" required>\n"
        "        </div>\n"
        "      </div>\n"
        "      <div class=\"form-group\">\n"
        "        <label for=\"f-message\">Message</label>\n"
        "        <textarea id=\"f-message\" name=\"message\" rows=\"4\" "
        "placeholder=\"Any additional details...\"></textarea>\n"
        "      </div>\n"
        "      <p id=\"form-error\" style=\"display:none;color:#e53935;margin-bottom:1rem;\">"
        "Something went wrong. Please try again.</p>\n"
        "      <button type=\"submit\" id=\"form-btn\">Request Appointment</button>\n"
        "    </form>\n"
        "  </div>\n"
        "</section>\n\n"
        "Add this JavaScript inside the <script> block for AJAX submission "
        "(keeps user on the page, no redirect):\n\n"
        "document.getElementById('booking-form').addEventListener('submit', async function(e) {\n"
        "  e.preventDefault();\n"
        "  var btn = document.getElementById('form-btn');\n"
        "  btn.disabled = true; btn.textContent = 'Sending...';\n"
        "  try {\n"
        "    var res = await fetch(e.target.action, {\n"
        "      method: 'POST',\n"
        "      body: new FormData(e.target),\n"
        "      headers: { 'Accept': 'application/json' }\n"
        "    });\n"
        "    if (res.ok) {\n"
        "      e.target.innerHTML = '<p style=\"text-align:center;padding:2rem\">"
        "&#10003; Thanks! We\\'ll be in touch to confirm your appointment.</p>';\n"
        "    } else {\n"
        "      document.getElementById('form-error').style.display = 'block';\n"
        "      btn.disabled = false; btn.textContent = 'Request Appointment';\n"
        "    }\n"
        "  } catch(err) {\n"
        "    document.getElementById('form-error').style.display = 'block';\n"
        "    btn.disabled = false; btn.textContent = 'Request Appointment';\n"
        "  }\n"
        "});\n\n"
        "Style the booking section with a light background that complements the site palette. "
        "Add .form-row { display:flex; gap:1rem; } and .form-group { flex:1; display:flex; "
        "flex-direction:column; gap:0.4rem; } at minimum. "
        "On mobile (max-width:600px) stack the form-rows to a single column.\n"
    )
else:
    _booking_form_extra = ""
```

Then in `builder_system`, replace the current literal `500` with `{_line_limit}` and append `{_booking_form_extra}` at the end:

```python
builder_system = f"""\
You are the Builder in a multi-agent website build pipeline.

CRITICAL — READ BEFORE WRITING ANY FILE:
The ONLY permitted project directory is: {_build_dir}
The site slug is: {site_name}

OUTPUT CONSTRAINTS — MUST BE FOLLOWED WITHOUT EXCEPTION:
- Write ONE file only: {_build_dir}/index.html
- Maximum {_line_limit} lines total
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
1. Write a single self-contained index.html under {_line_limit} lines
2. Use the brief's colour scheme, tone, and content
3. Draw on the research for copy and layout decisions
4. Mobile-responsive using simple CSS (flexbox/grid, media queries)
5. Clean semantic HTML — no unnecessary divs or complexity

When done, confirm: "Files written to {_build_dir}/"
{_booking_form_extra}\
"""
```

### What to add to the test file

Append `TestBookingFormPipeline` to `backend/tests/test_booking_form.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBookingFormPipeline:

    @pytest.mark.asyncio
    async def test_booking_form_requested__builder_system_includes_formspree(self):
        """When request mentions 'booking form', builder_system must include Formspree."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-salon\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-salon.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a site for Sarah's Beauty Salon. "
                "Include an appointment booking form. "
                "Booking notification email: sarah@sarahs-salon.co.uk.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system, "Builder stage was never reached"
        system = captured_builder_system[0]
        assert "formspree.io/sarah@sarahs-salon.co.uk" in system.lower()
        assert "booking" in system.lower()

    @pytest.mark.asyncio
    async def test_booking_form_not_requested__builder_system_has_no_formspree(self):
        """When request has no booking form mention, builder_system must NOT mention Formspree."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-plumber\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-plumber.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a website for Mike's Plumbing, London.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system, "Builder stage was never reached"
        assert "formspree" not in captured_builder_system[0].lower()

    @pytest.mark.asyncio
    async def test_booking_form_line_limit_is_600(self):
        """With a booking form, the builder_system must say 600 lines, not 500."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-physio\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-physio.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a site for City Physio. "
                "Include an appointment booking form. "
                "Booking notification email: info@cityphysio.co.uk.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system
        assert "600" in captured_builder_system[0]
        assert "500" not in captured_builder_system[0]

    @pytest.mark.asyncio
    async def test_no_booking_form_line_limit_is_500(self):
        """Without a booking form, the builder_system must say 500 lines."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-cafe\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-cafe.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a website for The Corner Café, Bristol.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system
        assert "500" in captured_builder_system[0]
        assert "600" not in captured_builder_system[0]

    @pytest.mark.asyncio
    async def test_booking_form_contains_all_required_fields(self):
        """The Formspree template must include all 7 required fields."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-barber\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-barber.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a site for The Classic Barber. "
                "Include a booking form. "
                "Booking notification email: cuts@classicbarber.co.uk.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system
        s = captured_builder_system[0]
        # All 7 required fields must appear in the template
        assert "name=\"name\"" in s or "name=name" in s.lower()
        assert "name=\"email\"" in s or "name=email" in s.lower()
        assert "name=\"phone\"" in s or "name=phone" in s.lower()
        assert "name=\"service\"" in s or "name=service" in s.lower()
        assert "name=\"date\"" in s or "name=date" in s.lower()
        assert "name=\"time\"" in s or "name=time" in s.lower()
        assert "name=\"message\"" in s or "name=message" in s.lower()

    @pytest.mark.asyncio
    async def test_booking_form_ajax_javascript_included(self):
        """The template must include fetch-based AJAX JavaScript for form submission."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-yoga\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-yoga.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a site for Zen Yoga Studio. "
                "Include a booking form. "
                "Booking notification email: hello@zenyoga.co.uk.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system
        s = captured_builder_system[0]
        assert "fetch(" in s
        assert "application/json" in s
        assert "e.preventDefault" in s

    @pytest.mark.asyncio
    async def test_no_email_provided__placeholder_used(self):
        """If no email address in request, fall back to placeholder, not crash."""
        captured_builder_system = []

        async def fake_stage(stage_label, prompt, system_prompt, tools,
                              on_message, history, **kwargs):
            if stage_label == "🏗️ Builder Agent":
                captured_builder_system.append(system_prompt)
            return {
                "🧠 Planner Agent":  "SITE_NAME: test-nail\nBrief done.",
                "🔍 Researcher Agent": "Research done.",
                "🏗️ Builder Agent":   "Build done.",
                "🚀 Deployer Agent":  "Live URL: https://test-nail.netlify.app",
            }.get(stage_label, "done.")

        with (
            patch("zeus_agent._run_stage_with_retry", side_effect=fake_stage),
            patch("zeus_agent._generate_seo_files"),
            patch("zeus_agent._submit_url_to_google"),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "Build a site for Nail Bar. Include a booking form.",
                AsyncMock(),
                MagicMock(),
                user_id=None,
            )

        assert captured_builder_system
        s = captured_builder_system[0]
        assert "formspree.io" in s.lower()
        assert "REPLACE_WITH_OWNER_EMAIL" in s
```

- [ ] **Step 1: Write the failing tests**

Append the `TestBookingFormPipeline` class shown above to `backend/tests/test_booking_form.py`.

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_booking_form.py::TestBookingFormPipeline -v
```

Expected: 7 FAILED (booking form logic doesn't exist yet)

- [ ] **Step 3: Add booking form detection before Stage 1 in `run_multi_agent`**

In `backend/zeus_agent.py`, find the comment line:

```python
    # ── Stage 1: Planner ──────────────────────────────────────────────────────
```

Insert this block immediately above it (after the build limit gate's closing `except` block):

```python
    # ── Booking form detection ────────────────────────────────────────────────
    _wants_booking_form = bool(
        re.search(r'\bbook(?:ing)?\s+(?:form|appointment)', request, re.IGNORECASE)
    )
    _booking_email = ""
    if _wants_booking_form:
        _em = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', request)
        _booking_email = _em.group(0) if _em else ""

    _line_limit = 600 if _wants_booking_form else 500

    if _wants_booking_form:
        _form_action = (
            "https://formspree.io/" + _booking_email
            if _booking_email
            else "https://formspree.io/REPLACE_WITH_OWNER_EMAIL"
        )
        _booking_form_extra = (
            "\n\nBOOKING FORM REQUIREMENT:\n"
            "The brief requests an appointment booking form. You MUST include it as a dedicated section.\n"
            "Form action (Formspree — no backend needed): " + _form_action + "\n\n"
            "Required fields: Name, Email, Phone, Service (dropdown with 4–6 options from the brief),\n"
            "Preferred Date, Preferred Time, Message.\n\n"
            "Use this HTML structure (adapt all CSS colours and fonts to match the site palette):\n\n"
            "<section id=\"booking\">\n"
            "  <div class=\"container\">\n"
            "    <h2>Book an Appointment</h2>\n"
            "    <form id=\"booking-form\" action=\"" + _form_action + "\" method=\"POST\">\n"
            "      <div class=\"form-row\">\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-name\">Name *</label>\n"
            "          <input type=\"text\" id=\"f-name\" name=\"name\" required placeholder=\"Your full name\">\n"
            "        </div>\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-email\">Email *</label>\n"
            "          <input type=\"email\" id=\"f-email\" name=\"email\" required placeholder=\"your@email.com\">\n"
            "        </div>\n"
            "      </div>\n"
            "      <div class=\"form-row\">\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-phone\">Phone</label>\n"
            "          <input type=\"tel\" id=\"f-phone\" name=\"phone\" placeholder=\"07700 000000\">\n"
            "        </div>\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-service\">Service *</label>\n"
            "          <select id=\"f-service\" name=\"service\" required>\n"
            "            <option value=\"\">Select a service...</option>\n"
            "            <!-- Add 4-6 <option> elements relevant to this business from the brief -->\n"
            "          </select>\n"
            "        </div>\n"
            "      </div>\n"
            "      <div class=\"form-row\">\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-date\">Preferred Date *</label>\n"
            "          <input type=\"date\" id=\"f-date\" name=\"date\" required>\n"
            "        </div>\n"
            "        <div class=\"form-group\">\n"
            "          <label for=\"f-time\">Preferred Time *</label>\n"
            "          <input type=\"time\" id=\"f-time\" name=\"time\" required>\n"
            "        </div>\n"
            "      </div>\n"
            "      <div class=\"form-group\">\n"
            "        <label for=\"f-message\">Message</label>\n"
            "        <textarea id=\"f-message\" name=\"message\" rows=\"4\" "
            "placeholder=\"Any additional details...\"></textarea>\n"
            "      </div>\n"
            "      <p id=\"form-error\" style=\"display:none;color:#e53935;margin-bottom:1rem;\">"
            "Something went wrong. Please try again.</p>\n"
            "      <button type=\"submit\" id=\"form-btn\">Request Appointment</button>\n"
            "    </form>\n"
            "  </div>\n"
            "</section>\n\n"
            "Add this JavaScript inside the <script> block for AJAX submission "
            "(keeps user on the page, no redirect):\n\n"
            "document.getElementById('booking-form').addEventListener('submit', async function(e) {\n"
            "  e.preventDefault();\n"
            "  var btn = document.getElementById('form-btn');\n"
            "  btn.disabled = true; btn.textContent = 'Sending...';\n"
            "  try {\n"
            "    var res = await fetch(e.target.action, {\n"
            "      method: 'POST',\n"
            "      body: new FormData(e.target),\n"
            "      headers: { 'Accept': 'application/json' }\n"
            "    });\n"
            "    if (res.ok) {\n"
            "      e.target.innerHTML = '<p style=\"text-align:center;padding:2rem\">"
            "&#10003; Thanks! We\\'ll be in touch to confirm your appointment.</p>';\n"
            "    } else {\n"
            "      document.getElementById('form-error').style.display = 'block';\n"
            "      btn.disabled = false; btn.textContent = 'Request Appointment';\n"
            "    }\n"
            "  } catch(err) {\n"
            "    document.getElementById('form-error').style.display = 'block';\n"
            "    btn.disabled = false; btn.textContent = 'Request Appointment';\n"
            "  }\n"
            "});\n\n"
            "Style the booking section with a light background complementing the site palette. "
            "Add .form-row { display:flex; gap:1rem; } and .form-group { flex:1; display:flex; "
            "flex-direction:column; gap:0.4rem; } in the <style> block. "
            "On mobile (max-width:600px) override .form-row to flex-direction:column.\n"
        )
    else:
        _booking_form_extra = ""
```

- [ ] **Step 4: Update `builder_system` to use `_line_limit` and `_booking_form_extra`**

In `run_multi_agent`, find the existing `builder_system` f-string (around line 1963). It contains:

```
- Maximum 500 lines total
```

and ends with:

```
When done, confirm: "Files written to {_build_dir}/"\
"""
```

Make two changes:

1. Replace the literal `500` with `{_line_limit}`:

```python
- Maximum {_line_limit} lines total
```

2. Change the closing line of the f-string from:

```python
When done, confirm: "Files written to {_build_dir}/"\
"""
```

to:

```python
When done, confirm: "Files written to {_build_dir}/"
{_booking_form_extra}\
"""
```

The full `builder_system` assignment should look exactly like this after editing (other lines unchanged):

```python
    builder_system = f"""\
You are the Builder in a multi-agent website build pipeline.

CRITICAL — READ BEFORE WRITING ANY FILE:
The ONLY permitted project directory is: {_build_dir}
The site slug is: {site_name}

OUTPUT CONSTRAINTS — MUST BE FOLLOWED WITHOUT EXCEPTION:
- Write ONE file only: {_build_dir}/index.html
- Maximum {_line_limit} lines total
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
1. Write a single self-contained index.html under {_line_limit} lines
2. Use the brief's colour scheme, tone, and content
3. Draw on the research for copy and layout decisions
4. Mobile-responsive using simple CSS (flexbox/grid, media queries)
5. Clean semantic HTML — no unnecessary divs or complexity

When done, confirm: "Files written to {_build_dir}/"
{_booking_form_extra}\
"""
```

- [ ] **Step 5: Run the new tests**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/test_booking_form.py::TestBookingFormPipeline -v
```

Expected: 7 PASSED

- [ ] **Step 6: Run the full test suite**

```
cd C:\Users\Student\zeus-app\backend
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass (133+ prior tests + 10 new booking form tests).

- [ ] **Step 7: Commit**

```bash
git add backend/zeus_agent.py backend/tests/test_booking_form.py
git commit -m "feat: add appointment booking form to multi-agent website builds via Formspree"
```

---

## Edge cases handled

| Edge case | How handled |
|-----------|-------------|
| User says "no" to booking form | Zeus doesn't include it in the request; `_wants_booking_form` is false; builder_system unchanged |
| User says "yes" but forgets the email | Zeus re-prompts (instructed in system prompt); if email still absent, `REPLACE_WITH_OWNER_EMAIL` placeholder used — build still succeeds |
| 500-line limit too tight with form | `_line_limit` raised to 600; Builder instructed throughout to write under `{_line_limit}` lines |
| JavaScript curly braces in f-string | `_booking_form_extra` is a plain string (string concatenation), not an f-string; no escaping issue when interpolated |
| Formspree first-submission verification | First submission triggers a Formspree confirmation email to the owner; this is a one-time action, documented in how Formspree works (not a code issue) |
| Spam submissions | Formspree's default spam filter applies automatically |
| No Netlify/backend changes needed | Formspree is entirely client-side; no new env vars, no server routes, no DB changes |
| Background builds (`CreateBackgroundTask`) | Uses same `run_multi_agent` internally; booking form flows through automatically |
| Service dropdown options | Builder is instructed to infer 4–6 options from the Planner brief (business type); Builder has access to the full brief |
| Mobile responsiveness | Template instructions include explicit `.form-row` flex-direction override at 600px |
| Form submission redirect | AJAX fetch prevents page redirect; success message rendered inline |
| Formspree 50/month free limit | This is Formspree's constraint; for high-traffic clients the builder can be asked to upgrade to Formspree paid (out of scope here) |
| Multiple email addresses in request (e.g. "client is joe@plumbing.co.uk, send bookings to bookings@plumbing.co.uk") | Regex takes the first email match; Zeus system prompt instructs to say "Booking notification email: X" so the booking email is typically the only one or comes first |
