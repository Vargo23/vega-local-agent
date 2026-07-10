"""Safe, read-only file inspection tools for VEGA."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from core.safety import (
    DEFAULT_MAX_CHARS,
    FileSafetyError,
    get_project_root,
    is_blocked_directory,
    is_sensitive_file,
    read_text,
    safe_path,
    validate_readable_file,
)


def _result(data: Any = None, error: str | None = None) -> dict:
    return {"ok": error is None, "error": error, "data": data if error is None else None}


def _relative(path: Path) -> str:
    value = path.relative_to(get_project_root()).as_posix()
    return value or "."


def _walk(start: Path):
    for current, directories, files in os.walk(start, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if not is_blocked_directory(name) and not (Path(current) / name).is_symlink()
        )
        yield Path(current), sorted(files)


def list_dir(path: str = ".") -> dict:
    try:
        directory = safe_path(path)
        if not directory.is_dir():
            raise FileSafetyError(f"Not a directory: {path}")
        items = []
        for item in sorted(directory.iterdir(), key=lambda value: (not value.is_dir(), value.name.lower())):
            if item.is_symlink() or (item.is_dir() and is_blocked_directory(item.name)):
                continue
            if item.is_file() and is_sensitive_file(item):
                continue
            entry = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
            if item.is_file():
                entry["size"] = item.stat().st_size
            items.append(entry)
        return _result({"path": _relative(directory), "items": items})
    except (FileSafetyError, OSError) as exc:
        return _result(error=str(exc))


def read_file(path: str, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    try:
        file_path = validate_readable_file(path)
        text, truncated = read_text(file_path, max_chars)
        return _result({
            "path": _relative(file_path), "size": file_path.stat().st_size,
            "truncated": truncated, "text": text,
        })
    except (FileSafetyError, OSError) as exc:
        return _result(error=str(exc))


def find_file(name: str, path: str = ".") -> dict:
    try:
        if not isinstance(name, str) or not name.strip() or Path(name).name != name:
            raise FileSafetyError("File name must be a plain, non-empty name.")
        start = safe_path(path)
        if not start.is_dir():
            raise FileSafetyError(f"Not a directory: {path}")
        matches = []
        for current, files in _walk(start):
            for filename in files:
                candidate = current / filename
                if candidate.is_symlink() or is_sensitive_file(candidate):
                    continue
                if filename.lower() == name.lower():
                    matches.append(_relative(candidate))
        return _result(matches)
    except (FileSafetyError, OSError) as exc:
        return _result(error=str(exc))


def search_in_files(query: str, path: str = ".", max_results: int = 20) -> dict:
    try:
        if not isinstance(query, str) or not query:
            raise FileSafetyError("Search query must not be empty.")
        if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
            raise FileSafetyError("max_results must be a positive integer.")
        start = safe_path(path)
        if not start.is_dir():
            raise FileSafetyError(f"Not a directory: {path}")
        results = []
        needle = query.casefold()
        for current, files in _walk(start):
            for filename in files:
                candidate = current / filename
                if candidate.is_symlink() or is_sensitive_file(candidate):
                    continue
                try:
                    safe_candidate = validate_readable_file(_relative(candidate))
                    text, _ = read_text(safe_candidate, 1_000_000)
                except (FileSafetyError, OSError):
                    continue
                for line_number, line in enumerate(text.splitlines(), 1):
                    if needle in line.casefold():
                        results.append({"path": _relative(candidate), "line": line_number, "text": line})
                        if len(results) >= max_results:
                            return _result(results)
        return _result(results)
    except (FileSafetyError, OSError) as exc:
        return _result(error=str(exc))


def summarize_file(path: str, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    result = read_file(path, max_chars)
    if not result["ok"]:
        return result
    source = result["data"]
    text = source["text"]
    lines = text.splitlines()
    meaningful = [line.strip() for line in lines if line.strip()][:10]
    symbols = []
    if Path(source["path"]).suffix.lower() == ".py":
        pattern = re.compile(r"^\s*(?:async\s+)?(class|def)\s+([A-Za-z_]\w*)", re.MULTILINE)
        symbols = [{"type": kind, "name": name} for kind, name in pattern.findall(text)]
    return _result({
        "path": source["path"], "size": source["size"], "lines": len(lines),
        "truncated": source["truncated"], "first_meaningful_lines": meaningful,
        "python_symbols": symbols,
    })
