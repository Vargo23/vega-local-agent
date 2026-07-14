"""Terminal rendering for safe execution progress events and elapsed time."""

from __future__ import annotations

import math
import sys
import threading
from typing import TextIO

from core.execution_progress import ExecutionProgressEvent, ExecutionProgressStage
from core.request_metrics import RequestMetrics
from ui.request_summary import format_duration
from ui.terminal_theme import TerminalCapabilities, detect_terminal_capabilities


class TerminalProgressRenderer:
    """Render progress and a request-local timer without execution authority."""

    _UNICODE_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧")
    _ASCII_SPINNER = ("|", "/", "-", "\\")

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        interactive: bool | None = None,
        ansi: bool | None = None,
        unicode: bool | None = None,
        width: int = 20,
        metrics: RequestMetrics | None = None,
        refresh_interval: float = 1.0,
    ) -> None:
        if type(width) is not int or width < 4:
            raise ValueError("width must be an integer of at least 4")
        if (
            isinstance(refresh_interval, bool)
            or not isinstance(refresh_interval, (int, float))
            or refresh_interval <= 0
            or not math.isfinite(float(refresh_interval))
        ):
            raise ValueError("refresh_interval must be finite and positive")
        if metrics is not None and not isinstance(metrics, RequestMetrics):
            raise TypeError("metrics must be RequestMetrics or None")

        self.stream = stream or sys.stdout
        self.capabilities: TerminalCapabilities = detect_terminal_capabilities(
            self.stream,
            interactive=interactive,
            ansi=ansi,
            unicode=unicode,
        )
        self.width = width
        self.metrics = metrics
        self.refresh_interval = float(refresh_interval)
        self._spinner_index = 0
        self._line_active = False
        self._closed = False
        self._active_text: str | None = None
        self._write_lock = threading.RLock()
        self._timer_stop = threading.Event()
        self._timer_thread: threading.Thread | None = None

    def __enter__(self) -> "TerminalProgressRenderer":
        self.start_timer()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __call__(self, event: ExecutionProgressEvent) -> None:
        self.handle(event)

    def _symbol(self, unicode_value: str, ascii_value: str) -> str:
        return unicode_value if self.capabilities.unicode else ascii_value

    def _spinner(self) -> str:
        frames = (
            self._UNICODE_SPINNER
            if self.capabilities.unicode
            else self._ASCII_SPINNER
        )
        frame = frames[self._spinner_index % len(frames)]
        self._spinner_index += 1
        return frame

    def _elapsed(self, explicit: float | None = None) -> float | None:
        if self.metrics is not None:
            return self.metrics.elapsed_seconds
        return explicit

    def _decorate(self, text: str, elapsed: float | None) -> str:
        if elapsed is None:
            return text
        separator = " · " if self.capabilities.unicode else " - "
        return text + separator + format_duration(
            elapsed,
            unicode=self.capabilities.unicode,
        )

    def _write_line(self, text: str, *, elapsed: float | None = None) -> None:
        with self._write_lock:
            decorated = self._decorate(text, self._elapsed(elapsed))
            if self.capabilities.interactive:
                prefix = "\r\x1b[2K" if self.capabilities.ansi else "\r"
                self.stream.write(prefix + decorated)
                self._line_active = True
                self._active_text = text
            else:
                self.stream.write(decorated + "\n")
            self.stream.flush()

    def _finish_line(
        self,
        text: str | None = None,
        *,
        elapsed: float | None = None,
    ) -> None:
        with self._write_lock:
            decorated = (
                self._decorate(text, self._elapsed(elapsed))
                if text is not None
                else None
            )
            if self.capabilities.interactive:
                if decorated is not None:
                    prefix = "\r\x1b[2K" if self.capabilities.ansi else "\r"
                    self.stream.write(prefix + decorated)
                if self._line_active or decorated is not None:
                    self.stream.write("\n")
                self._line_active = False
            elif decorated is not None:
                self.stream.write(decorated + "\n")
            self._active_text = None
            self.stream.flush()

    def refresh_timer(self) -> None:
        """Redraw the active interactive line with current elapsed time."""

        if (
            self._closed
            or not self.capabilities.interactive
            or self.metrics is None
        ):
            return
        with self._write_lock:
            if self._active_text is None:
                return
            prefix = "\r\x1b[2K" if self.capabilities.ansi else "\r"
            self.stream.write(
                prefix
                + self._decorate(
                    self._active_text,
                    self.metrics.elapsed_seconds,
                )
            )
            self.stream.flush()

    def _timer_loop(self) -> None:
        while not self._timer_stop.wait(self.refresh_interval):
            self.refresh_timer()

    def start_timer(self) -> None:
        """Start request-local redraws; redirected output is never spammed."""

        if (
            self._closed
            or self.metrics is None
            or not self.capabilities.interactive
            or self._timer_thread is not None
        ):
            return
        self._timer_stop.clear()
        self._timer_thread = threading.Thread(
            target=self._timer_loop,
            name="vega-request-timer",
            daemon=True,
        )
        self._timer_thread.start()

    def stop_timer(self) -> None:
        thread = self._timer_thread
        if thread is None:
            return
        self._timer_stop.set()
        if thread is not threading.current_thread():
            thread.join(timeout=max(0.1, self.refresh_interval * 2))
        self._timer_thread = None

    def _bar(self, event: ExecutionProgressEvent) -> str:
        if event.total_steps <= 0:
            return ""
        filled = round(self.width * event.current_step / event.total_steps)
        if event.stage is not ExecutionProgressStage.COMPLETED:
            filled = min(filled, self.width - 1)
        filled = max(0, min(self.width, filled))
        if self.capabilities.unicode:
            return "[" + "█" * filled + "░" * (self.width - filled) + "]"
        return "[" + "#" * filled + "-" * (self.width - filled) + "]"

    def _count(self, event: ExecutionProgressEvent) -> str:
        return f"{event.current_step}/{event.total_steps}"

    def _display_title(self, event: ExecutionProgressEvent, fallback: str) -> str:
        title = event.title or fallback
        if not self.capabilities.unicode and not title.isascii():
            return fallback
        return title

    def _progress_line(self, event: ExecutionProgressEvent, marker: str) -> str:
        ascii_fallbacks = {
            ExecutionProgressStage.STEP_RUNNING: "Step running",
            ExecutionProgressStage.AWAITING_CONFIRMATION: "Awaiting confirmation",
            ExecutionProgressStage.STEP_COMPLETED: "Step completed",
            ExecutionProgressStage.STEP_SKIPPED: "Step skipped",
            ExecutionProgressStage.STEP_FAILED: "Step failed",
            ExecutionProgressStage.COMPLETED: "Done",
            ExecutionProgressStage.FAILED: "Execution failed",
            ExecutionProgressStage.CANCELLED: "Cancelled",
            ExecutionProgressStage.TIMED_OUT: "Timed out",
        }
        title = self._display_title(
            event,
            "Шаг выполняется"
            if self.capabilities.unicode
            else ascii_fallbacks.get(event.stage, "Progress"),
        )
        separator = " · " if self.capabilities.unicode else " - "
        return f"{marker} {self._bar(event)} {self._count(event)}{separator}{title}"

    def _render_plan(self, event: ExecutionProgressEvent) -> str:
        if self.capabilities.unicode:
            header = f"План выполнения · {event.total_steps} шагов"
        else:
            header = f"Execution plan - {event.total_steps} steps"
        lines = [header, ""]
        for index, title in enumerate(event.plan_titles, 1):
            if not self.capabilities.unicode and not title.isascii():
                title = f"Operation {index}"
            lines.append(f"  {index}. {title}")
        return "\n".join(lines).rstrip()

    def handle(self, event: ExecutionProgressEvent) -> None:
        if self._closed:
            return
        if not isinstance(event, ExecutionProgressEvent):
            raise TypeError("event must be an ExecutionProgressEvent")
        stage = event.stage
        if stage is ExecutionProgressStage.RECEIVED:
            text = (
                "VEGA приняла запрос…"
                if self.capabilities.unicode
                else "VEGA received the request..."
            )
            self._write_line(f"{self._spinner()} {text}", elapsed=event.elapsed_seconds)
        elif stage is ExecutionProgressStage.ANALYZING:
            text = event.title or (
                "VEGA анализирует запрос…"
                if self.capabilities.unicode
                else "VEGA analyzes the request..."
            )
            self._write_line(f"{self._spinner()} {text}", elapsed=event.elapsed_seconds)
        elif stage is ExecutionProgressStage.PLANNING:
            text = event.title or (
                "VEGA строит план выполнения…"
                if self.capabilities.unicode
                else "VEGA builds the execution plan..."
            )
            self._write_line(f"{self._spinner()} {text}", elapsed=event.elapsed_seconds)
        elif stage is ExecutionProgressStage.PLAN_READY:
            self._finish_line()
            with self._write_lock:
                self.stream.write(self._render_plan(event) + "\n\n")
                self.stream.flush()
        elif stage is ExecutionProgressStage.STEP_RUNNING:
            self._write_line(
                self._progress_line(event, self._spinner()),
                elapsed=event.elapsed_seconds,
            )
        elif stage is ExecutionProgressStage.AWAITING_CONFIRMATION:
            self._finish_line(
                self._progress_line(event, self._symbol("◆", "!")),
                elapsed=event.elapsed_seconds,
            )
        elif stage is ExecutionProgressStage.STEP_COMPLETED:
            self._write_line(
                self._progress_line(event, self._symbol("✓", "+")),
                elapsed=event.elapsed_seconds,
            )
        elif stage is ExecutionProgressStage.STEP_SKIPPED:
            self._finish_line(
                self._progress_line(event, self._symbol("–", "-")),
                elapsed=event.elapsed_seconds,
            )
        elif stage is ExecutionProgressStage.STEP_FAILED:
            self._write_line(
                self._progress_line(event, self._symbol("✗", "x")),
                elapsed=event.elapsed_seconds,
            )
        elif stage is ExecutionProgressStage.COMPLETED:
            self.stop_timer()
            marker = self._symbol("✓", "+")
            title = self._display_title(
                event,
                "Готово" if self.capabilities.unicode else "Done",
            )
            if self.metrics is None and event.elapsed_seconds is not None:
                duration = f"{event.elapsed_seconds:.1f}"
                if self.capabilities.unicode:
                    duration = duration.replace(".", ",")
                    title = f"{title} за {duration} сек."
                else:
                    title = f"{title} in {duration} sec."
            terminal = ExecutionProgressEvent(
                stage=stage,
                current_step=event.total_steps,
                total_steps=event.total_steps,
                title=title,
                elapsed_seconds=event.elapsed_seconds,
            )
            line = (
                self._progress_line(terminal, marker)
                if terminal.total_steps
                else f"{marker} {title}"
            )
            # Legacy renderers already include the explicit completion duration
            # in ``title``. Request metrics are decorated independently.
            self._finish_line(line)
        elif stage in {
            ExecutionProgressStage.FAILED,
            ExecutionProgressStage.CANCELLED,
            ExecutionProgressStage.TIMED_OUT,
        }:
            self.stop_timer()
            defaults = {
                ExecutionProgressStage.FAILED: (
                    "Выполнение завершилось с ошибкой",
                    "Execution failed",
                ),
                ExecutionProgressStage.CANCELLED: (
                    "Обработка отменена",
                    "Cancelled",
                ),
                ExecutionProgressStage.TIMED_OUT: (
                    "Превышен тайм-аут",
                    "Timed out",
                ),
            }
            unicode_title, ascii_title = defaults[stage]
            title = self._display_title(
                event,
                unicode_title if self.capabilities.unicode else ascii_title,
            )
            terminal = ExecutionProgressEvent(
                stage=stage,
                current_step=event.current_step,
                total_steps=event.total_steps,
                title=title,
                elapsed_seconds=event.elapsed_seconds,
            )
            marker = self._symbol("✗", "x")
            line = (
                self._progress_line(terminal, marker)
                if terminal.total_steps
                else f"{marker} {title}"
            )
            self._finish_line(line, elapsed=event.elapsed_seconds)

    def close(self) -> None:
        if self._closed:
            return
        self.stop_timer()
        self._finish_line()
        self._closed = True


__all__ = ["TerminalProgressRenderer"]
