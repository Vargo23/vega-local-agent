"""One-time interactive confirmation for permission-protected tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from core.tool_executor import ToolExecutionResult, ToolExecutionStatus, ToolExecutor, ToolRequest


class ToolConfirmationDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class ToolConfirmationRequest:
    tool_name: str
    risk: str
    capabilities: tuple[str, ...] = ()
    argument_keys: tuple[str, ...] = ()

    @classmethod
    def from_execution(cls, request: ToolRequest, result: ToolExecutionResult) -> "ToolConfirmationRequest":
        return cls(request.tool_name, result.permission_risk or "unknown", result.permission_capabilities, tuple(sorted(request.arguments)))


ToolConfirmationCallback = Callable[[str], object]


class ToolConfirmationManager:
    def __init__(self, callback: ToolConfirmationCallback | None = None) -> None:
        if callback is not None and not callable(callback):
            raise TypeError("callback must be callable or None")
        self._callback = callback

    @staticmethod
    def build_prompt(request: ToolConfirmationRequest) -> str:
        capabilities = ", ".join(request.capabilities) or "unspecified"
        keys = ", ".join(request.argument_keys) or "none"
        return (f'Tool "{request.tool_name}" requests one-time execution.\n'
                f"Risk: {request.risk}.\nCapabilities: {capabilities}.\n"
                f"Argument names: {keys}.\nAllow this invocation once? [y/N] ")

    def decide(self, request: ToolConfirmationRequest) -> ToolConfirmationDecision:
        if self._callback is None:
            return ToolConfirmationDecision.CANCEL
        try:
            response = self._callback(self.build_prompt(request))
        except (EOFError, KeyboardInterrupt):
            return ToolConfirmationDecision.CANCEL
        except Exception:
            return ToolConfirmationDecision.CANCEL
        if response is True:
            return ToolConfirmationDecision.APPROVE
        if response is False:
            return ToolConfirmationDecision.REJECT
        if isinstance(response, ToolConfirmationDecision):
            return response
        if isinstance(response, str):
            normalized = response.strip().lower()
            if normalized in {"y", "yes"}:
                return ToolConfirmationDecision.APPROVE
            if normalized in {"n", "no"}:
                return ToolConfirmationDecision.REJECT
        return ToolConfirmationDecision.REJECT


def execute_tool_with_confirmation(executor: ToolExecutor, request: ToolRequest, manager: ToolConfirmationManager | None = None) -> ToolExecutionResult:
    original = ToolRequest(request.tool_name, dict(request.arguments))
    result = executor.execute(original)
    if result.error_code != "confirmation_required" or manager is None:
        return result
    decision = manager.decide(ToolConfirmationRequest.from_execution(original, result))
    if decision is not ToolConfirmationDecision.APPROVE:
        return ToolExecutionResult(ToolExecutionStatus.FAILED, original.tool_name, error="Tool execution confirmation was rejected or cancelled.", error_code="confirmation_rejected", permission_risk=result.permission_risk, permission_capabilities=result.permission_capabilities)
    return executor._execute_confirmed_once(original)


__all__ = ["ToolConfirmationCallback", "ToolConfirmationDecision", "ToolConfirmationManager", "ToolConfirmationRequest", "execute_tool_with_confirmation"]
