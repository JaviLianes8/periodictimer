"""Where every kind of failure goes, for both timers, pinned case by case.

An ``Exception`` from the callback goes to ``on_error`` or the log; anything else
derived only from ``BaseException`` is not a callback error and ends the worker.
A handler that raises an ``Exception`` or returns an awaitable is logged with a fixed
message and stops the worker; a returned coroutine is closed first. A ``BaseException``
from the handler is not swallowed either.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from collections.abc import Generator
from typing import Any

import pytest
from _helpers import FakeClock, fake_sleep, fake_waiter

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


class Abort(BaseException):
    """Not an Exception: never an ordinary callback error."""


class Awaitable:
    """An awaitable that is not a coroutine and has no ``close`` method."""

    def __await__(self) -> Generator[None, None, None]:
        yield None


def boom() -> None:
    raise ValueError("boom")


async def aboom() -> None:
    raise ValueError("boom")


def records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "periodictimer"]


def run_thread(fn: Any, **options: Any) -> PeriodicTimer:
    clock = FakeClock()
    holder: list[PeriodicTimer] = []
    waiter = fake_waiter(clock, lambda: holder[0].calls >= 3)
    timer = PeriodicTimer(1.0, fn, clock=clock, waiter=waiter, **options)
    holder.append(timer)
    timer.start()
    assert timer.join(10.0)
    return timer


def run_async(fn: Any, **options: Any) -> AsyncPeriodicTimer:
    async def main() -> AsyncPeriodicTimer:
        clock = FakeClock()
        timer = AsyncPeriodicTimer(1.0, fn, clock=clock, sleep=fake_sleep(clock), **options)
        timer.start()
        while timer.is_running() and timer.calls < 3:
            await asyncio.sleep(0)
        await timer.aclose()
        return timer

    return asyncio.run(main())


RUNNERS = [(run_thread, boom), (run_async, aboom)]


@pytest.mark.parametrize(("run", "fn"), RUNNERS)
def test_a_logged_callback_error_has_its_fixed_message(
    run: Any, fn: Any, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        timer = run(fn)
    assert timer.calls == 3
    assert [r.getMessage() for r in records(caplog)] == [f"callback of {timer!r} raised"] * 3


@pytest.mark.parametrize(("run", "fn"), RUNNERS)
@pytest.mark.parametrize("kind", ["coroutine", "awaitable", "raise"])
def test_a_failing_handler_is_logged_once_and_stops(
    run: Any, fn: Any, kind: str, caplog: pytest.LogCaptureFixture
) -> None:
    returned: list[Any] = []

    def handler(exc: Exception) -> Any:
        if kind == "raise":
            raise RuntimeError("give up")
        result: Any = asyncio.sleep(0) if kind == "coroutine" else Awaitable()
        returned.append(result)
        return result

    with caplog.at_level(logging.ERROR, logger="periodictimer"):
        timer = run(fn, on_error=handler)
    assert timer.calls == 1
    (record,) = records(caplog)
    assert record.getMessage() == f"on_error of {timer!r} raised, stopping the timer"
    assert record.exc_info is not None
    error = record.exc_info[1]
    if kind == "raise":
        assert type(error) is RuntimeError and str(error) == "give up"
        return
    assert type(error) is TypeError
    assert str(error) == "on_error returned an awaitable, which is never awaited"
    if kind == "coroutine":
        assert inspect.getcoroutinestate(returned[0]) == inspect.CORO_CLOSED


def test_an_async_callback_base_exception_ends_the_task_unhandled() -> None:
    handled: list[Exception] = []

    async def fn() -> None:
        raise Abort("stop")

    async def main() -> None:
        timer = AsyncPeriodicTimer(1.0, fn, immediate=True, on_error=handled.append)
        timer.start()
        with pytest.raises(Abort):
            await timer.join(5.0)
        assert not timer.is_running()

    asyncio.run(main())
    assert handled == []


def test_an_async_handler_base_exception_ends_the_task() -> None:
    def handler(exc: Exception) -> None:
        raise Abort("stop")

    async def main() -> None:
        timer = AsyncPeriodicTimer(1.0, aboom, immediate=True, on_error=handler)
        timer.start()
        with pytest.raises(Abort):
            await timer.join(5.0)

    asyncio.run(main())


@pytest.mark.parametrize("where", ["fn", "on_error"])
def test_a_thread_base_exception_escapes_the_worker(
    where: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    escaped: list[type[BaseException] | None] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: escaped.append(args.exc_type))

    def fn() -> None:
        if where == "fn":
            raise Abort("stop")
        boom()

    def handler(exc: Exception) -> None:
        raise Abort("stop")

    timer = PeriodicTimer(1.0, fn, immediate=True, on_error=handler)
    timer.start()
    assert timer.join(5.0)
    assert escaped == [Abort]
    assert timer.calls == 0


def test_stop_during_a_later_callback_never_cancels_it() -> None:
    # The first call comes after a sleep, so the sleeping state must have been cleared.
    finished: list[int] = []

    async def main() -> None:
        clock = FakeClock()

        async def fn() -> None:
            timer.stop()
            for _ in range(5):
                await asyncio.sleep(0)
            finished.append(timer.calls)

        timer = AsyncPeriodicTimer(1.0, fn, clock=clock, sleep=fake_sleep(clock))
        timer.start()
        assert await timer.join(5.0)
        assert timer.calls == 1

    asyncio.run(main())
    assert finished == [0]
