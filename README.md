# periodictimer

Drift-free repeating timers for threads and asyncio: a callback every `interval` seconds,
on a monotonic clock, with an explicit policy for ticks missed by a slow callback.

## Install

```
pip install periodictimer
```

Python 3.10 or newer, no dependencies.

## Usage

`PeriodicTimer` runs a callback on one background thread:

```python
from periodictimer import PeriodicTimer

count = 0


def poll() -> None:
    global count
    count += 1
    print(f"tick {count}")
    if count == 3:
        timer.stop()  # stopping from inside the callback is fine


timer = PeriodicTimer(0.05, poll)
timer.start()
timer.join()  # returns once poll has stopped the timer
print(timer.calls)
# tick 1
# tick 2
# tick 3
# 3
```

Calls are scheduled at `epoch + n * interval`, where `epoch` is the monotonic clock value
read by `start()`. The time a call takes never pushes later calls back, and a late
wake-up of one tick is not carried into the next: over an hour the calls stay on the same
grid instead of sliding later and later. The timer is also a context manager:
`with PeriodicTimer(5.0, poll):` starts it, and leaving the block stops and joins it.

### Missed ticks

When a call runs past one or more slots, `on_missed` decides what happens:

- `"skip"` (default): drop the missed slots and wait for the next one not yet past.
- `"coalesce"`: make one call at once, late, standing in for every slot that was missed.
- `"burst"`: make one call per missed slot, back to back, until the timer catches up.

`missed` counts the slots dropped, `calls` the calls made. The `clock` and `waiter`
hooks make this exact in a test, with no real waiting:

```python
from periodictimer import PeriodicTimer


class Clock:
    """A clock that only moves when the code below moves it."""

    now = 0.0

    def __call__(self) -> float:
        return self.now


for policy in ("skip", "coalesce", "burst"):
    clock = Clock()
    seen: list[float] = []

    def job() -> None:
        seen.append(clock.now)
        if clock.now == 1.0:
            clock.now += 3.5  # the first run overruns three slots

    def waiter(seconds: float) -> bool:
        clock.now += seconds  # jump instead of sleeping
        return len(seen) >= 4  # True stops the timer

    timer = PeriodicTimer(1.0, job, on_missed=policy, clock=clock, waiter=waiter)
    timer.start()
    timer.join()
    print(policy, seen, timer.missed)
# skip [1.0, 5.0, 6.0, 7.0] 3
# coalesce [1.0, 4.5, 5.0, 6.0] 2
# burst [1.0, 4.5, 4.5, 4.5] 0
```

### Fixed delay and jitter

`mode="fixed_delay"` waits `interval` after each call ends instead of keeping a fixed
rate, for work that must rest between runs. `jitter` delays each call by a random amount
between zero and that many seconds, so many processes started together do not all hit a
server at the same instant; the slots themselves never move. Pass `rng=random.Random(seed)`
for a reproducible sequence.

```python
from periodictimer import PeriodicTimer


def refresh_cache() -> None: ...


timer = PeriodicTimer(60.0, refresh_cache, mode="fixed_delay", jitter=5.0)
print(timer)
# <PeriodicTimer refresh_cache every 60.0s, idle>
```

### Errors

An exception from the callback never stops the timer. It goes to `on_error` when given;
without a handler it is logged on the `periodictimer` logger, so a failure is never
silent. To give up, call `stop()` from the handler, or raise from it: an exception raised
by `on_error` is logged and stops the timer.

```python
from periodictimer import PeriodicTimer

attempts = 0


def sync() -> None:
    global attempts
    attempts += 1
    raise ConnectionError("database is down")


def report(exc: Exception) -> None:
    print(f"attempt {attempts}: {exc}")
    if attempts == 2:
        timer.stop()


timer = PeriodicTimer(0.01, sync, on_error=report)
timer.start()
timer.join()
# attempt 1: database is down
# attempt 2: database is down
```

### asyncio

`AsyncPeriodicTimer` takes the same options and awaits an async callback in one task,
scheduled on the loop's own clock:

```python
import asyncio

from periodictimer import AsyncPeriodicTimer


async def main() -> None:
    beats = 0

    async def heartbeat() -> None:
        nonlocal beats
        beats += 1
        print(f"beat {beats}")
        if beats == 2:
            timer.stop()

    timer = AsyncPeriodicTimer(0.05, heartbeat, immediate=True)
    async with timer:
        await timer.join()


asyncio.run(main())
# beat 1
# beat 2
```

`start()` needs a running loop, `stop()` returns at once, `await join(timeout)` waits for
the task and `await aclose()` does both. `stop()` cancels the task only while it sleeps,
never in the middle of the callback. The timer is not thread-safe: from another thread,
use `loop.call_soon_threadsafe(timer.stop)`.

## Options

Both timers take `interval` (seconds, a finite positive number) and the callback, then:

- `immediate` (default `False`): first call at the epoch instead of one interval later.
- `on_missed` (default `"skip"`): `"skip"`, `"coalesce"` or `"burst"`, see above.
- `mode` (default `"fixed_rate"`): or `"fixed_delay"`.
- `jitter` (default `0`): up to this many seconds of random delay per call, at most
  `interval`; `rng` is the `random.Random` it draws from.
- `on_error`: called with each exception the callback raises.
- `name`: the thread name, or the task name for the asyncio timer.
- `clock`: the time source, `time.monotonic` for threads and `loop.time` for asyncio.
- `daemon` (threads, default `True`): a daemon timer never keeps the program alive, but
  is cut off at exit; use `False` together with `stop()` and `join()` for a clean end.
- `waiter` (threads) and `sleep` (asyncio): hooks that replace the wait, for tests.

Bad values raise `TypeError` or `ValueError` when the timer is built, not later in the
worker.

## Guarantees

- No call starts before its slot: the clock is read again after every wake-up.
- No drift: slot `n` is always `epoch + n * interval`, whatever the calls cost.
- Calls never overlap: one worker waits for each call to return.
- `stop()` interrupts a pending wait at once; a call already running finishes, and
  `join()` waits for it. After `join()` returns `True` the callback never runs again.
- `join()` from inside the callback raises `RuntimeError` instead of hanging.
- A timer starts once; `start()` after `start()` or after `stop()` raises.
- Intervals up to `1e300` seconds work: waits are capped below the platform limit.

## Why

`threading.Timer` is one-shot: to repeat it you reschedule after each call, which drifts,
because every period silently absorbs the callback's own run time. Chaining
`time.sleep(interval)` has the same flaw, and the error accumulates. `schedule` and
`APScheduler` solve the general case but pull in a framework for what should be a few lines.
`periodictimer` is the small, typed, zero-dependency middle ground: a repeating timer for
threads or asyncio that schedules against a fixed monotonic epoch, with documented
policies for missed ticks, fixed delay, jitter and failures.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
