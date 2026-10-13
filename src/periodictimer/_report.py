"""Routing of callback failures, shared by the thread and asyncio timers."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger("periodictimer")

ErrorHandler = Callable[[Exception], object]


def handle_failure(owner: object, exc: Exception, on_error: ErrorHandler | None) -> bool:
    """Deal with an exception from the callback; return False when the timer must stop.

    Without a handler the failure is logged, so it is never silent, and the timer keeps
    going. With one, the handler decides; if the handler itself raises, that is logged and
    the timer stops, which gives callers a plain way to stop on the first failure.
    """
    if on_error is None:
        logger.error("callback of %r raised", owner, exc_info=exc)
        return True
    try:
        on_error(exc)
    except Exception as handler_exc:
        logger.error("on_error of %r raised, stopping the timer", owner, exc_info=handler_exc)
        return False
    return True
