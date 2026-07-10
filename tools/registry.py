"""Registry of tools available to VEGA."""

from __future__ import annotations

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
    propose_patch,
    propose_patch_from_file,
    rollback_patch,
    show_patch,
)


TOOL_REGISTRY = {
    "list_dir": list_dir,
    "read_file": read_file,
    "find_file": find_file,
    "search_in_files": search_in_files,
    "summarize_file": summarize_file,
    "propose_patch": propose_patch,
    "propose_patch_from_file": propose_patch_from_file,
    "list_patches": list_patches,
    "show_patch": show_patch,
    "apply_patch": apply_patch,
    "rollback_patch": rollback_patch,
}


def get_tool(name: str):
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY)
