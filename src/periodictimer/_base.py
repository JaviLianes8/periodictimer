"""State and options shared by the thread and asyncio timers."""

from __future__ import annotations

import inspect
import random

from ._options import (
    Mode,
    Policy,
    check_callable,
    check_flag,
    check_interval,
    check_jitter,
    check_mode,
    check_policy,
    check_rng,
)
from ._report import ErrorHandler
from ._schedule import Schedule


class TimerBase:
    """Validated options, the schedule and the read-only views both timers expose."""

    def __init__(
        self,
        interval: float,
        fn: object,
        *,
        immediate: bool,
        on_missed: Policy,
        mode: Mode,
        jitter: float,
        rng: random.Random | None,
        on_error: ErrorHandler | None,
        hooks: dict[str, object],
    ) -> None:
        self._interval = check_interval(interval)
        check_callable(fn, "fn")
        self._policy = check_policy(on_missed)
        self._mode = check_mode(mode)
        self._jitter = check_jitter(jitter, self._interval)
        for label, hook in {"on_error": on_error, **hooks}.items():
            if hook is not None:
                check_callable(hook, label)
        if inspect.iscoroutinefunction(on_error):
            raise TypeError("on_error must be a plain function; it is called, never awaited")
        if rng is not None:
            check_rng(rng)
        self._immediate = check_flag(immediate, "immediate")
        self._rng = rng if rng is not None else random.Random()
        self._on_error = on_error
        self._label = getattr(fn, "__qualname__", type(fn).__name__)
        self._schedule: Schedule | None = None

    def _new_schedule(self, epoch: float) -> Schedule:
        return Schedule(
            epoch,
            self._interval,
            immediate=self._immediate,
            policy=self._policy,
            mode=self._mode,
            jitter=self._jitter,
            uniform=self._rng.uniform,
        )

    @property
    def interval(self) -> float:
        """The configured period in seconds."""
        return self._interval

    @property
    def epoch(self) -> float | None:
        """The clock value the schedule is anchored to, set by ``start``; None before."""
        return None if self._schedule is None else self._schedule.epoch

    @property
    def calls(self) -> int:
        """How many calls of ``fn`` have finished, including those that raised."""
        return 0 if self._schedule is None else self._schedule.calls

    @property
    def missed(self) -> int:
        """How many slots were dropped by the ``skip`` or ``coalesce`` policy."""
        return 0 if self._schedule is None else self._schedule.missed

    def is_running(self) -> bool:
        """True while the timer's worker has not finished."""
        raise NotImplementedError

    def __repr__(self) -> str:
        state = "running" if self.is_running() else "idle"
        kind = type(self).__name__
        return f"<{kind} {self._label} every {self._interval}s, {state}>"
