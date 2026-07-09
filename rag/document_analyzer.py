from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from rag.document_index import load_documents_index
from rag.document_loader import read_document
from rag.document_search import search_documents


STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "are", "was", "were",
    "you", "your", "about", "have", "has", "not", "but", "can", "will", "should",
    "это", "как", "что", "для", "или", "при", "над", "под", "его", "она", "они",
    "если", "есть", "нужно", "надо", "будет", "без", "все", "уже", "только",
}
RISK_TERMS = {
    "error", "bug", "problem", "risk", "issue", "fail", "failed", "warning",
    "ошибка", "баг", "проблема", "риск", "не работает", "сломано", "предупреждение",
}
ACTION_TERMS = {
    "todo", "fix", "add", "implement", "update", "remove", "refactor",
    "сделать", "добавить", "исправить", "обновить", "удалить", "переработать",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[\w#./-]+", text.lower(), flags=re.IGNORECASE | re.UNICODE)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n\s*\n", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _find_headings(lines: list[str]) -> list[str]:
    headings: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        markdown = re.match(r"^#{1,3}\s+(.+)$", stripped)
        if markdown:
            headings.append(markdown.group(1).strip())
            continue

        looks_like_heading = (
            len(stripped) <= 80
            and len(stripped.split()) <= 10
            and not stripped.endswith((".", ",", ";"))
            and any(char.isalpha() for char in stripped)
        )
        if looks_like_heading:
            headings.append(stripped)

    return headings[:20]


def _keywords(text: str, limit: int = 12) -> list[str]:
    tokens = [
        token
        for token in _words(text)
        if len(token) >= 3 and token not in STOP_WORDS and not token.isdigit()
    ]
    return [word for word, _ in Counter(tokens).most_common(limit)]


def _summary(text: str, max_points: int = 8) -> list[str]:
    selected: list[str] = []

    for sentence in _sentences(text):
        clean = " ".join(sentence.split())
        if len(clean) < 20:
            continue
        selected.append(clean[:300])
        if len(selected) >= max_points:
            break

    return selected


def _matching_lines(lines: list[str], terms: set[str], limit: int = 10) -> list[str]:
    matches: list[str] = []

    for line in lines:
        clean = " ".join(line.split())
        lowered = clean.lower()
        if clean and any(term in lowered for term in terms):
            matches.append(clean[:300])
            if len(matches) >= limit:
                break

    return matches


def analyze_document(project_root: Path, filename: str) -> dict:
    document = read_document(project_root, filename)
    content = document["content"]
    lines = content.splitlines()

    return {
        "document": document["name"],
        "extension": document["extension"],
        "size": document["size"],
        "characters": len(content),
        "lines": len(lines),
        "words": len(_words(content)),
        "headings": _find_headings(lines),
        "keywords": _keywords(content),
        "summary": _summary(content),
        "risks": _matching_lines(lines, RISK_TERMS),
        "actions": _matching_lines(lines, ACTION_TERMS),
    }


def summarize_document(project_root: Path, filename: str, max_points: int = 8) -> dict:
    document = read_document(project_root, filename)
    return {
        "document": document["name"],
        "summary": _summary(document["content"], max_points=max_points),
    }


def _extractive_answer(question: str, results: list[dict]) -> str:
    terms = set(_words(question))
    answer_parts: list[str] = []

    for result in results[:3]:
        text = str(result.get("text", ""))
        sentences = _sentences(text)
        matching = [
            " ".join(sentence.split())
            for sentence in sentences
            if any(term in sentence.lower() for term in terms)
        ]

        if matching:
            answer_parts.extend(matching[:2])
            continue

        first_lines = [
            " ".join(line.split())
            for line in text.splitlines()
            if line.strip()
        ]
        if first_lines:
            answer_parts.append(first_lines[0])

    if not answer_parts:
        return "I found related fragments, but no direct answer."

    return " ".join(answer_parts[:4])


def ask_documents(project_root: Path, question: str, limit: int = 5) -> dict:
    if load_documents_index(project_root) is None:
        return {
            "question": question,
            "answer": "",
            "chunks": [],
            "error": "Document index not found. Run /docs index first.",
        }

    results = search_documents(project_root, question, limit=limit)
    if not results:
        return {
            "question": question,
            "answer": "No relevant document chunks found.",
            "chunks": [],
            "error": "",
        }

    return {
        "question": question,
        "answer": _extractive_answer(question, results),
        "chunks": results,
        "error": "",
    }
