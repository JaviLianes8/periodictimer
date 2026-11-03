"""Stable constructors, read-only state and executable public documentation."""

from __future__ import annotations

import doctest
import importlib
import inspect
import random
import time
from collections.abc import Callable

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer

TIMERS = [PeriodicTimer, AsyncPeriodicTimer]


@pytest.mark.parametrize("timer", TIMERS)
def test_constructor_names_kinds_and_defaults(
    timer: type[PeriodicTimer | AsyncPeriodicTimer],
) -> None:
    parameters = inspect.signature(timer).parameters
    expected: dict[str, object] = {
        "interval": inspect.Parameter.empty,
        "fn": inspect.Parameter.empty,
        "immediate": False,
        "on_missed": "skip",
        "mode": "fixed_rate",
        "jitter": 0.0,
        "rng": None,
        "on_error": None,
        "name": None,
    }
    if timer is PeriodicTimer:
        expected.update(daemon=True, clock=time.monotonic, waiter=None)
    else:
        expected.update(clock=None, sleep=None)
    assert list(parameters) == list(expected)
    for name, default in expected.items():
        assert parameters[name].default == default
        assert parameters[name].kind == (
            inspect.Parameter.POSITIONAL_OR_KEYWORD
            if name in ("interval", "fn")
            else inspect.Parameter.KEYWORD_ONLY
        )


@pytest.mark.parametrize("timer", TIMERS)
def test_complete_public_method_and_property_surface(
    timer: type[PeriodicTimer | AsyncPeriodicTimer],
) -> None:
    names = {name for name in dir(timer) if not name.startswith("_")}
    assert names == {
        "interval",
        "epoch",
        "calls",
        "missed",
        "start",
        "stop",
        "join",
        "is_running",
    } | ({"aclose"} if timer is AsyncPeriodicTimer else set())
    for name in names:
        member = getattr(timer, name)
        assert ">>>" in (inspect.getdoc(member) or ""), name
    for name in ("start", "stop", "is_running"):
        assert list(inspect.signature(getattr(timer, name)).parameters) == ["self"]
    join = inspect.signature(timer.join).parameters
    assert list(join) == ["self", "timeout"]
    assert join["timeout"].default is None


@pytest.mark.parametrize("name", ["interval", "epoch", "calls", "missed"])
def test_state_properties_are_read_only(name: str) -> None:
    for timer in TIMERS:
        prop = getattr(timer, name)
        assert isinstance(prop, property)
        assert prop.fset is None


@pytest.mark.parametrize("module", ["_timer", "_atimer", "_base"])
def test_all_public_doctests_including_inherited_properties(module: str) -> None:
    result = doctest.testmod(importlib.import_module(f"periodictimer.{module}"))
    assert result.attempted > 0
    assert result.failed == 0


def test_jitter_never_draws_from_rng_when_disabled() -> None:
    class NoDraw(random.Random):
        def uniform(self, a: float, b: float) -> float:
            raise AssertionError("zero jitter must not consume randomness")

    timer = PeriodicTimer(1, lambda: None, rng=NoDraw(), waiter=lambda delay: True)
    timer.start()
    assert timer.join(5)


def test_join_preserves_worker_exception_identity() -> None:
    error = OSError("clock unavailable")
    readings = iter([0.0])

    def clock() -> float:
        value = next(readings, None)
        if value is None:
            raise error
        return value

    timer = PeriodicTimer(1, lambda: None, clock=clock)
    timer.start()
    for _ in range(2):
        with pytest.raises(OSError) as caught:
            timer.join(5)
        assert caught.value is error


def test_thread_join_normalizes_an_overflowing_negative_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timer = PeriodicTimer(3600, lambda: None)
    timer.start()
    original: Callable[[float | None], None] = timer._thread.join
    seen: list[float | None] = []
    try:
        monkeypatch.setattr(timer._thread, "join", seen.append)
        assert timer.join(-(10**400)) is False
        assert seen == [0.0]
    finally:
        timer.stop()
        original(5)
