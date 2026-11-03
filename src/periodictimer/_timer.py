"""Drift-free repeating timer running a callback on a background thread."""

from __future__ import annotations

import inspect
import random
import threading
import time
from collections.abc import Callable
from types import TracebackType

from ._base import TimerBase
from ._numbers import check_flag, check_timeout
from ._options import FIXED_RATE, SKIP, Mode, Policy, check_callable
from ._report import ErrorHandler, handle_failure

Callback = Callable[[], object]
Waiter = Callable[[float], bool]


class PeriodicTimer(TimerBase):
    """Run ``fn`` every ``interval`` seconds on one background thread, without drift.

    Fixed-rate slots stay at ``epoch + n * interval``; calls never overlap or start
    before their slot. ``on_missed`` is skip, coalesce or burst. Fixed delay waits after
    each call; jitter adds a bounded random delay. Callback exceptions go to ``on_error``
    or the logger; a failing handler stops the worker. ``waiter(seconds)`` returns True
    to stop. See GUIDE for the complete option and error contracts.

    >>> timer = PeriodicTimer(1, lambda: timer.stop(), immediate=True)
    >>> timer.start()
    >>> timer.join(5)
    True
    >>> timer.calls
    1
    """

    def __init__(
        self,
        interval: float,
        fn: Callback,
        *,
        immediate: bool = False,
        on_missed: Policy = SKIP,
        mode: Mode = FIXED_RATE,
        jitter: float = 0.0,
        rng: random.Random | None = None,
        on_error: ErrorHandler | None = None,
        name: str | None = None,
        daemon: bool = True,
        clock: Callable[[], float] = time.monotonic,
        waiter: Waiter | None = None,
    ) -> None:
        if inspect.iscoroutinefunction(fn):
            raise TypeError("fn is a coroutine function; use AsyncPeriodicTimer")
        check_callable(clock, "clock")
        super().__init__(
            interval,
            fn,
            immediate=immediate,
            on_missed=on_missed,
            mode=mode,
            jitter=jitter,
            rng=rng,
            on_error=on_error,
            hooks={"clock": clock, "waiter": waiter},
        )
        self._fn = fn
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._waiter: Waiter = waiter if waiter is not None else self._stop.wait
        self._thread = threading.Thread(
            target=self._run, name=name, daemon=check_flag(daemon, "daemon")
        )
        self._failure: Exception | None = None

    def is_running(self) -> bool:
        """True while the worker thread is alive.

        >>> PeriodicTimer(1, lambda: None).is_running()
        False
        """
        return self._thread.is_alive()

    def start(self) -> None:
        """Anchor the schedule at the current clock value and start the worker thread.

        A timer starts once: starting it again, or after ``stop``, raises RuntimeError.

        >>> timer = PeriodicTimer(1, lambda: None, waiter=lambda delay: True)
        >>> timer.start()
        >>> timer.join(5)
        True
        """
        with self._lock:
            if self._schedule is not None:
                raise RuntimeError("timer already started")
            if self._stop.is_set():
                raise RuntimeError("timer was stopped before it started")
            self._schedule = self._new_schedule(self._clock())
            self._thread.start()

    def stop(self) -> None:
        """Ask the worker to finish and return at once, interrupting any pending wait.

        A call already in progress runs to its end; ``join`` waits for it. Safe to call
        more than once, before ``start`` and from inside the callback.

        >>> timer = PeriodicTimer(1, lambda: None)
        >>> timer.stop()
        >>> timer.is_running()
        False
        """
        self._stop.set()

    def join(self, timeout: float | None = None) -> bool:
        """Wait up to ``timeout`` seconds for the worker to end; True when it has ended.

        Returns True at once for a timer that never started. Re-raises an error that
        ended the worker (a failing ``clock`` or ``waiter``), and raises RuntimeError when
        called from the callback itself, which would wait forever.

        >>> PeriodicTimer(1, lambda: None).join()
        True
        """
        limit = check_timeout(timeout)
        if threading.current_thread() is self._thread:
            raise RuntimeError("cannot join a timer from its own callback; call stop()")
        with self._lock:
            started = self._schedule is not None
        if not started:
            return True
        self._thread.join(limit)
        if self._thread.is_alive():
            return False
        if self._failure is not None:
            raise self._failure
        return True

    def __enter__(self) -> PeriodicTimer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
        self.join()

    def _run(self) -> None:
        try:
            self._loop()
        except Exception as exc:  # a failing clock or waiter: kept for join to raise
            self._failure = exc
            self._stop.set()

    def _loop(self) -> None:
        schedule = self._schedule
        assert schedule is not None
        while self._wait_until(schedule.due):
            keep_going = self._invoke()
            schedule.fired(self._clock)
            if not keep_going:
                self._stop.set()
                return

    def _wait_until(self, due: float) -> bool:
        # The clock is read again after every wake-up, so a waiter that returns early
        # never makes a call start before its slot.
        while not self._stop.is_set():
            delay = due - self._clock()
            if delay <= 0:
                return True
            if self._waiter(min(delay, threading.TIMEOUT_MAX)):
                self._stop.set()
                return False
        return False

    def _invoke(self) -> bool:
        try:
            result = self._fn()
        except Exception as exc:  # the timer must survive any callback failure
            return handle_failure(self, exc, self._on_error)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            error = TypeError("fn returned an awaitable; use AsyncPeriodicTimer")
            return handle_failure(self, error, self._on_error)
        return True
