"""Automated safety checks for VEGA Patch Tools."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import core.safety as safety
import tools.patch_tools as patches


PASSED = 0


def check(condition: bool, message: str) -> None:
    global PASSED

    if not condition:
        raise AssertionError(message)

    PASSED += 1
    print(f"PASS: {message}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    original_patch_root = patches.get_project_root
    original_safety_root = safety.get_project_root

    with tempfile.TemporaryDirectory(
        prefix="vega_patch_tools_"
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)

        patches.get_project_root = lambda: temporary_root
        safety.get_project_root = lambda: temporary_root

        try:
            original_bytes = b"alpha\r\nbeta\r\n"
            proposed_bytes = b"alpha\r\nbeta changed\r\n"

            target = temporary_root / "target.txt"
            proposal = temporary_root / "proposal.txt"

            target.write_bytes(original_bytes)
            proposal.write_bytes(proposed_bytes)

            result = patches.propose_patch_from_file(
                "target.txt",
                "proposal.txt",
                "Automated Patch Tools check",
            )

            check(
                result["ok"] is True,
                "pending patch can be proposed",
            )

            patch_id = result["data"]["patch_id"]

            check(
                result["data"]["status"] == "pending",
                "new patch has pending status",
            )

            check(
                target.read_bytes() == original_bytes,
                "proposal does not change the target file",
            )

            pending_file = (
                temporary_root
                / "data"
                / "patches"
                / "pending"
                / f"{patch_id}.json"
            )

            check(
                pending_file.is_file(),
                "pending metadata file is created",
            )

            listed = patches.list_patches("pending")

            check(
                listed["ok"] is True
                and any(
                    item["patch_id"] == patch_id
                    for item in listed["data"]
                ),
                "pending patch appears in list_patches",
            )

            shown = patches.show_patch(patch_id)

            check(
                shown["ok"] is True
                and shown["data"]["status"] == "pending",
                "show_patch returns pending metadata",
            )

            check(
                "new_content" not in shown["data"],
                "show_patch does not expose stored full content",
            )

            denied_apply = patches.apply_patch(patch_id)

            check(
                denied_apply["ok"] is False
                and "confirmation" in denied_apply["error"].lower(),
                "apply without confirmation is blocked",
            )

            check(
                target.read_bytes() == original_bytes,
                "blocked apply leaves target unchanged",
            )

            applied = patches.apply_patch(
                patch_id,
                confirmed=True,
            )

            check(
                applied["ok"] is True
                and applied["data"]["status"] == "applied",
                "confirmed patch can be applied",
            )

            check(
                target.read_bytes() == proposed_bytes,
                "applied patch preserves exact CRLF bytes",
            )

            backup_file = (
                temporary_root
                / applied["data"]["backup_path"]
            )

            check(
                backup_file.is_file()
                and backup_file.read_bytes() == original_bytes,
                "backup contains exact original bytes",
            )

            applied_file = (
                temporary_root
                / "data"
                / "patches"
                / "applied"
                / f"{patch_id}.json"
            )

            check(
                applied_file.is_file()
                and not pending_file.exists(),
                "metadata moves from pending to applied",
            )

            denied_rollback = patches.rollback_patch(patch_id)

            check(
                denied_rollback["ok"] is False
                and "confirmation" in denied_rollback["error"].lower(),
                "rollback without confirmation is blocked",
            )

            rolled_back = patches.rollback_patch(
                patch_id,
                confirmed=True,
            )

            check(
                rolled_back["ok"] is True
                and rolled_back["data"]["status"] == "rolled_back",
                "confirmed rollback succeeds",
            )

            check(
                target.read_bytes() == original_bytes,
                "rollback restores exact original bytes",
            )

            check(
                sha256(target.read_bytes())
                == sha256(original_bytes),
                "rollback restores original SHA-256",
            )

            rolled_back_list = patches.list_patches(
                "rolled_back"
            )

            check(
                rolled_back_list["ok"] is True
                and any(
                    item["patch_id"] == patch_id
                    for item in rolled_back_list["data"]
                ),
                "rolled-back patch appears in filtered list",
            )

            history_file = (
                temporary_root
                / "data"
                / "patches"
                / "history.json"
            )

            history = json.loads(
                history_file.read_text(encoding="utf-8")
            )

            check(
                [entry["action"] for entry in history]
                == ["applied", "rolled_back"],
                "history records apply and rollback",
            )

            target.write_bytes(original_bytes)
            proposal.write_bytes(proposed_bytes)

            stale_result = patches.propose_patch_from_file(
                "target.txt",
                "proposal.txt",
                "Stale patch check",
            )

            check(
                stale_result["ok"] is True,
                "second patch can be proposed for stale check",
            )

            stale_patch_id = stale_result["data"]["patch_id"]
            later_user_bytes = b"user changed this file\r\n"
            target.write_bytes(later_user_bytes)

            stale_apply = patches.apply_patch(
                stale_patch_id,
                confirmed=True,
            )

            check(
                stale_apply["ok"] is False
                and "changed after" in stale_apply["error"].lower(),
                "stale patch application is blocked",
            )

            check(
                target.read_bytes() == later_user_bytes,
                "stale patch does not overwrite later user changes",
            )

            traversal = patches.propose_patch(
                "../outside.txt",
                "blocked",
            )

            check(
                traversal["ok"] is False,
                "parent-directory traversal is blocked",
            )

            sensitive = temporary_root / ".env"
            sensitive.write_text(
                "TOKEN=test\n",
                encoding="utf-8",
            )

            sensitive_result = patches.propose_patch(
                ".env",
                "TOKEN=changed\n",
            )

            check(
                sensitive_result["ok"] is False
                and "sensitive" in sensitive_result["error"].lower(),
                "sensitive files cannot be patched",
            )

            same_file = patches.propose_patch_from_file(
                "target.txt",
                "target.txt",
            )

            check(
                same_file["ok"] is False,
                "target and proposal cannot be the same file",
            )

        finally:
            patches.get_project_root = original_patch_root
            safety.get_project_root = original_safety_root

    print()
    print(f"PASS: Patch Tools checks completed ({PASSED} checks)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1) from exc
