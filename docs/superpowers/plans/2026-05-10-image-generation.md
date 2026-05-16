# Image Generation (Apiframe Flux) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add async AI image generation via Apiframe Flux to the Zeus backend, exposed as REST endpoints and as a Zeus agent tool.

**Architecture:** A new `image_generator.py` module wraps the Apiframe v2 API (mirrors the existing `portrait_generator.py` pattern). Three REST endpoints are added to `main.py`: submit, poll, and webhook receiver. The existing `GenerateImage` tool in `zeus_agent.py` is updated from Pollinations.ai to Apiframe, with `use_case` replacing `width/height`.

**Tech Stack:** FastAPI, Apiframe v2 (`/v2/images/generate`, `/v2/jobs/{id}`), ffmpeg (WebP→JPEG fallback), Railway `/data` volume, `requests`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/image_generator.py` | **Create** | `submit_image_generation()`, `get_image_job_status()`, `download_and_save_image()` |
| `backend/tests/test_image_generator.py` | **Create** | Unit tests for the module (mocked HTTP) |
| `backend/tests/test_images_endpoint.py` | **Create** | FastAPI TestClient tests for the 3 endpoints |
| `backend/main.py` | **Modify** | Startup dir creation, StaticFiles mount, 3 endpoints |
| `backend/zeus_agent.py` | **Modify** | Updated `GenerateImage` TOOLS schema + `_run_tool()` dispatch |

---

## Task 1: `image_generator.py` module

**Files:**
- Create: `backend/image_generator.py`
- Test: `backend/tests/test_image_generator.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_image_generator.py`:

```python
import os
import pathlib
import sys

import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")


def _make_resp(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


class TestSubmitImageGeneration:
    def test_returns_job_id(self):
        import image_generator
        mock_resp = _make_resp({"jobId": "abc123"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            job_id = image_generator.submit_image_generation(
                "a dog", "1:1", "flux", "https://example.com/webhooks/image"
            )
        assert job_id == "abc123"
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["prompt"] == "a dog"
        assert call_json["aspectRatio"] == "1:1"
        assert call_json["model"] == "flux"
        assert call_json["webhookUrl"] == "https://example.com/webhooks/image"

    def test_omits_webhook_when_empty(self):
        import image_generator
        mock_resp = _make_resp({"jobId": "abc123"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            image_generator.submit_image_generation("a dog", "1:1")
        call_json = mock_post.call_args.kwargs["json"]
        assert "webhookUrl" not in call_json

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.APIFRAME_API_KEY", ""):
            with pytest.raises(ValueError, match="APIFRAME_API_KEY"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_raises_if_no_job_id_in_response(self):
        import image_generator
        mock_resp = _make_resp({"error": "bad request"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="jobId"):
                image_generator.submit_image_generation("a dog", "1:1")


class TestGetImageJobStatus:
    def test_completed_extracts_image_url(self):
        import image_generator
        mock_resp = _make_resp({
            "status": "COMPLETED",
            "result": {"images": ["https://cdn.apiframe.ai/img.jpg"]},
        })
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.get", return_value=mock_resp):
            result = image_generator.get_image_job_status("abc123")
        assert result["status"] == "COMPLETED"
        assert result["image_url"] == "https://cdn.apiframe.ai/img.jpg"

    def test_pending_returns_none_url(self):
        import image_generator
        mock_resp = _make_resp({"status": "PENDING"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.get", return_value=mock_resp):
            result = image_generator.get_image_job_status("abc123")
        assert result["status"] == "PENDING"
        assert result["image_url"] is None

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.APIFRAME_API_KEY", ""):
            with pytest.raises(ValueError, match="APIFRAME_API_KEY"):
                image_generator.get_image_job_status("abc123")
```

- [ ] **Step 2: Verify tests fail**

```bash
cd backend && python -m pytest tests/test_image_generator.py -v
```

Expected: `ModuleNotFoundError: No module named 'image_generator'`

- [ ] **Step 3: Create `backend/image_generator.py`**

```python
"""image_generator.py — AI image generation via Apiframe Flux."""
import logging
import os
import pathlib
import subprocess
import tempfile

import requests

log = logging.getLogger("zeus.image")

APIFRAME_API_KEY = os.environ.get("APIFRAME_API_KEY", "").strip()
APIFRAME_BASE = "https://api.apiframe.ai"
ZEUS_PUBLIC_URL = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")


def submit_image_generation(
    prompt: str,
    aspect_ratio: str,
    model: str = "flux",
    webhook_url: str = "",
) -> str:
    """Submit image generation to Apiframe. Returns job_id."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    body: dict = {
        "prompt": prompt,
        "model": model,
        "aspectRatio": aspect_ratio,
    }
    if webhook_url:
        body["webhookUrl"] = webhook_url
        body["webhookEvents"] = ["completed", "failed"]

    response = requests.post(
        f"{APIFRAME_BASE}/v2/images/generate",
        headers={"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    job_id = data.get("jobId")
    if not job_id:
        raise RuntimeError(f"Apiframe response missing jobId: {data!r}")
    log.info("submit_image_generation: job_id=%s model=%s ratio=%s", job_id, model, aspect_ratio)
    return job_id


def get_image_job_status(job_id: str) -> dict:
    """Poll Apiframe for image job status. Returns {status, image_url}."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    response = requests.get(
        f"{APIFRAME_BASE}/v2/jobs/{job_id}",
        headers={"X-API-Key": APIFRAME_API_KEY},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    status = data.get("status", "").upper()
    image_url = None
    if status == "COMPLETED":
        result = data.get("result") or {}
        images = result.get("images", [])
        image_url = images[0] if images else None
    return {"status": status, "image_url": image_url}


def download_and_save_image(job_id: str, image_url: str) -> str:
    """Download image_url, save to /data/images/{job_id}.jpg, return public URL."""
    images_dir = pathlib.Path("/data/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = images_dir / f"{job_id}.jpg"

    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()

    if image_url.lower().endswith(".webp"):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            subprocess.run(
                ["ffmpeg", "-i", tmp_path, "-q:v", "2", "-y", str(dest)],
                check=True,
                capture_output=True,
            )
        finally:
            if tmp_path and pathlib.Path(tmp_path).exists():
                pathlib.Path(tmp_path).unlink()
    else:
        dest.write_bytes(resp.content)

    log.info("download_and_save_image: saved %s", dest)
    return f"{ZEUS_PUBLIC_URL}/files/images/{job_id}.jpg"
```

- [ ] **Step 4: Verify tests pass**

```bash
cd backend && python -m pytest tests/test_image_generator.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/image_generator.py backend/tests/test_image_generator.py
git commit -m "feat: add image_generator module wrapping Apiframe Flux"
```

---

## Task 2: REST endpoints in `main.py`

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_images_endpoint.py`

- [ ] **Step 1: Write the failing endpoint tests**

Create `backend/tests/test_images_endpoint.py`:

```python
import os
import pathlib
import sys

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Set required env vars before importing main (webhooks.py reads them at module level)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com")


def _test_user():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "User",
        "is_admin": 0,
    }


class TestGenerateImageEndpoint:
    def test_returns_job_id_and_url(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        try:
            with patch("image_generator.submit_image_generation", return_value="job-xyz123"):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/images/generate",
                        json={"prompt": "a god of thunder", "use_case": "social"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-xyz123"
        assert "job-xyz123" in data["url"]
        assert data["url"].endswith(".jpg")

    def test_hero_use_case_passes_16_9_ratio(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        captured = {}
        def _fake_submit(prompt, aspect_ratio, model="flux", webhook_url=""):
            captured["aspect_ratio"] = aspect_ratio
            return "job-abc"
        try:
            with patch("image_generator.submit_image_generation", side_effect=_fake_submit):
                with TestClient(app) as client:
                    client.post(
                        "/api/images/generate",
                        json={"prompt": "hero image", "use_case": "hero"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert captured["aspect_ratio"] == "16:9"

    def test_unauthenticated_returns_401(self):
        import main as _main
        app = _main.app
        with TestClient(app) as client:
            resp = client.post(
                "/api/images/generate",
                json={"prompt": "test", "use_case": "social"},
            )
        assert resp.status_code == 401


class TestImageStatusEndpoint:
    def test_returns_status_and_url(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        try:
            with patch("image_generator.get_image_job_status", return_value={"status": "COMPLETED", "image_url": "https://cdn.apiframe.ai/img.jpg"}):
                with TestClient(app) as client:
                    resp = client.get("/api/images/status/job-abc123")
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["image_url"] == "https://cdn.apiframe.ai/img.jpg"


class TestImageWebhookEndpoint:
    def test_completed_event_downloads_and_saves(self):
        import main as _main
        app = _main.app
        with patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/job-abc.jpg") as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image",
                    json={
                        "jobId": "job-abc",
                        "event": "completed",
                        "status": "COMPLETED",
                        "result": {"images": ["https://cdn.apiframe.ai/img.jpg"]},
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_dl.assert_called_once_with("job-abc", "https://cdn.apiframe.ai/img.jpg")

    def test_failed_event_returns_ok_without_download(self):
        import main as _main
        app = _main.app
        with patch("image_generator.download_and_save_image") as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image",
                    json={"jobId": "job-abc", "event": "failed", "status": "FAILED"},
                )
        assert resp.status_code == 200
        mock_dl.assert_not_called()

    def test_missing_job_id_returns_400(self):
        import main as _main
        app = _main.app
        with TestClient(app) as client:
            resp = client.post("/webhooks/image", json={"event": "completed"})
        assert resp.status_code == 400
```

- [ ] **Step 2: Verify tests fail**

```bash
cd backend && python -m pytest tests/test_images_endpoint.py -v
```

Expected: tests fail with 404 (endpoints don't exist yet) or import errors.

- [ ] **Step 3: Add `/data/images` startup dir to `main.py`**

Find the block (around line 257):
```python
    for _d in ("/data/avatars", "/data/videos"):
        pathlib.Path(_d).mkdir(parents=True, exist_ok=True)
    log.info("Storage directories ready: /data/avatars, /data/videos")
```

Replace with:
```python
    for _d in ("/data/avatars", "/data/videos", "/data/images"):
        pathlib.Path(_d).mkdir(parents=True, exist_ok=True)
    log.info("Storage directories ready: /data/avatars, /data/videos, /data/images")
```

- [ ] **Step 4: Add `ImageGenerateRequest` model to `main.py`**

Find any existing `class` Pydantic model near the top of the API section (search for `class SongGenerateRequest` or similar). Add immediately before or after an existing model:

```python
class ImageGenerateRequest(BaseModel):
    prompt: str
    use_case: str = "social"  # hero | social | portrait | banner
    model: str = "flux"       # flux | gpt-image-2
```

- [ ] **Step 5: Add the three endpoints to `main.py`**

Find the songs-related endpoints section (search for `@app.post("/api/songs/`) and add the image endpoints nearby in the file, before the StaticFiles mounts at the bottom:

```python
_IMAGE_USE_CASE_RATIO = {
    "hero":     "16:9",
    "social":   "1:1",
    "portrait": "9:16",
    "banner":   "3:1",
}


@app.post("/api/images/generate")
async def generate_image(
    body: ImageGenerateRequest,
    user: dict = Depends(auth.get_current_user),
):
    import image_generator as _img
    aspect_ratio = _IMAGE_USE_CASE_RATIO.get(body.use_case, "1:1")
    zeus_url = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")
    webhook_url = f"{zeus_url}/webhooks/image"
    job_id = _img.submit_image_generation(body.prompt, aspect_ratio, body.model, webhook_url)
    public_url = f"{zeus_url}/files/images/{job_id}.jpg"
    return {"job_id": job_id, "url": public_url}


@app.get("/api/images/status/{job_id}")
async def image_status(job_id: str, user: dict = Depends(auth.get_current_user)):
    import image_generator as _img
    return _img.get_image_job_status(job_id)


@app.post("/webhooks/image")
async def image_webhook(request: Request):
    import image_generator as _img
    body = await request.json()
    job_id = body.get("jobId")
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing jobId")
    event = body.get("event", "")
    status = body.get("status", "").upper()
    if event == "failed" or status == "FAILED":
        log.warning("Image generation failed for job %s", job_id)
        return {"ok": True}
    result = body.get("result") or {}
    images = result.get("images", [])
    if not images:
        log.warning("Image webhook completed but no images for job %s", job_id)
        return {"ok": True}
    public_url = _img.download_and_save_image(job_id, images[0])
    log.info("Image webhook: saved job %s → %s", job_id, public_url)
    return {"ok": True, "url": public_url}
```

- [ ] **Step 6: Add StaticFiles mount for `/files/images` in `main.py`**

Find the existing mounts block near the bottom of `main.py`:
```python
_video_storage = pathlib.Path("/data/videos")
```

Add after the existing `_video_storage` mount:
```python
_image_storage = pathlib.Path("/data/images")
_image_storage.mkdir(parents=True, exist_ok=True)
app.mount("/files/images", _StaticFiles(directory=str(_image_storage)), name="images")
```

- [ ] **Step 7: Verify tests pass**

```bash
cd backend && python -m pytest tests/test_images_endpoint.py -v
```

Expected: `9 passed`

- [ ] **Step 8: Commit**

```bash
git add backend/main.py backend/tests/test_images_endpoint.py
git commit -m "feat: add /api/images/* endpoints and /webhooks/image handler"
```

---

## Task 3: Update `GenerateImage` tool in `zeus_agent.py`

**Files:**
- Modify: `backend/zeus_agent.py`

- [ ] **Step 1: Update the TOOLS entry for `GenerateImage`**

Find (around line 331):
```python
        "name": "GenerateImage",
        "description": (
            "Generate an image from a text prompt using AI and return a URL the user can view. "
            "Use this when asked to create, design, or visualise anything — logos, banners, "
            "illustrations, mockups, background images, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed description of the image to generate"},
                "width":  {"type": "integer", "description": "Image width in pixels (default 1024)"},
                "height": {"type": "integer", "description": "Image height in pixels (default 1024)"},
            },
            "required": ["prompt"],
        },
```

Replace with:
```python
        "name": "GenerateImage",
        "description": (
            "Generate an AI image using Flux (photorealistic) or GPT-Image-2 (illustrated). "
            "Use for website hero images, social media posts, banners, blog headers, or any "
            "visual content. Submits async generation and returns the future public URL immediately. "
            "Tell the user the image will be ready in about 30 seconds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of the image. Be specific about style, colours, mood, and content.",
                },
                "use_case": {
                    "type": "string",
                    "enum": ["hero", "social", "portrait", "banner"],
                    "description": "hero=website hero 16:9, social=square 1:1, portrait=Instagram story 9:16, banner=wide 3:1",
                },
                "model": {
                    "type": "string",
                    "enum": ["flux", "gpt-image-2"],
                    "description": "flux for photorealistic, gpt-image-2 for illustrated/artistic style",
                },
            },
            "required": ["prompt", "use_case"],
        },
```

- [ ] **Step 2: Update `_run_tool()` dispatch for `GenerateImage`**

Find (around line 993):
```python
        elif name == "GenerateImage":
            import urllib.parse
            prompt = inp["prompt"]
            width  = int(inp.get("width", 1024))
            height = int(inp.get("height", 1024))
            encoded = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
            # Verify the image is reachable
            try:
                check = httpx.head(url, timeout=20, follow_redirects=True)
                if check.status_code >= 400:
                    return f"Image generation failed (HTTP {check.status_code}). Try a different prompt."
            except Exception:
                pass  # Return the URL anyway — HEAD may be blocked but GET will work
            return f"Generated image URL: {url}\n\nPrompt used: {prompt}"
```

Replace with:
```python
        elif name == "GenerateImage":
            import image_generator as _img_mod
            _use_case_ratio = {"hero": "16:9", "social": "1:1", "portrait": "9:16", "banner": "3:1"}
            prompt = inp["prompt"]
            use_case = inp.get("use_case", "social")
            model = inp.get("model", "flux")
            aspect_ratio = _use_case_ratio.get(use_case, "1:1")
            zeus_url = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")
            webhook_url = f"{zeus_url}/webhooks/image"
            job_id = _img_mod.submit_image_generation(prompt, aspect_ratio, model, webhook_url)
            public_url = f"{zeus_url}/files/images/{job_id}.jpg"
            return (
                f"Generating your image — it'll be ready at {public_url} in about 30 seconds.\n\n"
                f"You can share that URL directly or embed it in a website. "
                f"Job ID: {job_id}"
            )
```

- [ ] **Step 3: Verify existing tests still pass**

```bash
cd backend && python -m pytest tests/ -v --ignore=tests/test_image_generator.py --ignore=tests/test_images_endpoint.py -x
```

Expected: all previously-passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add backend/zeus_agent.py
git commit -m "feat: upgrade GenerateImage tool to Apiframe Flux with use_case aspect ratios"
```

---

## Task 4: Push and verify

- [ ] **Step 1: Run the full test suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass (or same count as before plus the 16 new ones).

- [ ] **Step 2: Push to GitHub (Railway auto-deploys)**

```bash
git push origin HEAD
```

- [ ] **Step 3: Smoke test on production**

In the Zeus chat, send: `Generate a dramatic image of Zeus the AI god building a website, lightning and code flying around — make it a social media post format.`

Zeus should reply with a `zeusaidesign.com/files/images/<job_id>.jpg` URL. Wait 30 seconds, open the URL — image should load.

---

## Self-Review Checklist

- [x] `submit_image_generation` — spec says "Returns job_id" ✓
- [x] `get_image_job_status` — spec says "Returns {status, image_url}" ✓
- [x] `/data/images` mounted at `/files/images` ✓
- [x] `POST /api/images/generate` with `{prompt, aspect_ratio, use_case}` ✓
- [x] `GET /api/images/status/{job_id}` ✓
- [x] `POST /webhooks/image` — downloads to `/data/images/<job_id>.jpg`, returns public URL ✓
- [x] `GenerateImage` tool added to TOOLS list with correct schema ✓
- [x] `_run_tool()` dispatch calls Apiframe, returns immediate message with future URL ✓
- [x] Async pattern: Zeus returns URL immediately, Apiframe calls webhook ~30s later to persist the file ✓
- [x] WebP fallback in `download_and_save_image` (consistent with portrait_generator.py) ✓
- [x] `use_case` → `aspect_ratio` mapping applied in both endpoint and agent tool ✓
