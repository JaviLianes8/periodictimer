"""Start, stop, join and the context manager of the thread timer, on real time."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

import pytest

from periodictimer import PeriodicTimer


def test_cannot_be_started_twice() -> None:
    with PeriodicTimer(30.0, lambda: None) as timer, pytest.raises(RuntimeError, match="already"):
        timer.start()


def test_a_timer_stopped_before_start_refuses_to_start() -> None:
    timer = PeriodicTimer(30.0, lambda: None)
    timer.stop()
    with pytest.raises(RuntimeError, match="stopped"):
        timer.start()
    assert not timer.is_running()


def test_join_before_start_returns_true_at_once() -> None:
    assert PeriodicTimer(30.0, lambda: None).join() is True


def test_fires_several_times_then_stops_and_the_thread_is_gone() -> None:
    calls: list[float] = []
    done = threading.Event()

    def record() -> None:
        calls.append(time.monotonic())
        if len(calls) >= 3:
            done.set()

    with PeriodicTimer(0.01, record, name="ticker") as timer:
        assert timer.is_running()
        assert "running" in repr(timer)
        assert any(thread.name == "ticker" for thread in threading.enumerate())
        assert done.wait(5.0)
    assert not timer.is_running()
    assert all(thread.name != "ticker" for thread in threading.enumerate())
    assert timer.calls >= 3


def test_stop_interrupts_a_long_wait() -> None:
    timer = PeriodicTimer(3600.0, lambda: None)
    timer.start()
    begin = time.monotonic()
    timer.stop()
    assert timer.join(5.0)
    assert time.monotonic() - begin < 2.0


def test_a_huge_interval_waits_quietly_and_still_stops() -> None:
    timer = PeriodicTimer(1e300, lambda: None)
    timer.start()
    time.sleep(0.05)
    assert timer.is_running()
    timer.stop()
    assert timer.join(5.0)


def test_join_with_a_timeout_reports_a_call_still_running() -> None:
    entered = threading.Event()
    release = threading.Event()

    def block() -> None:
        entered.set()
        release.wait(10.0)

    timer = PeriodicTimer(30.0, block, immediate=True)
    timer.start()
    assert entered.wait(5.0)
    timer.stop()
    assert timer.join(0.05) is False
    release.set()
    assert timer.join(5.0) is True
    assert timer.calls == 1


def test_stop_from_inside_the_callback_ends_after_that_call() -> None:
    calls: list[int] = []
    holder: list[PeriodicTimer] = []

    def once() -> None:
        calls.append(1)
        holder[0].stop()

    timer = PeriodicTimer(0.001, once, immediate=True)
    holder.append(timer)
    timer.start()
    assert timer.join(5.0)
    assert calls == [1]


def test_join_from_inside_the_callback_raises_instead_of_hanging() -> None:
    errors: list[BaseException] = []
    holder: list[PeriodicTimer] = []

    def join_self() -> None:
        try:
            holder[0].join()
        except RuntimeError as exc:
            errors.append(exc)
        holder[0].stop()

    timer = PeriodicTimer(0.001, join_self, immediate=True)
    holder.append(timer)
    timer.start()
    assert timer.join(5.0)
    assert len(errors) == 1
    assert "own callback" in str(errors[0])


def test_daemon_flag_reaches_the_thread() -> None:
    for daemon in (True, False):
        with PeriodicTimer(30.0, lambda: None, daemon=daemon, name=f"d{daemon}") as timer:
            (thread,) = [t for t in threading.enumerate() if t.name == f"d{daemon}"]
            assert thread.daemon is daemon
        assert not timer.is_running()


@pytest.mark.parametrize("timeout", [math.inf, 1e300, -5.0, 0])
def test_join_accepts_any_non_nan_timeout(timeout: float) -> None:
    timer = PeriodicTimer(30.0, lambda: None)
    timer.start()
    timer.stop()
    assert timer.join(timeout) in (True, False)
    assert timer.join(5.0)


@pytest.mark.parametrize(("timeout", "error"), [(math.nan, ValueError), ("1", TypeError)])
def test_join_rejects_a_nonsense_timeout(timeout: Any, error: type[Exception]) -> None:
    with pytest.raises(error, match="timeout"):
        PeriodicTimer(30.0, lambda: None).join(timeout)


def test_without_immediate_nothing_fires_within_the_first_interval() -> None:
    fired = threading.Event()
    with PeriodicTimer(30.0, fired.set):
        assert not fired.wait(0.2)
