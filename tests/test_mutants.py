"""Tests that pin behaviour a mutation run found unguarded."""

from __future__ import annotations

from typing import Any

import pytest
from _helpers import FakeClock, fake_waiter

from periodictimer import PeriodicTimer


def test_join_refuses_a_bool_timeout() -> None:
    with pytest.raises(TypeError, match="timeout"):
        PeriodicTimer(1.0, lambda: None).join(True)


def test_stop_from_the_callback_wins_over_slots_already_past_due() -> None:
    clock = FakeClock(0.0)
    holder: list[PeriodicTimer] = []

    def overrun_then_stop() -> None:
        clock.now += 5.0  # three slots are past due when this call returns
        holder[0].stop()

    waiter = fake_waiter(clock, lambda: False)
    timer = PeriodicTimer(1.0, overrun_then_stop, on_missed="burst", clock=clock, waiter=waiter)
    holder.append(timer)
    timer.start()
    assert timer.join(5.0)
    assert timer.calls == 1


def test_a_coroutine_returned_by_the_callback_is_closed() -> None:
    async def work() -> None:
        return None

    made: list[Any] = []
    holder: list[PeriodicTimer] = []

    def make() -> Any:
        made.append(work())
        return made[-1]

    def handler(exc: Exception) -> None:
        holder[0].stop()

    timer = PeriodicTimer(0.001, make, immediate=True, on_error=handler)
    holder.append(timer)
    timer.start()
    assert timer.join(5.0)
    assert made
    assert all(coro.cr_frame is None for coro in made)
