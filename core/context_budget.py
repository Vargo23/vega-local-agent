"""Character-based evidence budgeting without mutating execution results."""

from __future__ import annotations

from dataclasses import dataclass


OMITTED_CONTENT_MARKER = "\n...[omitted middle fragment]...\n"


@dataclass(frozen=True, slots=True)
class ContextBudgetResult:
    evidence: str
    original_chars: int
    selected_chars: int
    max_chars: int
    truncated: bool

    @property
    def selected_evidence(self) -> str:
        return self.evidence

    @property
    def metadata(self) -> dict[str, int | bool]:
        return {
            "original_chars": self.original_chars,
            "selected_chars": self.selected_chars,
            "max_chars": self.max_chars,
            "truncated": self.truncated,
        }


def apply_context_budget(
    evidence: str,
    max_chars: int,
    *,
    head_ratio: float,
) -> ContextBudgetResult:
    """Keep the beginning and end of evidence within a character limit."""

    if not isinstance(evidence, str):
        raise TypeError("evidence must be a string")
    if type(max_chars) is not int or max_chars <= 0:
        raise ValueError("max_chars must be a positive integer")
    if (
        isinstance(head_ratio, bool)
        or not isinstance(head_ratio, (int, float))
        or not 0.0 < float(head_ratio) < 1.0
    ):
        raise ValueError("head_ratio must be between 0 and 1")

    original_chars = len(evidence)
    if original_chars <= max_chars:
        return ContextBudgetResult(
            evidence=evidence,
            original_chars=original_chars,
            selected_chars=original_chars,
            max_chars=max_chars,
            truncated=False,
        )
    if max_chars < len(OMITTED_CONTENT_MARKER):
        raise ValueError("max_chars is too small for the omission marker")

    content_chars = max_chars - len(OMITTED_CONTENT_MARKER)
    head_chars = int(content_chars * float(head_ratio))
    tail_chars = content_chars - head_chars

    head = _prefer_head_line_boundary(evidence, head_chars)
    tail = _prefer_tail_line_boundary(evidence, tail_chars)
    selected = head.rstrip("\r\n") + OMITTED_CONTENT_MARKER + tail.lstrip("\r\n")

    # Boundary adjustments only remove characters, but keep this invariant local.
    if len(selected) > max_chars:
        selected = selected[:max_chars]

    return ContextBudgetResult(
        evidence=selected,
        original_chars=original_chars,
        selected_chars=len(selected),
        max_chars=max_chars,
        truncated=True,
    )


def _prefer_head_line_boundary(value: str, limit: int) -> str:
    candidate = value[:limit]
    boundary = candidate.rfind("\n")
    if boundary > limit // 2:
        return candidate[: boundary + 1]
    return candidate


def _prefer_tail_line_boundary(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    candidate = value[-limit:]
    boundary = candidate.find("\n")
    if 0 <= boundary < limit // 2:
        return candidate[boundary + 1 :]
    return candidate


budget_evidence = apply_context_budget


__all__ = [
    "ContextBudgetResult",
    "OMITTED_CONTENT_MARKER",
    "apply_context_budget",
    "budget_evidence",
]
