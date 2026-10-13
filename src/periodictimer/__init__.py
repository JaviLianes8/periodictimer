"""Drift-free repeating timers for threads and asyncio."""

from __future__ import annotations

from ._atimer import AsyncPeriodicTimer
from ._timer import PeriodicTimer

__version__ = "0.2.0"

__all__ = ["AsyncPeriodicTimer", "PeriodicTimer"]
