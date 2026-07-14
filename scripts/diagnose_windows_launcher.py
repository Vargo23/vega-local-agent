#!/usr/bin/env python3
"""Report which checkout and runtime a Windows VEGA launcher selected."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.version import VERSION


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def main() -> int:
    report = {
        "global_launcher": os.environ.get("VEGA_GLOBAL_LAUNCHER", "not set"),
        "repository_launcher": os.environ.get(
            "VEGA_REPOSITORY_LAUNCHER", str(PROJECT_ROOT / "vega.cmd")
        ),
        "project_root": str(PROJECT_ROOT),
        "python_executable": sys.executable,
        "git_branch": _git_value("branch", "--show-current"),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "vega_version": VERSION,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
