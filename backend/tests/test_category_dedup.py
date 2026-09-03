"""Category-keyed dedup for alerts.py — step 2 of the alerting build.

_should_send_alert (the original dedup) keys on exact message text, which never
matches twice for alert_lyrics_generation_failed: the email and error string vary
every call, so 50 failures in a row would have produced 50 Telegram messages. This
tests the replacement: _dedupe_by_category / send_admin_alert_deduped, keyed on a
stable category string instead of the message body.

Expected pattern for a burst of repeated failures in the same category:
  occurrence 1            -> sent immediately
  occurrences 2..N        -> suppressed (counted, not sent)
  first occurrence after the cooldown expires -> ONE "still happening x(N-1)" send,
                              then the counter resets
Not: one message per occurrence.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import alerts  # noqa: E402


def _reset():
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()


def test_first_occurrence_sends_immediately(monkeypatch):
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    result = alerts.send_admin_alert_deduped("test_cat", "boom #1", cooldown_seconds=900)

    assert result is True
    assert len(sent) == 1
    assert "boom #1" in sent[0]
    assert "still happening" not in sent[0] and "suppressed" not in sent[0]


def test_repeated_failures_within_cooldown_are_suppressed_not_sent(monkeypatch):
    """Simulates a burst: one real failure, then 9 more in quick succession — must
    produce exactly ONE send, not ten."""
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    results = [
        alerts.send_admin_alert_deduped("test_cat", f"boom #{i}", cooldown_seconds=900)
        for i in range(1, 11)
    ]

    assert results[0] is True
    assert results[1:] == [False] * 9, "occurrences 2-10 must be suppressed, not sent"
    assert len(sent) == 1, f"expected exactly 1 Telegram send for a 10-failure burst, got {len(sent)}"


def test_cooldown_expiry_sends_one_still_happening_follow_up_with_correct_count(monkeypatch):
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    # Occurrence 1: real send.
    alerts.send_admin_alert_deduped("test_cat", "boom #1", cooldown_seconds=900)
    # Occurrences 2-6: suppressed-and-counted (5 of them) while "inside" the cooldown.
    for i in range(2, 7):
        alerts.send_admin_alert_deduped("test_cat", f"boom #{i}", cooldown_seconds=900)
    assert len(sent) == 1, "no sends should have happened yet for the suppressed occurrences"

    # Force the cooldown to have elapsed, then the next occurrence should flush.
    alerts._ALERT_CATEGORY_STATE["test_cat"]["last_sent"] -= 901
    result = alerts.send_admin_alert_deduped("test_cat", "boom #7", cooldown_seconds=900)

    assert result is True
    assert len(sent) == 2, "the cooldown-expiry occurrence must send exactly one follow-up"
    follow_up = sent[1]
    assert "boom #7" in follow_up
    assert "5 more" in follow_up, f"expected the 5 suppressed occurrences reported, got: {follow_up!r}"

    # And the counter must have reset — immediately re-triggering should suppress again.
    result2 = alerts.send_admin_alert_deduped("test_cat", "boom #8", cooldown_seconds=900)
    assert result2 is False
    assert len(sent) == 2, "counter must reset after the follow-up, not keep accumulating"


def test_categories_are_independent(monkeypatch):
    """A burst in one category must not suppress or interfere with another category."""
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    r1 = alerts.send_admin_alert_deduped("lyrics_failed:normal", "boom normal", cooldown_seconds=900)
    r2 = alerts.send_admin_alert_deduped("lyrics_failed:kids-story", "boom kids", cooldown_seconds=900)
    r3 = alerts.send_admin_alert_deduped("lyrics_failed:normal", "boom normal again", cooldown_seconds=900)

    assert r1 is True and r2 is True, "both categories must send their first occurrence independently"
    assert r3 is False, "second occurrence in the SAME category must still be suppressed"
    assert len(sent) == 2


def test_category_dedup_bypasses_the_exact_text_dedup(monkeypatch):
    """If two occurrences in DIFFERENT categories happen to produce byte-identical
    message text, the base 30-min exact-text dedup must not swallow the second one —
    category dedup is authoritative for send_admin_alert_deduped calls."""
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    r1 = alerts.send_admin_alert_deduped("cat_a", "identical text", cooldown_seconds=900)
    r2 = alerts.send_admin_alert_deduped("cat_b", "identical text", cooldown_seconds=900)

    assert r1 is True
    assert r2 is True, "same message text in a different category must still send"
    assert len(sent) == 2


def test_alert_lyrics_generation_failed_uses_per_song_type_category(monkeypatch):
    """Confirms the step-1 alert now goes through the deduped sender, keyed by
    song_type — so a burst of normal-song failures dedupes independently from a
    burst of kids-story failures (both being broken at once is itself signal)."""
    _reset()
    calls = []

    def _fake_deduped(category, message, cooldown_seconds=900):
        calls.append((category, message))
        return True

    monkeypatch.setattr(alerts, "send_admin_alert_deduped", _fake_deduped)

    alerts.alert_lyrics_generation_failed("a@example.com", "normal", "boom 1")
    alerts.alert_lyrics_generation_failed("b@example.com", "kids-story", "boom 2")
    alerts.alert_lyrics_generation_failed("c@example.com", "normal", "boom 3")

    categories = [c for c, _ in calls]
    assert categories == ["lyrics_failed:normal", "lyrics_failed:kids-story", "lyrics_failed:normal"]
