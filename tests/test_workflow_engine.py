"""Compatibility coverage for the exported v2.13 WorkflowEngine API."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from workflows import WorkflowEngine, default_registry
from workflows.controlled_engine import ActiveWorkflowError
from workflows.models import WorkflowStatus


ROOT = Path(__file__).resolve().parents[1]


class Patches:
    def __init__(self) -> None:
        self.state = "pending"
        self.applied = 0

    def prepare_safe(self, patch_id: str) -> dict[str, str]:
        return {
            "patch_id": patch_id,
            "status": self.state,
            "target_path": "sample.py",
            "original_sha256": hashlib.sha256(b"old").hexdigest(),
            "proposed_sha256": hashlib.sha256(b"new").hexdigest(),
        }

    def apply(self, patch_id: str, confirmed: bool = False) -> dict[str, object]:
        assert confirmed and self.state == "pending"
        self.state = "applied"
        self.applied += 1
        return {"ok": True, "data": {"patch_id": patch_id, "status": "applied", "target_path": "sample.py"}}

    def rollback(self, patch_id: str, confirmed: bool = False) -> dict[str, str]:
        assert confirmed and self.state == "applied"
        self.state = "rolled_back"
        return {"patch_id": patch_id, "status": "rolled_back", "target_path": "sample.py"}


class WorkflowTests:
    def __init__(self) -> None:
        self.runs = 0

    def resolve(self, group_id: str) -> dict[str, str]:
        return {"group_id": group_id, "command_id": "tests-workflow"}

    def run_group(self, group_id: str) -> dict[str, object]:
        self.runs += 1
        return {"passed": True, "returncode": 0, "timed_out": False, "duration_ms": 1, "outcome_code": "passed"}


@pytest.fixture
def configured_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(ROOT / "config" / name, tmp_path / "config" / name)
    (tmp_path / "sample.py").write_text("old\n", encoding="utf-8")
    return tmp_path


def make_engine(root: Path) -> tuple[WorkflowEngine, Patches, WorkflowTests]:
    patches, tests = Patches(), WorkflowTests()
    return WorkflowEngine(root, default_registry(), patch_tools=patches, test_tools=tests), patches, tests


def test_legacy_bugfix_alias_uses_controlled_bug_fix_type(configured_root: Path) -> None:
    engine, _, _ = make_engine(configured_root)
    run = engine.start("bugfix", "Fix parser")
    assert run.workflow_type == "bug-fix"
    assert run.status is WorkflowStatus.WAITING_PATCH


@pytest.mark.parametrize("workflow_type", ["feature", "refactor"])
def test_existing_coding_types_remain_available_but_controlled(
    configured_root: Path, workflow_type: str
) -> None:
    engine, patches, tests = make_engine(configured_root)
    run = engine.start(workflow_type, "Change parser", patch_id="patch-1")
    assert run.status is WorkflowStatus.AWAITING_PATCH_CONFIRMATION
    applied = engine.confirm()
    assert applied.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert patches.applied == 1 and tests.runs == 0
    completed = engine.confirm()
    assert completed.status is WorkflowStatus.COMPLETED
    assert tests.runs == 1


def test_only_one_active_workflow_and_cancel_archives(configured_root: Path) -> None:
    engine, _, _ = make_engine(configured_root)
    run = engine.start("bug-fix", "Fix parser")
    with pytest.raises(ActiveWorkflowError, match="active_workflow_exists"):
        engine.start("feature", "Other change")
    cancelled = engine.cancel(run.workflow_id)
    assert cancelled.status is WorkflowStatus.CANCELLED
    assert engine.status() is None
    assert engine.show(run.workflow_id).status is WorkflowStatus.CANCELLED


def test_status_and_history_do_not_expose_raw_task(configured_root: Path) -> None:
    engine, _, _ = make_engine(configured_root)
    run = engine.start("bug-fix", "SECRET-SENTINEL raw task")
    assert run.task == "[redacted]"
    engine.cancel(run.workflow_id)
    assert all(item.task == "[redacted]" for item in engine.history())


def test_confirm_never_authorizes_two_dangerous_actions(configured_root: Path) -> None:
    engine, patches, tests = make_engine(configured_root)
    engine.start("bug-fix", "Fix parser", patch_id="patch-1")
    first = engine.confirm()
    assert first.status is WorkflowStatus.AWAITING_TEST_CONFIRMATION
    assert patches.applied == 1
    assert tests.runs == 0
