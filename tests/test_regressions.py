"""Regression tests for defects found in review, one per defect."""

from __future__ import annotations

import asyncio
import random
import sys
from typing import Any

import pytest
from _helpers import FakeClock

from periodictimer import AsyncPeriodicTimer, PeriodicTimer
from periodictimer._options import POLICIES, Policy
from periodictimer._schedule import Schedule

TIMERS: list[Any] = [PeriodicTimer, AsyncPeriodicTimer]


async def _noop() -> None:
    return None


def _sync() -> None:
    return None


def _fn(timer: Any) -> Any:
    return _noop if timer is AsyncPeriodicTimer else _sync


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("option", ["interval", "jitter"])
def test_a_number_too_large_for_a_float_is_a_value_error(timer: Any, option: str) -> None:
    with pytest.raises(ValueError, match=option):
        if option == "interval":
            timer(10**400, _fn(timer))
        else:
            timer(1.0, _fn(timer), jitter=10**400)


@pytest.mark.parametrize("timer", TIMERS)
def test_an_rng_without_uniform_is_refused_at_build(timer: Any) -> None:
    with pytest.raises(TypeError, match="rng"):
        timer(1.0, _fn(timer), rng=object())


@pytest.mark.parametrize("timer", TIMERS)
def test_immediate_must_be_a_real_bool(timer: Any) -> None:
    with pytest.raises(TypeError, match="immediate"):
        timer(1.0, _fn(timer), immediate="no")


def test_daemon_must_be_a_real_bool() -> None:
    with pytest.raises(TypeError, match="daemon"):
        PeriodicTimer(1.0, _sync, daemon="yes")  # type: ignore[arg-type]


@pytest.mark.parametrize("timer", TIMERS)
def test_an_async_on_error_is_refused_at_build(timer: Any) -> None:
    async def handler(exc: Exception) -> None:
        return None

    with pytest.raises(TypeError, match="on_error"):
        timer(1.0, _fn(timer), on_error=handler)


def test_an_on_error_returning_an_awaitable_stops_the_timer() -> None:
    clock = FakeClock()

    def boom() -> None:
        raise ValueError("boom")

    def waiter(delay: float) -> bool:
        clock.now += delay
        return False

    timer = PeriodicTimer(1.0, boom, on_error=lambda exc: _noop(), clock=clock, waiter=waiter)  # type: ignore[arg-type]
    timer.start()
    assert timer.join(5.0)
    assert timer.calls == 1


@pytest.mark.parametrize("policy", POLICIES)
def test_a_subnormal_interval_never_overflows_the_scheduler(policy: Policy) -> None:
    schedule = Schedule(
        0.0,
        1e-310,
        immediate=False,
        policy=policy,
        mode="fixed_rate",
        jitter=0.0,
        uniform=random.uniform,
    )
    schedule.fired(1.0)
    assert schedule.index == 2


@pytest.mark.parametrize("interval", [0.1, 0.3, 0.7, 1.1, 1e-3])
def test_inexact_intervals_never_start_early_or_repeat_a_slot(interval: float) -> None:
    rng = random.Random(interval)
    for policy in POLICIES:
        schedule = Schedule(
            0.0,
            interval,
            immediate=False,
            policy=policy,
            mode="fixed_rate",
            jitter=0.0,
            uniform=rng.uniform,
        )
        now, last = 0.0, 0
        for _ in range(2000):
            assert schedule.index > last
            assert schedule.index == 1 + schedule.calls + schedule.missed
            last = schedule.index
            start = max(now, schedule.due)
            now = start + rng.choice([0.0, interval * 0.3, interval * 2.7, interval * 5])
            schedule.fired(now)


def test_a_failing_clock_in_the_thread_timer_is_raised_by_join() -> None:
    readings: list[float] = []

    def clock() -> float:
        if len(readings) >= 2:
            raise OSError("clock gone")
        readings.append(0.0)
        return 0.0

    timer = PeriodicTimer(1.0, _sync, clock=clock, waiter=lambda d: False)
    timer.start()
    with pytest.raises(OSError, match="clock gone"):
        timer.join(5.0)
    assert not timer.is_running()


@pytest.mark.skipif(sys.version_info < (3, 12), reason="eager task factory arrived in 3.12")
def test_an_eager_task_factory_cannot_run_the_callback_inside_start() -> None:
    seen: list[str] = []
    holder: list[AsyncPeriodicTimer] = []

    async def probe() -> None:
        timer = holder[0]
        seen.append(f"running={timer.is_running()}")
        try:
            timer.start()
        except RuntimeError:
            seen.append("start refused")
        try:
            await timer.join()
        except RuntimeError:
            seen.append("join refused")
        timer.stop()

    async def main() -> None:
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)  # type: ignore[attr-defined]
        timer = AsyncPeriodicTimer(0.001, probe, immediate=True)
        holder.append(timer)
        timer.start()
        assert seen == []
        assert await timer.join(5.0)

    asyncio.run(main())
    assert seen == ["running=True", "start refused", "join refused"]
