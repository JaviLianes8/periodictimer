"""Pure tick-scheduling math for the timers, with no threads, loops or real clocks."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil, floor

from ._options import BURST, FIXED_DELAY, SKIP, Mode, Policy


def first_index(immediate: bool) -> int:
    """Index of the first tick: 0 fires at the epoch, 1 one interval later."""
    return 0 if immediate else 1


def target_time(epoch: float, interval: float, index: int) -> float:
    """Absolute time of a tick, always an exact multiple of interval from the epoch."""
    return epoch + index * interval


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
    if policy == SKIP:
        return max(following, ceil((now - epoch) / interval))
    return max(following, floor((now - epoch) / interval))


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

    def fired(self, now: float) -> None:
        """Record a finished call that ended at ``now`` and work out the next due time."""
        self.calls += 1
        if self.mode == FIXED_DELAY:
            self.index += 1
            self.due = self._offset(now + self.interval)
            return
        nxt = next_index(self.epoch, self.interval, self.index, now, self.policy)
        self.missed += nxt - self.index - 1
        self.index = nxt
        self.due = self._offset(target_time(self.epoch, self.interval, nxt))
