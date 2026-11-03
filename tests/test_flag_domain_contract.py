"""The boolean flags of both timers accept exactly ``True`` and ``False``, with effect.

``immediate`` (both timers) and ``daemon`` (thread timer) go through one check: the
value's type must be ``bool`` itself. Everything else, including ints, int subclasses,
numbers equal to one, truthy objects and objects whose dunders raise, is a TypeError
that names the flag, and no dunder of the value is ever called.
"""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from fractions import Fraction
from typing import Any

import pytest
from _numeric_domain import MARKER, Int, Truth, boom
from _numeric_probes import TIMERS, callback_for, first_events

from periodictimer import PeriodicTimer


class Answer(IntEnum):
    NO = 0
    YES = 1


class Touchy:
    """Any comparison, truth test or conversion of this value is a bug."""

    def __bool__(self) -> bool:
        raise AssertionError(MARKER)

    def __eq__(self, other: object) -> bool:
        raise AssertionError(MARKER)

    def __hash__(self) -> int:
        raise AssertionError(MARKER)

    def __index__(self) -> int:
        raise AssertionError(MARKER)

    def __int__(self) -> int:
        raise AssertionError(MARKER)


class PretendBool:
    @property  # type: ignore[misc]
    def __class__(self) -> type:
        return bool


NOT_BOOLS: list[Any] = [
    0,
    1,
    -1,
    2,
    10**400,
    Int(1),
    Int(0),
    Answer.YES,
    Answer.NO,
    0.0,
    1.0,
    Decimal(1),
    Fraction(1),
    1 + 0j,
    "True",
    "yes",
    "",
    b"\x01",
    None,
    [],
    [True],
    (True,),
    object(),
    Truth(True),
    Truth(boom(RuntimeError)),
    Touchy(),
    PretendBool(),
    bool,
]

FLAGS = [(timer, "immediate") for timer in TIMERS] + [(PeriodicTimer, "daemon")]


@pytest.mark.parametrize(("timer", "flag"), FLAGS)
@pytest.mark.parametrize("value", NOT_BOOLS, ids=[repr(v)[:30] for v in NOT_BOOLS])
def test_anything_but_a_bool_is_a_type_error(timer: Any, flag: str, value: object) -> None:
    with pytest.raises(TypeError) as caught:
        timer(1, callback_for(timer), **{flag: value})
    assert type(caught.value) is TypeError
    assert flag in str(caught.value)
    assert MARKER not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize(
    ("immediate", "expected"),
    [(True, ["call"]), (False, [("wait", 2.0), "call"])],
)
def test_immediate_decides_whether_the_first_call_waits(
    timer: Any, immediate: bool, expected: list[object]
) -> None:
    events, _ = first_events(timer, immediate=immediate)
    assert events == expected


def test_immediate_defaults_to_false() -> None:
    for timer in TIMERS:
        assert first_events(timer)[0] == [("wait", 2.0), "call"]


@pytest.mark.parametrize("daemon", [True, False])
def test_daemon_decides_the_worker_thread_flag(daemon: bool) -> None:
    events, daemons = first_events(PeriodicTimer, immediate=True, daemon=daemon)
    assert events == ["call"]
    assert daemons == [daemon]
    assert type(daemons[0]) is bool


def test_daemon_defaults_to_true() -> None:
    assert first_events(PeriodicTimer, immediate=True)[1] == [True]
