"""Deterministic runtime evaluation of loaded permission policies."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from permissions.models import (
    PermissionEffect,
    PermissionPolicy,
    PermissionRule,
    PermissionValidationError,
    validate_tool_name,
)


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    effect: PermissionEffect
    rule: PermissionRule | None = None
    error_code: str = ""
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.effect is PermissionEffect.ALLOW and not self.error_code

    @property
    def confirmation_required(self) -> bool:
        return self.effect is PermissionEffect.CONFIRM and not self.error_code


class PermissionEvaluator:
    """Evaluate normalized names against an already-loaded immutable policy."""
    def __init__(self, policy: PermissionPolicy) -> None:
        if not isinstance(policy, PermissionPolicy):
            raise PermissionValidationError("policy must be a PermissionPolicy")
        self._policy = policy
        self._rules = MappingProxyType(
            {rule.tool_name: rule for rule in policy.rules}
        )

    def evaluate(self, tool_name: str) -> PermissionDecision:
        try:
            normalized_name = validate_tool_name(tool_name)
        except PermissionValidationError as exc:
            return PermissionDecision(
                PermissionEffect.DENY,
                error_code="permission_policy_error",
                reason=str(exc),
            )
        rule = self._rules.get(normalized_name)
        if rule is None:
            return PermissionDecision(
                self._policy.default_effect,
                error_code="permission_policy_error",
                reason="No permission policy rule exists for the tool.",
            )
        return PermissionDecision(rule.effect, rule=rule, reason=rule.reason)

    def accepts_confirmation(self, token: object) -> bool:
        return token == self._policy.confirmation_token

    def allows_session_grant(self, decision: PermissionDecision) -> bool:
        """Return whether this current confirm decision permits session scope."""
        return (
            isinstance(decision, PermissionDecision)
            and decision.confirmation_required
            and decision.rule is not None
            and decision.rule.session_grant_allowed
        )

    @property
    def confirmation_token(self) -> str:
        """Return the token already validated by PermissionPolicy."""
        return self._policy.confirmation_token


__all__ = ["PermissionDecision", "PermissionEvaluator"]
