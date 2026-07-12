#!/usr/bin/env python3
"""Dependency-free check for the current VEGA runtime identity."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent_runtime import load_system_prompt
from scripts.version import VERSION


def main() -> int:
    prompt = load_system_prompt(PROJECT_ROOT)

    checks = {
        "VERSION has release format": VERSION.startswith("v") and VERSION.count(".") == 2,
        "prompt contains current VERSION": VERSION in prompt,
        "prompt excludes v0.3-dev": "v0.3-dev" not in prompt,
        "prompt excludes v1.1.0": "v1.1.0" not in prompt,
        "VERSION marker was replaced": "{{VERSION}}" not in prompt,
    }

    failed = [name for name, passed in checks.items() if not passed]

    if failed:
        print("FAIL: VEGA identity check")
        for name in failed:
            print(f"- {name}")
        return 1

    print(f"PASS: VEGA identity uses runtime version {VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
