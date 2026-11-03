"""Completed invocations remain observable when a later clock read fails."""

from __future__ import annotations

import asyncio

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("raises", [False, True])
def test_completed_callback_is_counted_before_clock_failure(
    asynchronous: bool, raises: bool
) -> None:
    completed: list[bool] = []
    handled: list[Exception] = []
    failure = OSError("clock unavailable")
    callback_failure = ValueError("callback failed")

    def clock() -> float:
        if completed:
            raise failure
        return 0.0

    def tick() -> None:
        completed.append(True)
        if raises:
            raise callback_failure

    async def atick() -> None:
        tick()

    async def run() -> AsyncPeriodicTimer:
        timer = AsyncPeriodicTimer(1, atick, immediate=True, clock=clock, on_error=handled.append)
        timer.start()
        with pytest.raises(OSError) as caught:
            await timer.join(5)
        assert caught.value is failure
        return timer

    timer: PeriodicTimer | AsyncPeriodicTimer
    if asynchronous:
        timer = asyncio.run(run())
    else:
        timer = PeriodicTimer(1, tick, immediate=True, clock=clock, on_error=handled.append)
        timer.start()
        with pytest.raises(OSError) as caught:
            timer.join(5)
        assert caught.value is failure
    assert not timer.is_running()
    assert completed == [True]
    assert handled == ([callback_failure] if raises else [])
    assert timer.calls == 1
    assert timer.missed == 0
