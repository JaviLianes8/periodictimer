from __future__ import annotations

import pytest

from periodictimer._schedule import first_index, next_index, target_time


def test_first_index_depends_on_immediate() -> None:
    assert first_index(True) == 0
    assert first_index(False) == 1


def test_target_is_an_exact_multiple_of_interval_from_the_epoch() -> None:
    for index in range(100):
        assert target_time(10.0, 0.25, index) == 10.0 + index * 0.25


def test_consecutive_targets_keep_a_constant_period() -> None:
    previous = target_time(5.0, 0.1, 0)
    for index in range(1, 50):
        current = target_time(5.0, 0.1, index)
        assert current - previous == pytest.approx(0.1)
        previous = current


def test_skip_coalesces_every_missed_tick_into_the_next_future_slot() -> None:
    # Tick 1 fired at epoch + interval, then the callback ran until now = 4.5 intervals in.
    assert next_index(0.0, 1.0, 1, now=4.5, policy="skip") == 5


def test_skip_without_a_miss_steps_one_slot() -> None:
    assert next_index(0.0, 1.0, 1, now=1.0, policy="skip") == 2


def test_burst_steps_one_slot_so_past_due_ticks_fire_back_to_back() -> None:
    assert next_index(0.0, 1.0, 1, now=4.5, policy="burst") == 2
