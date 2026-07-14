"""User-facing duration and exact token-usage formatting."""

from __future__ import annotations

import math

from core.request_metrics import RequestMetricsSnapshot, RequestStatus


def format_duration(seconds: float, *, unicode: bool = True) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise TypeError("seconds must be a number")
    if seconds < 0 or not math.isfinite(float(seconds)):
        raise ValueError("seconds must be finite and non-negative")

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)

    if unicode:
        if hours:
            return f"{hours} ч. {minutes} мин. {remaining_seconds} сек."
        if minutes:
            return f"{minutes} мин. {remaining_seconds} сек."
        return f"{remaining_seconds} сек."

    if hours:
        return f"{hours} h {minutes} min {remaining_seconds} sec"
    if minutes:
        return f"{minutes} min {remaining_seconds} sec"
    return f"{remaining_seconds} sec"


def format_token_count(value: int, *, unicode: bool = True) -> str:
    if type(value) is not int or value < 0:
        raise ValueError("token count must be a non-negative integer")
    separator = " " if unicode else ","
    return f"{value:,}".replace(",", separator)


def format_request_summary(
    snapshot: RequestMetricsSnapshot,
    *,
    unicode: bool = True,
    detailed: bool = True,
) -> str:
    if not isinstance(snapshot, RequestMetricsSnapshot):
        raise TypeError("snapshot must be a RequestMetricsSnapshot")

    duration = format_duration(snapshot.duration_seconds, unicode=unicode)
    usage = snapshot.token_usage

    if unicode:
        if snapshot.status is RequestStatus.COMPLETED:
            prefix = f"Решено за {duration}"
        elif snapshot.status is RequestStatus.TIMED_OUT:
            prefix = f"Превышен тайм-аут через {duration}"
        else:
            prefix = f"Обработка остановлена через {duration}"

        if usage is None:
            return prefix + " Данные об использовании токенов недоступны."

        total = format_token_count(usage.total_tokens, unicode=True)
        if not detailed:
            return prefix + f" Использовано {total} токенов."
        input_count = format_token_count(usage.input_tokens, unicode=True)
        output_count = format_token_count(usage.output_tokens, unicode=True)
        return (
            prefix
            + f" Использовано {total} токенов: "
            + f"{input_count} входных и {output_count} выходных."
        )

    if snapshot.status is RequestStatus.COMPLETED:
        prefix = f"Solved in {duration}."
    elif snapshot.status is RequestStatus.TIMED_OUT:
        prefix = f"Timed out after {duration}."
    else:
        prefix = f"Processing stopped after {duration}."
    if usage is None:
        return prefix + " Token usage is unavailable."
    total = format_token_count(usage.total_tokens, unicode=False)
    if not detailed:
        return prefix + f" Used {total} tokens."
    input_count = format_token_count(usage.input_tokens, unicode=False)
    output_count = format_token_count(usage.output_tokens, unicode=False)
    return (
        prefix
        + f" Used {total} tokens: "
        + f"{input_count} input and {output_count} output."
    )


__all__ = ["format_duration", "format_request_summary", "format_token_count"]
