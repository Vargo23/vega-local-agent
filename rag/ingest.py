from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.store import save_index  # noqa: E402


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
}
SYSTEM_FILE_NAMES = {
    ".gitkeep",
    ".gitignore",
    "desktop.ini",
    "thumbs.db",
}

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


def read_text_file(path: Path) -> str:
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1251",
    ]

    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Cannot decode file: {path}"
    )


def iter_supported_files(documents_dir: Path) -> Iterable[Path]:
    if not documents_dir.exists():
        return []

    files = []

    for path in documents_dir.rglob("*"):
        path_parts = {part.lower() for part in path.parts}
        name = path.name

        if "__pycache__" in path_parts:
            continue

        if not path.is_file():
            continue

        if name.startswith("."):
            continue

        if name.lower() in SYSTEM_FILE_NAMES:
            continue

        if path.stat().st_size == 0:
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        files.append(path)

    return sorted(files)


def make_document_id(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[dict]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap must be 0 or greater")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        fragment = text[start:end].strip()

        if fragment:
            chunks.append({
                "chunk_index": chunk_index,
                "char_start": start,
                "char_end": end,
                "text": fragment,
            })
            chunk_index += 1

        if end >= len(text):
            break

        start = max(0, end - overlap)

    return chunks


def build_index(
    project_root: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict:
    documents_dir = project_root / "data" / "documents"

    documents = []
    all_chunks = []

    files = list(iter_supported_files(documents_dir))

    for file_path in files:
        relative_path = file_path.relative_to(project_root).as_posix()
        document_id = make_document_id(relative_path)

        try:
            text = read_text_file(file_path)
            status = "indexed"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)

        file_chunks = []

        if text:
            raw_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

            for raw_chunk in raw_chunks:
                chunk_id = f"{document_id}:{raw_chunk['chunk_index']}"

                chunk = {
                    "id": chunk_id,
                    "document_id": document_id,
                    "source_path": relative_path,
                    "file_name": file_path.name,
                    "extension": file_path.suffix.lower(),
                    "chunk_index": raw_chunk["chunk_index"],
                    "char_start": raw_chunk["char_start"],
                    "char_end": raw_chunk["char_end"],
                    "text": raw_chunk["text"],
                }

                file_chunks.append(chunk)
                all_chunks.append(chunk)

        documents.append({
            "id": document_id,
            "source_path": relative_path,
            "file_name": file_path.name,
            "extension": file_path.suffix.lower(),
            "status": status,
            "error": error,
            "size_bytes": file_path.stat().st_size,
            "chunks": len(file_chunks),
        })

    return {
        "schema": "vega.documents_index.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project_root),
        "documents_dir": "data/documents",
        "index_file": "data/index/documents_index.json",
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "documents_count": len(documents),
        "chunks_count": len(all_chunks),
        "documents": documents,
        "chunks": all_chunks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VEGA v0.3.1 document ingestion")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    args = parser.parse_args()

    index = build_index(
        PROJECT_ROOT,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    index_path = save_index(PROJECT_ROOT, index)

    print("VEGA v0.3.1 document ingestion")
    print("=" * 36)
    print(f"Project: {PROJECT_ROOT}")
    print(f"Documents indexed: {index['documents_count']}")
    print(f"Chunks created: {index['chunks_count']}")
    print(f"Index saved to: {index_path}")

    if index["documents_count"] == 0:
        print("")
        print("No supported documents found in data/documents.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
