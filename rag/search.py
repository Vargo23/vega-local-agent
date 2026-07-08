from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.store import load_index, index_exists  # noqa: E402


def normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е")


def tokenize_query(query: str) -> list[str]:
    normalized = normalize_text(query)
    tokens = re.findall(r"[a-zа-я0-9_#./-]+", normalized, flags=re.IGNORECASE)
    return [token for token in tokens if len(token) >= 2]


def make_snippet(text: str, query_terms: list[str], max_length: int = 320) -> str:
    clean = " ".join(text.split())

    if len(clean) <= max_length:
        return clean

    normalized = normalize_text(clean)

    first_pos = None

    for term in query_terms:
        pos = normalized.find(term)
        if pos != -1:
            if first_pos is None or pos < first_pos:
                first_pos = pos

    if first_pos is None:
        return clean[:max_length].rstrip() + "..."

    start = max(0, first_pos - max_length // 3)
    end = min(len(clean), start + max_length)

    snippet = clean[start:end].strip()

    if start > 0:
        snippet = "..." + snippet

    if end < len(clean):
        snippet = snippet + "..."

    return snippet


def score_chunk(chunk: dict[str, Any], query: str, query_terms: list[str]) -> int:
    text = normalize_text(chunk.get("text", ""))
    source_path = normalize_text(chunk.get("source_path", ""))
    file_name = normalize_text(chunk.get("file_name", ""))

    normalized_query = normalize_text(query)

    score = 0

    if normalized_query and normalized_query in text:
        score += 20

    for term in query_terms:
        text_hits = text.count(term)
        path_hits = source_path.count(term)
        file_hits = file_name.count(term)

        score += text_hits * 4
        score += path_hits * 2
        score += file_hits * 2

    unique_terms_found = sum(1 for term in set(query_terms) if term in text)
    score += unique_terms_found * 3

    return score


def search_index(project_root: Path, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    index = load_index(project_root)
    chunks = index.get("chunks", [])

    query_terms = tokenize_query(query)

    if not query_terms:
        return []

    results = []

    for chunk in chunks:
        score = score_chunk(chunk, query, query_terms)

        if score <= 0:
            continue

        results.append({
            "score": score,
            "chunk_id": chunk.get("id", ""),
            "source_path": chunk.get("source_path", ""),
            "file_name": chunk.get("file_name", ""),
            "chunk_index": chunk.get("chunk_index", 0),
            "snippet": make_snippet(chunk.get("text", ""), query_terms),
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    return results[:limit]


def print_results(query: str, results: list[dict[str, Any]]) -> None:
    print("VEGA v0.3.2 keyword search")
    print("=" * 32)
    print(f"Query: {query}")
    print(f"Results: {len(results)}")
    print("")

    if not results:
        print("No matching documents found.")
        return

    for index, item in enumerate(results, start=1):
        print(f"{index}. {item['source_path']}")
        print(f"   Score: {item['score']}")
        print(f"   Chunk: {item['chunk_index']}")
        print(f"   Snippet: {item['snippet']}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="VEGA v0.3.2 keyword search")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Maximum result count")
    parser.add_argument("--json", action="store_true", help="Print raw JSON results")

    args = parser.parse_args()

    query = " ".join(args.query).strip()

    if not index_exists(PROJECT_ROOT):
        print("Index not found.")
        print("Run first:")
        print("python .\\rag\\ingest.py")
        return 1

    results = search_index(PROJECT_ROOT, query=query, limit=args.limit)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_results(query, results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
