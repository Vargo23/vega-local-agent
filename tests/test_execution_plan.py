import pytest

from core.execution_plan import (
    ExecutionPlan,
    PlanState,
    PlanValidationError,
    ToolCallStep,
)


def test_valid_execution_plan_serializes() -> None:
    plan = ExecutionPlan(
        goal="Find references to the old API",
        steps=(
            ToolCallStep(
                step_id=1,
                tool_name="file.search",
                arguments={"query": "old_api"},
                required_permission="read",
            ),
            ToolCallStep(
                step_id=2,
                tool_name="report.build",
                arguments={"format": "summary"},
                required_permission="draft",
                depends_on=(1,),
            ),
        ),
    )

    result = plan.to_dict()

    assert result["goal"] == "Find references to the old API"
    assert result["state"] == PlanState.DRAFT.value
    assert result["steps"][0]["tool_name"] == "file.search"
    assert result["steps"][0]["required_permission"] == "READ"
    assert result["steps"][1]["depends_on"] == [1]


def test_plan_reports_required_permissions() -> None:
    plan = ExecutionPlan(
        goal="Analyze and prepare a patch",
        steps=(
            ToolCallStep(
                step_id=1,
                tool_name="file.read",
                required_permission="READ",
            ),
            ToolCallStep(
                step_id=2,
                tool_name="patch.propose",
                required_permission="DRAFT",
                depends_on=(1,),
            ),
            ToolCallStep(
                step_id=3,
                tool_name="patch.apply",
                required_permission="WRITE",
                depends_on=(2,),
            ),
        ),
    )

    assert plan.required_permissions() == (
        "READ",
        "DRAFT",
        "WRITE",
    )
    assert plan.requires_confirmation({"READ", "DRAFT"}) is True
    assert plan.requires_confirmation(
        {"READ", "DRAFT", "WRITE"}
    ) is False


def test_plan_rejects_unknown_previous_dependency() -> None:
    with pytest.raises(
        PlanValidationError,
        match="do not refer to earlier steps",
    ):
        ExecutionPlan(
            goal="Invalid dependency",
            steps=(
                ToolCallStep(
                    step_id=1,
                    tool_name="file.read",
                    depends_on=(2,),
                ),
                ToolCallStep(
                    step_id=2,
                    tool_name="report.build",
                ),
            ),
        )


def test_plan_rejects_step_limit_overflow() -> None:
    steps = tuple(
        ToolCallStep(
            step_id=index,
            tool_name=f"tool.step_{index}",
        )
        for index in range(1, 4)
    )

    with pytest.raises(
        PlanValidationError,
        match="maximum is 2",
    ):
        ExecutionPlan(
            goal="Too many steps",
            steps=steps,
            max_steps=2,
        )


def test_plan_round_trip() -> None:
    original = ExecutionPlan(
        goal="Inspect Git changes",
        steps=(
            ToolCallStep(
                step_id=1,
                tool_name="git.diff",
                arguments={"staged": False},
                required_permission="READ",
            ),
        ),
        metadata={"source": "natural_language"},
    )

    restored = ExecutionPlan.from_dict(original.to_dict())

    assert restored == original


def test_tool_name_rejects_free_form_shell_command() -> None:
    with pytest.raises(
        PlanValidationError,
        match="tool_name may contain only",
    ):
        ToolCallStep(
            step_id=1,
            tool_name="powershell Remove-Item -Recurse",
        )
