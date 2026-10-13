"""Start, stop, join, cancellation and the context manager of the asyncio timer."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer


async def _noop() -> None:
    return None


def _run(test: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(asyncio.wait_for(test(), 10.0))


def test_start_needs_a_running_loop() -> None:
    with pytest.raises(RuntimeError):
        AsyncPeriodicTimer(1.0, _noop).start()


def test_cannot_be_started_twice_or_after_stop() -> None:
    async def main() -> None:
        async with AsyncPeriodicTimer(30.0, _noop) as timer:
            with pytest.raises(RuntimeError, match="already"):
                timer.start()
        stopped = AsyncPeriodicTimer(30.0, _noop)
        stopped.stop()
        with pytest.raises(RuntimeError, match="stopped"):
            stopped.start()

    _run(main)


def test_join_before_start_returns_true() -> None:
    async def main() -> None:
        assert await AsyncPeriodicTimer(30.0, _noop).join() is True

    _run(main)


def test_stop_interrupts_a_long_sleep_and_a_huge_interval() -> None:
    async def main() -> None:
        for interval in (3600.0, 1e300):
            timer = AsyncPeriodicTimer(interval, _noop)
            timer.start()
            await asyncio.sleep(0.01)
            assert timer.is_running()
            begin = time.monotonic()
            timer.stop()
            assert await timer.join(5.0)
            assert time.monotonic() - begin < 2.0
            assert not timer.is_running()

    _run(main)


def test_stop_never_cancels_a_running_callback() -> None:
    entered = asyncio.Event()
    finished: list[bool] = []

    async def main() -> None:
        release = asyncio.Event()

        async def slow() -> None:
            entered.set()
            await release.wait()
            finished.append(True)

        timer = AsyncPeriodicTimer(0.001, slow, immediate=True)
        timer.start()
        await entered.wait()
        timer.stop()
        assert await timer.join(0.05) is False
        release.set()
        assert await timer.join(5.0) is True
        assert timer.calls == 1

    _run(main)
    assert finished == [True]


def test_join_from_inside_the_callback_raises() -> None:
    errors: list[BaseException] = []
    holder: list[AsyncPeriodicTimer] = []

    async def join_self() -> None:
        try:
            await holder[0].join()
        except RuntimeError as exc:
            errors.append(exc)
        holder[0].stop()

    async def main() -> None:
        timer = AsyncPeriodicTimer(0.001, join_self, immediate=True)
        holder.append(timer)
        timer.start()
        assert await timer.join(5.0)

    _run(main)
    assert len(errors) == 1


def test_a_failing_clock_ends_the_task_and_join_raises_it() -> None:
    readings: list[float] = []

    def clock() -> float:
        if readings:
            raise OSError("clock gone")
        readings.append(0.0)
        return 0.0

    async def main() -> None:
        timer = AsyncPeriodicTimer(1.0, _noop, clock=clock)
        timer.start()
        with pytest.raises(OSError, match="clock gone"):
            await timer.join(5.0)

    _run(main)


def test_an_outside_cancel_ends_the_timer_and_join_returns_true() -> None:
    async def main() -> None:
        timer = AsyncPeriodicTimer(3600.0, _noop)
        timer.start()
        await asyncio.sleep(0.01)
        task: Any = timer._task
        task.cancel()
        assert await timer.join(5.0)
        assert task.cancelled()

    _run(main)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Task.cancelling arrived in 3.11")
def test_stop_leaves_no_pending_cancellation_on_the_task() -> None:
    async def main() -> None:
        timer = AsyncPeriodicTimer(3600.0, _noop)
        timer.start()
        await asyncio.sleep(0.01)
        timer.stop()
        timer.stop()
        await timer.aclose()
        task: Any = timer._task
        assert not task.cancelled()
        assert task.cancelling() == 0

    _run(main)


def test_stop_from_inside_the_callback_ends_after_that_call() -> None:
    calls: list[int] = []
    holder: list[AsyncPeriodicTimer] = []

    async def once() -> None:
        calls.append(1)
        holder[0].stop()

    async def main() -> None:
        timer = AsyncPeriodicTimer(0.001, once, immediate=True)
        holder.append(timer)
        timer.start()
        assert await timer.join(5.0)

    _run(main)
    assert calls == [1]
