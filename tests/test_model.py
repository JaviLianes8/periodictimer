"""The scheduler agrees with a brute-force model on thousands of random timelines."""

from __future__ import annotations

import random

import pytest

from periodictimer._options import POLICIES, Policy
from periodictimer._schedule import Schedule


def _model(
    interval: float, immediate: bool, policy: Policy, durations: list[float]
) -> tuple[list[tuple[int, float]], int]:
    """Walk the slots one by one: the slow, obvious version of the policies."""
    starts: list[tuple[int, float]] = []
    now = 0.0
    slot = 0 if immediate else 1
    missed = 0
    for duration in durations:
        start = max(now, slot * interval)
        starts.append((slot, start))
        now = start + duration
        late = []
        candidate = slot + 1
        while candidate * interval < now:
            late.append(candidate)
            candidate += 1
        if policy == "burst" or not late:
            slot += 1
        elif policy == "skip":
            missed += len(late)
            slot = candidate
        else:
            # One call stands in for every slot due by now, including one due exactly now.
            if candidate * interval == now:
                late.append(candidate)
            missed += len(late) - 1
            slot = late[-1]
    return starts, missed


def _real(
    interval: float, immediate: bool, policy: Policy, durations: list[float]
) -> tuple[list[tuple[int, float]], int]:
    schedule = Schedule(
        0.0,
        interval,
        immediate=immediate,
        policy=policy,
        mode="fixed_rate",
        jitter=0.0,
        uniform=random.uniform,
    )
    starts: list[tuple[int, float]] = []
    now = 0.0
    for duration in durations:
        start = max(now, schedule.due)
        starts.append((schedule.index, start))
        now = start + duration
        schedule.fired(now)
    assert schedule.calls == len(durations)
    return starts, schedule.missed


@pytest.mark.parametrize("seed", range(40))
def test_scheduler_matches_the_model(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(50):
        # Binary fractions keep every sum exact, so the model and the code see equal times.
        interval = rng.choice([0.25, 0.5, 1.0, 2.0])
        durations = [rng.choice([0.0, 0.125, 0.25, 0.75, 1.0, 2.5, 4.0]) for _ in range(30)]
        immediate = rng.random() < 0.5
        for policy in POLICIES:
            expected = _model(interval, immediate, policy, durations)
            assert _real(interval, immediate, policy, durations) == expected


@pytest.mark.parametrize("policy", POLICIES)
def test_call_index_is_first_slot_plus_calls_plus_missed(policy: Policy) -> None:
    rng = random.Random(policy)
    schedule = Schedule(
        0.0, 1.0, immediate=False, policy=policy, mode="fixed_rate", jitter=0.0, uniform=rng.uniform
    )
    now = 0.0
    for _ in range(200):
        assert schedule.index == 1 + schedule.calls + schedule.missed
        start = max(now, schedule.due)
        assert start >= schedule.index * 1.0
        now = start + rng.choice([0.0, 0.5, 3.25])
        schedule.fired(now)
