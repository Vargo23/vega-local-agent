"""Bounded HTTP client for the local Ollama chat API."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.request_metrics import TokenUsage


DEFAULT_API_URL = "http://localhost:11434/api/chat"
DEFAULT_TIMEOUT_SECONDS = 120


class OllamaChatStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class OllamaChatResponse:
    status: OllamaChatStatus
    content: str
    usage: TokenUsage | None = None

    @property
    def ok(self) -> bool:
        return self.status is OllamaChatStatus.COMPLETED


def api_error_message() -> str:
    """Return a stable message for unavailable Ollama runtime."""
    return "\n".join(
        [
            "Ollama API is unavailable.",
            "Check that Ollama is running.",
            "Then try:",
            "ollama list",
        ]
    )


def timeout_error_message() -> str:
    return "Ollama API request timed out."


def missing_model_message(model: str) -> str:
    """Return installation guidance for a missing model."""
    return f"Model may not be installed. Run: ollama pull {model}"


def _token_usage(data: Mapping[str, Any]) -> TokenUsage | None:
    input_tokens = data.get("prompt_eval_count")
    output_tokens = data.get("eval_count")
    if (
        type(input_tokens) is not int
        or input_tokens < 0
        or type(output_tokens) is not int
        or output_tokens < 0
    ):
        return None
    return TokenUsage(input_tokens, output_tokens)


def _content(data: Mapping[str, Any]) -> str:
    message = data.get("message", {})
    if not isinstance(message, Mapping):
        return ""
    return str(message.get("content", ""))


def _error_response(model: str, data: Mapping[str, Any]) -> OllamaChatResponse | None:
    if not data.get("error"):
        return None
    error = str(data["error"])
    if "not found" in error.lower() or "model" in error.lower():
        return OllamaChatResponse(
            OllamaChatStatus.FAILED,
            f"Model `{model}` was not found.\n{missing_model_message(model)}",
        )
    return OllamaChatResponse(OllamaChatStatus.FAILED, error)


def _safe_chunk_callback(
    callback: Callable[[str], object] | None,
    content: str,
) -> None:
    if callback is None or not content:
        return
    try:
        callback(content)
    except Exception:
        return


def request_ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    api_url: str = DEFAULT_API_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stream: bool = False,
    chunk_callback: Callable[[str], object] | None = None,
) -> OllamaChatResponse:
    """Send one chat request and retain exact server-provided usage."""

    if not isinstance(model, str) or not model.strip():
        raise ValueError("Ollama model name must not be empty.")
    if not isinstance(messages, list):
        raise TypeError("Ollama messages must be a list.")
    if not isinstance(stream, bool):
        raise TypeError("stream must be a boolean")

    payload = json.dumps(
        {
            "model": model.strip(),
            "messages": messages,
            "stream": stream,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if stream:
                parts: list[str] = []
                final_data: Mapping[str, Any] | None = None
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        return OllamaChatResponse(
                            OllamaChatStatus.FAILED,
                            "Ollama API returned an unreadable stream.",
                        )
                    if not isinstance(data, Mapping):
                        return OllamaChatResponse(
                            OllamaChatStatus.FAILED,
                            "Ollama API returned an unreadable stream.",
                        )
                    error_response = _error_response(model, data)
                    if error_response is not None:
                        return error_response
                    part = _content(data)
                    parts.append(part)
                    _safe_chunk_callback(chunk_callback, part)
                    if data.get("done") is True:
                        final_data = data
                usage = _token_usage(final_data) if final_data is not None else None
                return OllamaChatResponse(
                    OllamaChatStatus.COMPLETED,
                    "".join(parts).strip(),
                    usage,
                )

            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404 or "not found" in body.lower() or "model" in body.lower():
            return OllamaChatResponse(
                OllamaChatStatus.FAILED,
                f"Model `{model}` was not found.\n{missing_model_message(model)}",
            )
        return OllamaChatResponse(
            OllamaChatStatus.FAILED,
            body.strip() or f"Ollama API returned HTTP {exc.code}.",
        )
    except (TimeoutError, socket.timeout):
        return OllamaChatResponse(OllamaChatStatus.TIMED_OUT, timeout_error_message())
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return OllamaChatResponse(
                OllamaChatStatus.TIMED_OUT,
                timeout_error_message(),
            )
        return OllamaChatResponse(OllamaChatStatus.FAILED, api_error_message())
    except OSError:
        return OllamaChatResponse(OllamaChatStatus.FAILED, api_error_message())

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return OllamaChatResponse(
            OllamaChatStatus.FAILED,
            raw.strip() or "Ollama API returned an unreadable response.",
        )
    if not isinstance(data, Mapping):
        return OllamaChatResponse(
            OllamaChatStatus.FAILED,
            "Ollama API returned an unreadable response.",
        )
    error_response = _error_response(model, data)
    if error_response is not None:
        return error_response
    return OllamaChatResponse(
        OllamaChatStatus.COMPLETED,
        _content(data).strip(),
        _token_usage(data),
    )


def call_ollama_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    api_url: str = DEFAULT_API_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    stream: bool = False,
    chunk_callback: Callable[[str], object] | None = None,
    usage_callback: Callable[[TokenUsage | None], object] | None = None,
) -> tuple[bool, str]:
    """Compatibility tuple API with optional exact-usage observation."""

    response = request_ollama_chat(
        model,
        messages,
        api_url=api_url,
        timeout=timeout,
        stream=stream,
        chunk_callback=chunk_callback,
    )
    if usage_callback is not None:
        try:
            usage_callback(response.usage)
        except Exception:
            pass
    return response.ok, response.content


def check_ollama_ready(
    model: str,
    *,
    api_url: str = DEFAULT_API_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[bool, str]:
    """Run a minimal Ollama chat health check."""

    messages = [
        {"role": "system", "content": "Reply with exactly: OK"},
        {"role": "user", "content": "health check"},
    ]
    return call_ollama_chat(model, messages, api_url=api_url, timeout=timeout)


__all__ = [
    "OllamaChatResponse",
    "OllamaChatStatus",
    "api_error_message",
    "call_ollama_chat",
    "check_ollama_ready",
    "missing_model_message",
    "request_ollama_chat",
    "timeout_error_message",
]
