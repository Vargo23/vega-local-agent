from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.contextual_router import (
    ContextualRoutingError,
    route_contextual_request,
)


PLAN_HELP = """Contextual planning commands:
  /plan <task>

Examples:
  /plan Найди в проекте использование старого API
  /plan Проанализируй "docs/report.md" и сделай краткий отчёт
  /plan Посмотри staged изменения и оцени риски

The command only builds a preview.
It never executes tools or changes project files."""


def _format_value(value: object) -> str:
    if isinstance(value, str):
        return value

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def handle_plan_command(
    command: str,
    project_root: str | Path,
    *,
    registry: object | None = None,
    capability_config: (
        Mapping[str, Any] | str | Path | None
    ) = None,
    policy_config: (
        Mapping[str, Any] | str | Path | None
    ) = None,
) -> str:
    """Build and format a contextual execution preview."""

    if not isinstance(command, str):
        raise TypeError("command must be a string")

    root = Path(project_root).resolve()
    stripped = command.strip()
    parts = stripped.split(maxsplit=1)

    if (
        not parts
        or parts[0].lower() != "/plan"
        or len(parts) == 1
        or not parts[1].strip()
    ):
        return PLAN_HELP

    task_text = parts[1].strip()

    if registry is None:
        from tools.registry import TOOL_REGISTRY

        registry = TOOL_REGISTRY

    if capability_config is None:
        capability_config = (
            root / "config" / "tool_capabilities.json"
        )

    if policy_config is None:
        policy_config = (
            root / "config" / "tool_routing_policy.json"
        )

    try:
        result = route_contextual_request(
            task_text,
            registry,
            capability_config,
            policy_config,
            workspace=root,
            preview=True,
        )
    except ContextualRoutingError as exc:
        return f"Plan command error: {exc}"

    lines = [
        "Contextual execution plan",
        f"Intent: {result.analysis.intent.value}",
        f"Confidence: {result.analysis.confidence:.2f}",
        "Execution: preview only",
        (
            "Requires confirmation: "
            + (
                "yes"
                if result.requires_confirmation
                else "no"
            )
        ),
        f"Steps: {len(result.plan.steps)}",
    ]

    for step in result.plan.steps:
        lines.extend(
            [
                "",
                f"Step {step.step_id}",
                f"  Tool: {step.tool_name}",
                (
                    "  Permission: "
                    f"{step.required_permission}"
                ),
            ]
        )

        if step.depends_on:
            dependencies = ", ".join(
                str(item)
                for item in step.depends_on
            )
            lines.append(
                f"  Depends on: {dependencies}"
            )

        if step.arguments:
            lines.append("  Arguments:")

            for name, value in sorted(
                step.arguments.items()
            ):
                lines.append(
                    f"    {name}: {_format_value(value)}"
                )
        else:
            lines.append("  Arguments: none")

    return "\n".join(lines)


__all__ = [
    "PLAN_HELP",
    "handle_plan_command",
]
