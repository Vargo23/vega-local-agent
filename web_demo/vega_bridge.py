import threading
import time

import requests


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "vega-core"
MAX_HISTORY_MESSAGES = 20
SESSION_TTL_SECONDS = 2 * 60 * 60
BACKEND_UNAVAILABLE = (
    "VEGA backend is unavailable. Check that Ollama is running and model vega-core exists."
)
SYSTEM_PROMPT = (
    "You are VEGA, a local project coding-agent running in remote demo mode. Multiple users "
    "may be connected at the same time. Keep each conversation separate. Do not execute shell "
    "commands, do not modify files, and do not claim that you changed the project. Explain, "
    "analyze, help with architecture, code understanding, and presentation demo tasks."
)

sessions: dict[str, dict[str, object]] = {}
sessions_lock = threading.Lock()
ollama_semaphore = threading.Semaphore(2)


def _cleanup_sessions(now: float) -> None:
    expired = [
        session_id
        for session_id, session in sessions.items()
        if now - float(session["last_seen"]) > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        del sessions[session_id]


def _get_history(session_id: str, now: float) -> list[dict[str, str]]:
    with sessions_lock:
        _cleanup_sessions(now)
        session = sessions.setdefault(session_id, {"last_seen": now, "messages": []})
        session["last_seen"] = now
        return list(session["messages"])


def _save_exchange(session_id: str, user_message: str, assistant_reply: str, now: float) -> None:
    with sessions_lock:
        session = sessions.setdefault(session_id, {"last_seen": now, "messages": []})
        messages = session["messages"]
        messages.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_reply},
            ]
        )
        session["messages"] = messages[-MAX_HISTORY_MESSAGES:]
        session["last_seen"] = now


def ask_vega(session_id: str, message: str) -> str:
    text = message.strip()
    if not text:
        return "Please enter a message."

    now = time.time()
    history = _get_history(session_id, now)
    payload = {
        "model": MODEL_NAME,
        "stream": False,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": text}],
    }

    try:
        with ollama_semaphore:
            response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
    except requests.RequestException:
        return BACKEND_UNAVAILABLE
    except ValueError:
        return BACKEND_UNAVAILABLE

    reply = data.get("message", {}).get("content")
    if not reply:
        return BACKEND_UNAVAILABLE

    _save_exchange(session_id, text, reply, time.time())
    return reply
