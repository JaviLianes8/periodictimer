"""Seeded property contract: missed-slot selection against an independent oracle.

The oracle restates the documented rule directly: slot ``i`` is due at the float
``epoch + i * interval`` (infinite once that overflows). After slot ``index`` fires at
``now``, burst and an on-time next slot step one slot; skip takes the first slot not yet
past (target ``>= now``); coalesce takes the slot just before the first one strictly
after ``now``. When ``(now - epoch) / interval`` is not finite the scheduler steps one
slot. The oracle finds boundaries with a plain doubling and bisection over the grid,
never with the library's division estimate.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from periodictimer._schedule import Schedule, next_index

SEEDS = [5, 271828, 20261103]
COUNT = 1500
POLICIES = ("skip", "coalesce", "burst")


def target(epoch: float, interval: float, index: int) -> float:
    try:
        return epoch + index * interval
    except OverflowError:
        return math.inf


def oracle(epoch: float, interval: float, index: int, now: float, policy: str) -> int:
    following = index + 1
    if policy == "burst" or target(epoch, interval, following) >= now:
        return following
    if not math.isfinite((now - epoch) / interval):
        return following

    def beyond(i: int) -> bool:
        t = target(epoch, interval, i)
        return t >= now if policy == "skip" else t > now

    low, step = following, 1
    while not beyond(low + step):
        step *= 2
    high = low + step
    while high - low > 1:
        middle = (low + high) // 2
        if beyond(middle):
            high = middle
        else:
            low = middle
    return high if policy == "skip" else high - 1


def case(rng: random.Random) -> tuple[float, float, int, float]:
    if rng.random() < 0.05:
        # A clock far from zero with a tiny interval: the elapsed slot count is finite
        # although epoch plus now, divided by the interval, would overflow.
        epoch = rng.choice([1e9, -1e9, 5e8])
        return (
            epoch,
            10 ** rng.uniform(-305, -300),
            rng.randrange(3),
            epoch + rng.choice([0.5, 1.0, 3.0]),
        )
    epoch = rng.choice(
        [0.0, 1000.0, -1.0, 1e9, 1e16, -1e16, 1e300, rng.uniform(-1e6, 1e6), rng.uniform(0, 1e12)]
    )
    interval = 10 ** rng.uniform(-320, 6) if rng.random() < 0.3 else 10 ** rng.uniform(-6, 4)
    interval = interval if interval > 0 else 5e-324
    index = rng.choice([0, 1, 2, rng.randrange(100), rng.randrange(10**6)])
    base = target(epoch, interval, index)
    kind = rng.randrange(4)
    if kind == 0:
        now = base + interval * rng.uniform(-2, 2) * 10 ** rng.uniform(0, 6)
    elif kind == 1:
        k = index + rng.randrange(1, 10 ** rng.randrange(1, 12))
        now = target(epoch, interval, k)
        now = rng.choice([now, math.nextafter(now, math.inf), math.nextafter(now, -math.inf)])
    elif kind == 2:
        now = base + rng.choice([1.0, 60.0, 3600.0, 1e6])
    else:
        now = base + rng.uniform(0, 10) * 10 ** rng.uniform(-6, 12)
    if not math.isfinite(now):
        now = base
    return epoch, interval, index, now


def cases(seed: int) -> list[tuple[float, float, int, float]]:
    rng = random.Random(seed)
    return [case(rng) for _ in range(COUNT)]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("policy", POLICIES)
def test_next_index_matches_the_oracle(seed: int, policy: Any) -> None:
    for epoch, interval, index, now in cases(seed):
        expected = oracle(epoch, interval, index, now, policy)
        observed = next_index(epoch, interval, index, now, policy)
        assert observed == expected, (epoch, interval, index, now, policy)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("policy", POLICIES)
def test_fired_counts_exactly_the_slots_it_steps_over(seed: int, policy: Any) -> None:
    for epoch, interval, index, now in cases(seed)[:300]:
        schedule = Schedule(
            epoch,
            interval,
            immediate=True,
            policy=policy,
            mode="fixed_rate",
            jitter=0.0,
            uniform=random.Random(0).uniform,
        )
        schedule.index = index
        schedule.fired(lambda: now)  # noqa: B023
        expected = oracle(epoch, interval, index, now, policy)
        assert schedule.index == expected
        assert schedule.missed == expected - index - 1
        assert schedule.calls == 1
        assert schedule.due == target(epoch, interval, expected)


def test_the_cases_reach_every_branch() -> None:
    reached = set()
    for seed in SEEDS:
        for epoch, interval, index, now in cases(seed):
            following = index + 1
            if target(epoch, interval, following) >= now:
                reached.add("on time")
            elif not math.isfinite((now - epoch) / interval):
                reached.add("overflowing estimate")
            elif not math.isfinite((now + epoch) / interval):
                reached.add("finite estimate, overflowing sum")
            elif oracle(epoch, interval, index, now, "skip") - following > 10**6:
                reached.add("long skip")
            else:
                reached.add("short skip")
    assert reached == {
        "on time",
        "overflowing estimate",
        "long skip",
        "finite estimate, overflowing sum",
        "short skip",
    }
