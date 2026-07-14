import json
import socket
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from core.ollama_client import (
    OllamaChatStatus,
    api_error_message,
    call_ollama_chat,
    check_ollama_ready,
    request_ollama_chat,
)
from core.request_metrics import TokenUsage


class StreamingResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def __iter__(self):
        return iter(self.lines)


class OllamaClientTests(unittest.TestCase):
    @patch(
        "core.ollama_client."
        "urllib.request.urlopen"
    )
    def test_successful_chat_response(
        self,
        urlopen,
    ) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"message":{"content":"  Hello  "}}'
        )
        urlopen.return_value = response

        ok, content = call_ollama_chat(
            "test-model",
            [
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
        )

        self.assertTrue(ok)
        self.assertEqual(
            content,
            "Hello",
        )

    @patch("core.ollama_client.urllib.request.urlopen")
    def test_exact_server_usage_is_returned(self, urlopen) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "message": {"content": "OK"},
                "prompt_eval_count": 1247,
                "eval_count": 53,
            }
        ).encode("utf-8")
        urlopen.return_value = response
        observed = []

        ok, content = call_ollama_chat(
            "test-model",
            [],
            usage_callback=observed.append,
        )

        self.assertTrue(ok)
        self.assertEqual(content, "OK")
        self.assertEqual(observed, [TokenUsage(1247, 53)])

    @patch("core.ollama_client.urllib.request.urlopen")
    def test_incomplete_server_usage_is_unavailable(self, urlopen) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"message":{"content":"OK"},"eval_count":3}'
        )
        urlopen.return_value = response
        observed = []

        ok, _ = call_ollama_chat(
            "test-model",
            [],
            usage_callback=observed.append,
        )

        self.assertTrue(ok)
        self.assertEqual(observed, [None])

    @patch("core.ollama_client.urllib.request.urlopen")
    def test_stream_uses_final_chunk_usage_and_emits_content(
        self,
        urlopen,
    ) -> None:
        urlopen.return_value = StreamingResponse(
            [
                b'{"message":{"content":"Hel"},"done":false}\n',
                b'{"message":{"content":"lo"},"done":false}\n',
                (
                    b'{"message":{"content":""},"done":true,'
                    b'"prompt_eval_count":9,"eval_count":2}\n'
                ),
            ]
        )
        chunks = []

        result = request_ollama_chat(
            "test-model",
            [],
            stream=True,
            chunk_callback=chunks.append,
        )

        self.assertEqual(result.status, OllamaChatStatus.COMPLETED)
        self.assertEqual(result.content, "Hello")
        self.assertEqual(result.usage, TokenUsage(9, 2))
        self.assertEqual(chunks, ["Hel", "lo"])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertTrue(payload["stream"])

    @patch("core.ollama_client.urllib.request.urlopen")
    def test_stream_without_final_usage_does_not_invent_tokens(
        self,
        urlopen,
    ) -> None:
        urlopen.return_value = StreamingResponse(
            [b'{"message":{"content":"OK"},"done":true}\n']
        )

        result = request_ollama_chat("test-model", [], stream=True)

        self.assertTrue(result.ok)
        self.assertIsNone(result.usage)

    @patch("core.ollama_client.urllib.request.urlopen")
    def test_timeout_has_distinct_status(self, urlopen) -> None:
        urlopen.side_effect = socket.timeout()

        result = request_ollama_chat("test-model", [])

        self.assertEqual(result.status, OllamaChatStatus.TIMED_OUT)
        self.assertIsNone(result.usage)

    @patch(
        "core.ollama_client."
        "urllib.request.urlopen"
    )
    def test_request_contains_model_and_messages(
        self,
        urlopen,
    ) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"message":{"content":"OK"}}'
        )
        urlopen.return_value = response

        messages = [
            {
                "role": "user",
                "content": "Test",
            }
        ]

        call_ollama_chat(
            "test-model",
            messages,
        )

        request = urlopen.call_args.args[0]
        payload = json.loads(
            request.data.decode("utf-8")
        )

        self.assertEqual(
            payload["model"],
            "test-model",
        )
        self.assertEqual(
            payload["messages"],
            messages,
        )
        self.assertFalse(
            payload["stream"]
        )

    @patch(
        "core.ollama_client."
        "urllib.request.urlopen"
    )
    def test_unavailable_api_returns_stable_error(
        self,
        urlopen,
    ) -> None:
        urlopen.side_effect = (
            urllib.error.URLError(
                "connection refused"
            )
        )

        ok, content = call_ollama_chat(
            "test-model",
            [],
        )

        self.assertFalse(ok)
        self.assertEqual(
            content,
            api_error_message(),
        )

    @patch(
        "core.ollama_client."
        "urllib.request.urlopen"
    )
    def test_invalid_json_is_rejected(
        self,
        urlopen,
    ) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b"invalid-response"
        )
        urlopen.return_value = response

        ok, content = call_ollama_chat(
            "test-model",
            [],
        )

        self.assertFalse(ok)
        self.assertEqual(
            content,
            "invalid-response",
        )

    @patch(
        "core.ollama_client."
        "urllib.request.urlopen"
    )
    def test_model_error_contains_install_command(
        self,
        urlopen,
    ) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            b'{"error":"model not found"}'
        )
        urlopen.return_value = response

        ok, content = call_ollama_chat(
            "missing-model",
            [],
        )

        self.assertFalse(ok)
        self.assertIn(
            "ollama pull missing-model",
            content,
        )

    @patch(
        "core.ollama_client.call_ollama_chat"
    )
    def test_health_check_uses_chat_client(
        self,
        call_chat,
    ) -> None:
        call_chat.return_value = (
            True,
            "OK",
        )

        result = check_ollama_ready(
            "test-model"
        )

        self.assertEqual(
            result,
            (True, "OK"),
        )
        call_chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
