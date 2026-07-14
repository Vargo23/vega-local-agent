from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from workflows.controlled_models import (
    ControlledWorkflowState,
    ControlledWorkflowValidationError,
    PatchEvidence,
)
from workflows.controlled_store import (
    ControlledStoreConflict,
    ControlledStoreError,
    ControlledWorkflowStore,
    MAX_WORKFLOW_STATE_BYTES,
)
from workflows.models import WorkflowRun, WorkflowStatus


def digest(character: str) -> str:
    return character * 64


@pytest.mark.parametrize(
    "target",
    (
        "../escape.py",
        "C:/escape.py",
        "/etc/passwd",
        ".git/config",
        "data/workflows/active.json",
        ".venv/file.py",
        "venv/file.py",
        "node_modules/file.js",
        "cache/../escape.py",
    ),
)
def test_patch_evidence_rejects_unsafe_paths(target: str) -> None:
    with pytest.raises(ControlledWorkflowValidationError):
        PatchEvidence("patch-1", digest("a"), target, digest("b"), digest("c"), "pending")


def test_models_are_frozen_slotted_and_manual_serialization(tmp_path: Path) -> None:
    state = ControlledWorkflowState.create("bug-fix", "secret task", digest("a"))
    assert not hasattr(state, "__dict__")
    with pytest.raises(Exception):
        state.revision = 99
    source = (Path(__file__).resolve().parents[1] / "workflows" / "controlled_models.py").read_text(encoding="utf-8")
    assert "asdict" not in source
    assert "vars(" not in source
    assert "__dict__" not in source


def test_corrupt_unknown_and_oversized_state_fail_closed(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    corrupt = store.active_dir / f"workflow-{'1' * 32}.json"
    corrupt.write_text("{", encoding="utf-8")
    with pytest.raises(ControlledStoreError):
        store.load_active()
    corrupt.write_text(json.dumps({"schema_version": 2, "unknown": True}), encoding="utf-8")
    with pytest.raises(ControlledStoreError):
        store.load_active()
    corrupt.write_bytes(b"x" * (MAX_WORKFLOW_STATE_BYTES + 1))
    with pytest.raises(ControlledStoreError):
        store.load_active()


def test_interrupted_temporary_state_is_ignored(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    temporary = store.active_dir / f".workflow-{'1' * 32}.{'2' * 32}.tmp"
    temporary.write_text("{partial", encoding="utf-8")
    assert store.load_active() is None
    assert temporary.read_text(encoding="utf-8") == "{partial"


def test_unknown_json_filename_fails_closed(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    (store.active_dir / "unmanaged.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ControlledStoreError, match="state_invalid"):
        store.load_active()


def test_parallel_reads_observe_only_complete_state(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    state = ControlledWorkflowState.create("feature", "task", digest("a"))
    with store.mutation():
        store.save_active(state)

    with ThreadPoolExecutor(max_workers=8) as pool:
        observed = list(pool.map(lambda _: ControlledWorkflowStore(tmp_path).load_active(), range(64)))

    assert observed == [state] * 64


def test_concurrent_mutation_times_out_without_writing(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path, lock_timeout_ms=100)
    contender = ControlledWorkflowStore(tmp_path, lock_timeout_ms=0)

    def attempt() -> str:
        try:
            with contender.mutation():
                raise AssertionError("contender unexpectedly acquired the lock")
        except ControlledStoreConflict as exc:
            return exc.code

    with store.mutation(), ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(attempt).result(timeout=2) == "lock_timeout"
    assert list(store.active_dir.glob("*.json")) == []


def test_replace_failure_preserves_previous_complete_state(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    state = ControlledWorkflowState.create("feature", "task", digest("a"))
    store.save_active(state)
    before = (store.active_dir / f"{state.workflow_id}.json").read_bytes()

    with patch("workflows.controlled_store.os.replace", side_effect=OSError("injected")):
        with pytest.raises(ControlledStoreError, match="state_write_failed"):
            store.save_active(state.evolve(next_actions=("cancel", "show")))

    assert (store.active_dir / f"{state.workflow_id}.json").read_bytes() == before
    assert list(store.active_dir.glob("*.tmp")) == []


def test_symlinked_state_file_fails_closed(tmp_path: Path) -> None:
    store = ControlledWorkflowStore(tmp_path)
    target = tmp_path / "outside.json"
    state = ControlledWorkflowState.create("feature", "task", digest("a"))
    target.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    link = store.active_dir / f"{state.workflow_id}.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(ControlledStoreError, match="state_incompatible"):
        store.load_active()


def test_legacy_state_migration_strips_raw_task_on_resume(tmp_path: Path) -> None:
    import shutil

    from workflows import WorkflowEngine, default_registry

    config = tmp_path / "config"
    config.mkdir()
    root = Path(__file__).resolve().parents[1]
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(root / "config" / name, config / name)
    legacy = WorkflowRun.create("feature", "TOP-SECRET-LEGACY-TASK", [])
    legacy.status = WorkflowStatus.WAITING_PATCH
    store = ControlledWorkflowStore(tmp_path)
    path = store.active_dir / f"{legacy.workflow_id}.json"
    path.write_text(json.dumps(legacy.to_dict()), encoding="utf-8")

    resumed = WorkflowEngine(tmp_path, default_registry()).resume(legacy.workflow_id)

    rendered = path.read_text(encoding="utf-8")
    assert resumed.status is WorkflowStatus.WAITING_PATCH
    assert resumed.migrated_from_schema == 1
    assert '"schema_version":2' in rendered.replace(" ", "")
    assert "TOP-SECRET-LEGACY-TASK" not in rendered


def test_ambiguous_legacy_state_is_archived_failed_without_execution(tmp_path: Path) -> None:
    import shutil

    from workflows import WorkflowEngine, default_registry

    config = tmp_path / "config"
    config.mkdir()
    root = Path(__file__).resolve().parents[1]
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(root / "config" / name, config / name)
    legacy = WorkflowRun.create("bugfix", "TOP-SECRET-AMBIGUOUS", [])
    legacy.status = WorkflowStatus.WAITING_CONFIRMATION
    store = ControlledWorkflowStore(tmp_path)
    active = store.active_dir / f"{legacy.workflow_id}.json"
    active.write_text(json.dumps(legacy.to_dict()), encoding="utf-8")

    result = WorkflowEngine(tmp_path, default_registry()).resume(legacy.workflow_id)

    history = store.history_dir / active.name
    assert result.status is WorkflowStatus.FAILED
    assert result.error_codes == ("state_incompatible",)
    assert not active.exists()
    assert "TOP-SECRET-AMBIGUOUS" not in history.read_text(encoding="utf-8")
