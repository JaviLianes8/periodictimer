"""Negative joins poll without waiting for active callbacks to finish."""

from __future__ import annotations

import asyncio
import math
import threading

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


@pytest.mark.parametrize("timeout", [-60.0, -0.25, -5e-324, -1e300, -math.inf])
def test_thread_negative_join_polls_active_callback(
    timeout: float, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        # Check the blocking boundary without relying on elapsed wall-clock time.
        assert timeout == 0.0, "negative join must poll with a zero timeout"
        original_join(timeout)

    try:
        assert entered.wait(5)
        with monkeypatch.context() as patch:
            patch.setattr(timer._thread, "join", join)
            assert timer.join(timeout) is False
        assert not completed.is_set()
        assert timer.is_running()
        assert timer.calls == 0
    finally:
        release.set()
        timer.stop()
        original_join(5)
        assert not timer.is_running()
    assert completed.is_set()
    assert timer.calls == 1


@pytest.mark.parametrize("timeout", [-60.0, -0.25, -5e-324, -1e300, -math.inf])
def test_async_negative_join_polls_active_callback(
    timeout: float, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        original_wait = asyncio.wait

        async def wait(
            tasks: set[asyncio.Task[None]], *, timeout: float | None = None
        ) -> tuple[set[asyncio.Task[None]], set[asyncio.Task[None]]]:
            # Delegate the zero-timeout poll to the real event loop.
            assert timeout == 0.0, "negative join must poll with a zero timeout"
            return await original_wait(tasks, timeout=timeout)

        try:
            await asyncio.wait_for(entered.wait(), 5)
            with monkeypatch.context() as patch:
                patch.setattr(asyncio, "wait", wait)
                assert await timer.join(timeout) is False
            assert not completed.is_set()
            assert timer.is_running()
            assert timer.calls == 0
        finally:
            release.set()
            await asyncio.wait_for(timer.aclose(), 5)
            assert not timer.is_running()
        assert completed.is_set()
        assert timer.calls == 1

    asyncio.run(main())
