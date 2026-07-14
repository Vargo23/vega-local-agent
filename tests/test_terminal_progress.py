from io import StringIO

from core.execution_progress import ExecutionProgressEvent, ExecutionProgressStage
from core.request_metrics import RequestMetrics, RequestStatus
from ui.terminal_progress import TerminalProgressRenderer


def _event(stage: ExecutionProgressStage, **values) -> ExecutionProgressEvent:
    return ExecutionProgressEvent(stage=stage, **values)


def test_preplan_status_has_spinner_without_fake_percentage() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=True
    )

    renderer(_event(ExecutionProgressStage.RECEIVED))
    renderer(_event(ExecutionProgressStage.ANALYZING))
    renderer(_event(ExecutionProgressStage.PLANNING))

    output = stream.getvalue()
    assert "анализирует" in output
    assert "строит план" in output
    assert "%" not in output
    assert "[" not in output
    assert "\r" not in output
    assert "\x1b" not in output


def test_plan_and_real_step_progress_are_rendered() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=True, width=10
    )
    renderer(
        _event(
            ExecutionProgressStage.PLAN_READY,
            total_steps=2,
            plan_titles=("Проверить проект", "Запустить тесты"),
        )
    )
    renderer(
        _event(
            ExecutionProgressStage.STEP_RUNNING,
            current_step=1,
            total_steps=2,
            title="Проверить проект",
        )
    )

    output = stream.getvalue()
    assert "План выполнения · 2 шагов" in output
    assert "1. Проверить проект" in output
    assert "[█████░░░░░] 1/2" in output


def test_final_step_is_not_full_until_completed() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=True, width=4
    )
    renderer(
        _event(
            ExecutionProgressStage.STEP_RUNNING,
            current_step=1,
            total_steps=1,
            title="Тест",
        )
    )
    renderer(
        _event(
            ExecutionProgressStage.COMPLETED,
            current_step=1,
            total_steps=1,
            title="Готово",
            elapsed_seconds=12.4,
        )
    )

    lines = stream.getvalue().splitlines()
    assert "[███░]" in lines[0]
    assert "[████]" in lines[1]
    assert "12,4 сек." in lines[1]
    assert stream.getvalue().endswith("\n")


def test_waiting_skipped_and_failed_are_distinct() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=True
    )
    base = {"current_step": 2, "total_steps": 3}
    renderer(
        _event(
            ExecutionProgressStage.AWAITING_CONFIRMATION,
            title="Ожидаю подтверждение",
            **base,
        )
    )
    renderer(
        _event(
            ExecutionProgressStage.STEP_SKIPPED,
            title="Шаг пропущен",
            **base,
        )
    )
    renderer(
        _event(
            ExecutionProgressStage.STEP_FAILED,
            title="Шаг завершился с ошибкой",
            **base,
        )
    )

    output = stream.getvalue()
    assert "◆" in output
    assert "–" in output
    assert "✗" in output


def test_ascii_fallback_contains_no_unicode_or_controls() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=False, width=6
    )
    renderer(
        _event(
            ExecutionProgressStage.PLAN_READY,
            total_steps=1,
            plan_titles=("Проверить проект",),
        )
    )
    renderer(
        _event(
            ExecutionProgressStage.AWAITING_CONFIRMATION,
            current_step=1,
            total_steps=1,
            title="Ожидаю подтверждение",
        )
    )

    output = stream.getvalue()
    assert output.isascii()
    assert "Execution plan - 1 steps" in output
    assert "Awaiting confirmation" in output
    assert "\r" not in output


def test_interactive_renderer_closes_active_line() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=True, ansi=False, unicode=False
    )
    renderer(_event(ExecutionProgressStage.ANALYZING))
    renderer.close()

    assert stream.getvalue().startswith("\r")
    assert stream.getvalue().endswith("\n")


def test_empty_plan_completion_is_safe() -> None:
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream, interactive=False, ansi=False, unicode=False
    )
    renderer(
        _event(
            ExecutionProgressStage.COMPLETED,
            current_step=0,
            total_steps=0,
            elapsed_seconds=0,
        )
    )

    assert stream.getvalue() == "+ Done in 0.0 sec.\n"


def test_interactive_request_timer_updates_and_stops() -> None:
    now = [0.0]
    metrics = RequestMetrics(clock=lambda: now[0])
    stream = StringIO()
    renderer = TerminalProgressRenderer(
        stream,
        interactive=True,
        ansi=False,
        unicode=False,
        metrics=metrics,
        refresh_interval=10,
    )

    renderer.start_timer()
    renderer(_event(ExecutionProgressStage.RECEIVED))
    assert renderer._timer_thread is not None
    now[0] = 65
    renderer.refresh_timer()
    metrics.stop(RequestStatus.COMPLETED)
    renderer(_event(ExecutionProgressStage.COMPLETED, title="Done"))
    stopped_output = stream.getvalue()
    now[0] = 100
    renderer.refresh_timer()

    assert "1 min 5 sec" in stopped_output
    assert renderer._timer_thread is None
    assert stream.getvalue() == stopped_output


def test_error_cancel_and_timeout_stop_request_timer() -> None:
    for stage in (
        ExecutionProgressStage.FAILED,
        ExecutionProgressStage.CANCELLED,
        ExecutionProgressStage.TIMED_OUT,
    ):
        now = [0.0]
        metrics = RequestMetrics(clock=lambda: now[0])
        renderer = TerminalProgressRenderer(
            StringIO(),
            interactive=True,
            ansi=False,
            unicode=False,
            metrics=metrics,
            refresh_interval=10,
        )
        renderer.start_timer()
        renderer(_event(ExecutionProgressStage.ANALYZING))
        now[0] = 4
        metrics.stop(RequestStatus.FAILED)
        renderer(_event(stage))

        assert renderer._timer_thread is None
