"""Registry of tools available to VEGA."""

from __future__ import annotations

from tools.file_tools import find_file, list_dir, read_file, search_in_files, summarize_file


TOOL_REGISTRY = {
    "list_dir": list_dir,
    "read_file": read_file,
    "find_file": find_file,
    "search_in_files": search_in_files,
    "summarize_file": summarize_file,
}


def get_tool(name: str):
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY)
