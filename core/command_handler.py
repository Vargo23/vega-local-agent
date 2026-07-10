"""Command handlers shared by the VEGA CLI."""

from __future__ import annotations

import json
import shlex

from tools.file_tools import (
    find_file,
    list_dir,
    read_file,
    search_in_files,
    summarize_file,
)
from tools.patch_tools import (
    apply_patch,
    list_patches,
    propose_patch_from_file,
    rollback_patch,
    show_patch,
)


FILE_HELP = """File commands (safe read-only access):
  /file list <path>       List a project directory
  /file read <path>       Read a UTF-8 text file
  /file find <name>       Find files by name
  /file search <query>    Search text in project files
  /file summary <path>    Show a deterministic file summary"""


PATCH_HELP = """Patch commands (confirmed safe writes):
  /patch list                         List all saved patches
  /patch list pending                 List pending patches
  /patch list applied                 List applied patches
  /patch list rolled_back             List rolled-back patches
  /patch show <patch_id>              Show patch metadata and diff
  /patch propose <target> <proposal>  Propose target content from another file
  /patch apply <patch_id> CONFIRM     Apply a pending patch
  /patch rollback <patch_id> CONFIRM  Roll back an applied patch

Examples:
  /patch propose README.md README.proposal.md "Update documentation"
  /patch show patch-20260710T150136Z-6ba02018
  /patch apply patch-20260710T150136Z-6ba02018 CONFIRM"""


def _clean_cli_token(value: str) -> str:
    return value.strip().strip('"').strip("'")


def handle_file_command(command: str) -> str:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        return f"File command error: {exc}"

    if len(parts) == 1:
        return FILE_HELP

    action = _clean_cli_token(parts[1]).lower()
    argument = " ".join(parts[2:]).strip().strip('"')

    if action == "list":
        result = list_dir(argument or ".")
    elif action == "read" and argument:
        result = read_file(argument)
    elif action == "find" and argument:
        result = find_file(argument)
    elif action == "search" and argument:
        result = search_in_files(argument)
    elif action in {"summary", "summarize"} and argument:
        result = summarize_file(argument)
    else:
        return FILE_HELP

    if not result["ok"]:
        return f"File command error: {result['error']}"

    return json.dumps(
        result["data"],
        ensure_ascii=False,
        indent=2,
    )


def handle_patch_command(command: str) -> str:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        return f"Patch command error: {exc}"

    if len(parts) == 1:
        return PATCH_HELP

    action = _clean_cli_token(parts[1]).lower()

    if action == "list":
        if len(parts) > 3:
            return PATCH_HELP

        status = None
        if len(parts) == 3:
            status = _clean_cli_token(parts[2]).lower()

        result = list_patches(status)

    elif action == "show" and len(parts) == 3:
        patch_id = _clean_cli_token(parts[2])
        result = show_patch(patch_id)

    elif action == "propose" and len(parts) >= 4:
        target_path = _clean_cli_token(parts[2])
        proposal_path = _clean_cli_token(parts[3])

        reason = " ".join(
            _clean_cli_token(part)
            for part in parts[4:]
        ).strip()

        result = propose_patch_from_file(
            target_path,
            proposal_path,
            reason,
        )

    elif action == "apply" and len(parts) in {3, 4}:
        patch_id = _clean_cli_token(parts[2])

        confirmed = (
            len(parts) == 4
            and _clean_cli_token(parts[3]) == "CONFIRM"
        )

        result = apply_patch(
            patch_id,
            confirmed=confirmed,
        )

    elif action == "rollback" and len(parts) in {3, 4}:
        patch_id = _clean_cli_token(parts[2])

        confirmed = (
            len(parts) == 4
            and _clean_cli_token(parts[3]) == "CONFIRM"
        )

        result = rollback_patch(
            patch_id,
            confirmed=confirmed,
        )

    else:
        return PATCH_HELP

    if not result["ok"]:
        return f"Patch command error: {result['error']}"

    return json.dumps(
        result["data"],
        ensure_ascii=False,
        indent=2,
    )


def tools_list_text() -> str:
    from tools.registry import list_tools

    return "Available tools:\n" + "\n".join(
        f"  {name}"
        for name in list_tools()
    )
