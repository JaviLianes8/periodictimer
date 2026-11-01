"""Numeric classification failures remain bounded at both public timer APIs."""

from __future__ import annotations

import asyncio
import traceback
from typing import Any

import pytest

from periodictimer import AsyncPeriodicTimer, PeriodicTimer


@pytest.mark.parametrize("timer", [PeriodicTimer, AsyncPeriodicTimer])
@pytest.mark.parametrize("option", ["interval", "jitter", "timeout"])
def test_numeric_classification_errors_are_bounded(timer: Any, option: str) -> None:
    class HostileMeta(type):
        def __hash__(cls) -> int:
            raise RuntimeError("private-marker" + "x" * 1_000_000)

    class Hostile(metaclass=HostileMeta):
        pass

    async def noop() -> None:
        pass

    callback = noop if timer is AsyncPeriodicTimer else lambda: None
    caught: Exception | None = None
    try:
        if option == "timeout":
            worker = timer(1, callback)
            if timer is AsyncPeriodicTimer:
                asyncio.run(worker.join(Hostile()))
            else:
                worker.join(Hostile())
        else:
            timer(**{"interval": 1, "fn": callback, option: Hostile()})
    except Exception as exc:
        caught = exc
    # Avoid printing the original payload even when this contract fails.
    assert caught is not None
    assert type(caught) is TypeError, type(caught).__name__
    assert len(str(caught)) < 180
    assert option in str(caught)
    assert "private-marker" not in str(caught)
    rendered = "".join(traceback.format_exception(type(caught), caught, caught.__traceback__))
    assert "private-marker" not in rendered
