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
        raise TypeError("timeout must be a real number or None")
    try:
        result = float(timeout)
    except OverflowError:
        return 0.0 if timeout < 0 else None
    except ValueError:
        raise ValueError("timeout must not be NaN") from None
    if math.isnan(result):
        raise ValueError("timeout must not be NaN")
    if result == math.inf:
        return None
    return min(max(result, 0.0), threading.TIMEOUT_MAX)
