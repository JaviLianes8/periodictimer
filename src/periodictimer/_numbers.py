"""The one validator behind every numeric and boolean argument of both timers.

Every timing argument (``interval``, ``jitter`` and the ``join`` timeout) goes through
``seconds`` first, so all of them classify, convert and fail in exactly the same way;
each caller then applies only its own range rule to the resulting float.
"""

from __future__ import annotations

import math
import numbers
import threading
from decimal import Decimal
from typing import cast


def seconds(value: object, name: str) -> float:
    """``value`` converted to a float, possibly infinite but never NaN.

    ``bool`` and anything that is neither ``numbers.Real`` nor ``Decimal`` raise
    TypeError, as does a conversion that raises TypeError. A conversion that overflows
    becomes an infinity of the value's sign. NaN and any other conversion failure raise
    ValueError. Messages name the argument only, and never chain the original error.
    """
    message = f"{name} must be a real number"
    # bool is an int subclass, and True as a period of one second is a bug, not a choice.
    try:
        valid = type(value) is not bool and issubclass(type(value), (numbers.Real, Decimal))
    except Exception:
        # Numeric ABC classification can invoke caller-controlled metaclass hooks.
        raise TypeError(message) from None
    if not valid:
        raise TypeError(message)
    number = cast("numbers.Real | Decimal", value)
    try:
        result = float(number)
    except OverflowError:
        result = _overflow(number, name)
    except TypeError:
        raise TypeError(message) from None
    except Exception:
        raise ValueError(f"{name} must be a convertible real number") from None
    if math.isnan(result):
        raise ValueError(f"{name} must not be NaN")
    return result


def _overflow(number: numbers.Real | Decimal, name: str) -> float:
    # A value too large for a float keeps its sign; asking for it is caller code too.
    try:
        negative = bool(number < 0)
    except Exception:
        raise ValueError(f"{name} must be a convertible real number") from None
    return -math.inf if negative else math.inf


def check_interval(value: object) -> float:
    """The period in seconds: a finite float strictly above zero."""
    result = seconds(value, "interval")
    if not math.isfinite(result) or result <= 0:
        raise ValueError("interval must be a positive finite number of seconds")
    return result


def check_jitter(value: object, interval: float) -> float:
    """The jitter in seconds: a float from zero to the interval, both included."""
    result = seconds(value, "jitter")
    if not 0 <= result <= interval:
        raise ValueError("jitter must be between 0 and the interval")
    return result


def check_timeout(value: object) -> float | None:
    """A timeout fit for a blocking call: None waits forever, zero only polls.

    None, positive infinity and positive values too large for a float wait forever.
    Zero, negatives and negative infinity poll. Finite positive values are kept as they
    are, capped at ``threading.TIMEOUT_MAX`` so the standard library never overflows.
    """
    if value is None:
        return None
    result = seconds(value, "timeout")
    if result == math.inf:
        return None
    if result <= 0:
        return 0.0
    return min(result, threading.TIMEOUT_MAX)


def check_flag(value: object, name: str) -> bool:
    """A real bool: an int such as 0 or a string such as "no" would be a silent guess."""
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool")
    return value
