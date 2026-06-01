"""voice_agent.py — Porick, the Zeus Beats AI phone receptionist.

Conversation flow:
  1. Incoming Twilio call → /voice/incoming → TwiML <Gather> (speech)
  2. Caller speaks → Twilio sends transcript to /voice/respond
  3. Claude generates Porick's reply
  4. ElevenLabs synthesises speech → saved to /data/porick-audio/
  5. TwiML <Play> streams the audio back; <Gather> opens next turn
  6. Silence / hangup / "goodbye" → graceful close
"""

import hashlib
import logging
import os
import pathlib
import re
import uuid

import httpx
from fastapi import APIRouter, Form, Request, Response

log = logging.getLogger("zeus.porick")

router = APIRouter(prefix="/voice", tags=["voice-agent"])

# ── Environment ───────────────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
ZEUS_PUBLIC_URL     = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")

# ElevenLabs voice for Porick — confident, warm, British male
PORICK_VOICE_ID = os.environ.get("PORICK_VOICE_ID", "WUyjxM8OTY6l8LhTmdkq")

_AUDIO_DIR = pathlib.Path("/data/porick-audio")

# ── Porick system prompt ──────────────────────────────────────────────────────

_PORICK_SYSTEM = """You are Porick, the AI phone receptionist for Zeus Beats — an AI music creation platform where users create songs in any genre using AI.

Your personality:
- Warm, confident and enthusiastic about music
- Concise — phone conversations need short answers (2-4 sentences max)
- Knowledgeable about Zeus Beats features: song generation, kids stories, 60+ genres, voice cloning, premium credits
- Helpful and redirecting — always guide callers to zeusaidesign.com or the app

You handle:
- General enquiries about Zeus Beats (what it is, how it works, pricing)
- Questions about genres, features, subscriptions
- Technical support direction ("visit our help page or email support@zeusaidesign.com")
- Greetings and farewells

You do NOT:
- Handle account login, payment disputes, or data requests — direct to support email
- Make up pricing or feature details you are unsure of
- Have long conversations — keep every response to 2-4 short sentences

When the caller says goodbye / thanks / done, close warmly and end with: "Have a wonderful day. Goodbye!"
That phrase signals the call should end."""

_FAREWELL_SIGNAL = "Have a wonderful day. Goodbye!"

# ── In-memory conversation store (per CallSid) ────────────────────────────────
# Calls are short-lived; no persistence needed.
_conversations: dict[str, list[dict]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _twiml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


def _twiml_gather(prompt_url: str, action_url: str, timeout: int = 5) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{prompt_url}</Play>
  <Gather input="speech" action="{action_url}" method="POST"
          speechTimeout="auto" timeout="{timeout}" language="en-GB">
  </Gather>
  <Redirect method="POST">{action_url}?SpeechResult=&lt;no+input&gt;</Redirect>
</Response>"""


def _twiml_play_and_end(prompt_url: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{prompt_url}</Play>
  <Hangup/>
</Response>"""


async def _synthesise(text: str) -> str:
    """Call ElevenLabs TTS, cache result, return public URL."""
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    slug = hashlib.md5(text.encode()).hexdigest()[:16]
    path = _AUDIO_DIR / f"{slug}.mp3"
    if not path.exists():
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{PORICK_VOICE_ID}",
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.65, "similarity_boost": 0.80},
                },
            )
            resp.raise_for_status()
            path.write_bytes(resp.content)
        log.info("_synthesise: generated %s (%d bytes)", path.name, len(resp.content))
    return f"{ZEUS_PUBLIC_URL}/files/porick-audio/{path.name}"


async def _porick_reply(call_sid: str, caller_text: str) -> str:
    """Run caller_text through Claude with conversation history. Returns Porick's reply."""
    from anthropic import AsyncAnthropic
    history = _conversations.setdefault(call_sid, [])
    history.append({"role": "user", "content": caller_text})

    client = AsyncAnthropic()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=_PORICK_SYSTEM,
        messages=history,
    )
    reply = response.content[0].text.strip()
    history.append({"role": "assistant", "content": reply})

    # Trim history to last 10 turns to avoid unbounded growth
    if len(history) > 20:
        _conversations[call_sid] = history[-20:]

    return reply


def _is_farewell(text: str) -> bool:
    return _FAREWELL_SIGNAL in text


# ── Greeting audio (cached at startup) ───────────────────────────────────────

_GREETING_TEXT = (
    "Hello! You've reached Zeus Beats. I'm Porick, your AI music assistant. "
    "How can I help you today?"
)

_greeting_url: str | None = None


async def ensure_greeting() -> str:
    global _greeting_url
    if not _greeting_url:
        _greeting_url = await _synthesise(_GREETING_TEXT)
    return _greeting_url


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/incoming")
async def incoming_call(
    request: Request,
    CallSid: str = Form(default=""),
):
    """Entry point — Twilio calls this when a call arrives."""
    call_sid = CallSid or str(uuid.uuid4())
    log.info("incoming_call: CallSid=%s", call_sid)
    _conversations.pop(call_sid, None)  # fresh conversation

    if not ELEVENLABS_API_KEY:
        # Fallback to plain TwiML text-to-speech if ElevenLabs not configured
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Brian">Hello! You've reached Zeus Beats. I'm Porick, your AI music assistant. How can I help you today?</Say>
  <Gather input="speech" action="/voice/respond" method="POST" speechTimeout="auto" timeout="5" language="en-GB"/>
</Response>"""
        return _twiml(xml)

    greeting_url = await ensure_greeting()
    action_url = f"{ZEUS_PUBLIC_URL}/voice/respond"
    return _twiml(_twiml_gather(greeting_url, action_url))


@router.post("/respond")
async def respond(
    request: Request,
    CallSid: str = Form(default=""),
    SpeechResult: str = Form(default=""),
):
    """Twilio sends the caller's speech here. We reply via Claude + ElevenLabs."""
    call_sid = CallSid or "unknown"
    caller_text = SpeechResult.strip() or "<no input>"
    log.info("respond: CallSid=%s speech=%r", call_sid, caller_text[:120])

    try:
        reply = await _porick_reply(call_sid, caller_text)
        log.info("respond: Porick reply=%r", reply[:120])
    except Exception:
        log.exception("respond: Claude call failed")
        reply = "Sorry, I'm having a little trouble right now. Please try calling back or email support@zeusaidesign.com."

    if not ELEVENLABS_API_KEY:
        # Plain TwiML fallback
        safe = reply.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if _is_farewell(reply):
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Brian">{safe}</Say>
  <Hangup/>
</Response>"""
        else:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Brian">{safe}</Say>
  <Gather input="speech" action="/voice/respond" method="POST" speechTimeout="auto" timeout="5" language="en-GB"/>
</Response>"""
        _conversations.pop(call_sid, None) if _is_farewell(reply) else None
        return _twiml(xml)

    try:
        audio_url = await _synthesise(reply)
    except Exception:
        log.exception("respond: ElevenLabs synthesis failed")
        audio_url = None

    action_url = f"{ZEUS_PUBLIC_URL}/voice/respond"

    if _is_farewell(reply):
        _conversations.pop(call_sid, None)
        if audio_url:
            return _twiml(_twiml_play_and_end(audio_url))
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Brian">Have a wonderful day. Goodbye!</Say>
  <Hangup/>
</Response>"""
        return _twiml(xml)

    if audio_url:
        return _twiml(_twiml_gather(audio_url, action_url))

    # ElevenLabs failed — fall back to Polly TTS
    safe = reply.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Brian">{safe}</Say>
  <Gather input="speech" action="{action_url}" method="POST" speechTimeout="auto" timeout="5" language="en-GB"/>
</Response>"""
    return _twiml(xml)
