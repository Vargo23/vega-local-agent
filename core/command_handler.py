"""Command handlers shared by the VEGA CLI."""

from __future__ import annotations

import json
import shlex

from tools.file_tools import find_file, list_dir, read_file, search_in_files, summarize_file


FILE_HELP = """File commands (safe read-only access):
  /file list <path>       List a project directory
  /file read <path>       Read a UTF-8 text file
  /file find <name>       Find files by name
  /file search <query>    Search text in project files
  /file summary <path>    Show a deterministic file summary"""


def handle_file_command(command: str) -> str:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        return f"File command error: {exc}"
    if len(parts) == 1:
        return FILE_HELP
    action = parts[1].lower()
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
    return json.dumps(result["data"], ensure_ascii=False, indent=2)


def tools_list_text() -> str:
    from tools.registry import list_tools
    return "Available tools:\n" + "\n".join(f"  {name}" for name in list_tools())
