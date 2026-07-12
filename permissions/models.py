"""Strict, immutable data models for VEGA permission policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, ClassVar


class PermissionsError(Exception):
    """Base exception for the permission subsystem."""


class PermissionValidationError(PermissionsError, ValueError):
    """Raised when permission data violates the schema."""


class PermissionPolicyError(PermissionsError):
    """Raised when a permission policy cannot be loaded safely."""


class PermissionEffect(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


class PermissionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionCapability(str, Enum):
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    MANAGED_STATE_READ = "managed_state.read"
    MANAGED_STATE_WRITE = "managed_state.write"
    PROCESS_EXECUTE = "process.execute"
    NETWORK_CONTROL = "network.control"
    NETWORK_FETCH = "network.fetch"
    GIT_READ = "git.read"
    GIT_WRITE = "git.write"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    DOCUMENTATION_READ = "documentation.read"
    DOCUMENTATION_WRITE = "documentation.write"
    RELEASE_READ = "release.read"


class PermissionGrantScope(str, Enum):
    ONCE = "once"
    SESSION = "session"


_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_REASON_LENGTH = 500


def validate_tool_name(value: Any) -> str:
    if not isinstance(value, str):
        raise PermissionValidationError("tool_name must be a string")
    if not value:
        raise PermissionValidationError("tool_name must not be empty")
    if not _TOOL_NAME.fullmatch(value):
        raise PermissionValidationError(
            "tool_name must use normalized lowercase identifier characters"
        )
    return value


def _enum_value(enum_type: type[Enum], value: Any, field: str):
    if not isinstance(value, str):
        raise PermissionValidationError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise PermissionValidationError(f"invalid {field}: {value!r}") from exc


def _require_object(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise PermissionValidationError(f"{label} must be an object")
    if not all(isinstance(key, str) for key in data):
        raise PermissionValidationError(f"{label} field names must be strings")
    return data


def _require_fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    actual = set(data)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise PermissionValidationError(f"invalid {label} fields ({'; '.join(details)})")


@dataclass(frozen=True, slots=True)
class PermissionRule:
    tool_name: str
    capabilities: tuple[PermissionCapability, ...]
    risk: PermissionRisk
    effect: PermissionEffect
    session_grant_allowed: bool
    reason: str

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"tool_name", "capabilities", "risk", "effect", "session_grant_allowed", "reason"}
    )

    def __post_init__(self) -> None:
        validate_tool_name(self.tool_name)
        if not isinstance(self.capabilities, (list, tuple)) or not self.capabilities:
            raise PermissionValidationError("capabilities must be a non-empty list or tuple")
        if isinstance(self.capabilities, list):
            object.__setattr__(self, "capabilities", tuple(self.capabilities))
        if any(not isinstance(item, PermissionCapability) for item in self.capabilities):
            raise PermissionValidationError("capabilities contain an invalid value")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise PermissionValidationError("capabilities must not contain duplicates")
        if not isinstance(self.risk, PermissionRisk):
            raise PermissionValidationError("risk must be a PermissionRisk")
        if not isinstance(self.effect, PermissionEffect):
            raise PermissionValidationError("effect must be a PermissionEffect")
        if type(self.session_grant_allowed) is not bool:
            raise PermissionValidationError("session_grant_allowed must be a boolean")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise PermissionValidationError("reason must be a non-empty string")
        if self.reason != self.reason.strip() or len(self.reason) > _MAX_REASON_LENGTH:
            raise PermissionValidationError("reason must be trimmed and at most 500 characters")
        if self.session_grant_allowed and self.effect is PermissionEffect.DENY:
            raise PermissionValidationError("denied rules cannot allow session grants")
        if self.session_grant_allowed and self.risk is PermissionRisk.CRITICAL:
            raise PermissionValidationError("critical rules cannot allow session grants")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "capabilities": [item.value for item in self.capabilities],
            "risk": self.risk.value,
            "effect": self.effect.value,
            "session_grant_allowed": self.session_grant_allowed,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PermissionRule":
        obj = _require_object(data, "permission rule")
        _require_fields(obj, cls._FIELDS, "permission rule")
        raw_capabilities = obj["capabilities"]
        if not isinstance(raw_capabilities, (list, tuple)) or not raw_capabilities:
            raise PermissionValidationError("capabilities must be a non-empty array")
        capabilities = tuple(
            _enum_value(PermissionCapability, item, "capability")
            for item in raw_capabilities
        )
        return cls(
            tool_name=obj["tool_name"],
            capabilities=capabilities,
            risk=_enum_value(PermissionRisk, obj["risk"], "risk"),
            effect=_enum_value(PermissionEffect, obj["effect"], "effect"),
            session_grant_allowed=obj["session_grant_allowed"],
            reason=obj["reason"],
        )


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    schema_version: int
    default_effect: PermissionEffect
    confirmation_token: str
    max_session_grants: int
    rules: tuple[PermissionRule, ...]

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"schema_version", "default_effect", "confirmation_token", "max_session_grants", "rules"}
    )

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise PermissionValidationError("supported schema_version is exactly 1")
        if self.default_effect is not PermissionEffect.DENY:
            raise PermissionValidationError("default_effect must be deny")
        if self.confirmation_token != "CONFIRM":
            raise PermissionValidationError("confirmation_token must be exactly CONFIRM")
        if type(self.max_session_grants) is not int:
            raise PermissionValidationError("max_session_grants must be an integer")
        if not 1 <= self.max_session_grants <= 1000:
            raise PermissionValidationError("max_session_grants must be between 1 and 1000")
        if not isinstance(self.rules, (list, tuple)):
            raise PermissionValidationError("rules must be a list or tuple")
        if isinstance(self.rules, list):
            object.__setattr__(self, "rules", tuple(self.rules))
        if any(not isinstance(rule, PermissionRule) for rule in self.rules):
            raise PermissionValidationError("rules contain an invalid value")
        names = [rule.tool_name for rule in self.rules]
        if len(set(names)) != len(names):
            raise PermissionValidationError("rules must contain exactly one rule per tool_name")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "default_effect": self.default_effect.value,
            "confirmation_token": self.confirmation_token,
            "max_session_grants": self.max_session_grants,
            "rules": [rule.to_dict() for rule in sorted(self.rules, key=lambda item: item.tool_name)],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "PermissionPolicy":
        obj = _require_object(data, "permission policy")
        _require_fields(obj, cls._FIELDS, "permission policy")
        raw_rules = obj["rules"]
        if not isinstance(raw_rules, (list, tuple)):
            raise PermissionValidationError("rules must be an array")
        return cls(
            schema_version=obj["schema_version"],
            default_effect=_enum_value(PermissionEffect, obj["default_effect"], "default_effect"),
            confirmation_token=obj["confirmation_token"],
            max_session_grants=obj["max_session_grants"],
            rules=tuple(PermissionRule.from_dict(item) for item in raw_rules),
        )
