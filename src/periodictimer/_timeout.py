"""Validation of the timeouts given to join."""

from __future__ import annotations

import math
import numbers
import threading
from decimal import Decimal
from typing import cast


def check_timeout(timeout: object) -> float | None:
    """A timeout fit for a blocking call: None waits forever, negatives mean zero.

    Infinity means forever and anything above ``threading.TIMEOUT_MAX`` is capped, so a
    huge value cannot raise OverflowError from deep inside the standard library.
    """
    if timeout is None:
        return None
    if type(timeout) is bool or not issubclass(type(timeout), (numbers.Real, Decimal)):
        raise TypeError("timeout must be a real number or None")
    timeout = cast("numbers.Real | Decimal", timeout)
    try:
        result = float(timeout)
    except OverflowError:
        try:
            return 0.0 if timeout < 0 else None
        except Exception:
            raise ValueError("timeout must be a real number or None") from None
    except TypeError:
        raise TypeError("timeout must be a real number or None") from None
    except Exception:
        raise ValueError("timeout must not be NaN") from None
    if math.isnan(result):
        raise ValueError("timeout must not be NaN")
    if result == math.inf:
        return None
    return min(max(result, 0.0), threading.TIMEOUT_MAX)
