"""Fractional joins preserve their budget and wait for callback completion."""

from __future__ import annotations

import asyncio
import threading

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


def test_thread_fractional_join_waits_for_active_callback(monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert timeout == 0.75, "fractional join must preserve the timeout"
        assert not completed.is_set()
        # Release at the wait boundary so scheduling cannot hide a truncated timeout.
        release.set()
        original_join(timeout)

    try:
        assert entered.wait(5)
        with monkeypatch.context() as patch:
            patch.setattr(timer._thread, "join", join)
            assert timer.join(0.75) is True
        assert completed.is_set()
        assert not timer.is_running()
        assert timer.calls == 1
    finally:
        release.set()
        timer.stop()
        original_join(5)
        assert not timer.is_running()


def test_async_fractional_join_waits_for_active_callback(monkeypatch: pytest.MonkeyPatch) -> None:
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
            assert timeout == 0.75, "fractional join must preserve the timeout"
            assert not completed.is_set()
            release.set()
            return await original_wait(tasks, timeout=timeout)

        try:
            await asyncio.wait_for(entered.wait(), 5)
            with monkeypatch.context() as patch:
                patch.setattr(asyncio, "wait", wait)
                assert await timer.join(0.75) is True
            assert completed.is_set()
            assert not timer.is_running()
            assert timer.calls == 1
        finally:
            release.set()
            await asyncio.wait_for(timer.aclose(), 5)
            assert not timer.is_running()

    asyncio.run(main())
