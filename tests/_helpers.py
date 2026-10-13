"""Fake time for the timer tests: a settable clock and waiters that move it."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class FakeClock:
    """A clock whose value only moves when a test moves it."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def fake_waiter(
    clock: FakeClock,
    done: Callable[[], bool],
    *,
    late: float = 0.0,
    early: float = 0.0,
    seen: list[float] | None = None,
) -> Callable[[float], bool]:
    """A waiter that jumps the clock instead of blocking, and stops once ``done()``.

    ``late`` overshoots every wake-up; ``early`` wakes up that many seconds short of the
    target whenever the wait is longer than that, as a real wait sometimes does.
    """

    def wait(delay: float) -> bool:
        if seen is not None:
            seen.append(delay)
        if done():
            return True
        step = delay - early if delay > early else delay
        clock.now += step + late
        return done()

    return wait


def fake_sleep(clock: FakeClock) -> Callable[[float], Awaitable[None]]:
    """An asyncio sleep that jumps the clock and only yields to the loop once."""

    async def sleep(delay: float) -> None:
        clock.now += delay
        await asyncio.sleep(0)

    return sleep
