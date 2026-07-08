from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .vega_bridge import ask_vega


# Temporary VEGA remote demo interface for presentations.
# This is not a production GUI and intentionally exposes only chat.
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="VEGA Remote Demo")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat")
def chat(payload: ChatRequest) -> dict[str, str]:
    session_id = payload.session_id or str(uuid4())
    return {"reply": ask_vega(session_id, payload.message), "session_id": session_id}
