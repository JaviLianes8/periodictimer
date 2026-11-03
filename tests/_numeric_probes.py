"""Probes that read back, through the public timers, the exact value an argument became.

``interval`` is read from the property. ``jitter`` is read from the bounds the timer
asks its ``rng`` for when ``start`` draws the first offset (none for zero jitter). The
``join`` timeout is read at the one blocking call each timer makes, with a worker that
is still running, so ``join`` must also answer False without waiting.
"""

from __future__ import annotations

import asyncio
import math
import random
import threading
from collections.abc import Callable
from typing import Any

from periodictimer import AsyncPeriodicTimer, PeriodicTimer

TIMERS: tuple[Any, ...] = (PeriodicTimer, AsyncPeriodicTimer)


async def noop() -> None:
    pass


def callback_for(timer: Any) -> Callable[[], object]:
    return noop if timer is AsyncPeriodicTimer else lambda: None


def same(observed: object, expected: object) -> bool:
    """Exact equality: None, or a float of the same value and sign."""
    if expected is None or observed is None:
        return observed is expected
    if type(observed) is not float or type(expected) is not float:
        return False
    if math.isnan(expected):
        return math.isnan(observed)
    return observed == expected and math.copysign(1, observed) == math.copysign(1, expected)


class Recorder(random.Random):
    """An rng that records the bounds of every draw and returns the lower one."""

    def __init__(self) -> None:
        super().__init__(0)
        self.draws: list[tuple[float, float]] = []

    def uniform(self, a: float, b: float) -> float:
        self.draws.append((a, b))
        return a


def interval_of(timer: Any, value: object) -> object:
    return timer(value, callback_for(timer)).interval


def jitter_draws(timer: Any, value: object, interval: float = 1.0) -> list[tuple[float, float]]:
    """The draws made when a timer with this jitter starts; raises what the timer raises.

    The clock is frozen, so the first slot is never due and no call (or second draw) runs.
    """
    rng = Recorder()
    if timer is PeriodicTimer:
        worker = PeriodicTimer(
            interval,
            lambda: None,
            jitter=value,  # type: ignore[arg-type]
            rng=rng,
            clock=lambda: 0.0,
            waiter=lambda delay: True,
        )
        worker.start()
        assert worker.join(5)
        return rng.draws

    async def main() -> None:
        worker = AsyncPeriodicTimer(interval, noop, jitter=value, rng=rng, clock=lambda: 0.0)  # type: ignore[arg-type]
        worker.start()
        await worker.aclose()

    asyncio.run(main())
    return rng.draws


class ThreadJoinProbe:
    """A started thread timer whose worker waits until the probe closes."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.timer = PeriodicTimer(1, lambda: None, waiter=lambda d: self.release.wait())
        self.seen: list[object] = []

    def __enter__(self) -> ThreadJoinProbe:
        self.timer.start()
        thread = self.timer._thread
        self.real_join = thread.join
        setattr(thread, "join", self.seen.append)  # noqa: B010
        return self

    def __call__(self, value: object) -> object:
        self.seen.clear()
        assert self.timer.join(value) is False  # type: ignore[arg-type]
        assert len(self.seen) == 1
        return self.seen[0]

    def __exit__(self, *exc: object) -> None:
        setattr(self.timer._thread, "join", self.real_join)  # noqa: B010
        self.release.set()
        self.timer.stop()
        self.real_join(5)
        assert not self.timer.is_running()


class AsyncJoinProbe:
    """A started asyncio timer whose task sleeps until the probe closes."""

    async def __aenter__(self) -> AsyncJoinProbe:
        self.release = asyncio.Event()
        self.seen: list[object] = []

        async def sleep(delay: float) -> None:
            await self.release.wait()

        async def wait(tasks: Any, *, timeout: object = None) -> tuple[set[Any], set[Any]]:
            self.seen.append(timeout)
            return set(), set(tasks)

        self.timer = AsyncPeriodicTimer(1, noop, sleep=sleep)
        self.timer.start()
        await asyncio.sleep(0)
        self.real_wait = asyncio.wait
        setattr(asyncio, "wait", wait)  # noqa: B010
        return self

    async def __call__(self, value: object) -> object:
        self.seen.clear()
        assert await self.timer.join(value) is False  # type: ignore[arg-type]
        assert len(self.seen) == 1
        return self.seen[0]

    async def __aexit__(self, *exc: object) -> None:
        setattr(asyncio, "wait", self.real_wait)  # noqa: B010
        self.release.set()
        await self.timer.aclose()
        assert not self.timer.is_running()


def unstarted_join(timer: Any, value: object) -> bool:
    if timer is PeriodicTimer:
        return bool(PeriodicTimer(1, lambda: None).join(value))  # type: ignore[arg-type]
    return bool(asyncio.run(AsyncPeriodicTimer(1, noop).join(value)))  # type: ignore[arg-type]


def first_events(timer: Any, **options: Any) -> tuple[list[object], list[bool]]:
    """What a timer does up to its first call, with a clock that only moves when it waits.

    Each wait moves the clock by exactly its delay; the first call stops the timer.
    The second list holds the daemon flag of the thread running a thread timer's call.
    """
    events: list[object] = []
    daemons: list[bool] = []
    now = [50.0]
    if timer is PeriodicTimer:

        def call() -> None:
            events.append("call")
            daemons.append(threading.current_thread().daemon)
            worker.stop()

        def waiter(delay: float) -> bool:
            events.append(("wait", delay))
            now[0] += delay
            return False

        worker = PeriodicTimer(2, call, clock=lambda: now[0], waiter=waiter, **options)
        worker.start()
        assert worker.join(5)
        return events, daemons

    async def main() -> None:
        async def call() -> None:
            events.append("call")
            worker.stop()

        async def sleep(delay: float) -> None:
            events.append(("wait", delay))
            now[0] += delay

        worker = AsyncPeriodicTimer(2, call, clock=lambda: now[0], sleep=sleep, **options)
        worker.start()
        assert await worker.join(5)

    asyncio.run(main())
    return events, daemons
