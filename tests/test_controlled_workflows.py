from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from workflows import default_registry
from workflows.controlled_engine import ControlledWorkflowError, WorkflowEngine
from workflows.controlled_models import MAX_ITERATIONS
from workflows.models import WorkflowStatus


ROOT = Path(__file__).resolve().parents[1]


class ManagedPatches:
    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.identities: dict[str, tuple[str, str]] = {}
        self.applied: list[str] = []
        self.rolled_back: list[str] = []

    def add(self, patch_id: str, target: str = "sample.py") -> None:
        self.states[patch_id] = "pending"
        self.identities[patch_id] = (
            hashlib.sha256(f"{patch_id}:old".encode()).hexdigest(),
            hashlib.sha256(f"{patch_id}:new".encode()).hexdigest(),
        )

    def prepare_safe(self, patch_id: str) -> dict[str, str]:
        original, proposed = self.identities[patch_id]
        return {
            "patch_id": patch_id,
            "status": self.states[patch_id],
            "target_path": "sample.py",
            "original_sha256": original,
            "proposed_sha256": proposed,
        }

    def apply(self, patch_id: str, confirmed: bool = False) -> dict[str, object]:
        assert confirmed is True
        assert self.states[patch_id] == "pending"
        self.states[patch_id] = "applied"
        self.applied.append(patch_id)
        return {
            "ok": True,
            "error": None,
            "data": {"patch_id": patch_id, "target_path": "sample.py", "status": "applied"},
        }

    def rollback(self, patch_id: str, confirmed: bool = False) -> dict[str, str]:
        assert confirmed is True
        if self.states[patch_id] != "applied":
            raise ControlledWorkflowError("rollback_refused")
        self.states[patch_id] = "rolled_back"
        self.rolled_back.append(patch_id)
        return {"patch_id": patch_id, "target_path": "sample.py", "status": "rolled_back"}


class ControlledTests:
    def __init__(self, results: list[bool] | None = None) -> None:
        self.results = list(results or [True])
        self.runs: list[str] = []

    def resolve(self, group_id: str) -> dict[str, str]:
        if group_id not in {"workflow", "all"}:
            raise ValueError
        return {
            "group_id": group_id,
            "command_id": "tests-workflow" if group_id == "workflow" else "tests",
        }

    def run_group(self, group_id: str) -> dict[str, object]:
        self.runs.append(group_id)
        passed = self.results.pop(0)
        return {
            "passed": passed,
            "returncode": 0 if passed else 1,
            "timed_out": False,
            "duration_ms": 7,
            "outcome_code": "passed" if passed else "failed",
            "stdout": "SECRET-SENTINEL-OUTPUT",
        }


class CrashAfterApplyPatches(ManagedPatches):
    def apply(self, patch_id: str, confirmed: bool = False) -> dict[str, object]:
        super().apply(patch_id, confirmed)
        raise RuntimeError("sensitive injected crash")


class InterruptedTests(ControlledTests):
    def run_group(self, group_id: str) -> dict[str, object]:
        self.runs.append(group_id)
        raise KeyboardInterrupt


class MutatingTests(ControlledTests):
    def __init__(self, root: Path) -> None:
        super().__init__([True])
        self.root = root

    def run_group(self, group_id: str) -> dict[str, object]:
        result = super().run_group(group_id)
        (self.root / "unexpected-during-tests.py").write_text("changed = True\n", encoding="utf-8")
        return result


@pytest.fixture
def project(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(ROOT / "config" / name, config / name)
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("def parser_error():\n    return 1\n", encoding="utf-8")
    return tmp_path


def engine(
    project: Path,
    patches: ManagedPatches | None = None,
    tests: ControlledTests | None = None,
) -> tuple[WorkflowEngine, ManagedPatches, ControlledTests]:
    patch_tools = patches or ManagedPatches()
    test_tools = tests or ControlledTests()
    return (
        WorkflowEngine(
            project,
            default_registry(),
            patch_tools=patch_tools,
            test_tools=test_tools,
        ),
        patch_tools,
        test_tools,
    )


def test_bug_fix_happy_path_requires_separate_patch_and_test_approvals(project: Path) -> None:
    workflow, patches, tests = engine(project)
    patches.add("patch-1")
    started = workflow.start("bug-fix", "SECRET-SENTINEL fix parser error")
    assert started.status is WorkflowStatus.WAITING_PATCH
    assert patches.applied == [] and tests.runs == []
    serialized = (workflow.active_dir / f"{started.workflow_id}.json").read_text(encoding="utf-8")
    assert "SECRET-SENTINEL" not in serialized
    assert "parser error" not in serialized

    proposed = workflow.attach_patch("patch-1")
    assert proposed.status is WorkflowStatus.AWAITING_PATCH_CONFIRMATION
    assert proposed.confirmation is not None
    assert proposed.confirmation.action == "patch_application"
    assert tests.runs == []

    applied = workflow.approve_patch(started.workflow_id)
    assert applied.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert patches.applied == ["patch-1"]
    assert tests.runs == []
    assert applied.confirmation is not None
    assert applied.confirmation.action == "test_execution"

    completed = workflow.approve_tests(started.workflow_id)
    assert completed.status is WorkflowStatus.COMPLETED
    assert tests.runs == ["workflow"]
    assert completed.rollback_available
    assert workflow.status() is None
    assert workflow.show(started.workflow_id) == completed


def test_confirmation_is_rejected_after_workspace_drift(project: Path) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    (project / "unexpected.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(ControlledWorkflowError, match="workspace_drift"):
        workflow.approve_patch(run.workflow_id)

    drifted = workflow.status()
    assert drifted is not None
    assert drifted.status is WorkflowStatus.WAITING_PATCH
    assert drifted.workspace_drift
    assert patches.applied == []


def test_changed_patch_identity_and_wrong_workflow_are_rejected(project: Path) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    patches.identities["patch-1"] = (
        patches.identities["patch-1"][0],
        hashlib.sha256(b"changed").hexdigest(),
    )
    with pytest.raises(ControlledWorkflowError, match="patch_identity_changed"):
        workflow.approve_patch(run.workflow_id)
    invalidated = workflow.status()
    assert invalidated is not None
    assert invalidated.status is WorkflowStatus.WAITING_PATCH
    assert invalidated.confirmation is None
    with pytest.raises(Exception):
        workflow.approve_patch("workflow-" + "0" * 32)
    assert patches.applied == []


def test_policy_inconsistency_stops_before_patch_application(project: Path) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    (project / "config" / "permission_policy.json").write_text("{}", encoding="utf-8")
    workflow.attach_patch("patch-1")

    with pytest.raises(ControlledWorkflowError, match="permission_policy_error"):
        workflow.approve_patch(run.workflow_id)

    assert patches.applied == []


def test_invalid_review_scope_and_test_group_create_no_workflow(project: Path) -> None:
    workflow, _, _ = engine(project)
    with pytest.raises(ControlledWorkflowError, match="review_scope_invalid"):
        workflow.start("review", "working-tree")
    assert workflow.status() is None
    with pytest.raises(ControlledWorkflowError, match="test_configuration_missing"):
        workflow.start("test", "arbitrary -k expression")
    assert workflow.status() is None


def test_trace_failure_is_isolated_from_workflow_result(project: Path, monkeypatch) -> None:
    workflow, _, _ = engine(project)
    monkeypatch.setattr("workflows.controlled_engine.append_trace", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("trace failure")))

    state = workflow.start("feature", "Add parser")

    assert state.status is WorkflowStatus.WAITING_PATCH


def test_failed_test_preserves_patch_and_allows_second_controlled_iteration(project: Path) -> None:
    tests = ControlledTests([False, True])
    workflow, patches, _ = engine(project, tests=tests)
    patches.add("patch-1")
    patches.add("patch-2")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    workflow.approve_patch(run.workflow_id)
    failed = workflow.approve_tests(run.workflow_id)
    assert failed.status is WorkflowStatus.WAITING_PATCH
    assert failed.rollback_available
    assert len(failed.test_results) == 1
    assert failed.patches[0].status == "applied"

    workflow.attach_patch("patch-2")
    workflow.approve_patch(run.workflow_id)
    completed = workflow.approve_tests(run.workflow_id)
    assert completed.status is WorkflowStatus.COMPLETED
    assert completed.iteration_count == 2
    assert patches.applied == ["patch-1", "patch-2"]


def test_compiled_iteration_limit_is_three(project: Path) -> None:
    tests = ControlledTests([False, False, False])
    workflow, patches, _ = engine(project, tests=tests)
    for index in range(1, MAX_ITERATIONS + 1):
        patches.add(f"patch-{index}")
    run = workflow.start("bug-fix", "Fix parser")
    result = run
    for index in range(1, MAX_ITERATIONS + 1):
        workflow.attach_patch(f"patch-{index}")
        workflow.approve_patch(run.workflow_id)
        result = workflow.approve_tests(run.workflow_id)
    assert result.status is WorkflowStatus.FAILED
    assert result.error_codes == ("iteration_limit_reached",)
    assert result.iteration_count == MAX_ITERATIONS


def test_standalone_full_suite_is_bound_and_runs_once(project: Path) -> None:
    workflow, _, tests = engine(project)
    run = workflow.start("test", "all")
    assert run.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert run.test_group == "all"
    assert tests.runs == []
    completed = workflow.approve_tests(run.workflow_id)
    assert completed.status is WorkflowStatus.COMPLETED
    assert tests.runs == ["all"]


def test_restart_resume_never_replays_completed_action(project: Path) -> None:
    workflow, patches, tests = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    workflow.approve_patch(run.workflow_id)
    restarted = WorkflowEngine(
        project,
        default_registry(),
        patch_tools=patches,
        test_tools=tests,
    )
    resumed = restarted.resume(run.workflow_id)
    assert resumed.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert patches.applied == ["patch-1"]
    assert tests.runs == []


def test_interrupted_patch_apply_is_reconciled_without_replay(project: Path) -> None:
    patches = CrashAfterApplyPatches()
    patches.add("patch-1")
    workflow, _, tests = engine(project, patches=patches)
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")

    with pytest.raises(ControlledWorkflowError, match="patch_apply_failed"):
        workflow.approve_patch(run.workflow_id)
    assert patches.applied == ["patch-1"]

    resumed = WorkflowEngine(
        project, default_registry(), patch_tools=patches, test_tools=tests
    ).resume(run.workflow_id)
    assert resumed.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert patches.applied == ["patch-1"]
    assert tests.runs == []


def test_interrupted_test_run_fails_closed_and_is_not_replayed(project: Path) -> None:
    tests = InterruptedTests()
    workflow, _, _ = engine(project, tests=tests)
    run = workflow.start("test", "workflow")
    with pytest.raises(KeyboardInterrupt):
        workflow.approve_tests(run.workflow_id)
    assert tests.runs == ["workflow"]

    resumed = WorkflowEngine(
        project, default_registry(), patch_tools=ManagedPatches(), test_tools=tests
    ).resume(run.workflow_id)
    assert resumed.status is WorkflowStatus.FAILED
    assert resumed.error_codes == ("test_execution_failed",)
    assert tests.runs == ["workflow"]


def test_test_side_effect_workspace_drift_fails_workflow(project: Path) -> None:
    tests = MutatingTests(project)
    workflow, _, _ = engine(project, tests=tests)
    run = workflow.start("test", "workflow")

    result = workflow.approve_tests(run.workflow_id)

    assert result.status is WorkflowStatus.FAILED
    assert result.workspace_drift
    assert result.error_codes == ("workspace_drift",)


@pytest.mark.parametrize("stage", ["waiting_patch", "patch_confirmation", "test_confirmation"])
def test_cancellation_is_legal_at_controlled_wait_stages(project: Path, stage: str) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    if stage in {"patch_confirmation", "test_confirmation"}:
        workflow.attach_patch("patch-1")
    if stage == "test_confirmation":
        workflow.approve_patch(run.workflow_id)
    cancelled = workflow.cancel(run.workflow_id)
    assert cancelled.status is WorkflowStatus.CANCELLED


def test_rollback_is_refused_after_unrelated_user_edit(project: Path) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    workflow.approve_patch(run.workflow_id)
    (project / "unrelated.py").write_text("user = True\n", encoding="utf-8")
    with pytest.raises(ControlledWorkflowError, match="rollback_refused"):
        workflow.rollback(run.workflow_id)
    assert patches.rolled_back == []


def test_safe_rollback_of_completed_workflow_is_single_use(project: Path) -> None:
    workflow, patches, _ = engine(project)
    patches.add("patch-1")
    run = workflow.start("bug-fix", "Fix parser")
    workflow.attach_patch("patch-1")
    workflow.approve_patch(run.workflow_id)
    workflow.approve_tests(run.workflow_id)
    rolled = workflow.rollback(run.workflow_id)
    assert rolled.status is WorkflowStatus.ROLLED_BACK
    assert patches.rolled_back == ["patch-1"]
    with pytest.raises(ControlledWorkflowError, match="rollback_refused"):
        workflow.rollback(run.workflow_id)


def test_state_never_persists_test_output(project: Path) -> None:
    workflow, _, _ = engine(project)
    run = workflow.start("test", "workflow")
    workflow.approve_tests(run.workflow_id)
    serialized = (workflow.history_dir / f"{run.workflow_id}.json").read_text(encoding="utf-8")
    assert "SECRET-SENTINEL-OUTPUT" not in serialized
    assert "stdout" not in serialized and "stderr" not in serialized
    data = json.loads(serialized)
    assert set(data["test_results"][0]) == {
        "group_id", "command_id", "passed", "returncode", "timed_out", "duration_ms", "outcome_code"
    }
