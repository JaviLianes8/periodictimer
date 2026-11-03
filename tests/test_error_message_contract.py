"""Every error both timers raise or report, pinned to its exact class and message.

Messages name the option and the rule, never the rejected value. The table covers every
raise statement of the package, so a message cannot be emptied, reworded into something
that no longer names its option, or swapped to another class without a failure here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from _numeric_values import Real, boom

from periodictimer import AsyncPeriodicTimer, PeriodicTimer

TIMERS: tuple[Any, ...] = (PeriodicTimer, AsyncPeriodicTimer)


async def anoop() -> None:
    pass


def noop() -> None:
    pass


async def coroutine_handler(exc: Exception) -> None:
    pass


OVERFLOW_UNSIGNED = Real(OverflowError(), boom(RuntimeError))

OPTIONS: list[tuple[dict[str, Any], type[Exception], str]] = [
    ({"interval": "1"}, TypeError, "interval must be a real number"),
    ({"interval": True}, TypeError, "interval must be a real number"),
    ({"interval": float("nan")}, ValueError, "interval must not be NaN"),
    (
        {"interval": Real(boom(ValueError))},
        ValueError,
        "interval must be a convertible real number",
    ),
    ({"interval": OVERFLOW_UNSIGNED}, ValueError, "interval must be a convertible real number"),
    ({"interval": 0}, ValueError, "interval must be a positive finite number of seconds"),
    (
        {"interval": float("inf")},
        ValueError,
        "interval must be a positive finite number of seconds",
    ),
    ({"jitter": "0"}, TypeError, "jitter must be a real number"),
    ({"jitter": float("nan")}, ValueError, "jitter must not be NaN"),
    ({"jitter": 2}, ValueError, "jitter must be between 0 and the interval"),
    ({"jitter": -0.5}, ValueError, "jitter must be between 0 and the interval"),
    ({"immediate": 1}, TypeError, "immediate must be a bool"),
    ({"on_missed": "late"}, ValueError, "on_missed must be one of skip, coalesce, burst"),
    ({"mode": "rate"}, ValueError, "mode must be one of fixed_rate, fixed_delay"),
    ({"fn": 1}, TypeError, "fn must be callable"),
    ({"on_error": 1}, TypeError, "on_error must be callable"),
    ({"clock": 1}, TypeError, "clock must be callable"),
    ({"rng": object()}, TypeError, "rng must have a uniform(a, b) method"),
    (
        {"on_error": coroutine_handler},
        TypeError,
        "on_error must be a plain function; it is called, never awaited",
    ),
]

THREAD_ONLY: list[tuple[dict[str, Any], type[Exception], str]] = [
    ({"daemon": 0}, TypeError, "daemon must be a bool"),
    ({"waiter": 1}, TypeError, "waiter must be callable"),
    ({"fn": anoop}, TypeError, "fn is a coroutine function; use AsyncPeriodicTimer"),
]

TIMEOUTS: list[tuple[object, type[Exception], str]] = [
    ("1", TypeError, "timeout must be a real number"),
    (False, TypeError, "timeout must be a real number"),
    (float("nan"), ValueError, "timeout must not be NaN"),
    (Real(boom(ValueError)), ValueError, "timeout must be a convertible real number"),
    (OVERFLOW_UNSIGNED, ValueError, "timeout must be a convertible real number"),
]


def build(timer: Any, options: dict[str, Any]) -> Any:
    merged = {"interval": 1.0, "fn": noop if timer is PeriodicTimer else anoop, **options}
    return timer(merged.pop("interval"), merged.pop("fn"), **merged)


def check(action: Callable[[], object], kind: type[Exception], message: str) -> None:
    with pytest.raises(Exception) as caught:
        action()
    assert type(caught.value) is kind
    assert str(caught.value) == message


@pytest.mark.parametrize("timer", TIMERS)
@pytest.mark.parametrize(("options", "kind", "message"), OPTIONS)
def test_option_errors(timer: Any, options: dict[str, Any], kind: Any, message: str) -> None:
    check(lambda: build(timer, options), kind, message)


@pytest.mark.parametrize(("options", "kind", "message"), THREAD_ONLY)
def test_thread_option_errors(options: dict[str, Any], kind: Any, message: str) -> None:
    check(lambda: build(PeriodicTimer, options), kind, message)


def test_async_sleep_error() -> None:
    check(lambda: build(AsyncPeriodicTimer, {"sleep": 1}), TypeError, "sleep must be callable")


@pytest.mark.parametrize(("value", "kind", "message"), TIMEOUTS)
def test_timeout_errors(value: object, kind: Any, message: str) -> None:
    check(lambda: PeriodicTimer(1, noop).join(value), kind, message)  # type: ignore[arg-type]
    timer = AsyncPeriodicTimer(1, anoop)
    check(lambda: asyncio.run(timer.join(value)), kind, message)  # type: ignore[arg-type]


def test_thread_lifecycle_errors() -> None:
    twice = PeriodicTimer(1, noop, waiter=lambda delay: True)
    twice.start()
    check(twice.start, RuntimeError, "timer already started")
    assert twice.join(5)
    stopped = PeriodicTimer(1, noop)
    stopped.stop()
    check(stopped.start, RuntimeError, "timer was stopped before it started")
    seen: list[BaseException] = []

    def inside() -> None:
        try:
            timer.join()
        except RuntimeError as exc:
            seen.append(exc)
        timer.stop()

    timer = PeriodicTimer(1, inside, immediate=True)
    timer.start()
    assert timer.join(5)
    assert [str(exc) for exc in seen] == ["cannot join a timer from its own callback; call stop()"]


def test_async_lifecycle_errors() -> None:
    seen: list[str] = []

    async def main() -> None:
        async def inside() -> None:
            try:
                await timer.join()
            except RuntimeError as exc:
                seen.append(str(exc))
            timer.stop()

        timer = AsyncPeriodicTimer(1, inside, immediate=True)
        timer.start()
        check(timer.start, RuntimeError, "timer already started")
        assert await timer.join(5)
        stopped = AsyncPeriodicTimer(1, anoop)
        stopped.stop()
        check(stopped.start, RuntimeError, "timer was stopped before it started")

    asyncio.run(main())
    assert seen == ["cannot join a timer from its own callback; call stop()"]


def test_reported_callback_type_errors() -> None:
    thread_errors: list[Exception] = []
    holder: list[PeriodicTimer] = []

    def awaitable() -> object:
        holder[0].stop()
        return asyncio.sleep(0)

    thread = PeriodicTimer(1, awaitable, immediate=True, on_error=thread_errors.append)
    holder.append(thread)
    thread.start()
    assert thread.join(5)
    assert [(type(e), str(e)) for e in thread_errors] == [
        (TypeError, "fn returned an awaitable; use AsyncPeriodicTimer")
    ]
    async_errors: list[Exception] = []

    async def main() -> None:
        def plain() -> None:
            timer.stop()

        timer = AsyncPeriodicTimer(1, plain, immediate=True, on_error=async_errors.append)  # type: ignore[arg-type]
        timer.start()
        assert await timer.join(5)

    asyncio.run(main())
    assert [(type(e), str(e)) for e in async_errors] == [
        (TypeError, "fn returned a plain value; use PeriodicTimer for sync work")
    ]
