"""Differential timelines against real stdlib sched and a pinned fetched implementation."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import random
import sched
from pathlib import Path
from typing import Any

import pytest
from _helpers import FakeClock

from periodictimer import AsyncPeriodicTimer, PeriodicTimer

MANIFEST = Path(__file__).parent / "upstream/MANIFEST.json"


def _reference(factory: Any, durations: list[float], delay: bool, immediate: bool) -> list[float]:
    clock = FakeClock(8.0)

    def advance(seconds: float) -> None:
        clock.now += seconds

    queue = factory(clock, advance)
    seen: list[float] = []

    def record(index: int) -> None:
        seen.append(clock.now)
        clock.now += durations[index]
        if delay and index + 1 < len(durations):
            queue.enter(0.5, 1, record, (index + 1,))

    for index in range(1 if delay else len(durations)):
        queue.enterabs(8.0 + (index + (not immediate)) * 0.5, 1, record, (index,))
    queue.run()
    assert queue.empty()
    return seen


def _thread(durations: list[float], delay: bool, immediate: bool) -> list[float]:
    clock = FakeClock(8.0)
    seen: list[float] = []

    def record() -> None:
        seen.append(clock.now)
        clock.now += durations[len(seen) - 1]
        if len(seen) == len(durations):
            timer.stop()

    def wait(seconds: float) -> bool:
        clock.now += seconds
        return False

    timer = PeriodicTimer(
        0.5,
        record,
        clock=clock,
        waiter=wait,
        immediate=immediate,
        on_missed="burst",
        mode="fixed_delay" if delay else "fixed_rate",
    )
    timer.start()
    assert timer.join(5)
    assert (timer.calls, timer.missed) == (len(durations), 0)
    return seen


async def _async(durations: list[float], delay: bool, immediate: bool) -> list[float]:
    clock = FakeClock(8.0)
    seen: list[float] = []

    async def record() -> None:
        seen.append(clock.now)
        clock.now += durations[len(seen) - 1]
        if len(seen) == len(durations):
            timer.stop()

    async def sleep(seconds: float) -> None:
        clock.now += seconds
        await asyncio.sleep(0)

    timer = AsyncPeriodicTimer(
        0.5,
        record,
        clock=clock,
        sleep=sleep,
        immediate=immediate,
        on_missed="burst",
        mode="fixed_delay" if delay else "fixed_rate",
    )
    timer.start()
    assert await timer.join(5)
    assert (timer.calls, timer.missed) == (len(durations), 0)
    return seen


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("delay", [False, True])
@pytest.mark.parametrize("immediate", [False, True])
def test_both_timers_match_real_stdlib_scheduler(seed: int, delay: bool, immediate: bool) -> None:
    rng = random.Random(seed)
    for _ in range(20):
        # Synthetic workloads, not external vectors; expected starts come from sched.run().
        durations = [rng.choice([0, 0.125, 0.5, 1, 3.5]) for _ in range(40)]
        expected = _reference(sched.scheduler, durations, delay, immediate)
        assert _thread(durations, delay, immediate) == expected
        assert asyncio.run(_async(durations, delay, immediate)) == expected


def _fetched(name: str) -> Path:
    directory = os.environ.get("PERIODICTIMER_UPSTREAM")
    if not directory:
        pytest.skip("set PERIODICTIMER_UPSTREAM to the fetched reference directory")
    path = Path(directory) / name
    if not path.exists():
        pytest.skip(f"fetch reference file: {name}")
    entry = next(e for e in json.loads(MANIFEST.read_text()) if e["file"] == name)
    data = path.read_bytes()
    assert len(data) == entry["size"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    return path


@pytest.mark.parametrize(
    "name", ["sched.py", "sched.rst", "threading.rst", "time.rst", "asyncio-task.rst"]
)
def test_fetched_reference_integrity(name: str) -> None:
    _fetched(name)


def test_fetched_cpython_scheduler_produces_the_same_timelines() -> None:
    path = _fetched("sched.py")
    spec = importlib.util.spec_from_file_location("reference_sched", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rng = random.Random(20261101)
    for delay in (False, True):
        for immediate in (False, True):
            for _ in range(50):
                durations = [rng.choice([0, 0.125, 0.5, 1, 3.5]) for _ in range(40)]
                expected = _reference(module.scheduler, durations, delay, immediate)
                assert _thread(durations, delay, immediate) == expected
                assert asyncio.run(_async(durations, delay, immediate)) == expected
