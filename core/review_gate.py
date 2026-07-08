from __future__ import annotations

from pathlib import Path
from typing import Any

from core.task_manager import VALID_STATUSES


SYSTEM_DIRS = {".git", ".agents", ".codex", "core", "config", "scripts", "data"}
DELETE_MARKERS = {"delete", "remove", "rmdir", "del ", "erase", "unlink", "rm -rf", "rd /s"}
DANGEROUS_COMMANDS = {"rm -rf", "del /f", "rmdir /s", "format ", "git reset --hard", "shutdown", "powershell -enc"}


class ReviewGate:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.root = Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()

    def review_task(self, task: dict[str, Any], changed_files: list[str] | None = None) -> dict[str, Any]:
        checks = [
            self._check_architecture(task),
            self._check_safety(task),
            self._check_files(changed_files),
        ]
        if any(check["result"] == "failed" for check in checks):
            status = "failed"
        elif any(check["result"] == "needs_manual_review" for check in checks):
            status = "needs_manual_review"
        else:
            status = "passed"
        return {
            "status": status,
            "checks": checks,
            "summary": self._summary(status),
        }

    def _check_architecture(self, task: dict[str, Any]) -> dict[str, str]:
        if not isinstance(task, dict) or not task:
            return self._check("architecture", "failed", "Task does not exist.")
        if not str(task.get("title", "")).strip():
            return self._check("architecture", "failed", "Task has no title.")
        status = task.get("status")
        if status not in VALID_STATUSES:
            return self._check("architecture", "failed", f"Unsupported task status: {status}")
        return self._check("architecture", "passed", "Task exists, has a title, and uses a supported status.")

    def _check_safety(self, task: dict[str, Any]) -> dict[str, str]:
        haystack = " ".join([
            str(task.get("title", "")),
            " ".join(str(item) for item in task.get("plan", [])),
            " ".join(str(note) for note in task.get("notes", [])),
        ]).lower()
        for command in DANGEROUS_COMMANDS:
            if command in haystack:
                return self._check("safety", "failed", f"Dangerous command marker found: {command}")
        for marker in DELETE_MARKERS:
            if marker in haystack and any(system_dir in haystack for system_dir in SYSTEM_DIRS):
                return self._check("safety", "failed", "Potential attempt to delete a system project folder.")
        return self._check("safety", "passed", "No dangerous command or system-folder deletion marker found.")

    def _check_files(self, changed_files: list[str] | None) -> dict[str, str]:
        if changed_files is None:
            return self._check("files", "needs_manual_review", "Changed files were not provided.")
        for raw_path in changed_files:
            path_text = str(raw_path).strip()
            if not path_text:
                return self._check("files", "needs_manual_review", "Changed file list contains an empty path.")
            candidate = (self.root / path_text).resolve() if not Path(path_text).is_absolute() else Path(path_text).resolve()
            try:
                candidate.relative_to(self.root)
            except ValueError:
                return self._check("files", "failed", f"Changed file is outside project: {raw_path}")
            lowered = path_text.lower()
            if any(marker in lowered for marker in DELETE_MARKERS):
                return self._check("files", "failed", f"Deletion marker found in changed file path: {raw_path}")
        return self._check("files", "passed", "Changed files stay inside the project.")

    def _summary(self, status: str) -> str:
        if status == "passed":
            return "Review passed. Task can move to waiting_review."
        if status == "needs_manual_review":
            return "Review needs manual review before completion."
        return "Review found problems. Task needs rework."

    def _check(self, name: str, result: str, details: str) -> dict[str, str]:
        return {"name": name, "result": result, "details": details}
