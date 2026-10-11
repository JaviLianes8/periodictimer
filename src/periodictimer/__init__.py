"""Drift-free repeating timer that runs a callback on a background thread."""

from __future__ import annotations

from ._timer import PeriodicTimer

__version__ = "0.1.0"

__all__ = ["PeriodicTimer"]
