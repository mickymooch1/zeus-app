import asyncio
import logging
import os
import pathlib
import sys
import traceback
from contextlib import asynccontextmanager

# Log to stderr immediately — before basicConfig — so Railway captures startup
# crashes even if the import chain below fails.
print("zeus main.py: starting imports", file=sys.stderr, flush=True)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

print("zeus main.py: fastapi ok", file=sys.stderr, flush=True)

from zeus_agent import HistoryStore, run_turn_stream

print("zeus main.py: zeus_agent ok", file=sys.stderr, flush=True)

from tunnel import get_tunnel_url, start_tunnel_background, stop_tunnel

_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))

print("zeus main.py: tunnel ok", file=sys.stderr, flush=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("zeus")

# Log installed packages once so Railway deploy logs show the exact environment.
try:
    import importlib.metadata as _meta
    _pkgs = {d.metadata["Name"]: d.version for d in _meta.distributions()}
    for _name in ("fastapi", "starlette", "uvicorn", "anthropic", "httpx", "anyio"):
        log.info("pkg %s==%s", _name, _pkgs.get(_name, "NOT INSTALLED"))
except Exception:
    log.exception("could not enumerate installed packages")

history: HistoryStore | None = None
_background_tasks: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global history
    log.info("Startup: initialising HistoryStore")
    log.info("  HOME=%s", os.environ.get("HOME", "<unset>"))
    log.info("  ZEUS_DATA_DIR=%s", os.environ.get("ZEUS_DATA_DIR", "<unset>"))
    log.info("  PORT=%s", os.environ.get("PORT", "<unset>"))
    try:
        history = HistoryStore()
        log.info("HistoryStore ready at %s", history.dir)
    except Exception:
        log.exception("FATAL: HistoryStore init failed")
        raise
    if _RAILWAY:
        log.info("Running on Railway — skipping cloudflared tunnel (not installed)")
        yield
    else:
        port = int(os.environ.get("PORT", 8000))
        task = asyncio.create_task(start_tunnel_background(port))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        yield
        task.cancel()
        stop_tunnel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    if history is None:
        await websocket.send_json({"type": "error", "message": "Server still initialising"})
        await websocket.send_json({"type": "done"})
        await websocket.close()
        return
    try:
        data = await websocket.receive_json()
        prompt = data.get("prompt", "").strip()
        session_id = data.get("session_id")

        if not prompt:
            await websocket.send_json({"type": "error", "message": "prompt is required"})
            await websocket.send_json({"type": "done"})
            await websocket.close()
            return

        async def send(msg: dict):
            await websocket.send_json(msg)

        await run_turn_stream(prompt, session_id, send, history)
        await websocket.close()

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
            await websocket.send_json({"type": "done"})
            await websocket.close()
        except Exception:
            pass


@app.get("/sessions")
async def get_sessions():
    log.info("GET /sessions — history=%s", type(history).__name__ if history else None)
    if history is None:
        raise HTTPException(status_code=503, detail="Server still initialising")
    try:
        sessions = history.list_sessions()
        log.info("GET /sessions — returning %d sessions", len(sessions))
        return sessions
    except Exception:
        log.exception("GET /sessions — unhandled exception")
        raise HTTPException(status_code=500, detail=traceback.format_exc())


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    if history is None:
        raise HTTPException(status_code=503, detail="Server still initialising")
    try:
        return history.get_transcript(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/tunnel-url")
async def tunnel_url_endpoint():
    return {"url": get_tunnel_url()}


@app.get("/health")
async def health():
    log.info("GET /health — ok")
    return {"status": "ok"}


# Serve built React app from web/dist/ at root (lazy import — aiofiles not required on Railway)
_dist = pathlib.Path(__file__).parent.parent / "web" / "dist"
if _dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
