"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with PERIODICTIMER_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("PERIODICTIMER_E2E") != "1",
    reason="set PERIODICTIMER_E2E=1 to build and install",
)

PROGRAM = """
import asyncio, importlib.metadata, importlib.resources, threading
import periodictimer
from periodictimer import AsyncPeriodicTimer, PeriodicTimer

assert "site-packages" in periodictimer.__file__, periodictimer.__file__
assert importlib.metadata.version("periodictimer") == periodictimer.__version__
assert importlib.resources.files("periodictimer").joinpath("py.typed").is_file()

hits = []
done = threading.Event()
def tick():
    hits.append(1)
    if len(hits) == 3:
        done.set()
with PeriodicTimer(0.01, tick, name="e2e") as timer:
    assert done.wait(10), "timer never fired three times"
assert not timer.is_running()
assert all(t.name != "e2e" for t in threading.enumerate())

class Clock:
    now = 0.0
    def __call__(self):
        return self.now
clock = Clock()
seen = []
def job():
    seen.append(clock.now)
    if clock.now == 1.0:
        clock.now += 3.5
def waiter(seconds):
    clock.now += seconds
    return len(seen) >= 3
t = PeriodicTimer(1.0, job, on_missed="coalesce", clock=clock, waiter=waiter)
t.start()
assert t.join(10)
assert (seen, t.missed) == ([1.0, 4.5, 5.0], 2), (seen, t.missed)

for bad in (float("nan"), 0, True):
    try:
        PeriodicTimer(bad, tick)
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError(f"accepted interval {bad!r}")

async def main():
    beats = []
    async def beat():
        beats.append(1)
        if len(beats) == 2:
            timer.stop()
    timer = AsyncPeriodicTimer(0.01, beat, immediate=True)
    async with timer:
        assert await timer.join(10)
    assert len(beats) == 2
    assert asyncio.all_tasks() == {asyncio.current_task()}

asyncio.run(main())
print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("periodictimer-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["e2e ok"]
