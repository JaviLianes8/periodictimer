"""Validation of the options shared by the thread and asyncio timers."""

from __future__ import annotations

import math
import numbers
from decimal import Decimal
from typing import Literal

Policy = Literal["skip", "coalesce", "burst"]
Mode = Literal["fixed_rate", "fixed_delay"]

SKIP: Policy = "skip"
COALESCE: Policy = "coalesce"
BURST: Policy = "burst"
FIXED_RATE: Mode = "fixed_rate"
FIXED_DELAY: Mode = "fixed_delay"

POLICIES: tuple[Policy, ...] = (SKIP, COALESCE, BURST)
MODES: tuple[Mode, ...] = (FIXED_RATE, FIXED_DELAY)


def _real(value: object, name: str) -> float:
    # bool is an int subclass, and True as a period of one second is a bug, not a choice.
    if isinstance(value, bool) or not isinstance(value, (numbers.Real, Decimal)):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    try:
        result = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be finite, got a value too large for a float") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite, got {result!r}")
    return result


def check_interval(value: object) -> float:
    """The period in seconds as a float, or an error for anything not finite and positive."""
    result = _real(value, "interval")
    if result <= 0:
        raise ValueError(f"interval must be positive, got {result!r}")
    return result


def check_jitter(value: object, interval: float) -> float:
    """The jitter in seconds, between zero and the interval inclusive."""
    result = _real(value, "jitter")
    if result < 0 or result > interval:
        raise ValueError(f"jitter must be between 0 and the interval, got {result!r}")
    return result


def check_policy(value: object) -> Policy:
    """The missed-tick policy, refusing anything but the documented names."""
    for policy in POLICIES:
        if value == policy:
            return policy
    raise ValueError(f"on_missed must be one of {', '.join(POLICIES)}, got {value!r}")


def check_mode(value: object) -> Mode:
    """The scheduling mode, refusing anything but the documented names."""
    for mode in MODES:
        if value == mode:
            return mode
    raise ValueError(f"mode must be one of {', '.join(MODES)}, got {value!r}")


def check_callable(value: object, name: str) -> None:
    """Refuse a callback or handler that cannot be called."""
    if not callable(value):
        raise TypeError(f"{name} must be callable, got {type(value).__name__}")


def check_flag(value: object, name: str) -> bool:
    """A real bool: a string such as "no" is truthy and would silently mean yes."""
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool, got {type(value).__name__}")
    return value


def check_rng(value: object) -> None:
    """Refuse an rng without the ``uniform`` method jitter draws from."""
    if not callable(getattr(value, "uniform", None)):
        raise TypeError(f"rng must have a uniform(a, b) method, got {type(value).__name__}")
