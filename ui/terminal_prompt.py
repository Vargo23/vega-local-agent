"""Compact VEGA input prompt with a conservative ASCII fallback."""

from __future__ import annotations

import sys
from typing import TextIO

from ui.terminal_theme import detect_terminal_capabilities


def render_terminal_prompt(
    model: object,
    environment: object = "LOCAL",
    *,
    stream: TextIO | None = None,
    unicode: bool | None = None,
    color: bool = True,
) -> str:
    """Render the input prompt; model state is shown by the startup screen."""

    stream = stream or sys.stdout
    capabilities = detect_terminal_capabilities(stream, unicode=unicode)
    prompt = "vega › " if capabilities.unicode else "vega > "
    if color and capabilities.ansi:
        return f"\x1b[36m{prompt}\x1b[0m"
    return prompt


__all__ = ["render_terminal_prompt"]
