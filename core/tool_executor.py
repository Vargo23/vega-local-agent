"""Controlled execution of registered VEGA tools."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from permissions.evaluator import PermissionEvaluator
from permissions.models import PermissionEffect
from permissions.session_grants import SessionGrantStore
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
    confirmation_token: str | None = None

    def __post_init__(self) -> None:
        """Normalize and detach request values from caller state."""
        if not isinstance(self.tool_name, str):
            raise TypeError("tool_name must be a string.")

        normalized_name = self.tool_name.strip()

        if not normalized_name:
            raise ValueError("tool_name must not be empty.")

        if not isinstance(self.arguments, dict):
            raise TypeError("arguments must be a dictionary.")
        if self.confirmation_token is not None and not isinstance(
            self.confirmation_token,
            str,
        ):
            raise TypeError("confirmation_token must be a string or None.")

        object.__setattr__(self, "tool_name", normalized_name)
        object.__setattr__(self, "arguments", dict(self.arguments))


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Describe the outcome of one controlled tool invocation."""

    status: ToolExecutionStatus
    tool_name: str
    data: Any = None
    error: str = ""
    error_code: str = ""
    permission_risk: str = ""
    permission_capabilities: tuple[str, ...] = ()
    permission_session_allowed: bool = False

    @property
    def ok(self) -> bool:
        """Return whether the tool completed successfully."""
        return self.status is ToolExecutionStatus.SUCCESS


class ToolExecutor:
    """Invoke only explicitly registered callables with bound arguments."""

    def __init__(
        self,
        registry: Mapping[str, Callable[..., Any]] | None = None,
        permission_evaluator: PermissionEvaluator | None = None,
        session_grants: SessionGrantStore | None = None,
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
        if permission_evaluator is not None and not isinstance(
            permission_evaluator,
            PermissionEvaluator,
        ):
            raise TypeError(
                "permission_evaluator must be a PermissionEvaluator instance."
            )
        self._permission_evaluator = permission_evaluator
        if session_grants is not None and not isinstance(session_grants, SessionGrantStore):
            raise TypeError("session_grants must be a SessionGrantStore instance.")
        self._session_grants = session_grants

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

        permission_failure = self._permission_failure(request)
        if permission_failure is not None:
            return permission_failure

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

    def _permission_failure(
        self,
        request: ToolRequest,
    ) -> ToolExecutionResult | None:
        evaluator = self._permission_evaluator
        if evaluator is None:
            return None
        try:
            decision = evaluator.evaluate(request.tool_name)
            if decision.allowed:
                return None
            if decision.confirmation_required:
                if evaluator.accepts_confirmation(request.confirmation_token):
                    return None
                if (
                    self._session_grants is not None
                    and self._session_grants.contains(request.tool_name)
                    and evaluator.allows_session_grant(decision)
                ):
                    return None
                return ToolExecutionResult(
                    ToolExecutionStatus.FAILED,
                    request.tool_name,
                    error="Tool execution requires explicit confirmation.",
                    error_code="confirmation_required",
                    permission_risk=decision.rule.risk.value,
                    permission_capabilities=tuple(
                        item.value for item in decision.rule.capabilities
                    ),
                    permission_session_allowed=evaluator.allows_session_grant(decision),
                )
            if decision.effect is PermissionEffect.DENY and not decision.error_code:
                return ToolExecutionResult(
                    ToolExecutionStatus.FAILED,
                    request.tool_name,
                    error="Tool execution is denied by permission policy.",
                    error_code="permission_denied",
                )
            return ToolExecutionResult(
                ToolExecutionStatus.FAILED,
                request.tool_name,
                error=(
                    "Tool execution failed closed due to permission policy "
                    "state."
                ),
                error_code="permission_policy_error",
            )
        except Exception as exc:
            return ToolExecutionResult(
                ToolExecutionStatus.FAILED,
                request.tool_name,
                error=(
                    "Permission evaluation failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                error_code="permission_policy_error",
            )

    def execute_named(
        self,
        tool_name: str,
        *,
        confirmation_token: str | None = None,
        **arguments: Any,
    ) -> ToolExecutionResult:
        """Build and execute one named tool request."""
        return self.execute(
            ToolRequest(
                tool_name=tool_name,
                arguments=arguments,
                confirmation_token=confirmation_token,
            )
        )

    def _execute_confirmed_once(
        self,
        request: ToolRequest,
    ) -> ToolExecutionResult:
        """Retry one request with the evaluator's validated internal token."""
        if not isinstance(request, ToolRequest):
            raise TypeError("request must be a ToolRequest instance.")
        evaluator = self._permission_evaluator
        if evaluator is None:
            return self.execute(request)
        confirmed = ToolRequest(
            request.tool_name,
            dict(request.arguments),
            confirmation_token=evaluator.confirmation_token,
        )
        return self.execute(confirmed)

    def grant_session_for_tool(self, tool_name: str) -> None:
        """Grant one registered tool only after current policy validation."""
        if not isinstance(tool_name, str):
            raise TypeError("tool_name must be a string.")
        normalized_name = tool_name.strip()
        if not normalized_name:
            raise ValueError("tool_name must not be empty.")
        if normalized_name not in self._registry:
            raise ValueError(f"Unknown tool: {normalized_name}.")
        if self._permission_evaluator is None or self._session_grants is None:
            raise RuntimeError("session grants are unavailable")
        decision = self._permission_evaluator.evaluate(normalized_name)
        if not self._permission_evaluator.allows_session_grant(decision):
            raise RuntimeError("session grant is not permitted by policy")
        self._session_grants.grant(normalized_name)
