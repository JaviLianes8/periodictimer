"""Drift-free repeating timer running a callback on a background thread."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from ._schedule import BURST, SKIP, Policy, first_index, next_index, target_time

Callback = Callable[[], object]
ErrorHandler = Callable[[Exception], object]
Waiter = Callable[[float], bool]


class PeriodicTimer:
    """Run ``fn`` every ``interval`` seconds on a daemon thread, scheduled against a fixed
    epoch so the period never drifts.

    Each tick is timed at ``epoch + n * interval`` rather than by sleeping ``interval``
    after the previous call returns, so a slow callback does not push later ticks back and
    the error of one period never carries into the next. When a callback runs longer than
    the interval, the missed-tick policy decides what happens:

    - ``"skip"`` (default): drop the missed ticks and realign to the next future slot, so
      at most one call happens per catch-up. Missed ticks are coalesced into one.
    - ``"burst"``: fire the callback once for every elapsed slot, one call per missed
      period, until the schedule catches up.

    An exception raised by the callback never stops the timer: it is passed to ``on_error``
    when given, otherwise swallowed.
    """

    def __init__(
        self,
        interval: float,
        fn: Callback,
        *,
        immediate: bool = False,
        on_missed: Policy = SKIP,
        on_error: ErrorHandler | None = None,
        name: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        waiter: Waiter | None = None,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        if on_missed not in (SKIP, BURST):
            raise ValueError("on_missed must be 'skip' or 'burst'")
        self._interval = float(interval)
        self._fn = fn
        self._immediate = immediate
        self._on_missed: Policy = on_missed
        self._on_error = on_error
        self._clock = clock
        self._stop = threading.Event()
        self._waiter: Waiter = waiter if waiter is not None else self._stop.wait
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._started = False
        self._epoch: float | None = None

    @property
    def interval(self) -> float:
        """The configured period in seconds."""
        return self._interval

    @property
    def epoch(self) -> float | None:
        """The clock value the schedule is anchored to, or None before start."""
        return self._epoch

    def is_running(self) -> bool:
        """True while the worker thread is alive."""
        return self._thread.is_alive()

    def start(self) -> None:
        """Start the background thread. Starting an already-started timer raises."""
        if self._started:
            raise RuntimeError("timer already started")
        self._started = True
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to finish. Returns at once; call ``join`` to wait for it."""
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the worker thread to end, up to ``timeout`` seconds."""
        self._thread.join(timeout)

    def _run(self) -> None:
        epoch = self._clock()
        self._epoch = epoch
        index = first_index(self._immediate)
        while True:
            delay = target_time(epoch, self._interval, index) - self._clock()
            if delay > 0 and self._waiter(delay):
                return
            if self._stop.is_set():
                return
            self._invoke()
            index = next_index(epoch, self._interval, index, self._clock(), self._on_missed)

    def _invoke(self) -> None:
        try:
            self._fn()
        except Exception as exc:  # the timer must survive any callback failure
            if self._on_error is not None:
                self._on_error(exc)
