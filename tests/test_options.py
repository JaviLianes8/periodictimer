from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer

TIMERS: list[Any] = [PeriodicTimer, AsyncPeriodicTimer]


async def _work() -> None:
    return None


def _sync_work() -> None:
    return None


def _make(timer: Any, interval: Any = 1.0, **options: Any) -> Any:
    return timer(interval, _work if timer is AsyncPeriodicTimer else _sync_work, **options)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("interval", [0, -1.0, math.nan, math.inf, -math.inf, Decimal("NaN")])
def test_rejects_an_interval_that_is_not_finite_and_positive(timer: Any, interval: Any) -> None:
    with pytest.raises(ValueError, match="interval"):
        _make(timer, interval)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("interval", [True, "1", None, 1j])
def test_rejects_an_interval_that_is_not_a_real_number(timer: Any, interval: Any) -> None:
    with pytest.raises(TypeError, match="interval"):
        _make(timer, interval)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("interval", [2, Fraction(1, 4), Decimal("0.5"), 1e-9, 1e300])
def test_accepts_any_finite_positive_real_and_stores_a_float(timer: Any, interval: Any) -> None:
    made = _make(timer, interval)
    assert made.interval == float(interval)
    assert type(made.interval) is float


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("jitter", [-0.1, 1.5, math.nan, math.inf])
def test_rejects_jitter_outside_zero_to_interval(timer: Any, jitter: float) -> None:
    with pytest.raises(ValueError, match="jitter"):
        _make(timer, jitter=jitter)


@pytest.mark.parametrize("timer", TIMERS)
def test_jitter_may_equal_the_interval_or_zero(timer: Any) -> None:
    _make(timer, jitter=1.0)
    _make(timer, jitter=0)


@pytest.mark.parametrize("timer", TIMERS)
def test_rejects_a_jitter_of_the_wrong_type(timer: Any) -> None:
    with pytest.raises(TypeError, match="jitter"):
        _make(timer, jitter=False)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("policy", ["later", "SKIP", "", None, 1])
def test_rejects_an_unknown_missed_tick_policy(timer: Any, policy: Any) -> None:
    with pytest.raises(ValueError, match="on_missed"):
        _make(timer, on_missed=policy)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("mode", ["rate", "fixed-delay", None])
def test_rejects_an_unknown_mode(timer: Any, mode: Any) -> None:
    with pytest.raises(ValueError, match="mode"):
        _make(timer, mode=mode)


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("hook", ["fn", "on_error", "clock"])
def test_rejects_a_hook_that_cannot_be_called(timer: Any, hook: str) -> None:
    with pytest.raises(TypeError, match=hook):
        if hook == "fn":
            timer(1.0, 42)
        else:
            _make(timer, **{hook: 42})


def test_rejects_a_waiter_or_a_sleep_that_cannot_be_called() -> None:
    with pytest.raises(TypeError, match="waiter"):
        PeriodicTimer(1.0, _sync_work, waiter=3)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="sleep"):
        AsyncPeriodicTimer(1.0, _work, sleep=3)  # type: ignore[arg-type]


def test_the_thread_timer_refuses_a_coroutine_function() -> None:
    with pytest.raises(TypeError, match="AsyncPeriodicTimer"):
        PeriodicTimer(1.0, _work)


@pytest.mark.parametrize("timer", TIMERS)
def test_counters_and_epoch_are_empty_before_start(timer: Any) -> None:
    made = _make(timer)
    assert (made.epoch, made.calls, made.missed) == (None, 0, 0)
    assert not made.is_running()
    assert "idle" in repr(made)
    assert "_work" in repr(made)
    assert "every 1.0s" in repr(made)
