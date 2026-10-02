"""Shared test setup, loaded by pytest before ANY test file is imported.

cometapi.COMETAPI_API_KEY and main.COMETAPI_WEBHOOK_URL are read once, when those
modules are first imported. pytest imports every test file during collection,
before running anything, so the first file to import main/cometapi (e.g.
test_agent_self_heal.py) fixed those values for the whole run — and the
os.environ.setdefault calls in test_your_sound.py / test_memorial_generate_gating.py
came too late. The persona tests then failed in full runs only ("COMETAPI_API_KEY
not configured", or a 503 from the endpoint's fail-fast config check, or a webhook
token that no longer matched) while passing on their own. Setting the dummy values
here, before collection, makes the outcome independent of file order.

Tests that need the key to be missing (test_your_sound's
test_generate_with_persona_no_api_key_raises) clear it themselves.
"""
import os

os.environ.setdefault("COMETAPI_API_KEY", "test-comet-key")
os.environ.setdefault("COMETAPI_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/cometapi")
