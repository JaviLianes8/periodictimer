"""Many timers at once on real time: never early, never overlapping, nothing left behind."""

from __future__ import annotations

import asyncio
import random
import threading
import time
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer
from periodictimer._options import POLICIES

RUN_SECONDS = 0.6


class _Probe:
    """Checks one timer's invariants from inside its own callback."""

    def __init__(self, seed: int, interval: float, immediate: bool) -> None:
        self.rng = random.Random(seed)
        self.interval = interval
        self.first = 0 if immediate else 1
        self.active = 0
        self.ended: float | None = None
        self.problems: list[str] = []
        self.timer: Any = None

    def enter(self, now: float, fixed_delay: bool) -> float:
        timer = self.timer
        self.active += 1
        if self.active > 1:
            self.problems.append("overlap")
        if fixed_delay:
            if self.ended is not None and now < self.ended + self.interval:
                self.problems.append(f"fixed delay too short at {now}")
        else:
            slot = self.first + timer.calls + timer.missed
            if now < timer.epoch + slot * self.interval:
                self.problems.append(f"slot {slot} fired early at {now}")
        return self.rng.choice([0.0, 0.0, self.interval * 0.5, self.interval * 2.5])

    def leave(self, now: float) -> None:
        self.ended = now
        self.active -= 1


def _options(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    return {
        "interval": rng.choice([0.002, 0.005, 0.01]),
        "immediate": rng.random() < 0.5,
        "fixed_delay": rng.random() < 0.25,
    }


@pytest.mark.parametrize("policy", POLICIES)
def test_thread_timers_keep_their_invariants(policy: Any) -> None:
    before = set(threading.enumerate())
    probes: list[_Probe] = []
    for seed in range(16):
        opts = _options(seed)
        probe = _Probe(seed, opts["interval"], opts["immediate"])

        def work(probe: _Probe = probe, fixed_delay: bool = opts["fixed_delay"]) -> None:
            time.sleep(probe.enter(time.monotonic(), fixed_delay))
            probe.leave(time.monotonic())

        probe.timer = PeriodicTimer(
            opts["interval"],
            work,
            immediate=opts["immediate"],
            on_missed=policy,
            mode="fixed_delay" if opts["fixed_delay"] else "fixed_rate",
        )
        probes.append(probe)
    for probe in probes:
        probe.timer.start()
    time.sleep(RUN_SECONDS)
    for probe in probes:
        probe.timer.stop()
    assert all(probe.timer.join(10.0) for probe in probes)
    assert set(threading.enumerate()) <= before
    for probe in probes:
        assert probe.problems == []
        assert probe.timer.calls > 0
        if policy == "burst":
            assert probe.timer.missed == 0


@pytest.mark.parametrize("policy", POLICIES)
def test_async_timers_keep_their_invariants(policy: Any) -> None:
    probes: list[_Probe] = []

    async def main() -> None:
        loop = asyncio.get_running_loop()
        for seed in range(32):
            opts = _options(seed)
            probe = _Probe(seed, opts["interval"], opts["immediate"])

            async def work(probe: _Probe = probe, fixed_delay: bool = opts["fixed_delay"]) -> None:
                await asyncio.sleep(probe.enter(loop.time(), fixed_delay))
                probe.leave(loop.time())

            probe.timer = AsyncPeriodicTimer(
                opts["interval"],
                work,
                immediate=opts["immediate"],
                on_missed=policy,
                mode="fixed_delay" if opts["fixed_delay"] else "fixed_rate",
            )
            probes.append(probe)
            probe.timer.start()
        await asyncio.sleep(RUN_SECONDS)
        await asyncio.gather(*(probe.timer.aclose() for probe in probes))
        assert all(not probe.timer.is_running() for probe in probes)
        others = asyncio.all_tasks() - {asyncio.current_task()}
        assert others == set()

    asyncio.run(asyncio.wait_for(main(), 30.0))
    for probe in probes:
        assert probe.problems == []
        assert probe.timer.calls > 0
        if policy == "burst":
            assert probe.timer.missed == 0
