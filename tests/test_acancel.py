"""The asyncio timer's own cancel from stop() never hides or leaves behind another one."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer

pytestmark = pytest.mark.skipif(sys.version_info < (3, 11), reason="Task.uncancel is 3.11+")


async def _noop() -> None:
    return None


def test_an_outside_cancel_together_with_stop_still_cancels_the_task() -> None:
    async def main() -> None:
        timer = AsyncPeriodicTimer(3600.0, _noop)
        timer.start()
        await asyncio.sleep(0.01)
        task: Any = timer._task
        timer.stop()
        task.cancel()
        await asyncio.wait({task}, timeout=5.0)
        assert task.cancelled()

    asyncio.run(main())


def test_a_sleep_that_swallows_the_cancel_leaves_no_count_behind() -> None:
    async def stubborn_sleep(delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return None

    async def main() -> None:
        timer = AsyncPeriodicTimer(3600.0, _noop, sleep=stubborn_sleep)
        timer.start()
        await asyncio.sleep(0.01)
        timer.stop()
        assert await timer.join(5.0)
        task: Any = timer._task
        assert not task.cancelled()
        assert task.cancelling() == 0

    asyncio.run(main())


def test_stop_inside_a_timeout_scope_does_not_trip_the_timeout() -> None:
    async def main() -> None:
        async with asyncio.timeout(5.0):  # type: ignore[attr-defined]
            async with AsyncPeriodicTimer(3600.0, _noop):
                await asyncio.sleep(0.01)
        current: Any = asyncio.current_task()
        assert current.cancelling() == 0

    asyncio.run(main())
