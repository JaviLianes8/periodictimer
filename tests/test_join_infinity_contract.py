"""Infinite joins wait for active callbacks to complete on both timers."""

from __future__ import annotations

import asyncio
import math
import threading

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


def test_thread_infinite_join_waits_for_active_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def callback() -> None:
        entered.set()
        release.wait()
        timer.stop()
        completed.set()

    timer = PeriodicTimer(1, callback, immediate=True)
    timer.start()
    original_join = timer._thread.join

    def join(timeout: float | None = None) -> None:
        # Release only at the blocking boundary, avoiding thread scheduling races.
        assert not completed.is_set()
        assert timeout is None, "infinite join must wait without a timeout"
        release.set()
        original_join(timeout)

    try:
        assert entered.wait(5)
        monkeypatch.setattr(timer._thread, "join", join)
        assert timer.join(math.inf) is True
        assert completed.is_set()
        assert timer.calls == 1
    finally:
        release.set()
        timer.stop()
        original_join(5)
        assert not timer._thread.is_alive()


def test_async_infinite_join_waits_for_active_callback() -> None:
    async def main() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        completed = asyncio.Event()

        async def callback() -> None:
            entered.set()
            await release.wait()
            timer.stop()
            completed.set()

        timer = AsyncPeriodicTimer(1, callback, immediate=True)
        timer.start()
        joining = asyncio.create_task(timer.join(math.inf))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            for _ in range(10):
                await asyncio.sleep(0)
            assert not joining.done(), "infinite join returned before callback completion"
            assert not completed.is_set()
            release.set()
            assert await asyncio.wait_for(joining, 5) is True
            assert completed.is_set()
            assert timer.calls == 1
        finally:
            release.set()
            await timer.aclose()
            await joining

    asyncio.run(main())
