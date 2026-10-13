"""The public API is typed: mypy infers results and rejects bad calls."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from periodictimer import AsyncPeriodicTimer, PeriodicTimer
def tick() -> None: ...
async def atick() -> None: ...
timer = PeriodicTimer(1.0, tick, on_missed="coalesce", mode="fixed_delay")
atimer = AsyncPeriodicTimer(1.0, atick, on_missed="burst")
reveal_type(timer.join())
reveal_type(atimer.join())
reveal_type(timer.epoch)
reveal_type(atimer.missed)
PeriodicTimer(1.0, tick, on_missed="later")
PeriodicTimer(1.0, tick, mode="rate")
AsyncPeriodicTimer(1.0, tick)
PeriodicTimer(1.0, tick, 0.5)
PeriodicTimer(1.0, tick, on_error=lambda: None)
async def handler(exc: Exception) -> None: ...
AsyncPeriodicTimer(1.0, atick, on_error=handler)
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


@pytest.mark.parametrize(
    ("line", "expected"),
    [(7, "bool"), (8, "Coroutine[Any, Any, bool]"), (9, "float | None"), (10, "int")],
)
def test_results_are_typed(mypy_output: str, line: int, expected: str) -> None:
    match = re.search(rf"snippet\.py:{line}: note: Revealed type is \"(.+)\"", mypy_output)
    assert match, mypy_output
    revealed = re.sub(r"\b[a-z_][\w]*\.", "", match.group(1))
    assert revealed == expected


@pytest.mark.parametrize(
    ("line", "code"),
    [
        (11, "arg-type"),
        (12, "arg-type"),
        (13, "arg-type"),
        (14, "call-arg"),
        (15, "arg-type"),
        (17, "arg-type"),
    ],
)
def test_wrong_calls_are_rejected(mypy_output: str, line: int, code: str) -> None:
    assert re.search(rf"snippet\.py:{line}: error: .*\[{code}\]", mypy_output), mypy_output
