"""Instance-scoped, in-memory permission session grants."""

from __future__ import annotations

from dataclasses import dataclass

from permissions.models import validate_tool_name


class SessionGrantError(RuntimeError):
    """Raised when a session grant cannot be changed safely."""


@dataclass(frozen=True, slots=True)
class SessionGrant:
    tool_name: str

    def __post_init__(self) -> None:
        validate_tool_name(self.tool_name)


class SessionGrantStore:
    """Store normalized tool grants for one runtime session only."""

    def __init__(self, max_grants: int = 1000) -> None:
        if type(max_grants) is not int or not 1 <= max_grants <= 1000:
            raise SessionGrantError("max_grants must be between 1 and 1000")
        self._max_grants = max_grants
        self._grants: set[str] = set()

    def grant(self, tool_name: str) -> SessionGrant:
        normalized = validate_tool_name(tool_name)
        if normalized not in self._grants and len(self._grants) >= self._max_grants:
            raise SessionGrantError("session grant limit reached")
        self._grants.add(normalized)
        return SessionGrant(normalized)

    def contains(self, tool_name: str) -> bool:
        return validate_tool_name(tool_name) in self._grants

    def revoke(self, tool_name: str) -> bool:
        normalized = validate_tool_name(tool_name)
        if normalized not in self._grants:
            return False
        self._grants.remove(normalized)
        return True

    def clear(self) -> int:
        count = len(self._grants)
        self._grants.clear()
        return count

    def list_grants(self) -> tuple[SessionGrant, ...]:
        return tuple(SessionGrant(name) for name in sorted(self._grants))


__all__ = ["SessionGrant", "SessionGrantError", "SessionGrantStore"]
