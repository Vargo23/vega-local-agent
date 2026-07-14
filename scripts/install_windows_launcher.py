#!/usr/bin/env python3
"""Install the user-level Windows ``vega`` command for this checkout."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class InstallResult:
    project_root: Path
    launcher_path: Path
    action: str
    backup_path: Path | None
    path_changed: bool


def render_wrapper(project_root: Path) -> str:
    """Return a minimal wrapper that delegates only to ``project_root``."""

    root = str(project_root.resolve())
    if '"' in root or "\r" in root or "\n" in root:
        raise ValueError("The VEGA project path contains unsupported characters")
    return "\r\n".join(
        (
            "@echo off",
            "setlocal EnableExtensions DisableDelayedExpansion",
            "chcp 65001 > nul",
            f'set "VEGA_PROJECT={root}"',
            'set "VEGA_GLOBAL_LAUNCHER=%~f0"',
            'if not exist "%VEGA_PROJECT%\\vega.cmd" (',
            '    >&2 echo VEGA project launcher was not found: "%VEGA_PROJECT%\\vega.cmd"',
            "    exit /b 1",
            ")",
            'pushd "%VEGA_PROJECT%" > nul || (',
            '    >&2 echo VEGA project root could not be opened: "%VEGA_PROJECT%"',
            "    exit /b 1",
            ")",
            'call "%VEGA_PROJECT%\\vega.cmd" %*',
            'set "VEGA_EXIT_CODE=%ERRORLEVEL%"',
            "popd > nul",
            "exit /b %VEGA_EXIT_CODE%",
            "",
        )
    )


def _normalise_path_entry(value: str) -> str:
    expanded = os.path.expandvars(value.strip().strip('"'))
    return os.path.normcase(os.path.normpath(os.path.abspath(expanded)))


def add_path_entry(path_value: str, entry: Path) -> tuple[str, bool]:
    """Append ``entry`` exactly once while preserving existing PATH entries."""

    parts = [part.strip() for part in path_value.split(";") if part.strip()]
    wanted = _normalise_path_entry(str(entry))
    if any(_normalise_path_entry(part) == wanted for part in parts):
        return ";".join(parts), False
    parts.append(str(entry.resolve()))
    return ";".join(parts), True


def _read_user_path() -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return str(value)
    except FileNotFoundError:
        return ""


def _write_user_path(value: str) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, value)


def install_launcher(
    *,
    project_root: Path = PROJECT_ROOT,
    launcher_dir: Path | None = None,
    update_path: bool = True,
) -> InstallResult:
    project_root = project_root.resolve()
    if not (project_root / "vega.cmd").is_file():
        raise FileNotFoundError(f"VEGA repository launcher not found: {project_root / 'vega.cmd'}")

    launcher_dir = (launcher_dir or (Path.home() / "vega-bin")).resolve()
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = launcher_dir / "vega.cmd"
    expected = render_wrapper(project_root)
    backup_path: Path | None = None

    if launcher_path.exists():
        current = launcher_path.read_bytes().decode("utf-8-sig")
        if current == expected:
            action = "unchanged"
        else:
            backup_path = launcher_path.with_name("vega.cmd.bak")
            shutil.copy2(launcher_path, backup_path)
            launcher_path.write_text(expected, encoding="utf-8", newline="")
            action = "updated"
    else:
        launcher_path.write_text(expected, encoding="utf-8", newline="")
        action = "created"

    path_changed = False
    if update_path:
        user_path = _read_user_path()
        updated_path, path_changed = add_path_entry(user_path, launcher_dir)
        if path_changed:
            _write_user_path(updated_path)

    return InstallResult(
        project_root=project_root,
        launcher_path=launcher_path,
        action=action,
        backup_path=backup_path,
        path_changed=path_changed,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--launcher-dir", type=Path)
    parser.add_argument("--skip-path", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = install_launcher(
            project_root=args.project_root,
            launcher_dir=args.launcher_dir,
            update_path=not args.skip_path,
        )
    except (OSError, ValueError) as exc:
        print(f"VEGA launcher installation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Project root: {result.project_root}")
    print(f"Launcher path: {result.launcher_path}")
    print(f"Launcher action: {result.action}")
    if result.backup_path is not None:
        print(f"Backup path: {result.backup_path}")
    print(f"User PATH changed: {'yes' if result.path_changed else 'no'}")
    print(f"Restart terminal required: {'yes' if result.path_changed else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
