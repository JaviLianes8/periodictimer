"""The asyncio timer on a fake clock and sleep: exact times, no real waiting."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest
from _helpers import FakeClock, fake_sleep

from periodictimer import AsyncPeriodicTimer


def _drive(count: int, work: Any = None, **options: Any) -> tuple[list[float], AsyncPeriodicTimer]:
    clock = FakeClock(1000.0)
    times: list[float] = []

    async def record() -> None:
        times.append(clock.now)
        if work is not None:
            work(clock)

    async def main() -> AsyncPeriodicTimer:
        interval = options.pop("interval", 2.0)
        timer = AsyncPeriodicTimer(
            interval, record, clock=clock, sleep=fake_sleep(clock), **options
        )
        timer.start()
        assert timer.epoch == 1000.0
        while len(times) < count:
            await asyncio.sleep(0)
        await timer.aclose()
        return timer

    return times, asyncio.run(main())


def test_calls_land_exactly_on_the_slots() -> None:
    times, timer = _drive(4)
    assert times == [1002.0, 1004.0, 1006.0, 1008.0]
    assert timer.calls == 4


def test_immediate_fires_at_the_epoch() -> None:
    times, _ = _drive(2, immediate=True)
    assert times == [1000.0, 1002.0]


@pytest.mark.parametrize(
    ("policy", "expected", "missed"),
    [
        ("skip", [1002.0, 1010.0, 1012.0], 3),
        ("coalesce", [1002.0, 1009.0, 1010.0], 2),
        ("burst", [1002.0, 1009.0, 1009.0, 1009.0, 1010.0], 0),
    ],
)
def test_missed_slot_policies(policy: Any, expected: list[float], missed: int) -> None:
    def slow_first(clock: FakeClock) -> None:
        if clock.now == 1002.0:
            clock.now += 7.0

    times, timer = _drive(len(expected), slow_first, on_missed=policy)
    assert times[: len(expected)] == expected
    assert timer.missed == missed


def test_fixed_delay_waits_one_interval_after_each_call_ends() -> None:
    def slow(clock: FakeClock) -> None:
        clock.now += 0.5

    times, _ = _drive(3, slow, mode="fixed_delay")
    assert times == [1002.0, 1004.5, 1007.0]


def test_jitter_stays_within_bounds() -> None:
    times, _ = _drive(100, interval=1.0, jitter=0.3, rng=random.Random(4))
    offsets = [time - (1001.0 + index) for index, time in enumerate(times[:100])]
    assert all(0.0 <= offset <= 0.3 for offset in offsets)


def test_an_early_sleep_never_fires_before_the_slot() -> None:
    clock = FakeClock(0.0)
    times: list[float] = []

    async def short_sleep(delay: float) -> None:
        clock.now += delay / 2 if delay > 0.01 else delay
        await asyncio.sleep(0)

    async def main() -> None:
        async def record() -> None:
            times.append(clock.now)

        async with AsyncPeriodicTimer(1.0, record, clock=clock, sleep=short_sleep):
            while len(times) < 2:
                await asyncio.sleep(0)

    asyncio.run(main())
    assert times[0] >= 1.0
    assert times[1] >= 2.0


def test_plain_functions_are_accepted() -> None:
    calls: list[int] = []

    async def main() -> None:
        clock = FakeClock()

        def plain() -> None:
            calls.append(1)

        timer = AsyncPeriodicTimer(1.0, plain, clock=clock, sleep=fake_sleep(clock))  # type: ignore[arg-type]
        async with timer:
            while len(calls) < 3:
                await asyncio.sleep(0)

    asyncio.run(main())
    assert len(calls) >= 3


def test_uses_the_loop_clock_by_default() -> None:
    async def main() -> None:
        timer = AsyncPeriodicTimer(3600.0, asyncio.sleep)  # type: ignore[arg-type]
        loop = asyncio.get_running_loop()
        before = loop.time()
        async with timer:
            assert timer.epoch is not None
            assert before <= timer.epoch <= loop.time()

    asyncio.run(main())
