"""Read-only bounded diff-review workflow tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from workflows import WorkflowEngine, default_registry
from workflows.models import WorkflowStatus


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    for name in ("checkpoint_policy.json", "permission_policy.json", "allowed_commands.json"):
        shutil.copy(ROOT / "config" / name, tmp_path / "config" / name)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "sample.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "sample.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)
    return tmp_path


def test_unstaged_review_is_read_only_and_payload_free(repository: Path) -> None:
    path = repository / "sample.py"
    path.write_text("value = eval(user_value)\n", encoding="utf-8")
    before = path.read_bytes()
    engine = WorkflowEngine(repository, default_registry())
    result = engine.start("review", "unstaged")
    assert result.status is WorkflowStatus.COMPLETED
    assert result.review is not None
    assert result.review.scope == "unstaged"
    assert any(item.code == "dynamic_execution" for item in result.review.findings)
    assert path.read_bytes() == before
    serialized = (engine.history_dir / f"{result.workflow_id}.json").read_text(encoding="utf-8")
    assert "eval(user_value)" not in serialized


def test_staged_review_requires_explicit_scope(repository: Path) -> None:
    path = repository / "sample.py"
    path.write_text("token = 'sentinel'\n", encoding="utf-8")
    subprocess.run(["git", "add", "sample.py"], cwd=repository, check=True)
    engine = WorkflowEngine(repository, default_registry())
    result = engine.start("review", "staged")
    assert result.review is not None
    assert result.review.scope == "staged"
    assert any(item.code == "credential_marker" for item in result.review.findings)


def test_invalid_review_scope_fails_without_file_mutation(repository: Path) -> None:
    path = repository / "sample.py"
    before = path.read_bytes()
    engine = WorkflowEngine(repository, default_registry())
    with pytest.raises(Exception):
        engine.start("review", "both")
    assert path.read_bytes() == before
