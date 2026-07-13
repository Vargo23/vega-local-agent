import pytest

from core.intent_analyzer import (
    IntentType,
    analyze_intent,
    normalize_request,
)


@pytest.mark.parametrize(
    ("user_text", "expected_intent"),
    (
        (
            "Проанализируй этот документ и сделай краткий отчёт",
            IntentType.DOCUMENT_ANALYSIS,
        ),
        (
            "Найди в проекте использование старого API",
            IntentType.PROJECT_SEARCH,
        ),
        (
            "Исправь эту ошибку и проверь тесты",
            IntentType.BUG_FIX,
        ),
        (
            "Посмотри изменения и оцени риски",
            IntentType.CODE_REVIEW,
        ),
        (
            "Обнови документацию после изменений",
            IntentType.DOCUMENTATION_UPDATE,
        ),
        (
            "Проверь, готов ли проект к релизу",
            IntentType.RELEASE_CHECK,
        ),
        (
            "Запусти pytest",
            IntentType.TEST_RUN,
        ),
    ),
)
def test_analyze_supported_intents(
    user_text: str,
    expected_intent: IntentType,
) -> None:
    analysis = analyze_intent(user_text)

    assert analysis.intent is expected_intent
    assert analysis.is_actionable is True
    assert analysis.confidence > 0.0
    assert analysis.matched_signals


def test_unknown_request_is_not_actionable() -> None:
    analysis = analyze_intent(
        "Расскажи что-нибудь интересное"
    )

    assert analysis.intent is IntentType.UNKNOWN
    assert analysis.is_actionable is False
    assert analysis.confidence == 0.0


def test_empty_request_is_unknown() -> None:
    analysis = analyze_intent("   ")

    assert analysis.intent is IntentType.UNKNOWN
    assert analysis.normalized_text == ""


def test_normalization_handles_whitespace_and_yo() -> None:
    result = normalize_request(
        "  Сделай   краткий   ОТЧЁТ  "
    )

    assert result == "сделай краткий отчет"


def test_analysis_serializes_to_dictionary() -> None:
    analysis = analyze_intent(
        "Найди использование API в проекте"
    )

    result = analysis.to_dict()

    assert result["intent"] == "project_search"
    assert result["is_actionable"] is True
    assert isinstance(result["matched_signals"], list)


def test_non_string_request_is_rejected() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        analyze_intent(None)  # type: ignore[arg-type]

