"""The thread timer driven by a fake clock and waiter: exact times, no real waiting."""

from __future__ import annotations

import random
import threading
from typing import Any

import pytest
from _helpers import FakeClock, fake_waiter

from periodictimer import PeriodicTimer


def _drive(count: int, work: Any = None, **options: Any) -> tuple[list[float], PeriodicTimer]:
    """Start a timer on a fake clock at 1000.0 and collect the clock at each call."""
    clock = FakeClock(1000.0)
    times: list[float] = []

    def record() -> None:
        times.append(clock.now)
        if work is not None:
            work(clock)

    waiter = options.pop("waiter", None) or fake_waiter(clock, lambda: len(times) >= count)
    timer = PeriodicTimer(
        options.pop("interval", 2.0), record, clock=clock, waiter=waiter, **options
    )
    timer.start()
    assert timer.join(10.0)
    return times, timer


def test_epoch_is_set_by_start_before_the_worker_runs() -> None:
    clock = FakeClock(55.0)
    gate = threading.Event()
    timer = PeriodicTimer(1.0, lambda: None, clock=clock, waiter=lambda delay: gate.wait())
    timer.start()
    assert timer.epoch == 55.0
    gate.set()
    assert timer.join(5.0)


def test_calls_land_exactly_on_the_slots() -> None:
    times, timer = _drive(5)
    assert times == [1002.0, 1004.0, 1006.0, 1008.0, 1010.0]
    assert (timer.epoch, timer.calls, timer.missed) == (1000.0, 5, 0)


def test_immediate_fires_at_the_epoch() -> None:
    times, _ = _drive(3, immediate=True)
    assert times == [1000.0, 1002.0, 1004.0]


def test_late_wakeups_never_shift_the_schedule() -> None:
    clock_late = FakeClock(1000.0)
    seen: list[float] = []
    calls: list[float] = []
    waiter = fake_waiter(clock_late, lambda: len(calls) >= 5, late=0.3, seen=seen)
    timer = PeriodicTimer(
        2.0, lambda: calls.append(clock_late.now), clock=clock_late, waiter=waiter
    )
    timer.start()
    assert timer.join(10.0)
    assert calls == [1002.3, 1004.3, 1006.3, 1008.3, 1010.3]
    assert seen[:3] == pytest.approx([2.0, 1.7, 1.7])


def test_an_early_wakeup_never_fires_before_the_slot() -> None:
    clock = FakeClock(0.0)
    seen: list[float] = []
    calls: list[float] = []
    waiter = fake_waiter(clock, lambda: len(calls) >= 3, early=0.5, seen=seen)
    timer = PeriodicTimer(4.0, lambda: calls.append(clock.now), clock=clock, waiter=waiter)
    timer.start()
    assert timer.join(10.0)
    assert calls == [4.0, 8.0, 12.0]
    assert seen[:2] == [4.0, 0.5]


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
            clock.now += 7.0  # the first call runs past three slots

    times, timer = _drive(len(expected), slow_first, on_missed=policy)
    assert times == expected
    assert timer.missed == missed
    assert timer.calls == len(expected)


def test_fixed_delay_waits_one_interval_after_each_call_ends() -> None:
    def slow(clock: FakeClock) -> None:
        clock.now += 0.5

    times, timer = _drive(4, slow, mode="fixed_delay")
    assert times == [1002.0, 1004.5, 1007.0, 1009.5]
    assert timer.missed == 0


def test_jitter_delays_calls_without_moving_the_slots() -> None:
    times, _ = _drive(200, interval=1.0, jitter=0.25, rng=random.Random(3))
    offsets = [time - (1001.0 + index) for index, time in enumerate(times)]
    assert all(0.0 <= offset <= 0.25 for offset in offsets)
    assert len(set(offsets)) > 100


def test_jitter_is_reproducible_with_a_seeded_rng() -> None:
    first, _ = _drive(20, interval=1.0, jitter=0.5, rng=random.Random(9))
    second, _ = _drive(20, interval=1.0, jitter=0.5, rng=random.Random(9))
    assert first == second


def test_waits_are_capped_at_the_threading_limit() -> None:
    clock = FakeClock(0.0)
    seen: list[float] = []

    def waiter(delay: float) -> bool:
        seen.append(delay)
        return True

    timer = PeriodicTimer(1e300, lambda: None, clock=clock, waiter=waiter)
    timer.start()
    assert timer.join(5.0)
    assert seen == [threading.TIMEOUT_MAX]


def test_a_waiter_returning_true_stops_without_a_call() -> None:
    calls: list[int] = []
    timer = PeriodicTimer(1.0, lambda: calls.append(1), clock=FakeClock(), waiter=lambda d: True)
    timer.start()
    assert timer.join(5.0)
    assert calls == []
    assert timer.calls == 0
