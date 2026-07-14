from io import StringIO

from ui.terminal_prompt import render_terminal_prompt


def test_unicode_prompt_is_compact_and_not_duplicated() -> None:
    prompt = render_terminal_prompt(
        "qwen2.5-coder:14b",
        "LOCAL",
        stream=StringIO(),
        unicode=True,
    )

    assert prompt == "vega › "
    assert "\n" not in prompt


def test_ascii_prompt_is_plain_and_encodable() -> None:
    prompt = render_terminal_prompt(
        "qwen2.5-coder:7b",
        "LOCAL",
        stream=StringIO(),
        unicode=False,
    )

    assert prompt == "vega > "
    assert prompt.isascii()


def test_color_disabled_never_emits_ansi() -> None:
    prompt = render_terminal_prompt(
        "model",
        stream=StringIO(),
        unicode=True,
        color=False,
    )

    assert "\x1b[" not in prompt


def test_color_requires_ansi_capability() -> None:
    prompt = render_terminal_prompt(
        "model",
        stream=StringIO(),
        unicode=True,
        color=True,
    )

    assert "\x1b[" not in prompt
