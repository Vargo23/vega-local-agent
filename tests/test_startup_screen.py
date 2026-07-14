from __future__ import annotations

from io import StringIO
from pathlib import Path

import ui.startup_screen as startup_screen
from scripts.version import VERSION
from ui.startup_screen import build_startup_screen, render_startup_screen, visible_width


FORBIDDEN_STARTUP_TEXT = (
    "VEGA SESSION",
    "Internet",
    "network",
    "safety",
    "THINK // PATCH // TEST // REPEAT",
    "Local Project Coding-Agent",
    "logs\\sessions\\",
)


def test_operator_console_contains_current_runtime_values() -> None:
    output = build_startup_screen(
        version=VERSION,
        workspace="VEGA_agent_package",
        model="qwen2.5-coder:14b",
        status="Ready",
        width=62,
        color=False,
        unicode=True,
        stream=StringIO(),
    )

    assert "VEGA / OPERATOR CONSOLE" in output
    assert VERSION in output
    assert "workspace  VEGA_agent_package" in output
    assert "model      qwen2.5-coder:14b" in output
    assert "◇ Agent ready" in output
    assert "Give me a mission, or type /help." in output
    assert all(text not in output for text in FORBIDDEN_STARTUP_TEXT)
    assert "+" not in output
    assert "|" not in output


def test_render_prints_to_the_supplied_stream() -> None:
    stream = StringIO()

    render_startup_screen(
        version="v-test",
        workspace="project",
        model="model",
        width=40,
        color=False,
        unicode=False,
        stream=stream,
    )

    assert stream.getvalue().startswith("VEGA / OPERATOR CONSOLE")
    assert stream.getvalue().endswith("\n")
    assert "\x1b[" not in stream.getvalue()


def test_pre_v3_render_signature_remains_accepted_without_legacy_fields() -> None:
    stream = StringIO()

    render_startup_screen(
        "v-legacy",
        "legacy-model",
        "ON",
        "Ready",
        "C:/users/private/logs/sessions/session.md",
        workspace="project",
        width=48,
        color=False,
        unicode=False,
        stream=stream,
    )

    output = stream.getvalue()
    assert "v-legacy" in output
    assert "legacy-model" in output
    assert "workspace  project" in output
    assert "Internet" not in output
    assert "session.md" not in output


def test_colored_and_plain_modes_have_the_same_visible_content() -> None:
    arguments = {
        "version": "v9.8.7",
        "workspace": "project",
        "model": "model",
        "width": 48,
        "unicode": True,
        "stream": StringIO(),
    }

    plain = build_startup_screen(color=False, **arguments)
    colored = build_startup_screen(color=True, **arguments)

    assert "\x1b[" not in plain
    assert "\x1b[" in colored
    assert startup_screen._ANSI.sub("", colored) == plain


def test_narrow_terminal_moves_version_and_keeps_every_line_inside_width() -> None:
    width = 32
    output = build_startup_screen(
        version="v123.456.789",
        workspace="workspace",
        model="model",
        width=width,
        color=False,
        unicode=True,
        stream=StringIO(),
    )
    lines = output.splitlines()

    assert lines[0] == "VEGA / OPERATOR CONSOLE"
    assert lines[1] == "v123.456.789"
    assert all(visible_width(line) <= width for line in lines)
    assert lines[2] == "─" * width


def test_long_runtime_values_are_truncated_to_terminal_width() -> None:
    width = 28
    output = build_startup_screen(
        version="v-test",
        workspace="workspace-" + ("x" * 100),
        model="model-" + ("y" * 100),
        width=width,
        color=False,
        unicode=False,
        stream=StringIO(),
    )

    assert all(visible_width(line) <= width for line in output.splitlines())
    assert "workspace " in output
    assert "model " in output
    assert "..." in output
    assert output.splitlines()[2] == "-" * width


def test_version_and_model_are_taken_from_arguments_not_hardcoded() -> None:
    output = build_startup_screen(
        version="v-runtime",
        workspace="runtime-workspace",
        model="runtime-model",
        width=60,
        color=False,
        unicode=False,
        stream=StringIO(),
    )

    assert "v-runtime" in output
    assert "runtime-workspace" in output
    assert "runtime-model" in output
    assert "v2.11.0" not in output
    assert "qwen2.5-coder:14b" not in output


def test_defaults_use_canonical_version_and_current_workspace() -> None:
    output = build_startup_screen(
        model="runtime-model",
        width=60,
        color=False,
        unicode=False,
        stream=StringIO(),
    )

    assert VERSION in output
    assert f"workspace  {Path.cwd().name}" in output


def test_terminal_width_detection_failure_uses_safe_fallback(monkeypatch) -> None:
    def unavailable_terminal_size(*args, **kwargs):
        raise OSError("terminal size unavailable")

    monkeypatch.setattr(
        startup_screen.shutil,
        "get_terminal_size",
        unavailable_terminal_size,
    )

    output = build_startup_screen(
        version="v-test",
        workspace="project",
        model="model",
        color=False,
        unicode=False,
        stream=StringIO(),
    )

    assert all(
        visible_width(line) <= startup_screen.DEFAULT_TERMINAL_WIDTH
        for line in output.splitlines()
    )


def test_ascii_fallback_replaces_operator_symbols() -> None:
    output = build_startup_screen(
        version="v-test",
        workspace="project",
        model="model",
        width=40,
        color=False,
        unicode=False,
        stream=StringIO(),
    )

    assert "◇" not in output
    assert "─" not in output
    assert "* Agent ready" in output
    assert "-" * 40 in output
