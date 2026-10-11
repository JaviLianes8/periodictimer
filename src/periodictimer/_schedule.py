"""Pure tick-scheduling math for the periodic timer, with no threads or clocks."""

from __future__ import annotations

from math import floor
from typing import Literal

Policy = Literal["skip", "burst"]

SKIP: Policy = "skip"
BURST: Policy = "burst"


def first_index(immediate: bool) -> int:
    """Index of the first tick: 0 fires at the epoch, 1 one interval later."""
    return 0 if immediate else 1


def target_time(epoch: float, interval: float, index: int) -> float:
    """Absolute time of a tick, always an exact multiple of interval from the epoch."""
    return epoch + index * interval


def next_index(epoch: float, interval: float, index: int, now: float, policy: Policy) -> int:
    """Index of the tick after the one just fired, applying the missed-tick policy.

    ``burst`` always steps to the very next slot, so a slow callback leaves past-due
    targets that fire back to back until the schedule catches up. ``skip`` jumps straight
    to the next slot that is still in the future, coalescing every missed tick into one.
    """
    following = index + 1
    if policy == BURST:
        return following
    behind = floor((now - epoch) / interval) + 1
    return max(following, behind)
