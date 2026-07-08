from __future__ import annotations

import json
from pathlib import Path
from typing import Any


INDEX_FILE_NAME = "documents_index.json"


def get_index_path(project_root: Path) -> Path:
    return project_root / "data" / "index" / INDEX_FILE_NAME


def save_index(project_root: Path, index: dict[str, Any]) -> Path:
    index_path = get_index_path(project_root)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return index_path


def load_index(project_root: Path) -> dict[str, Any]:
    index_path = get_index_path(project_root)

    if not index_path.exists():
        return {
            "schema": "vega.documents_index.v1",
            "documents": [],
            "chunks": [],
        }

    return json.loads(index_path.read_text(encoding="utf-8"))


def index_exists(project_root: Path) -> bool:
    return get_index_path(project_root).exists()
