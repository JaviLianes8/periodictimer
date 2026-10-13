"""Drift-free repeating timer running an async callback as an asyncio task."""

from __future__ import annotations

import asyncio
import inspect
import random
from collections.abc import Awaitable, Callable
from types import TracebackType

from ._base import TimerBase
from ._options import FIXED_RATE, SKIP, Mode, Policy
from ._report import ErrorHandler, handle_failure
from ._timeout import check_timeout

AsyncCallback = Callable[[], Awaitable[object]]
Sleep = Callable[[float], Awaitable[object]]


class AsyncPeriodicTimer(TimerBase):
    """Await ``fn()`` every ``interval`` seconds in one asyncio task, without drift.

    The asyncio twin of ``PeriodicTimer``, with the same options and guarantees. The
    schedule runs on ``loop.time()``; calls never overlap, since the task awaits each one
    before it waits for the next slot. ``stop`` cancels the task only while it sleeps,
    never while ``fn`` runs. The timer is not thread-safe: use it from its own loop, or
    reach it with ``loop.call_soon_threadsafe(timer.stop)``.

    ``clock`` and ``sleep`` are hooks for tests that must not wait in real time.
    """

    def __init__(
        self,
        interval: float,
        fn: AsyncCallback,
        *,
        immediate: bool = False,
        on_missed: Policy = SKIP,
        mode: Mode = FIXED_RATE,
        jitter: float = 0.0,
        rng: random.Random | None = None,
        on_error: ErrorHandler | None = None,
        name: str | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        super().__init__(
            interval,
            fn,
            immediate=immediate,
            on_missed=on_missed,
            mode=mode,
            jitter=jitter,
            rng=rng,
            on_error=on_error,
            hooks={"clock": clock, "sleep": sleep},
        )
        self._fn = fn
        self._name = name
        self._clock = clock
        self._sleep: Sleep = sleep if sleep is not None else asyncio.sleep
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._sleeping = False
        self._cancelled = False

    def is_running(self) -> bool:
        """True while the timer's task has not finished."""
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Anchor the schedule and start the task on the running loop.

        Must be called from a coroutine. A timer starts once: starting it again, or after
        ``stop``, raises RuntimeError.
        """
        loop = asyncio.get_running_loop()
        if self._task is not None:
            raise RuntimeError("timer already started")
        if self._stopping:
            raise RuntimeError("timer was stopped before it started")
        clock = self._clock if self._clock is not None else loop.time
        self._clock = clock
        self._schedule = self._new_schedule(clock())
        # The timer holds the task: the loop keeps only a weak reference to it.
        self._task = loop.create_task(self._run(), name=self._name)

    def stop(self) -> None:
        """Ask the task to finish and return at once, interrupting a pending sleep."""
        self._stopping = True
        if self._task is not None and self._sleeping and not self._cancelled:
            self._cancelled = True
            self._task.cancel()

    async def join(self, timeout: float | None = None) -> bool:
        """Wait up to ``timeout`` seconds for the task to end; True when it has ended.

        Returns True at once for a timer that never started, re-raises an error that
        ended the task (a failing ``clock`` or ``sleep``), and raises RuntimeError when
        awaited from the callback itself.
        """
        limit = check_timeout(timeout)
        task = self._task
        if task is None:
            return True
        if task is asyncio.current_task():
            raise RuntimeError("cannot join a timer from its own callback; call stop()")
        await asyncio.wait({task}, timeout=limit)
        if not task.done():
            return False
        error = None if task.cancelled() else task.exception()
        if error is not None:
            raise error
        return True

    async def aclose(self) -> None:
        """Stop the timer and wait for its task to end."""
        self.stop()
        await self.join()

    async def __aenter__(self) -> AsyncPeriodicTimer:
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _run(self) -> None:
        schedule = self._schedule
        clock = self._clock
        assert schedule is not None and clock is not None
        while await self._wait_until(schedule.due, clock):
            keep_going = await self._invoke()
            schedule.fired(clock())
            if not keep_going:
                self._stopping = True
                return

    async def _wait_until(self, due: float, clock: Callable[[], float]) -> bool:
        while not self._stopping:
            delay = due - clock()
            if delay <= 0:
                return True
            self._sleeping = True
            try:
                await self._sleep(delay)
            except asyncio.CancelledError:
                if not self._cancelled:
                    raise
                # Our own cancellation from stop(): give it back so a TaskGroup or a
                # timeout around this task does not count it.
                task = asyncio.current_task()
                if task is not None and hasattr(task, "uncancel"):
                    task.uncancel()
                return False
            finally:
                self._sleeping = False
        return False

    async def _invoke(self) -> bool:
        try:
            result = self._fn()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # the timer must survive any callback failure
            return handle_failure(self, exc, self._on_error)
        return True
