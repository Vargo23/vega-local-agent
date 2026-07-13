from dataclasses import FrozenInstanceError

import pytest

from core.context_budget import OMITTED_CONTENT_MARKER, apply_context_budget


def test_short_evidence_is_unchanged() -> None:
    evidence = "first line\nsecond line"
    result = apply_context_budget(evidence, 100, head_ratio=0.6)
    assert result.evidence == evidence
    assert result.original_chars == len(evidence)
    assert result.selected_chars == len(evidence)
    assert result.max_chars == 100
    assert result.truncated is False


def test_long_evidence_keeps_head_tail_marker_and_metadata() -> None:
    evidence = "HEAD\n" + "middle line\n" * 100 + "TAIL"
    result = apply_context_budget(evidence, 160, head_ratio=0.6)
    assert result.truncated is True
    assert result.original_chars == len(evidence)
    assert result.selected_chars == len(result.evidence)
    assert result.selected_chars <= result.max_chars == 160
    assert result.evidence.startswith("HEAD\n")
    assert result.evidence.endswith("TAIL")
    assert OMITTED_CONTENT_MARKER in result.evidence
    with pytest.raises(FrozenInstanceError):
        result.truncated = False

