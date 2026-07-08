from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag.ingest import build_index
from rag.search import search_index
from rag.store import get_index_path, index_exists, load_index, save_index


DOCUMENTS_DIR = Path("data") / "documents"
INDEX_DIR = Path("data") / "index"
SYSTEM_FILE_NAMES = {
    ".gitkeep",
    ".gitignore",
    "desktop.ini",
    "thumbs.db",
}
TYPO_HINTS = {
    "serch": "search",
    "searh": "search",
    "seach": "search",
    "lst": "list",
    "indx": "index",
}


def get_documents_dir(project_root: Path) -> Path:
    return project_root / DOCUMENTS_DIR


def ensure_docs_paths(project_root: Path) -> tuple[Path, Path]:
    documents_dir = get_documents_dir(project_root)
    index_dir = project_root / INDEX_DIR
    documents_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    return documents_dir, index_dir


def load_index_safe(project_root: Path) -> tuple[dict[str, Any], str]:
    try:
        return load_index(project_root), ""
    except (OSError, json.JSONDecodeError) as exc:
        return {}, str(exc)


def count_indexed_documents(index: dict[str, Any]) -> int | str:
    documents = index.get("documents", [])
    if isinstance(documents, list):
        return len(documents)
    count = index.get("documents_count", "n/a")
    return count if isinstance(count, int) else "n/a"


def print_available_docs_commands() -> None:
    print("Available:")
    print("/docs")
    print("/docs list")
    print("/docs index")
    print("/docs search <query>")


def is_visible_document_file(path: Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and not name.startswith(".")
        and name.lower() not in SYSTEM_FILE_NAMES
        and "__pycache__" not in {part.lower() for part in path.parts}
    )


def print_docs_help(project_root: Path) -> None:
    ensure_docs_paths(project_root)
    index_path = get_index_path(project_root)

    print("VEGA Documents / RAG")
    print("=" * 24)
    print("Commands:")
    print("  /docs                 Show this help")
    print("  /docs list            Show indexed documents")
    print("  /docs index           Rebuild local document index")
    print("  /docs search <query>  Search indexed documents")
    print("")
    print("Folders:")
    print("  Documents: data/documents")
    print("  Index:     data/index/documents_index.json")
    print("")
    print(f"Index exists: {'YES' if index_path.exists() else 'NO'}")


def docs_list(project_root: Path) -> None:
    documents_dir, _ = ensure_docs_paths(project_root)
    index_path = get_index_path(project_root)
    index: dict[str, Any] = {}
    index_error = ""

    if index_path.exists():
        index, index_error = load_index_safe(project_root)

    files = sorted(path for path in documents_dir.iterdir() if is_visible_document_file(path))

    print("# Documents list")
    print("")
    print("Documents folder: data/documents")
    print("Index path: data/index/documents_index.json")
    print(f"Index exists: {'YES' if index_path.exists() else 'NO'}")

    if index_error:
        print("Documents indexed: n/a")
        print(f"Index error: {index_error}")
    else:
        print(f"Documents indexed: {count_indexed_documents(index)}")

    print("")
    print("Files:")

    if not files:
        print("No documents found in data/documents")
        return

    for path in files:
        print(f"* {path.name}")


def docs_index(project_root: Path) -> None:
    ensure_docs_paths(project_root)
    index = build_index(project_root)
    index_path = save_index(project_root, index)

    print("Document index rebuilt")
    print("=" * 22)
    print(f"Documents indexed: {index.get('documents_count', 0)}")
    print(f"Chunks created: {index.get('chunks_count', 0)}")
    print(f"Index saved to: {index_path}")

    if index.get("documents_count", 0) == 0:
        print("")
        print("No supported documents found in data/documents.")


def docs_search(project_root: Path, query: str) -> None:
    query = query.strip()

    if not query:
        print("Docs search error: query is empty.")
        print("Usage: /docs search <query>")
        return

    if not index_exists(project_root):
        print("Documents index not found.")
        print("Run: /docs index")
        return

    _, index_error = load_index_safe(project_root)
    if index_error:
        print(f"Documents index error: {index_error}")
        print("Run: /docs index")
        return

    results = search_index(project_root, query=query, limit=5)

    if not results:
        print(f"No document matches found for: {query}")
        return

    print("# Documents search results")
    print("")
    print(f"Query: {query}")
    print(f"Matches: {len(results)}")
    print("")

    for number, item in enumerate(results, start=1):
        name = item.get("file_name") or Path(item.get("source_path", "")).name or "unknown"
        source_path = item.get("source_path", "")
        score = item.get("score", "n/a")
        preview = str(item.get("snippet", "")).strip()
        if len(preview) > 500:
            preview = preview[:497].rstrip() + "..."

        print(f"[{number}] {name}")
        if source_path:
            print(f"Path: {source_path}")
        print(f"Score: {score if score != '' else 'n/a'}")
        print("Preview:")
        print(preview)
        print("")


def handle_docs_command(command: str, project_root: Path) -> bool:
    command = command.strip()

    if command != "/docs" and not command.startswith("/docs "):
        return False

    parts = command.split(maxsplit=2)

    if len(parts) == 1:
        print_docs_help(project_root)
        return True

    subcommand = parts[1].lower()

    if subcommand == "list":
        docs_list(project_root)
        return True

    if subcommand == "index":
        docs_index(project_root)
        return True

    if subcommand == "search":
        query = parts[2] if len(parts) >= 3 else ""
        docs_search(project_root, query)
        return True

    if subcommand in TYPO_HINTS:
        suggestion = TYPO_HINTS[subcommand]
        suffix = " <query>" if suggestion == "search" else ""
        print(f"Unknown /docs command: {subcommand}")
        print(f"Did you mean: /docs {suggestion}{suffix}?")
        print("")
        print_available_docs_commands()
        return True

    print("Unknown /docs command.")
    print_available_docs_commands()
    return True
