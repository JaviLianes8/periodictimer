"""Validation contracts for subclass hooks and integer boolean flags."""

from __future__ import annotations

import asyncio
import numbers
import traceback
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


async def _noop() -> None:
    pass


class HostileText(str):
    def __eq__(self, other: object) -> bool:
        raise RuntimeError("private-marker")

    def __str__(self) -> str:
        raise RuntimeError("private-marker")


class PretendText:
    def __eq__(self, other: object) -> bool:
        return True


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option, valid", [("on_missed", "burst"), ("mode", "fixed_delay")])
def test_string_options_ignore_subclass_equality(timer: Any, option: str, valid: str) -> None:
    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    timer(1, callback, **{option: HostileText(valid)})
    with pytest.raises(ValueError, match=option):
        timer(1, callback, **{option: HostileText("invalid")})


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option", ["on_missed", "mode"])
def test_nonstring_equality_cannot_spoof_an_option(timer: Any, option: str) -> None:
    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    with pytest.raises(ValueError, match=option):
        timer(1, callback, **{option: PretendText()})


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option", ["interval", "jitter", "timeout"])
@pytest.mark.parametrize("base", [int, float])
@pytest.mark.parametrize("error", [TypeError, ValueError, RuntimeError, OverflowError])
def test_numeric_conversion_errors_are_bounded(
    timer: Any, option: str, base: Any, error: type[Exception]
) -> None:
    class HostileNumber(base):  # type: ignore[misc]
        def __float__(self) -> float:
            raise error("private-marker" + "x" * 1_000_000)

        def __lt__(self, other: object) -> bool:
            raise RuntimeError("private-marker")

    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    caught: Exception | None = None
    try:
        if option == "timeout":
            worker = timer(1, callback)
            if timer is AsyncPeriodicTimer:
                asyncio.run(worker.join(HostileNumber(1)))
            else:
                worker.join(HostileNumber(1))
        else:
            timer(**{"interval": 1, "fn": callback, option: HostileNumber(1)})
    except Exception as exc:
        caught = exc
    # Keep failure reports bounded even when the exception carries a huge payload.
    assert caught is not None
    expected = TypeError if error is TypeError else ValueError
    assert type(caught) is expected, type(caught).__name__
    assert len(str(caught)) < 180
    assert option in str(caught)
    assert "private-marker" not in str(caught)
    rendered = "".join(traceback.format_exception(type(caught), caught, caught.__traceback__))
    assert "private-marker" not in rendered


@pytest.mark.parametrize(
    "timer, option",
    [
        (timer, option)
        for timer in (PeriodicTimer, AsyncPeriodicTimer)
        for option in ("interval", "jitter", "timeout", "mode", "on_missed", "immediate")
    ]
    + [(PeriodicTimer, "daemon")],
)
def test_option_classification_ignores_instance_class_properties(timer: Any, option: str) -> None:
    accesses = []

    class Hostile:
        @property  # type: ignore[misc]
        def __class__(self) -> type:
            accesses.append(True)
            raise RuntimeError("private-marker" + "x" * 1_000_000)

    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    caught: Exception | None = None
    try:
        if option == "timeout":
            worker = timer(1, callback)
            if timer is AsyncPeriodicTimer:
                asyncio.run(worker.join(Hostile()))
            else:
                worker.join(Hostile())
        else:
            timer(**{"interval": 1, "fn": callback, option: Hostile()})
    except Exception as exc:
        caught = exc
    assert caught is not None
    expected = ValueError if option in ("mode", "on_missed") else TypeError
    assert type(caught) is expected, type(caught).__name__
    assert not accesses
    assert len(str(caught)) < 180
    assert option in str(caught)
    rendered = "".join(traceback.format_exception(type(caught), caught, caught.__traceback__))
    assert "private-marker" not in rendered


@pytest.mark.parametrize(
    "timer, option",
    [(PeriodicTimer, "immediate"), (AsyncPeriodicTimer, "immediate"), (PeriodicTimer, "daemon")],
)
@pytest.mark.parametrize("value", [0, 1, -1, 2])
def test_integer_boolean_flags_are_rejected(timer: Any, option: str, value: int) -> None:
    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    with pytest.raises(TypeError, match=option):
        timer(1, callback, **{option: value})


@pytest.mark.parametrize(
    "timer, option",
    [(PeriodicTimer, "immediate"), (AsyncPeriodicTimer, "immediate"), (PeriodicTimer, "daemon")],
)
@pytest.mark.parametrize("value", [False, True])
def test_actual_boolean_flags_are_accepted(timer: Any, option: str, value: bool) -> None:
    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    timer(1, callback, **{option: value})


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option", ["interval", "jitter", "timeout"])
def test_registered_real_numbers_remain_supported(timer: Any, option: str) -> None:
    @numbers.Real.register
    class RegisteredReal:
        def __float__(self) -> float:
            return 0.5

    callback = _noop if timer is AsyncPeriodicTimer else lambda: None
    if option == "timeout":
        worker = timer(1, callback)
        if timer is AsyncPeriodicTimer:
            assert asyncio.run(worker.join(RegisteredReal()))
        else:
            assert worker.join(RegisteredReal())
    else:
        worker = timer(**{"interval": 1, "fn": callback, option: RegisteredReal()})
        assert worker.interval == (0.5 if option == "interval" else 1.0)
