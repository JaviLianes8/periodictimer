from __future__ import annotations

import threading
import time

import pytest

from periodictimer import PeriodicTimer


class _FakeClock:
    """A clock whose value only moves when a test moves it."""

    def __init__(self, start: float) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_rejects_a_non_positive_interval() -> None:
    with pytest.raises(ValueError):
        PeriodicTimer(0, lambda: None)


def test_rejects_an_unknown_missed_tick_policy() -> None:
    with pytest.raises(ValueError):
        PeriodicTimer(1.0, lambda: None, on_missed="later")  # type: ignore[arg-type]


def test_cannot_be_started_twice() -> None:
    timer = PeriodicTimer(30.0, lambda: None)
    timer.start()
    try:
        with pytest.raises(RuntimeError):
            timer.start()
    finally:
        timer.stop()
        timer.join(1.0)


def test_fires_several_times_then_stops() -> None:
    calls: list[float] = []
    done = threading.Event()

    def record() -> None:
        calls.append(time.monotonic())
        if len(calls) >= 3:
            done.set()

    timer = PeriodicTimer(0.01, record)
    timer.start()
    assert done.wait(2.0)
    timer.stop()
    timer.join(1.0)
    assert not timer.is_running()
    assert len(calls) >= 3


def test_stop_returns_long_before_the_interval_elapses() -> None:
    fired = threading.Event()
    timer = PeriodicTimer(30.0, fired.set, immediate=True)
    timer.start()
    assert fired.wait(2.0)
    begin = time.monotonic()
    timer.stop()
    timer.join(2.0)
    assert not timer.is_running()
    assert time.monotonic() - begin < 5.0


def test_immediate_runs_before_the_first_interval() -> None:
    fired = threading.Event()
    timer = PeriodicTimer(30.0, fired.set, immediate=True)
    timer.start()
    try:
        assert fired.wait(2.0)
    finally:
        timer.stop()
        timer.join(2.0)


def test_without_immediate_nothing_fires_within_the_first_interval() -> None:
    fired = threading.Event()
    timer = PeriodicTimer(30.0, fired.set)
    timer.start()
    try:
        assert not fired.wait(0.3)
    finally:
        timer.stop()
        timer.join(2.0)


def test_a_callback_exception_does_not_kill_the_timer() -> None:
    calls: list[int] = []
    errors: list[Exception] = []
    done = threading.Event()

    def boom() -> None:
        calls.append(1)
        if len(calls) >= 3:
            done.set()
        raise ValueError("boom")

    timer = PeriodicTimer(0.01, boom, on_error=errors.append)
    timer.start()
    assert done.wait(2.0)
    timer.stop()
    timer.join(1.0)
    assert len(calls) >= 3
    assert len(errors) >= 3
    assert all(isinstance(error, ValueError) for error in errors)


def test_ticks_stay_aligned_to_the_epoch_even_when_wakeups_run_late() -> None:
    clock = _FakeClock(1000.0)
    targets: list[float] = []

    def waiter(delay: float) -> bool:
        target = clock.now + delay
        targets.append(target)
        clock.now = target + 0.3  # wake up 0.3s late every time
        return len(targets) >= 5

    timer = PeriodicTimer(2.0, lambda: None, clock=clock, waiter=waiter)
    timer._run()  # drive the loop synchronously; the waiter stops it after five ticks

    assert targets == [1002.0, 1004.0, 1006.0, 1008.0, 1010.0]
    assert timer.epoch == 1000.0
