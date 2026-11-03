"""The documented range rules of each timing argument, restated from GUIDE.md.

Each rule takes what the shared conversion makes of a value (a float, or the exception
class it must raise) and gives what the argument must finally be, or raise.
"""

from __future__ import annotations

import math
import threading
from typing import Any


def interval_rule(converted: Any) -> Any:
    """GUIDE: positive finite seconds."""
    if isinstance(converted, type):
        return converted
    return converted if math.isfinite(converted) and converted > 0 else ValueError


def jitter_rule(converted: Any, interval: float) -> Any:
    """GUIDE: finite seconds from zero to the interval, inclusive."""
    if isinstance(converted, type):
        return converted
    return converted if 0 <= converted <= interval else ValueError


def timeout_rule(value: object, converted: Any) -> Any:
    """GUIDE: None and +inf wait forever, non-positive polls, finite is capped."""
    if value is None:
        return None
    if isinstance(converted, type):
        return converted
    if converted == math.inf:
        return None
    if converted <= 0:
        return 0.0
    return min(converted, threading.TIMEOUT_MAX)
