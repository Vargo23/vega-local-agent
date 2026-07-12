"""Fail-closed loading and registry alignment for permission policies."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from permissions.models import (
    PermissionPolicy,
    PermissionPolicyError,
    PermissionsError,
    PermissionValidationError,
    validate_tool_name,
)


def _registered_names(registered_tools: Any) -> tuple[str, ...]:
    if isinstance(registered_tools, Mapping):
        values: Iterable[Any] = registered_tools.keys()
    elif isinstance(registered_tools, (list, tuple)):
        values = registered_tools
    else:
        raise PermissionValidationError(
            "registered_tools must be a deterministic list, tuple, or mapping"
        )
    names = []
    for value in values:
        names.append(validate_tool_name(value))
    if len(set(names)) != len(names):
        raise PermissionValidationError("registered_tools contains duplicate tool names")
    return tuple(names)


def validate_policy_registry_alignment(
    policy: PermissionPolicy,
    registered_tools: Any,
) -> None:
    if not isinstance(policy, PermissionPolicy):
        raise PermissionValidationError("policy must be a PermissionPolicy")
    registered = set(_registered_names(registered_tools))
    configured = {rule.tool_name for rule in policy.rules}
    missing = sorted(registered - configured)
    extra = sorted(configured - registered)
    if missing or extra:
        details = []
        if missing:
            details.append("missing rules: " + ", ".join(missing))
        if extra:
            details.append("extra rules: " + ", ".join(extra))
        raise PermissionValidationError("registry alignment failed (" + "; ".join(details) + ")")


def load_permission_policy(project_root: Any, *, registered_tools: Any = None) -> PermissionPolicy:
    try:
        root = Path(project_root).resolve(strict=False)
    except (TypeError, ValueError, OSError) as exc:
        raise PermissionPolicyError("invalid project root") from exc
    policy_file = root / "config" / "permission_policy.json"
    try:
        text = policy_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PermissionPolicyError("permission policy could not be read") from exc
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise PermissionPolicyError("permission policy contains invalid JSON") from exc
    if not isinstance(data, dict):
        raise PermissionPolicyError("permission policy must contain a JSON object")
    try:
        policy = PermissionPolicy.from_dict(data)
        if registered_tools is not None:
            validate_policy_registry_alignment(policy, registered_tools)
    except PermissionValidationError as exc:
        raise PermissionPolicyError(f"invalid permission policy: {exc}") from exc
    return policy


__all__ = [
    "PermissionPolicyError",
    "PermissionsError",
    "PermissionValidationError",
    "load_permission_policy",
    "validate_policy_registry_alignment",
]
