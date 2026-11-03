"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with PERIODICTIMER_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
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
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False, timeout=120
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    import venv

    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("periodictimer-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    if os.environ.get("PERIODICTIMER_E2E_PYPI") == "1":
        previous = _run(python, "-m", "pip", "install", "-q", "periodictimer==0.2.0")
        assert previous.returncode == 0, previous.stderr
        baseline = _run(python, "-I", "-c", PROGRAM, cwd=tmp_path)
        assert baseline.returncode == 0, baseline.stderr
        version = _run(python, "-I", "-c", "import periodictimer; print(periodictimer.__version__)")
        assert version.stdout.strip() == "0.2.0"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["e2e ok"]
    version = _run(python, "-I", "-c", "import periodictimer; print(periodictimer.__version__)")
    assert version.stdout.strip() == "1.0.0"
    entrypoints = _run(
        python,
        "-I",
        "-c",
        "import importlib.metadata as m; assert not m.distribution('periodictimer').entry_points",
    )
    assert entrypoints.returncode == 0, entrypoints.stderr
    consumer = work / "consumer.py"
    consumer.write_text(
        "from periodictimer import PeriodicTimer, AsyncPeriodicTimer\n"
        "def tick() -> None: pass\n"
        "async def atick() -> None: pass\n"
        "timer = PeriodicTimer(1, tick, on_missed='burst', daemon=False)\n"
        "period: float = timer.interval\n"
        "epoch: float | None = timer.epoch\n"
        "calls: int = timer.calls + timer.missed\n"
        "running: bool = timer.is_running()\n"
        "joined: bool = timer.join(0)\n"
        "async def consume() -> bool:\n"
        "    async with AsyncPeriodicTimer(1, atick) as other:\n"
        "        other.stop()\n"
        "        await other.aclose()\n"
        "        return await other.join()\n",
        encoding="utf-8",
    )
    typed = _run(
        sys.executable,
        "-m",
        "mypy",
        "--strict",
        "--no-incremental",
        "--python-executable",
        python,
        "--cache-dir",
        tmp_path / "mypy-cache",
        consumer,
        cwd=work,
    )
    assert typed.returncode == 0, typed.stdout + typed.stderr
