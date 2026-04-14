import os
import pathlib
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import zeus_agent


class TestZeusSystemPromptBookingFormInstruction:
    def test_prompt_contains_booking_form_section(self):
        assert "## Booking form" in zeus_agent.ZEUS_SYSTEM_PROMPT

    def test_prompt_instructs_to_ask_before_build(self):
        booking_section = zeus_agent.ZEUS_SYSTEM_PROMPT.split("## Booking form", 1)[1].lower()
        # "before" must appear in the section
        assert "before" in booking_section
        # Both tool names must appear in the section
        assert "multiagentbuild" in booking_section
        assert "createbackgroundtask" in booking_section
        # "before" must precede the tool names (Zeus must ask BEFORE calling them)
        idx_before = booking_section.index("before")
        idx_tool = booking_section.index("multiagentbuild")
        assert idx_before < idx_tool

    def test_prompt_instructs_to_ask_for_email(self):
        booking_section = zeus_agent.ZEUS_SYSTEM_PROMPT.split("## Booking form", 1)[1].lower()
        assert "email address" in booking_section


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
        assert 'name="name"' in s
        assert 'name="email"' in s
        assert 'name="phone"' in s
        assert 'name="service"' in s
        assert 'name="date"' in s
        assert 'name="time"' in s
        assert 'name="message"' in s

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
