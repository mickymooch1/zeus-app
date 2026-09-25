"""422s are logged with their reason (2026-09-25).

A roast generation failed four times with 422 and Railway showed only
"POST /api/songs/generate 422" — the field and rule were invisible. Every
request-validation failure is now logged with the path, the user (if the token
is valid), and each error's field / type / limit — but never the rejected
input itself (roast details etc. can be personal). The 422 response body is
unchanged, since the frontend reads it to show the real message.
"""
import logging

from tests.test_clips_api import app_client, auth_hdr  # noqa: F401  (fixture import)

SECRET_TEXT = "Uncle Terry's secret embarrassing story " * 25   # ~1000 chars, > the 800 limit


def _roast_body(**overrides):
    body = {"brief": "", "genres": ["pop"], "is_roast": True, "roast_name": "Terry",
            "roast_details": SECRET_TEXT, "roast_vibe": "gentle"}
    body.update(overrides)
    return body


def _validation_logs(caplog):
    return [r.getMessage() for r in caplog.records if "validation" in r.getMessage().lower()]


def test_an_over_long_roast_details_is_a_422_with_the_standard_detail(app_client):
    client, *_, owner_token, _ = app_client
    r = client.post("/api/songs/generate", json=_roast_body(), headers=auth_hdr(owner_token))
    assert r.status_code == 422
    errs = r.json()["detail"]
    assert isinstance(errs, list)
    e = next(e for e in errs if e["loc"][-1] == "roast_details")
    assert e["type"] == "string_too_long" and e["ctx"]["max_length"] == 800


def test_the_422_is_logged_with_path_user_field_and_limit(app_client, caplog):
    client, _db, _clips, db_path, owner, viewer, owner_token, _ = app_client
    with caplog.at_level(logging.WARNING):
        client.post("/api/songs/generate", json=_roast_body(), headers=auth_hdr(owner_token))
    logs = _validation_logs(caplog)
    assert logs, "a 422 must leave a log line"
    line = logs[-1]
    assert "/api/songs/generate" in line
    assert owner["id"] in line
    assert "roast_details" in line and "string_too_long" in line and "800" in line


def test_the_log_never_contains_what_the_user_typed(app_client, caplog):
    client, *_, owner_token, _ = app_client
    with caplog.at_level(logging.DEBUG):
        client.post("/api/songs/generate", json=_roast_body(), headers=auth_hdr(owner_token))
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert "Uncle Terry" not in everything


def test_an_anonymous_422_is_still_logged(app_client, caplog):
    """Public endpoints can 422 too; no token → logged as anonymous, not an error."""
    client, *_ = app_client
    with caplog.at_level(logging.WARNING):
        r = client.post("/api/clips/1/view", json={"anon_id": 12345})   # anon_id must be a string
    if r.status_code == 422:
        assert any("anonymous" in m for m in _validation_logs(caplog))


def test_the_frontend_roast_details_cap_matches_the_backend_limit():
    """The Songs page caps the box with ROAST_DETAILS_MAX; if the two drift, users hit the 422 again."""
    import re
    from pathlib import Path
    import main
    js = (Path(__file__).resolve().parents[2] / "web-beats" / "src" / "utils" / "apiErrorMessage.js").read_text(encoding="utf-8")
    front = int(re.search(r"ROAST_DETAILS_MAX\s*=\s*(\d+)", js).group(1))
    back = next(m.max_length for m in main.SongsGenerateRequest.model_fields["roast_details"].metadata
                if hasattr(m, "max_length"))
    assert front == back
