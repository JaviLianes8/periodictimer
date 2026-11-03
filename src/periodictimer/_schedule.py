"""Pure tick-scheduling math for the timers, with no threads, loops or real clocks."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, isfinite

from ._options import BURST, FIXED_DELAY, SKIP, Mode, Policy


def first_index(immediate: bool) -> int:
    """Index of the first tick: 0 fires at the epoch, 1 one interval later."""
    return 0 if immediate else 1


def target_time(epoch: float, interval: float, index: int) -> float:
    """Absolute time of a tick, always an exact multiple of interval from the epoch."""
    try:
        return epoch + index * interval
    except OverflowError:
        # An index beyond float range lies after every finite clock reading.
        return float("inf")


def next_index(epoch: float, interval: float, index: int, now: float, policy: Policy) -> int:
    """Index of the tick after the one just fired, applying the missed-tick policy.

    A slot is missed when its target is already in the past at ``now``. ``burst`` steps
    to the very next slot, so past-due slots fire back to back. ``skip`` drops the missed
    slots and waits for the first one not yet past. ``coalesce`` keeps only the latest slot
    due by ``now``, which then fires at once, late, standing in for all of them.
    """
    following = index + 1
    if policy == BURST or target_time(epoch, interval, following) >= now:
        return following
    elapsed = (now - epoch) / interval
    if not isfinite(elapsed):
        # A subnormal interval overflows the slot count; stepping on is the only safe move.
        return following
    boundary = _boundary(epoch, interval, following, now, policy, ceil(elapsed))
    return boundary if policy == SKIP else boundary - 1


def _boundary(
    epoch: float, interval: float, following: int, now: float, policy: Policy, estimate: int
) -> int:
    # Division can round across an integer; compare the actual grid timestamps.
    # Exponential bracketing avoids walking huge runs of equal rounded timestamps.
    def beyond(index: int) -> bool:
        target = target_time(epoch, interval, index)
        return target >= now if policy == SKIP else target > now

    candidate = max(following, estimate)
    step = 1
    if beyond(candidate):
        high = candidate
        low = max(following - 1, high - step)
        while low >= following and beyond(low):
            high = low
            step *= 2
            low = max(following - 1, high - step)
    else:
        low = candidate
        high = low + step
        while not beyond(high):
            low = high
            step *= 2
            high = low + step
    while high - low > 1:
        middle = (low + high) // 2
        if beyond(middle):
            high = middle
        else:
            low = middle
    return high


class Schedule:
    """The state of one timer's schedule: the next due time and the counters."""

    def __init__(
        self,
        epoch: float,
        interval: float,
        *,
        immediate: bool,
        policy: Policy,
        mode: Mode,
        jitter: float,
        uniform: Callable[[float, float], float],
    ) -> None:
        self.epoch = epoch
        self.interval = interval
        self.policy = policy
        self.mode = mode
        self.jitter = jitter
        self._uniform = uniform
        self.index = first_index(immediate)
        self.calls = 0
        self.missed = 0
        self.due = self._offset(target_time(epoch, interval, self.index))

    def _offset(self, base: float) -> float:
        # Jitter moves one call, never the slots, so it cannot accumulate into drift.
        if self.jitter == 0:
            return base
        return base + self._uniform(0.0, self.jitter)

    def fired(self, clock: Callable[[], float]) -> None:
        """Record a finished call before reading the clock for the next due time."""
        self.calls += 1
        now = clock()
        if self.mode == FIXED_DELAY:
            self.index += 1
            self.due = self._offset(now + self.interval)
            return
        nxt = next_index(self.epoch, self.interval, self.index, now, self.policy)
        self.missed += nxt - self.index - 1
        self.index = nxt
        self.due = self._offset(target_time(self.epoch, self.interval, nxt))
