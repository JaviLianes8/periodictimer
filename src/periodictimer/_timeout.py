"""Validation of the timeouts given to join."""

from __future__ import annotations

import math
import numbers
import threading
from decimal import Decimal


def check_timeout(timeout: object) -> float | None:
    """A timeout fit for a blocking call: None waits forever, negatives mean zero.

    Infinity means forever and anything above ``threading.TIMEOUT_MAX`` is capped, so a
    huge value cannot raise OverflowError from deep inside the standard library.
    """
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, (numbers.Real, Decimal)):
        raise TypeError(f"timeout must be a real number or None, got {type(timeout).__name__}")
    try:
        result = float(timeout)
    except OverflowError:
        return None  # larger than any float: as good as forever
    if math.isnan(result):
        raise ValueError("timeout must not be NaN")
    if result == math.inf:
        return None
    return min(max(result, 0.0), threading.TIMEOUT_MAX)
