import asyncio
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from zeus_agent import HistoryStore, run_turn_stream
from tunnel import get_tunnel_url, start_tunnel_background, stop_tunnel

history = HistoryStore()
_background_tasks: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(start_tunnel_background(8000))
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
    return history.list_sessions()


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    return history.get_transcript(session_id)


@app.get("/tunnel-url")
async def tunnel_url_endpoint():
    return {"url": get_tunnel_url()}


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve built React app from web/dist/ at root
_dist = pathlib.Path(__file__).parent.parent / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
