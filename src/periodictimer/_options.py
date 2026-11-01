"""Validation of the options shared by the thread and asyncio timers."""

from __future__ import annotations

import math
import numbers
from decimal import Decimal
from typing import Literal, cast

Policy = Literal["skip", "coalesce", "burst"]
Mode = Literal["fixed_rate", "fixed_delay"]

SKIP: Policy = "skip"
COALESCE: Policy = "coalesce"
BURST: Policy = "burst"
FIXED_RATE: Mode = "fixed_rate"
FIXED_DELAY: Mode = "fixed_delay"

POLICIES: tuple[Policy, ...] = (SKIP, COALESCE, BURST)
MODES: tuple[Mode, ...] = (FIXED_RATE, FIXED_DELAY)


def _check_real_type(value: object, message: str) -> None:
    # bool is an int subclass, and True as a period of one second is a bug, not a choice.
    try:
        valid = type(value) is not bool and issubclass(type(value), (numbers.Real, Decimal))
    except Exception:
        # Numeric ABC classification can invoke caller-controlled metaclass hooks.
        raise TypeError(message) from None
    if not valid:
        raise TypeError(message)


def _real(value: object, name: str) -> float:
    _check_real_type(value, f"{name} must be a real number")
    try:
        result = float(cast("numbers.Real | Decimal", value))
    except OverflowError:
        raise ValueError(f"{name} must be finite, got a value too large for a float") from None
    except TypeError:
        raise TypeError(f"{name} must be a real number") from None
    except Exception:
        raise ValueError(f"{name} must be a finite real number") from None
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
        if issubclass(type(value), str) and str.__eq__(cast(str, value), policy):
            return policy
    raise ValueError(f"on_missed must be one of {', '.join(POLICIES)}")


def check_mode(value: object) -> Mode:
    """The scheduling mode, refusing anything but the documented names."""
    for mode in MODES:
        if issubclass(type(value), str) and str.__eq__(cast(str, value), mode):
            return mode
    raise ValueError(f"mode must be one of {', '.join(MODES)}")


def check_callable(value: object, name: str) -> None:
    """Refuse a callback or handler that cannot be called."""
    if not callable(value):
        raise TypeError(f"{name} must be callable")


def check_flag(value: object, name: str) -> bool:
    """A real bool: a string such as "no" is truthy and would silently mean yes."""
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool")
    return value


def check_rng(value: object) -> None:
    """Refuse an rng without the ``uniform`` method jitter draws from."""
    if not callable(getattr(value, "uniform", None)):
        raise TypeError("rng must have a uniform(a, b) method")
