"""Compact, width-aware VEGA operator console startup screen."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import TextIO

from ui.terminal_theme import detect_terminal_capabilities


DEFAULT_TERMINAL_WIDTH = 80
TITLE = "VEGA / OPERATOR CONSOLE"
INVITATION = "Give me a mission, or type /help."

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_CYAN = "36"
_GREEN = "32"
_NEUTRAL = "90"


def _clean(value: object, fallback: str) -> str:
    text = _CONTROL.sub("", str(value)).strip()
    return text or fallback


def _fit(text: str, width: int, *, unicode: bool) -> str:
    """Keep one plain-text line inside the available terminal width."""

    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    marker = "…" if unicode else "..."
    if width <= len(marker):
        return marker[:width]
    return text[: width - len(marker)].rstrip() + marker


def _terminal_width(width: int | None) -> int:
    if width is not None:
        try:
            return max(1, int(width))
        except (TypeError, ValueError):
            pass
    try:
        detected = shutil.get_terminal_size(
            fallback=(DEFAULT_TERMINAL_WIDTH, 24)
        ).columns
    except (OSError, ValueError):
        detected = DEFAULT_TERMINAL_WIDTH
    return max(1, detected)


def _field(label: str, value: object, width: int, *, unicode: bool) -> str:
    value_text = _clean(value, "unknown")
    if width >= 12:
        prefix = f"{label:<10} "
    else:
        prefix = f"{label} "
    return _fit(prefix + value_text, width, unicode=unicode)


def _paint(text: str, code: str, *, enabled: bool) -> str:
    if not enabled or not text:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def build_startup_screen(
    *,
    version: object | None = None,
    workspace: object | None = None,
    model: object | None = None,
    status: object = "Ready",
    width: int | None = None,
    color: bool | None = None,
    unicode: bool | None = None,
    stream: TextIO | None = None,
) -> str:
    """Build the startup screen from current runtime and terminal state."""

    stream = stream or sys.stdout
    capabilities = detect_terminal_capabilities(
        stream,
        ansi=color,
        unicode=unicode,
    )
    terminal_width = _terminal_width(width)

    if version is None:
        from scripts.version import VERSION

        version = VERSION
    if workspace is None:
        workspace = Path.cwd().name or str(Path.cwd())

    version_text = _clean(version, "unknown")
    model_text = _clean(model, "unknown-model")
    workspace_text = _clean(workspace, "workspace")
    status_text = _clean(status, "Ready")
    unicode_enabled = capabilities.unicode
    color_enabled = capabilities.ansi

    title = _fit(TITLE, terminal_width, unicode=unicode_enabled)
    version_label = _fit(version_text, terminal_width, unicode=unicode_enabled)
    header_gap = terminal_width - len(title) - len(version_label)
    if header_gap >= 2:
        header_lines = [
            _paint(title, _CYAN, enabled=color_enabled)
            + (" " * header_gap)
            + _paint(version_label, _NEUTRAL, enabled=color_enabled)
        ]
    else:
        header_lines = [
            _paint(title, _CYAN, enabled=color_enabled),
            _paint(version_label, _NEUTRAL, enabled=color_enabled),
        ]

    separator_symbol = "─" if unicode_enabled else "-"
    ready_symbol = "◇" if unicode_enabled else "*"
    normalized_status = status_text.lower()
    status_label = (
        "Agent ready"
        if normalized_status == "ready"
        else f"Agent {normalized_status}"
    )
    status_line = _fit(
        f"{ready_symbol} {status_label}",
        terminal_width,
        unicode=unicode_enabled,
    )
    invitation = _fit(
        f"  {INVITATION}",
        terminal_width,
        unicode=unicode_enabled,
    )

    lines = [
        *header_lines,
        _paint(
            separator_symbol * terminal_width,
            _CYAN,
            enabled=color_enabled,
        ),
        "",
        _field(
            "workspace",
            workspace_text,
            terminal_width,
            unicode=unicode_enabled,
        ),
        _field(
            "model",
            model_text,
            terminal_width,
            unicode=unicode_enabled,
        ),
        "",
        _paint(status_line, _GREEN, enabled=color_enabled),
        invitation,
    ]
    return "\n".join(lines)


def render_startup_screen(
    version: object | None = None,
    model: object | None = None,
    internet_status: object | None = None,
    status: object | None = None,
    log_path: object | None = None,
    *,
    workspace: object | None = None,
    width: int | None = None,
    color: bool | None = None,
    unicode: bool | None = None,
    stream: TextIO | None = None,
) -> None:
    """Print the startup screen without owning or duplicating the input prompt.

    ``internet_status`` and ``log_path`` retain the pre-v3 call signature but
    are intentionally not rendered by the operator console.
    """

    stream = stream or sys.stdout
    del internet_status, log_path
    print(
        build_startup_screen(
            version=version,
            workspace=workspace,
            model=model,
            status=status or "Ready",
            width=width,
            color=color,
            unicode=unicode,
            stream=stream,
        ),
        file=stream,
    )


def visible_width(line: str) -> int:
    """Return printable width for tests and terminal-safe integrations."""

    return len(_ANSI.sub("", line))


__all__ = ["build_startup_screen", "render_startup_screen", "visible_width"]
