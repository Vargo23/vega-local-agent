"""Checkpoint integration for schema-2 controlled workflow state."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from workflows import CheckpointStore, WorkflowEngine, default_registry
from workflows.checkpoint_models import CheckpointReason
from workflows.models import WorkflowStatus


ROOT = Path(__file__).resolve().parents[1]


class Patch:
    status = "pending"

    def prepare_safe(self, patch_id: str) -> dict[str, str]:
        return {
            "patch_id": patch_id,
            "status": self.status,
            "target_path": "sample.py",
            "original_sha256": hashlib.sha256(b"old").hexdigest(),
            "proposed_sha256": hashlib.sha256(b"new").hexdigest(),
        }

    def apply(self, patch_id: str, confirmed: bool = False) -> dict[str, object]:
        assert confirmed
        self.status = "applied"
        return {"ok": True, "data": {"patch_id": patch_id, "status": "applied", "target_path": "sample.py"}}


class Tests:
    def resolve(self, group_id: str) -> dict[str, str]:
        return {"group_id": group_id, "command_id": "tests-workflow"}

    def run_group(self, group_id: str) -> dict[str, object]:
        return {"passed": True, "returncode": 0, "timed_out": False, "duration_ms": 1, "outcome_code": "passed"}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(ROOT / "config" / name, tmp_path / "config" / name)
    (tmp_path / "sample.py").write_text("old\n", encoding="utf-8")
    return tmp_path


def test_checkpoint_sequence_covers_both_confirmation_boundaries(root: Path) -> None:
    engine = WorkflowEngine(root, default_registry(), patch_tools=Patch(), test_tools=Tests())
    run = engine.start("bug-fix", "Fix parser", patch_id="patch-1")
    engine.approve_patch(run.workflow_id)
    completed = engine.approve_tests(run.workflow_id)
    checkpoints = CheckpointStore(root).list_for_workflow(run.workflow_id, include_history=True)
    statuses = [item.workflow_status for item in checkpoints]
    reasons = [item.reason for item in checkpoints]
    assert statuses[0] is WorkflowStatus.PLANNED
    assert WorkflowStatus.WAITING_PATCH in statuses
    assert WorkflowStatus.AWAITING_PATCH_CONFIRMATION in statuses
    assert WorkflowStatus.AWAITING_TEST_CONFIRMATION in statuses
    assert WorkflowStatus.TESTS_RUNNING in statuses
    assert statuses[-1] is WorkflowStatus.COMPLETED
    assert CheckpointReason.BEFORE_PATCH_APPLY in reasons
    assert CheckpointReason.AFTER_PATCH_APPLY in reasons
    assert CheckpointReason.VERIFICATION_RECORDED in reasons
    assert completed.status is WorkflowStatus.COMPLETED


def test_checkpoint_payload_is_schema_two_and_contains_no_raw_payloads(root: Path) -> None:
    engine = WorkflowEngine(root, default_registry(), patch_tools=Patch(), test_tools=Tests())
    run = engine.start("bug-fix", "SECRET-SENTINEL task")
    checkpoint = CheckpointStore(root).latest(run.workflow_id)
    assert checkpoint is not None
    payload = checkpoint.workflow_payload
    assert payload["schema_version"] == 2
    rendered = str(payload)
    assert "SECRET-SENTINEL" not in rendered
    assert "stdout" not in rendered and "stderr" not in rendered


def test_completed_checkpoint_history_remains_integrity_verified(root: Path) -> None:
    engine = WorkflowEngine(root, default_registry(), patch_tools=Patch(), test_tools=Tests())
    run = engine.start("test", "workflow")
    engine.approve_tests(run.workflow_id)
    store = CheckpointStore(root)
    checkpoints = store.list_for_workflow(run.workflow_id, include_history=True)
    assert checkpoints
    for checkpoint in checkpoints:
        checkpoint.verify_integrity()
