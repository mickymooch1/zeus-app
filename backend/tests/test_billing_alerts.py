import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import alerts


def test_alert_webhook_error_sends_admin_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_admin_alert", lambda m: sent.append(m) or True)
    alerts.alert_webhook_error("checkout.session.completed", "evt_1", "KeyError: get")
    assert len(sent) == 1
    assert "checkout.session.completed" in sent[0]
    assert "evt_1" in sent[0]
    assert "KeyError: get" in sent[0]


def test_alert_credit_not_granted_sends_admin_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "send_admin_alert", lambda m: sent.append(m) or True)
    alerts.alert_credit_not_granted("x@y.com", "£0.99", "user not found", "pi_9")
    assert len(sent) == 1
    msg = sent[0]
    assert "x@y.com" in msg
    assert "£0.99" in msg
    assert "user not found" in msg
    assert "pi_9" in msg


def test_alerts_never_raise_even_if_telegram_fails(monkeypatch):
    def boom(_):
        raise RuntimeError("telegram down")
    monkeypatch.setattr(alerts, "send_admin_alert", boom)
    # Fire-and-forget: must swallow, never bubble into the webhook handler.
    alerts.alert_webhook_error("t", "id", "e")
    alerts.alert_credit_not_granted("e@x.com", "£1", "d", "r")
