"""Failures in the callback and in on_error, for both timers."""

from __future__ import annotations

import asyncio
import logging
import warnings
from typing import Any

import pytest
from _helpers import FakeClock, fake_sleep, fake_waiter

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


def _thread(fn: Any, count: int, **options: Any) -> PeriodicTimer:
    clock = FakeClock()
    holder: list[PeriodicTimer] = []
    waiter = fake_waiter(clock, lambda: holder[0].calls >= count)
    timer = PeriodicTimer(1.0, fn, clock=clock, waiter=waiter, **options)
    holder.append(timer)
    timer.start()
    assert timer.join(10.0)
    return timer


def _boom() -> None:
    raise ValueError("boom")


def test_errors_go_to_on_error_and_the_timer_keeps_going() -> None:
    errors: list[Exception] = []
    timer = _thread(_boom, 3, on_error=errors.append)
    assert timer.calls == 3
    assert [str(error) for error in errors] == ["boom"] * 3


def test_without_a_handler_errors_are_logged_not_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        timer = _thread(_boom, 2)
    assert timer.calls == 2
    records = [r for r in caplog.records if r.name == "periodictimer"]
    assert len(records) == 2
    assert all(r.exc_info and isinstance(r.exc_info[1], ValueError) for r in records)
    assert "_boom" in records[0].getMessage()


def test_a_raising_handler_is_logged_and_stops_the_timer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(exc: Exception) -> None:
        raise RuntimeError("give up") from exc

    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        timer = _thread(_boom, 50, on_error=handler)
    assert timer.calls == 1
    assert not timer.is_running()
    (record,) = [r for r in caplog.records if r.name == "periodictimer"]
    assert "stopping" in record.getMessage()
    assert record.exc_info is not None and str(record.exc_info[1]) == "give up"


def test_a_callback_returning_a_coroutine_is_reported_and_closed() -> None:
    async def work() -> None:
        return None

    errors: list[Exception] = []
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _thread(lambda: work(), 2, on_error=errors.append)
    assert len(errors) == 2
    assert all(isinstance(e, TypeError) and "AsyncPeriodicTimer" in str(e) for e in errors)


def _async(fn: Any, count: int, **options: Any) -> AsyncPeriodicTimer:
    async def main() -> AsyncPeriodicTimer:
        clock = FakeClock()
        timer = AsyncPeriodicTimer(1.0, fn, clock=clock, sleep=fake_sleep(clock), **options)
        timer.start()
        while timer.is_running() and timer.calls < count:
            await asyncio.sleep(0)
        await timer.aclose()
        return timer

    return asyncio.run(main())


async def _aboom() -> None:
    raise ValueError("boom")


def test_async_errors_go_to_on_error_and_the_timer_keeps_going() -> None:
    errors: list[Exception] = []
    timer = _async(_aboom, 3, on_error=errors.append)
    assert timer.calls == 3
    assert [str(error) for error in errors] == ["boom"] * 3


def test_async_errors_without_a_handler_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        _async(_aboom, 2)
    records = [r for r in caplog.records if r.name == "periodictimer"]
    assert len(records) == 2
    assert "AsyncPeriodicTimer" in records[0].getMessage()


def test_async_raising_handler_stops_the_timer(caplog: pytest.LogCaptureFixture) -> None:
    def handler(exc: Exception) -> None:
        raise RuntimeError("give up")

    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        timer = _async(_aboom, 50, on_error=handler)
    assert timer.calls == 1
    assert not timer.is_running()
