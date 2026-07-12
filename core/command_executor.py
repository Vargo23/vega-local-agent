"""Structured execution of already-routed VEGA commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from core.command_router import CommandRoute, CommandTarget


class CommandExecutionStatus(str, Enum):
    """Supported outcomes of one command execution."""

    SUCCESS = "success"
    UNKNOWN_COMMAND = "unknown_command"
    MISSING_HANDLER = "missing_handler"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CommandExecutionRequest:
    """Describe one request containing an already-routed command."""

    route: CommandRoute

    def __post_init__(self) -> None:
        """Validate that the request contains routing metadata."""
        if not isinstance(self.route, CommandRoute):
            raise TypeError("route must be a CommandRoute instance.")


@dataclass(frozen=True, slots=True)
class CommandExecutionResult:
    """Describe the outcome of one command-handler invocation."""

    status: CommandExecutionStatus
    target: CommandTarget
    command_name: str
    normalized_command: str
    data: Any = None
    error: str = ""
    keep_running: bool = True

    @property
    def ok(self) -> bool:
        """Return whether the command completed successfully."""
        return self.status is CommandExecutionStatus.SUCCESS


CommandHandler = Callable[[CommandExecutionRequest], Any]


class CommandExecutor:
    """Invoke handlers selected by existing command routing."""

    def __init__(
        self,
        registry: Mapping[CommandTarget, CommandHandler] | None = None,
    ) -> None:
        configured_registry = {} if registry is None else registry

        if not isinstance(configured_registry, Mapping):
            raise TypeError("registry must implement the Mapping interface.")

        validated: dict[CommandTarget, CommandHandler] = {}

        for target, handler in configured_registry.items():
            if not isinstance(target, CommandTarget):
                raise TypeError("Handler registry keys must be CommandTarget values.")

            if not callable(handler):
                raise TypeError(
                    f"Handler for {target.value!r} must be callable."
                )

            validated[target] = handler

        self._registry = MappingProxyType(validated)

    def registered_targets(self) -> tuple[CommandTarget, ...]:
        """Return registered targets in deterministic value order."""
        return tuple(
            sorted(
                self._registry,
                key=lambda target: target.value,
            )
        )

    def execute(
        self,
        request: CommandExecutionRequest,
    ) -> CommandExecutionResult:
        """Execute one already-routed command through its handler."""
        if not isinstance(request, CommandExecutionRequest):
            raise TypeError(
                "request must be a CommandExecutionRequest instance."
            )

        route = request.route
        keep_running = route.target is not CommandTarget.EXIT

        if route.target is CommandTarget.UNKNOWN:
            return self._result(
                request,
                CommandExecutionStatus.UNKNOWN_COMMAND,
                error=f"Unknown command: {route.command_name}.",
                keep_running=keep_running,
            )

        handler = self._registry.get(route.target)

        if handler is None:
            return self._result(
                request,
                CommandExecutionStatus.MISSING_HANDLER,
                error=f"No handler registered for {route.target.value}.",
                keep_running=keep_running,
            )

        try:
            data = handler(request)
        except Exception as exc:
            return self._result(
                request,
                CommandExecutionStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
                keep_running=keep_running,
            )

        return self._result(
            request,
            CommandExecutionStatus.SUCCESS,
            data=data,
            keep_running=keep_running,
        )

    @staticmethod
    def _result(
        request: CommandExecutionRequest,
        status: CommandExecutionStatus,
        *,
        data: Any = None,
        error: str = "",
        keep_running: bool = True,
    ) -> CommandExecutionResult:
        route = request.route
        return CommandExecutionResult(
            status=status,
            target=route.target,
            command_name=route.command_name,
            normalized_command=route.normalized_command,
            data=data,
            error=error,
            keep_running=keep_running,
        )
