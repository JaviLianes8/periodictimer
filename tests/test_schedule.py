from __future__ import annotations

import random

import pytest

from periodictimer._options import POLICIES, Policy
from periodictimer._schedule import Schedule, first_index, next_index, target_time


def _schedule(policy: Policy = "skip", **options: object) -> Schedule:
    settings: dict[str, object] = {
        "immediate": False,
        "policy": policy,
        "mode": "fixed_rate",
        "jitter": 0.0,
        "uniform": random.Random(0).uniform,
    }
    settings.update(options)
    return Schedule(0.0, 1.0, **settings)  # type: ignore[arg-type]


def test_first_index_depends_on_immediate() -> None:
    assert first_index(True) == 0
    assert first_index(False) == 1


def test_target_is_an_exact_multiple_of_interval_from_the_epoch() -> None:
    for index in range(100):
        assert target_time(10.0, 0.25, index) == 10.0 + index * 0.25


def test_without_a_miss_every_policy_steps_one_slot() -> None:
    for policy in POLICIES:
        assert next_index(0.0, 1.0, 1, now=1.5, policy=policy) == 2


def test_a_slot_due_exactly_now_is_not_missed() -> None:
    for policy in POLICIES:
        assert next_index(0.0, 1.0, 1, now=2.0, policy=policy) == 2


def test_skip_waits_for_the_first_slot_not_yet_past() -> None:
    assert next_index(0.0, 1.0, 1, now=4.5, policy="skip") == 5
    assert next_index(0.0, 1.0, 1, now=4.0, policy="skip") == 4


def test_coalesce_fires_the_latest_missed_slot_at_once() -> None:
    assert next_index(0.0, 1.0, 1, now=4.5, policy="coalesce") == 4


def test_burst_steps_one_slot_so_past_due_slots_fire_back_to_back() -> None:
    assert next_index(0.0, 1.0, 1, now=4.5, policy="burst") == 2


def test_a_clock_before_the_epoch_never_moves_the_schedule_back() -> None:
    for policy in POLICIES:
        assert next_index(10.0, 1.0, 3, now=-50.0, policy=policy) == 4


@pytest.mark.parametrize(
    ("policy", "missed", "due"), [("skip", 3, 5.0), ("coalesce", 2, 4.0), ("burst", 0, 2.0)]
)
def test_fired_counts_calls_and_missed_slots(policy: Policy, missed: int, due: float) -> None:
    schedule = _schedule(policy)
    assert schedule.due == 1.0
    schedule.fired(4.5)
    assert (schedule.calls, schedule.missed, schedule.due) == (1, missed, due)


def test_fixed_delay_waits_one_interval_after_each_call_ends() -> None:
    schedule = _schedule(mode="fixed_delay", immediate=True)
    assert schedule.due == 0.0
    schedule.fired(3.7)
    assert schedule.due == 4.7
    schedule.fired(4.9)
    assert (schedule.due, schedule.missed, schedule.calls) == (5.9, 0, 2)


def test_jitter_delays_each_call_within_bounds_and_never_moves_the_slots() -> None:
    schedule = _schedule(policy="burst", jitter=0.4, uniform=random.Random(7).uniform)
    offsets = []
    for slot in range(1, 500):
        offsets.append(schedule.due - slot)
        schedule.fired(schedule.due)
    assert all(0.0 <= offset <= 0.4 for offset in offsets)
    assert max(offsets) > 0.3
    assert min(offsets) < 0.1


def test_jitter_applies_after_a_fixed_delay_too() -> None:
    schedule = _schedule(mode="fixed_delay", jitter=0.5, uniform=lambda low, high: high)
    schedule.fired(10.0)
    assert schedule.due == 11.5
