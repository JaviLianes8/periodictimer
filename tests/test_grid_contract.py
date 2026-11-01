"""Hand-written rounded-grid scenarios checked by enumerating eligible slots."""

from __future__ import annotations

import asyncio
import math
import sys

import pytest
from _helpers import FakeClock, fake_sleep, fake_waiter

from periodictimer import AsyncPeriodicTimer, PeriodicTimer
from periodictimer._options import Policy


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("policy", ["skip", "coalesce", "burst"])
@pytest.mark.parametrize("epoch, interval", [(0.0, 0.1), (1.0, 0.001), (1e6, 0.01), (1e16, 0.001)])
@pytest.mark.parametrize("neighbor", [-1, 0, 1])
def test_both_timers_select_slots_on_the_rounded_grid(
    asynchronous: bool, policy: Policy, epoch: float, interval: float, neighbor: int
) -> None:
    clock = FakeClock(epoch)
    boundary = epoch + 3 * interval
    if epoch == 1e16:
        boundary = math.nextafter(epoch, math.inf)
    completion = (
        boundary if neighbor == 0 else math.nextafter(boundary, math.copysign(math.inf, neighbor))
    )
    # Enumerate timestamps directly, without dividing elapsed time by the interval.
    slot = 2
    if policy != "burst" and epoch + slot * interval < completion:
        while epoch + slot * interval < completion:
            slot += 1
        if policy == "coalesce":
            while epoch + slot * interval <= completion:
                slot += 1
            slot -= 1
    expected = [epoch + interval, max(completion, epoch + slot * interval)]
    seen: list[float] = []
    second_missed: list[int] = []
    timer: PeriodicTimer | AsyncPeriodicTimer

    def tick() -> None:
        seen.append(clock.now)
        if len(seen) == 1:
            clock.now = completion
        else:
            second_missed.append(timer.missed)
            timer.stop()

    async def atick() -> None:
        tick()

    async def run() -> None:
        nonlocal timer
        timer = AsyncPeriodicTimer(
            interval, atick, on_missed=policy, clock=clock, sleep=fake_sleep(clock)
        )
        timer.start()
        assert await timer.join(5)

    if asynchronous:
        asyncio.run(run())
    else:
        timer = PeriodicTimer(
            interval,
            tick,
            on_missed=policy,
            clock=clock,
            waiter=fake_waiter(clock, lambda: False),
        )
        timer.start()
        assert timer.join(5)
    assert seen == expected
    assert second_missed == [slot - 2]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("policy", ["skip", "coalesce"])
@pytest.mark.parametrize(
    "epoch, interval, completion",
    [
        (0.0, 1.0, 1e300),
        (1.0, 1e-100, math.nextafter(1.0, math.inf)),
        (0.0, 1.0, sys.float_info.max),
    ],
)
def test_large_rounded_plateaus_select_the_boundary_without_walking_slots(
    asynchronous: bool, policy: Policy, epoch: float, interval: float, completion: float
) -> None:
    clock = FakeClock(epoch)
    seen: list[float] = []
    selected: list[int] = []
    timer: PeriodicTimer | AsyncPeriodicTimer

    def tick() -> None:
        seen.append(clock.now)
        if len(seen) == 1:
            clock.now = completion
        else:
            selected.append(timer.missed + 2)
            timer.stop()

    async def atick() -> None:
        tick()

    async def run() -> None:
        nonlocal timer
        timer = AsyncPeriodicTimer(
            interval, atick, on_missed=policy, clock=clock, sleep=fake_sleep(clock)
        )
        timer.start()
        assert await timer.join(5)

    if asynchronous:
        asyncio.run(run())
    else:
        timer = PeriodicTimer(
            interval,
            tick,
            on_missed=policy,
            clock=clock,
            waiter=fake_waiter(clock, lambda: False),
        )
        timer.start()
        assert timer.join(5)
    assert seen == [epoch + interval, completion]
    (slot,) = selected

    def target(index: int) -> float:
        try:
            return epoch + index * interval
        except OverflowError:
            return math.inf

    if policy == "skip":
        assert target(slot - 1) < completion <= target(slot)
    else:
        assert target(slot) <= completion < target(slot + 1)
