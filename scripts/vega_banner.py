"""Compatibility renderer for the canonical UI startup screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from version import VERSION
except ImportError:
    from scripts.version import VERSION

from ui.startup_screen import build_startup_screen


@dataclass
class VegaStatus:
    model: str | None = None
    internet: bool = False
    version: str = VERSION
    workspace: str | None = None
    status: str = "Ready"


def render_banner(status: VegaStatus) -> str:
    root = Path(__file__).resolve().parents[1]
    model = status.model
    if not model:
        from core.agent_runtime import load_model_name

        model = load_model_name(root)

    return build_startup_screen(
        version=status.version,
        workspace=status.workspace or root.name,
        model=model,
        status=status.status,
        color=False,
    )
