"""Read-only release readiness checks for VEGA."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.doc_tools import check_documentation
from tools.git_tools import git_branch, git_status
from tools.terminal_tools import run_allowed_command


POLICY_RELATIVE_PATH = Path("config/release_policy.json")
VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
VERSION_ASSIGNMENT_PATTERN = re.compile(
    r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']\s*$',
    re.MULTILINE,
)
COMMAND_ID_PATTERN = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
)

BLOCKED_PATH_PARTS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
    }
)


class ReleasePolicyError(ValueError):
    """Raised when Release Manager policy is invalid."""


def _result(
    data: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": error is None,
        "error": error,
        "data": data if error is None else None,
    }


def _resolve_root(
    project_root: Path | str | None = None,
) -> Path:
    if project_root is None:
        return Path.cwd().resolve()

    return Path(project_root).resolve()


def _normalize_relative_path(
    root: Path,
    raw_path: Any,
    field_name: str,
) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ReleasePolicyError(
            f"{field_name} must be a non-empty relative path."
        )

    relative = Path(raw_path.strip())

    if relative.is_absolute():
        raise ReleasePolicyError(
            f"{field_name} cannot be absolute."
        )

    if ".." in relative.parts:
        raise ReleasePolicyError(
            f"{field_name} cannot contain parent traversal."
        )

    if any(
        part.lower() in BLOCKED_PATH_PARTS
        for part in relative.parts
    ):
        raise ReleasePolicyError(
            f"{field_name} contains a blocked directory."
        )

    resolved = (root / relative).resolve(strict=False)

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReleasePolicyError(
            f"{field_name} escapes the project root."
        ) from exc

    return relative.as_posix()


def _require_string_list(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        raise ReleasePolicyError(
            f"{field_name} must be a list."
        )

    normalized: list[str] = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ReleasePolicyError(
                f"{field_name} must contain non-empty strings."
            )
        normalized.append(item.strip())

    if not allow_empty and not normalized:
        raise ReleasePolicyError(
            f"{field_name} cannot be empty."
        )

    if len(normalized) != len(set(normalized)):
        raise ReleasePolicyError(
            f"{field_name} cannot contain duplicates."
        )

    return normalized


def _validate_policy(
    root: Path,
    raw_policy: Any,
) -> dict[str, Any]:
    if not isinstance(raw_policy, dict):
        raise ReleasePolicyError(
            "Release policy must be a JSON object."
        )

    if raw_policy.get("schema_version") != 1:
        raise ReleasePolicyError(
            "Unsupported release policy schema version."
        )

    required_raw = raw_policy.get("required_files")
    if not isinstance(required_raw, list) or not required_raw:
        raise ReleasePolicyError(
            "required_files must be a non-empty list."
        )

    required_files = [
        _normalize_relative_path(
            root,
            path,
            f"required_files[{index}]",
        )
        for index, path in enumerate(required_raw)
    ]

    if len(required_files) != len(set(required_files)):
        raise ReleasePolicyError(
            "required_files cannot contain duplicates."
        )

    branch_policy = raw_policy.get("branch_policy")
    if not isinstance(branch_policy, dict):
        raise ReleasePolicyError(
            "branch_policy must be an object."
        )

    allowed_check_branches = _require_string_list(
        branch_policy.get("allowed_check_branches"),
        "branch_policy.allowed_check_branches",
    )
    allowed_check_prefixes = _require_string_list(
        branch_policy.get("allowed_check_prefixes"),
        "branch_policy.allowed_check_prefixes",
        allow_empty=True,
    )

    publish_branch = branch_policy.get("publish_branch")
    if not isinstance(publish_branch, str) or not publish_branch.strip():
        raise ReleasePolicyError(
            "branch_policy.publish_branch must be a string."
        )
    publish_branch = publish_branch.strip()

    checks = raw_policy.get("checks")
    if not isinstance(checks, dict):
        raise ReleasePolicyError(
            "checks must be an object."
        )

    documentation_required = checks.get("documentation")
    if not isinstance(documentation_required, bool):
        raise ReleasePolicyError(
            "checks.documentation must be true or false."
        )

    command_ids = _require_string_list(
        checks.get("commands"),
        "checks.commands",
    )

    if not all(
        COMMAND_ID_PATTERN.fullmatch(command_id)
        for command_id in command_ids
    ):
        raise ReleasePolicyError(
            "checks.commands contains an invalid command id."
        )

    notes = raw_policy.get("notes")
    if not isinstance(notes, dict):
        raise ReleasePolicyError(
            "notes must be an object."
        )

    notes_source = _normalize_relative_path(
        root,
        notes.get("source"),
        "notes.source",
    )
    notes_output_dir = _normalize_relative_path(
        root,
        notes.get("output_dir"),
        "notes.output_dir",
    )

    max_chars = notes.get("max_chars")
    if (
        not isinstance(max_chars, int)
        or isinstance(max_chars, bool)
        or max_chars < 100
    ):
        raise ReleasePolicyError(
            "notes.max_chars must be an integer of at least 100."
        )

    publishing = raw_policy.get("publishing")
    if not isinstance(publishing, dict):
        raise ReleasePolicyError(
            "publishing must be an object."
        )

    publishing_keys = (
        "allow_commit",
        "allow_tag",
        "allow_push",
        "allow_github_release",
    )

    normalized_publishing: dict[str, bool] = {}

    for key in publishing_keys:
        value = publishing.get(key)

        if not isinstance(value, bool):
            raise ReleasePolicyError(
                f"publishing.{key} must be true or false."
            )

        if value:
            raise ReleasePolicyError(
                f"Automatic publishing is forbidden: {key}."
            )

        normalized_publishing[key] = value

    return {
        "schema_version": 1,
        "required_files": required_files,
        "branch_policy": {
            "allowed_check_branches": allowed_check_branches,
            "allowed_check_prefixes": allowed_check_prefixes,
            "publish_branch": publish_branch,
        },
        "checks": {
            "documentation": documentation_required,
            "commands": command_ids,
        },
        "notes": {
            "source": notes_source,
            "output_dir": notes_output_dir,
            "max_chars": max_chars,
        },
        "publishing": normalized_publishing,
    }


def _load_policy(root: Path) -> dict[str, Any]:
    policy_path = root / POLICY_RELATIVE_PATH

    if not policy_path.is_file():
        raise ReleasePolicyError(
            "Release policy does not exist: "
            f"{POLICY_RELATIVE_PATH.as_posix()}"
        )

    try:
        raw_policy = json.loads(
            policy_path.read_text(encoding="utf-8-sig")
        )
    except json.JSONDecodeError as exc:
        raise ReleasePolicyError(
            f"Release policy contains invalid JSON: {exc}"
        ) from exc
    except OSError as exc:
        raise ReleasePolicyError(
            "Release policy could not be read."
        ) from exc

    return _validate_policy(root, raw_policy)


def _read_version(root: Path) -> str:
    version_path = root / "scripts" / "version.py"

    if not version_path.is_file():
        raise ReleasePolicyError(
            "Version file does not exist: scripts/version.py"
        )

    text = version_path.read_text(
        encoding="utf-8-sig"
    )
    match = VERSION_ASSIGNMENT_PATTERN.search(text)

    if match is None:
        raise ReleasePolicyError(
            "VERSION was not found in scripts/version.py."
        )

    return match.group(1)


def _branch_is_allowed(
    branch: str,
    branch_policy: dict[str, Any],
) -> bool:
    if branch in branch_policy["allowed_check_branches"]:
        return True

    return any(
        branch.startswith(prefix)
        for prefix in branch_policy["allowed_check_prefixes"]
    )


def load_release_policy(
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Load and validate the Release Manager policy."""

    try:
        root = _resolve_root(project_root)
        policy = _load_policy(root)

        return _result(
            {
                "path": POLICY_RELATIVE_PATH.as_posix(),
                "policy": policy,
            }
        )
    except (
        OSError,
        ReleasePolicyError,
        ValueError,
    ) as exc:
        return _result(error=str(exc))


def get_release_status(
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Return release readiness without running validation commands."""

    try:
        root = _resolve_root(project_root)
        policy = _load_policy(root)
        version = _read_version(root)

        branch_result = git_branch(root)
        if not branch_result.ok:
            raise ReleasePolicyError(
                branch_result.stderr
                or "Current Git branch could not be read."
            )

        status_result = git_status(root)
        if not status_result.ok:
            raise ReleasePolicyError(
                status_result.stderr
                or "Git working tree status could not be read."
            )

        branch = branch_result.stdout.strip()
        git_clean = not status_result.stdout.strip()
        version_valid = bool(
            VERSION_PATTERN.fullmatch(version)
        )

        required_files = []
        missing_files = []

        for relative_path in policy["required_files"]:
            exists = (root / relative_path).is_file()
            item = {
                "path": relative_path,
                "exists": exists,
            }
            required_files.append(item)

            if not exists:
                missing_files.append(relative_path)

        documentation_result = check_documentation(root)
        documentation_passed = bool(
            documentation_result["ok"]
            and documentation_result["data"]
            and documentation_result["data"].get("passed")
        )

        branch_allowed = _branch_is_allowed(
            branch,
            policy["branch_policy"],
        )
        publish_branch_match = (
            branch
            == policy["branch_policy"]["publish_branch"]
        )

        issues: list[str] = []

        if not version_valid:
            issues.append(
                f"Invalid release version: {version}"
            )

        if not branch_allowed:
            issues.append(
                f"Branch is not allowed for release checks: {branch}"
            )

        if not git_clean:
            issues.append(
                "Git working tree is not clean."
            )

        for path in missing_files:
            issues.append(
                f"Required release file is missing: {path}"
            )

        if (
            policy["checks"]["documentation"]
            and not documentation_passed
        ):
            issues.append(
                "Documentation checks did not pass."
            )

        preparation_ready = not issues
        publish_ready = (
            preparation_ready
            and publish_branch_match
        )

        return _result(
            {
                "version": version,
                "version_valid": version_valid,
                "branch": branch,
                "branch_allowed": branch_allowed,
                "publish_branch": (
                    policy["branch_policy"]["publish_branch"]
                ),
                "publish_branch_match": publish_branch_match,
                "git_clean": git_clean,
                "required_files": required_files,
                "missing_files": missing_files,
                "documentation_passed": documentation_passed,
                "documentation": documentation_result,
                "preparation_ready": preparation_ready,
                "publish_ready": publish_ready,
                "issues": issues,
            }
        )
    except (
        OSError,
        ReleasePolicyError,
        ValueError,
    ) as exc:
        return _result(error=str(exc))


def run_release_check(
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Run the configured read-only release validation commands."""

    root = _resolve_root(project_root)
    status_result = get_release_status(root)

    if not status_result["ok"]:
        return status_result

    try:
        policy = _load_policy(root)
    except (
        OSError,
        ReleasePolicyError,
        ValueError,
    ) as exc:
        return _result(error=str(exc))

    command_results = []

    for command_id in policy["checks"]["commands"]:
        command_result = run_allowed_command(
            command_id,
            root,
        )
        data = command_result.get("data")

        passed = bool(
            command_result.get("ok")
            and data is not None
            and data.get("returncode") == 0
        )

        command_results.append(
            {
                "command_id": command_id,
                "passed": passed,
                "returncode": (
                    data.get("returncode")
                    if data is not None
                    else None
                ),
                "duration_ms": (
                    data.get("duration_ms")
                    if data is not None
                    else None
                ),
                "error": command_result.get("error"),
            }
        )

    commands_passed = all(
        item["passed"]
        for item in command_results
    )
    preparation_passed = bool(
        status_result["data"]["preparation_ready"]
        and commands_passed
    )

    return _result(
        {
            "status": status_result["data"],
            "commands": command_results,
            "commands_passed": commands_passed,
            "passed": preparation_passed,
            "publish_ready": bool(
                preparation_passed
                and status_result["data"][
                    "publish_branch_match"
                ]
            ),
        }
    )


def build_release_notes(
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Build an in-memory release-notes draft from CHANGELOG."""

    try:
        root = _resolve_root(project_root)
        policy = _load_policy(root)
        version = _read_version(root)

        source_path = (
            root / policy["notes"]["source"]
        )

        if not source_path.is_file():
            raise ReleasePolicyError(
                "Release notes source does not exist: "
                f"{policy['notes']['source']}"
            )

        changelog = source_path.read_text(
            encoding="utf-8-sig"
        )

        header_pattern = re.compile(
            rf"^##\s+{re.escape(version)}(?:\s+-.*)?$",
            re.MULTILINE,
        )
        header_match = header_pattern.search(changelog)

        if header_match is None:
            raise ReleasePolicyError(
                f"CHANGELOG section was not found for {version}."
            )

        next_header = re.search(
            r"^##\s+",
            changelog[header_match.end():],
            re.MULTILINE,
        )

        if next_header is None:
            section_end = len(changelog)
        else:
            section_end = (
                header_match.end()
                + next_header.start()
            )

        section = changelog[
            header_match.start():section_end
        ].strip()

        draft = (
            f"# VEGA {version} Release Notes\n\n"
            f"{section}\n"
        )

        if len(draft) > policy["notes"]["max_chars"]:
            raise ReleasePolicyError(
                "Generated release notes exceed the policy limit."
            )

        suggested_path = (
            Path(policy["notes"]["output_dir"])
            / f"{version}.md"
        ).as_posix()

        return _result(
            {
                "version": version,
                "source": policy["notes"]["source"],
                "suggested_path": suggested_path,
                "draft": draft,
                "written": False,
            }
        )
    except (
        OSError,
        ReleasePolicyError,
        ValueError,
    ) as exc:
        return _result(error=str(exc))


__all__ = [
    "ReleasePolicyError",
    "build_release_notes",
    "get_release_status",
    "load_release_policy",
    "run_release_check",
]
