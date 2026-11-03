"""Overdue or unrepresentably close deadlines must still let the event loop progress."""

from __future__ import annotations

import asyncio
from typing import Literal

import pytest
from _helpers import FakeClock

from periodictimer import AsyncPeriodicTimer


@pytest.mark.parametrize(
    ("interval", "mode", "duration"),
    [(1.0, "fixed_rate", 2.0), (5e-324, "fixed_rate", 0.0), (5e-324, "fixed_delay", 0.0)],
)
def test_every_callback_yields_to_allow_stop(
    interval: float, mode: Literal["fixed_rate", "fixed_delay"], duration: float
) -> None:
    async def main() -> None:
        clock = FakeClock(8.0)
        calls: list[float] = []

        async def tick() -> None:
            calls.append(clock.now)
            clock.now += duration
            if len(calls) == 5:
                timer.stop()  # bound the test even if the worker never yields

        timer = AsyncPeriodicTimer(
            interval, tick, immediate=True, on_missed="burst", mode=mode, clock=clock
        )
        timer.start()
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert len(calls) == 1
        finally:
            await timer.aclose()
        assert timer.calls == 1

    asyncio.run(main())
