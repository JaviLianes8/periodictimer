"""Drift-free repeating timers for threads and asyncio."""

from __future__ import annotations

from ._atimer import AsyncPeriodicTimer
from ._timer import PeriodicTimer

del annotations

__version__ = "1.0.0"

__all__ = ["AsyncPeriodicTimer", "PeriodicTimer"]
