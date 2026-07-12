"""Controlled execution of registered VEGA tools."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from tools.registry import TOOL_REGISTRY


class ToolExecutionStatus(str, Enum):
    """Supported outcomes of one tool execution."""

    SUCCESS = "success"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """Describe one explicit request to invoke a registered tool."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize and detach request values from caller state."""
        if not isinstance(self.tool_name, str):
            raise TypeError("tool_name must be a string.")

        normalized_name = self.tool_name.strip()

        if not normalized_name:
            raise ValueError("tool_name must not be empty.")

        if not isinstance(self.arguments, dict):
            raise TypeError("arguments must be a dictionary.")

        object.__setattr__(self, "tool_name", normalized_name)
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Describe the outcome of one controlled tool invocation."""

    status: ToolExecutionStatus
    tool_name: str
    data: Any = None
    error: str = ""

    @property
    def ok(self) -> bool:
        """Return whether the tool completed successfully."""
        return self.status is ToolExecutionStatus.SUCCESS


class ToolExecutor:
    """Invoke only explicitly registered callables with bound arguments."""

    def __init__(
        self,
        registry: Mapping[str, Callable[..., Any]] | None = None,
    ) -> None:
        configured_registry = (
            TOOL_REGISTRY if registry is None else registry
        )

        if not isinstance(configured_registry, Mapping):
            raise TypeError("registry must implement the Mapping interface.")

        validated: dict[str, Callable[..., Any]] = {}

        for tool_name, tool in configured_registry.items():
            if not isinstance(tool_name, str):
                raise TypeError("Tool names must be strings.")

            normalized_name = tool_name.strip()

            if not normalized_name:
                raise ValueError("Tool names must not be empty.")

            if not callable(tool):
                raise TypeError(
                    f"Registered tool {normalized_name!r} must be callable."
                )

            if normalized_name in validated:
                raise ValueError(
                    f"Duplicate normalized tool name: {normalized_name!r}."
                )

            validated[normalized_name] = tool

        self._registry = MappingProxyType(validated)

    def registered_tools(self) -> tuple[str, ...]:
        """Return registered tool names in sorted order."""
        return tuple(sorted(self._registry))

    def execute(self, request: ToolRequest) -> ToolExecutionResult:
        """Validate and execute one explicit tool request."""
        if not isinstance(request, ToolRequest):
            raise TypeError("request must be a ToolRequest instance.")

        tool = self._registry.get(request.tool_name)

        if tool is None:
            return ToolExecutionResult(
                status=ToolExecutionStatus.UNKNOWN_TOOL,
                tool_name=request.tool_name,
                error=f"Unknown tool: {request.tool_name}.",
            )

        try:
            signature = inspect.signature(tool)
        except (TypeError, ValueError) as exc:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                tool_name=request.tool_name,
                error=(
                    "Tool signature inspection failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        try:
            signature.bind(**request.arguments)
        except TypeError as exc:
            return ToolExecutionResult(
                status=ToolExecutionStatus.INVALID_ARGUMENTS,
                tool_name=request.tool_name,
                error=f"TypeError: {exc}",
            )

        try:
            data = tool(**request.arguments)
        except Exception as exc:
            return ToolExecutionResult(
                status=ToolExecutionStatus.FAILED,
                tool_name=request.tool_name,
                error=f"{type(exc).__name__}: {exc}",
            )

        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCESS,
            tool_name=request.tool_name,
            data=data,
        )

    def execute_named(
        self,
        tool_name: str,
        **arguments: Any,
    ) -> ToolExecutionResult:
        """Build and execute one named tool request."""
        return self.execute(
            ToolRequest(
                tool_name=tool_name,
                arguments=arguments,
            )
        )
