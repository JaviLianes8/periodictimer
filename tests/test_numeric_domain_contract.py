"""Every timing argument of both timers, pinned exactly over the whole numeric domain.

``interval``, ``jitter`` and the ``join`` timeout share one conversion, so each row of
the domain table must give, for every argument and both timers, either exactly the value
the documented range rule derives from the row, or exactly the documented exception.
"""

from __future__ import annotations

import asyncio
import math
import traceback
from typing import Any

import pytest
from _numeric_domain import MARKER, ROWS, Abort
from _numeric_probes import (
    TIMERS,
    AsyncJoinProbe,
    ThreadJoinProbe,
    interval_of,
    jitter_draws,
    same,
    unstarted_join,
)
from _numeric_rules import interval_rule, jitter_rule, timeout_rule

from periodictimer import PeriodicTimer

IDS = [row[0] for row in ROWS]
ARGS = [row[1:] for row in ROWS]


def assert_raised(caught: BaseException, expected: type[BaseException], name: str) -> None:
    assert type(caught) is expected, f"{type(caught).__name__} instead of {expected.__name__}"
    if expected is Abort:
        return
    text = str(caught)
    assert name in text
    assert len(text) < 120
    assert caught.__cause__ is None
    assert caught.__context__ is None or caught.__suppress_context__
    rendered = "".join(traceback.format_exception(type(caught), caught, caught.__traceback__))
    assert MARKER not in rendered


def outcome(action: Any) -> tuple[bool, Any]:
    try:
        return True, action()
    except BaseException as exc:  # Abort rows must be observed, not escape
        return False, exc


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize(("value", "converted"), ARGS, ids=IDS)
def test_interval_domain(timer: Any, value: object, converted: Any) -> None:
    expected = interval_rule(converted)
    ok, result = outcome(lambda: interval_of(timer, value))
    if isinstance(expected, type):
        assert not ok, f"accepted as {result!r}"
        assert_raised(result, expected, "interval")
    else:
        assert ok, f"raised {type(result).__name__}"
        assert same(result, expected), f"{result!r} instead of {expected!r}"


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize("interval", [1.0, 0.5])
@pytest.mark.parametrize(("value", "converted"), ARGS, ids=IDS)
def test_jitter_domain(timer: Any, interval: float, value: object, converted: Any) -> None:
    expected = jitter_rule(converted, interval)
    ok, result = outcome(lambda: jitter_draws(timer, value, interval))
    if isinstance(expected, type):
        assert not ok, f"accepted, drawing {result!r}"
        assert_raised(result, expected, "jitter")
    elif expected == 0:
        assert ok, f"raised {type(result).__name__}"
        assert result == [], "zero jitter must not draw"
    else:
        assert ok, f"raised {type(result).__name__}"
        assert len(result) == 1
        low, high = result[0]
        assert same(low, 0.0)
        assert same(high, expected), f"{high!r} instead of {expected!r}"


@pytest.mark.parametrize(("value", "converted"), [*ARGS, (None, None)], ids=[*IDS, "None"])
def test_thread_join_timeout_domain(value: object, converted: Any) -> None:
    expected = timeout_rule(value, converted)
    with ThreadJoinProbe() as probe:
        ok, result = outcome(lambda: probe(value))
    check_timeout_outcome(PeriodicTimer, value, expected, ok, result)


@pytest.mark.parametrize(("value", "converted"), [*ARGS, (None, None)], ids=[*IDS, "None"])
def test_async_join_timeout_domain(value: object, converted: Any) -> None:
    expected = timeout_rule(value, converted)

    async def main() -> tuple[bool, Any]:
        async with AsyncJoinProbe() as probe:
            try:
                return True, await probe(value)
            except BaseException as exc:  # Abort rows must be observed, not escape
                return False, exc

    ok, result = asyncio.run(main())
    check_timeout_outcome(TIMERS[1], value, expected, ok, result)


def check_timeout_outcome(timer: Any, value: object, expected: Any, ok: bool, result: Any) -> None:
    if isinstance(expected, type):
        assert not ok, f"accepted as {result!r}"
        assert_raised(result, expected, "timeout")
        # A timer that never started validates the timeout just the same.
        ok, result = outcome(lambda: unstarted_join(timer, value))
        assert not ok
        assert_raised(result, expected, "timeout")
    else:
        assert ok, f"raised {type(result).__name__}"
        assert same(result, expected), f"{result!r} instead of {expected!r}"
        assert unstarted_join(timer, value) is True


@pytest.mark.parametrize(
    ("value", "converted"),
    [(math.inf, None), (-math.inf, 0.0), (-60.0, 0.0), (0.75, 0.75), (10**400, None)],
)
def test_reported_timeout_instances_are_rows_of_the_table(value: object, converted: Any) -> None:
    # The values earlier rounds reported one at a time are all covered by the table.
    row = next(row for row in ROWS if row[1] == value and type(row[1]) is type(value))
    assert same(timeout_rule(value, row[2]), converted)
