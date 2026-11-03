"""Validation of the options shared by the thread and asyncio timers."""

from __future__ import annotations

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


def check_rng(value: object) -> None:
    """Refuse an rng without the ``uniform`` method jitter draws from."""
    if not callable(getattr(value, "uniform", None)):
        raise TypeError("rng must have a uniform(a, b) method")
