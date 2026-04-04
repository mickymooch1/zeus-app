import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def make_mock_run_turn_stream(events):
    """Helper: returns a mock run_turn_stream that emits given events."""
    async def mock_fn(prompt, session_id, on_message, history):
        new_sid = session_id
        for ev in events:
            if ev["type"] == "session_id":
                new_sid = ev["value"]
            await on_message(ev)
        return new_sid
    return mock_fn


class TestSessionsEndpoint:
    def test_returns_list(self):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/sessions")
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)


class TestHistoryEndpoint:
    def test_unknown_session_returns_empty_list(self):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/history/nonexistent-000")
            assert resp.status_code == 200
            assert resp.json() == []


class TestTunnelUrlEndpoint:
    def test_returns_url_key(self):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/tunnel-url")
            assert resp.status_code == 200
            assert "url" in resp.json()


class TestChatWebSocket:
    def test_streams_text_and_done(self):
        events = [
            {"type": "session_id", "value": "sess-abc"},
            {"type": "text", "delta": "Hello from Zeus!"},
            {"type": "done"},
        ]
        mock_stream = make_mock_run_turn_stream(events)

        with patch("main.run_turn_stream", mock_stream):
            from main import app
            with TestClient(app) as client:
                with client.websocket_connect("/chat") as ws:
                    ws.send_json({"prompt": "hi", "session_id": None})
                    received = []
                    while True:
                        data = ws.receive_json()
                        received.append(data)
                        if data["type"] == "done":
                            break
                    types = [m["type"] for m in received]
                    assert "session_id" in types
                    assert "text" in types
                    assert types[-1] == "done"
                    text_msg = next(m for m in received if m["type"] == "text")
                    assert text_msg["delta"] == "Hello from Zeus!"

    def test_error_event_reaches_client(self):
        events = [
            {"type": "error", "message": "CLI not found"},
            {"type": "done"},
        ]
        mock_stream = make_mock_run_turn_stream(events)

        with patch("main.run_turn_stream", mock_stream):
            from main import app
            with TestClient(app) as client:
                with client.websocket_connect("/chat") as ws:
                    ws.send_json({"prompt": "hi", "session_id": None})
                    received = []
                    while True:
                        data = ws.receive_json()
                        received.append(data)
                        if data["type"] == "done":
                            break
                    error_msgs = [m for m in received if m["type"] == "error"]
                    assert len(error_msgs) == 1
                    assert "CLI not found" in error_msgs[0]["message"]
