"""Bounded validation messages and timeout edge cases through the public API."""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


async def _noop() -> None:
    pass


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option", ["on_missed", "mode"])
def test_policy_errors_never_echo_input(timer: Any, option: str) -> None:
    for value in ("secret-" * 100_000, 10**5000):
        with pytest.raises(ValueError) as caught:
            timer(1, _noop if timer is AsyncPeriodicTimer else lambda: None, **{option: value})
        assert option in str(caught.value)
        assert "secret" not in str(caught.value)
        assert len(str(caught.value)) < 100


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
def test_type_errors_do_not_echo_type_names(timer: Any) -> None:
    value = type("secret" * 10_000, (), {})()
    with pytest.raises(TypeError) as caught:
        timer(value, _noop if timer is AsyncPeriodicTimer else lambda: None)
    assert str(caught.value) == "interval must be a real number"


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
def test_signalling_nan_errors_name_the_invalid_option(timer: Any) -> None:
    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    for option in ("interval", "jitter"):
        kwargs = {"interval": 1, "fn": callback, option: Decimal("sNaN")}
        with pytest.raises(ValueError, match=option):
            timer(**kwargs)


def test_thread_clock_cannot_be_none() -> None:
    with pytest.raises(TypeError, match="clock"):
        PeriodicTimer(1, lambda: None, clock=None)  # type: ignore[arg-type]


def test_async_huge_negative_join_returns_while_worker_is_running() -> None:
    async def main() -> None:
        async with AsyncPeriodicTimer(3600, _noop) as timer:
            assert await asyncio.wait_for(timer.join(-(10**400)), 1) is False
            assert timer.is_running()

    asyncio.run(main())


def test_signalling_nan_join_is_documented_for_both_timers() -> None:
    with pytest.raises(ValueError, match="timeout"):
        PeriodicTimer(1, lambda: None).join(Decimal("sNaN"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timeout"):
        asyncio.run(AsyncPeriodicTimer(1, _noop).join(Decimal("sNaN")))  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [17, 91, 20261101])
def test_seeded_invalid_option_strings_are_bounded(seed: int) -> None:
    rng = random.Random(seed)
    alphabet = "\0\n\r\ud800\uffffabcdefghijklmnopqrstuvwxyz"
    for _ in range(1000):
        value = "!" + "".join(rng.choices(alphabet, k=rng.randrange(200)))
        for key in ("on_missed", "mode"):
            for timer in (PeriodicTimer, AsyncPeriodicTimer):
                callback = _noop if timer is AsyncPeriodicTimer else lambda: None
                with pytest.raises(ValueError) as caught:
                    timer(1, callback, **{key: value})  # type: ignore[arg-type]
                assert len(str(caught.value)) < 100
