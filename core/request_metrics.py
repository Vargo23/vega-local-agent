"""Request-local timing, phase, status, and exact token-usage metrics."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class RequestStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class RequestPhase(str, Enum):
    PREPARING = "preparing"
    MODEL_WAIT = "model_wait"
    RESPONSE_PROCESSING = "response_processing"
    TOOLS = "tools"
    SAVING = "saving"


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    def __post_init__(self) -> None:
        for name, value in (
            ("input_tokens", self.input_tokens),
            ("output_tokens", self.output_tokens),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class RequestMetricsSnapshot:
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    status: RequestStatus
    token_usage: TokenUsage | None
    phase_durations: tuple[tuple[str, float], ...]

    def to_log_record(self) -> dict[str, object]:
        usage = self.token_usage
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 3),
            "input_tokens": usage.input_tokens if usage is not None else None,
            "output_tokens": usage.output_tokens if usage is not None else None,
            "total_tokens": usage.total_tokens if usage is not None else None,
            "status": self.status.value,
            "phase_durations_seconds": {
                name: round(seconds, 3)
                for name, seconds in self.phase_durations
            },
        }


class RequestMetrics:
    """Own independent mutable counters for exactly one user request."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] | None = None,
        started_monotonic: float | None = None,
        started_at: datetime | None = None,
    ) -> None:
        self._clock = clock
        self._wall_clock = wall_clock or (
            lambda: datetime.now(timezone.utc)
        )
        self._lock = threading.RLock()

        initial_tick = (
            float(clock())
            if started_monotonic is None
            else float(started_monotonic)
        )
        if not math.isfinite(initial_tick):
            raise ValueError("started_monotonic must be finite")

        initial_wall = started_at or self._wall_clock()
        if not isinstance(initial_wall, datetime):
            raise TypeError("started_at must be a datetime")
        if initial_wall.tzinfo is None:
            initial_wall = initial_wall.replace(tzinfo=timezone.utc)

        self._started_tick = initial_tick
        self._started_at = initial_wall
        self._phase = RequestPhase.PREPARING
        self._phase_tick = initial_tick
        self._phase_totals = {phase: 0.0 for phase in RequestPhase}
        self._usage_calls = 0
        self._usage_complete = True
        self._input_tokens = 0
        self._output_tokens = 0
        self._snapshot: RequestMetricsSnapshot | None = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._snapshot is None

    @property
    def elapsed_seconds(self) -> float:
        with self._lock:
            if self._snapshot is not None:
                return self._snapshot.duration_seconds
            return max(0.0, float(self._clock()) - self._started_tick)

    def mark_phase(self, phase: RequestPhase | str) -> None:
        normalized = (
            phase
            if isinstance(phase, RequestPhase)
            else RequestPhase(str(phase))
        )
        with self._lock:
            if self._snapshot is not None or normalized is self._phase:
                return
            now = float(self._clock())
            self._phase_totals[self._phase] += max(
                0.0,
                now - self._phase_tick,
            )
            self._phase = normalized
            self._phase_tick = now

    def record_usage(self, usage: TokenUsage | None) -> None:
        with self._lock:
            if self._snapshot is not None:
                return
            self._usage_calls += 1
            if usage is None:
                self._usage_complete = False
                return
            if not isinstance(usage, TokenUsage):
                raise TypeError("usage must be TokenUsage or None")
            self._input_tokens += usage.input_tokens
            self._output_tokens += usage.output_tokens

    def stop(
        self,
        status: RequestStatus | str,
    ) -> RequestMetricsSnapshot:
        normalized = (
            status
            if isinstance(status, RequestStatus)
            else RequestStatus(str(status))
        )
        with self._lock:
            if self._snapshot is not None:
                return self._snapshot

            finished_tick = float(self._clock())
            self._phase_totals[self._phase] += max(
                0.0,
                finished_tick - self._phase_tick,
            )
            duration = max(0.0, finished_tick - self._started_tick)
            finished_at = self._wall_clock()
            if not isinstance(finished_at, datetime):
                raise TypeError("wall_clock must return a datetime")
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)

            usage = None
            if self._usage_calls and self._usage_complete:
                usage = TokenUsage(
                    self._input_tokens,
                    self._output_tokens,
                )

            phases = tuple(
                (phase.value, self._phase_totals[phase])
                for phase in RequestPhase
                if self._phase_totals[phase] > 0
            )
            self._snapshot = RequestMetricsSnapshot(
                started_at=self._started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                status=normalized,
                token_usage=usage,
                phase_durations=phases,
            )
            return self._snapshot


__all__ = [
    "RequestMetrics",
    "RequestMetricsSnapshot",
    "RequestPhase",
    "RequestStatus",
    "TokenUsage",
]
