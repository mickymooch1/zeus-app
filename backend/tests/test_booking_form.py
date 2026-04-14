import os
import pathlib
import sys

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
