from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Tuple


_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class PlanValidationError(ValueError):
    """Raised when an execution plan is structurally invalid."""


class PlanState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVAL_REQUIRED = "approval_required"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolCallStep:
    """One structured call to a registered VEGA tool."""

    step_id: int
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    required_permission: str = "READ"
    description: str = ""
    depends_on: Tuple[int, ...] = ()

    def __post_init__(self) -> None:
        tool_name = self.tool_name.strip()
        permission = self.required_permission.strip().upper()
        description = self.description.strip()

        object.__setattr__(self, "tool_name", tool_name)
        object.__setattr__(self, "required_permission", permission)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "arguments", dict(self.arguments))
        object.__setattr__(self, "depends_on", tuple(self.depends_on))

        if self.step_id < 1:
            raise PlanValidationError("step_id must be greater than zero")

        if not tool_name:
            raise PlanValidationError("tool_name must not be empty")

        if not _TOOL_NAME_PATTERN.fullmatch(tool_name):
            raise PlanValidationError(
                "tool_name may contain only letters, numbers, dots, "
                "underscores and hyphens"
            )

        if not permission:
            raise PlanValidationError(
                "required_permission must not be empty"
            )

        if self.step_id in self.depends_on:
            raise PlanValidationError(
                "a step cannot depend on itself"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "required_permission": self.required_permission,
            "description": self.description,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolCallStep":
        return cls(
            step_id=int(data["step_id"]),
            tool_name=str(data["tool_name"]),
            arguments=dict(data.get("arguments", {})),
            required_permission=str(
                data.get("required_permission", "READ")
            ),
            description=str(data.get("description", "")),
            depends_on=tuple(data.get("depends_on", ())),
        )


@dataclass(frozen=True)
class ExecutionPlan:
    """Validated sequence of tool calls produced by the orchestrator."""

    goal: str
    steps: Tuple[ToolCallStep, ...]
    max_steps: int = 8
    state: PlanState = PlanState.DRAFT
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        goal = self.goal.strip()
        steps = tuple(self.steps)
        metadata = dict(self.metadata)

        state = self.state
        if not isinstance(state, PlanState):
            state = PlanState(str(state))

        object.__setattr__(self, "goal", goal)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "state", state)

        self.validate()

    def validate(self) -> None:
        if not self.goal:
            raise PlanValidationError("plan goal must not be empty")

        if self.max_steps < 1:
            raise PlanValidationError(
                "max_steps must be greater than zero"
            )

        if not self.steps:
            raise PlanValidationError(
                "execution plan must contain at least one step"
            )

        if len(self.steps) > self.max_steps:
            raise PlanValidationError(
                f"execution plan contains {len(self.steps)} steps; "
                f"maximum is {self.max_steps}"
            )

        seen_ids: set[int] = set()

        for step in self.steps:
            if step.step_id in seen_ids:
                raise PlanValidationError(
                    f"duplicate step_id: {step.step_id}"
                )

            missing_dependencies = [
                dependency
                for dependency in step.depends_on
                if dependency not in seen_ids
            ]

            if missing_dependencies:
                raise PlanValidationError(
                    f"step {step.step_id} has dependencies that do not "
                    f"refer to earlier steps: {missing_dependencies}"
                )

            seen_ids.add(step.step_id)

    def required_permissions(self) -> Tuple[str, ...]:
        permissions: list[str] = []

        for step in self.steps:
            if step.required_permission not in permissions:
                permissions.append(step.required_permission)

        return tuple(permissions)

    def requires_confirmation(
        self,
        automatic_permissions: Iterable[str],
    ) -> bool:
        allowed = {
            permission.strip().upper()
            for permission in automatic_permissions
        }

        return any(
            step.required_permission not in allowed
            for step in self.steps
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "max_steps": self.max_steps,
            "state": self.state.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionPlan":
        return cls(
            goal=str(data["goal"]),
            steps=tuple(
                ToolCallStep.from_dict(step)
                for step in data["steps"]
            ),
            max_steps=int(data.get("max_steps", 8)),
            state=PlanState(
                str(data.get("state", PlanState.DRAFT.value))
            ),
            metadata=dict(data.get("metadata", {})),
        )
