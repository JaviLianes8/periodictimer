"""Task execution and cancellation for the asyncio timer."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable

from ._base import TimerBase
from ._report import handle_failure


class AsyncWorker(TimerBase):
    """Private execution state shared with the public lifecycle class."""

    _fn: Callable[[], Awaitable[object]]
    _clock: Callable[[], float] | None
    _sleep: Callable[[float], Awaitable[object]]
    _task: asyncio.Task[None] | None
    _stopping: bool
    _sleeping: bool
    _cancel_pending: bool

    async def _run(self) -> None:
        schedule = self._schedule
        clock = self._clock
        assert schedule is not None and clock is not None
        # Yield once first, so no call runs inside start() even under an eager task
        # factory, before start() has stored the task.
        await asyncio.sleep(0)
        while await self._wait_until(schedule.due, clock):
            keep_going = await self._invoke()
            schedule.fired(clock())
            if not keep_going:
                self._stopping = True
                return
            # Overdue bursts and subnormal intervals must not monopolize the loop.
            await asyncio.sleep(0)

    async def _wait_until(self, due: float, clock: Callable[[], float]) -> bool:
        while not self._stopping:
            delay = due - clock()
            if delay <= 0:
                return True
            self._sleeping = True
            try:
                await self._sleep(delay)
            except asyncio.CancelledError:
                if not self._cancel_pending or self._give_back_cancel():
                    raise  # someone else cancelled the task too
                return False
            finally:
                self._sleeping = False
            if self._cancel_pending:  # a sleep hook swallowed the cancel from stop()
                self._give_back_cancel()
        return False

    def _give_back_cancel(self) -> bool:
        """Undo the cancel sent by stop(); True when another cancel is still pending.

        Giving it back keeps a TaskGroup or a timeout around the task from counting it.
        """
        self._cancel_pending = False
        task = asyncio.current_task()
        if task is None or not hasattr(task, "uncancel"):
            return False
        return bool(task.uncancel() > 0)

    async def _invoke(self) -> bool:
        try:
            result = self._fn()
            if not inspect.isawaitable(result):
                raise TypeError("fn returned a plain value; use PeriodicTimer for sync work")
            await result
        except Exception as exc:  # the timer must survive any callback failure
            return handle_failure(self, exc, self._on_error)
        return True
