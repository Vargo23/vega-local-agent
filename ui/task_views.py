from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any


WRAP_WIDTH = 96


def _lines(items: list[str]) -> str:
    return "\n".join(items).rstrip()


def _wrap(prefix: str, text: Any) -> list[str]:
    value = str(text)
    width = max(30, WRAP_WIDTH - len(prefix))
    wrapped = textwrap.wrap(value, width=width) or [""]
    lines = [prefix + wrapped[0]]
    indent = " " * len(prefix)
    lines.extend(indent + part for part in wrapped[1:])
    return lines


def _step_line(step: dict[str, Any]) -> list[str]:
    marker = "x" if step.get("done") else " "
    prefix = f"[{marker}] {step.get('number', '?')}. "
    return _wrap(prefix, step.get("text", ""))


def render_current_task(task: dict[str, Any]) -> str:
    lines = [
        "# Current task",
        "",
        f"Title: {task.get('title', 'n/a')}",
        f"Status: {task.get('status', 'active')}",
        f"Created: {task.get('created_at', 'n/a')}",
        "",
        "Steps:",
    ]

    steps = task.get("steps", [])
    if steps:
        for step in steps:
            lines.extend(_step_line(step))
    else:
        lines.append("No plan yet.")

    lines.extend(["", "Notes:"])
    notes = task.get("notes", [])
    if notes:
        for note in notes:
            lines.extend(_wrap(f"{note.get('number', '?')}. ", note.get("text", "")))
    else:
        lines.append("No notes yet.")

    return _lines(lines)


def render_no_task() -> str:
    return "No active task.\nCreate one with: /task new <title>"


def render_task_created(task: dict[str, Any]) -> str:
    return _lines([
        "Task created.",
        f"Title: {task.get('title', 'n/a')}",
        f"ID: {task.get('id', 'n/a')}",
    ])


def render_task_plan(task: dict[str, Any]) -> str:
    steps = task.get("steps", [])
    if not steps:
        return "No plan yet."

    lines = [
        "# Task plan",
        "",
        f"Task: {task.get('title', 'n/a')}",
        "",
    ]
    for step in steps:
        lines.extend(_step_line(step))
    return _lines(lines)


def render_step_added(task: dict[str, Any], step: dict[str, Any]) -> str:
    return _lines([
        "Task step added.",
        f"Task: {task.get('title', 'n/a')}",
        f"Step: {step.get('number', '?')}. {step.get('text', '')}",
    ])


def render_step_completed(task: dict[str, Any], step: dict[str, Any]) -> str:
    return _lines([
        "Task step completed.",
        f"Task: {task.get('title', 'n/a')}",
        f"Step: {step.get('number', '?')}. {step.get('text', '')}",
    ])


def render_note_added(task: dict[str, Any], note: dict[str, Any]) -> str:
    return _lines([
        "Task note added.",
        f"Task: {task.get('title', 'n/a')}",
        f"Note: {note.get('number', '?')}. {note.get('text', '')}",
    ])


def render_task_review(review_data: dict[str, Any]) -> str:
    task = review_data.get("task", {})
    lines = [
        "# Review gate",
        "",
        f"Task: {task.get('title', 'n/a')}",
        f"Completed: {review_data.get('completed', 0)}/{review_data.get('total', 0)}",
        f"Status: {review_data.get('status', 'n/a')}",
    ]

    open_steps = review_data.get("open_steps", [])
    if open_steps:
        lines.extend(["", "Open steps:"])
        for step in open_steps:
            lines.extend(_step_line(step))

    return _lines(lines)


def render_task_closed(archived_path: str | Path) -> str:
    return _lines([
        "Task closed and archived.",
        f"Archive: {archived_path}",
    ])


def render_task_cleared() -> str:
    return "Task cleared."


def render_workspace(workspace_data: dict[str, Any]) -> str:
    lines = [
        "# VEGA Workspace",
        "",
        f"Version: {workspace_data.get('version', 'n/a')}",
        f"Project: {workspace_data.get('project', 'n/a')}",
        f"Model: {workspace_data.get('model', 'n/a')}",
        f"Internet: {workspace_data.get('internet', 'n/a')}",
        f"Current task: {workspace_data.get('current_task', 'none')}",
        f"Task title: {workspace_data.get('task_title', 'n/a')}",
        f"Documents index: {workspace_data.get('documents_index', 'NO')}",
        f"Documents indexed: {workspace_data.get('documents_indexed', 'n/a')}",
        f"Log file: {workspace_data.get('log_file', 'n/a')}",
    ]

    if workspace_data.get("task_error"):
        lines.append(f"Task error: {workspace_data['task_error']}")

    return _lines(lines)


def render_task_error(message: str) -> str:
    return str(message).rstrip()
