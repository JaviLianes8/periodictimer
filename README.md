# periodictimer

Drift-free repeating timer that runs a callback on a background thread

## Install

```
pip install periodictimer
```

## Usage

```python
import time

from periodictimer import PeriodicTimer


def poll() -> None:
    print("tick")


timer = PeriodicTimer(5.0, poll)
timer.start()
time.sleep(17)
timer.stop()
timer.join()
```

`poll` runs every five seconds. Each tick is scheduled at `start + n * interval`, so the
work inside `poll` never pushes the next tick back: over an hour the calls stay aligned to
the original start instead of sliding later and later.

Run the first call right away, and catch up on ticks missed while a slow callback ran:

```python
timer = PeriodicTimer(5.0, poll, immediate=True, on_missed="burst")
```

Options:

- `immediate` (default `False`): fire once at the start before waiting the first interval.
- `on_missed` (default `"skip"`): when a callback runs longer than the interval, `"skip"`
  drops the missed ticks and realigns to the next future slot (they are coalesced into one
  call), while `"burst"` fires the callback once per missed slot until it catches up.
- `on_error`: a callable that receives any exception raised by the callback. A failing
  callback never stops the timer; without a handler the exception is swallowed.
- `clock`: the time source, `time.monotonic` by default.

`stop()` signals the thread and returns at once, interrupting any wait in progress, so a
pending tick does not delay shutdown. Call `join()` to wait for the thread to end.

## Why

`threading.Timer` is one-shot: to repeat it you reschedule after each call, which drifts,
because every period silently absorbs the callback's own run time. Chaining
`time.sleep(interval)` has the same flaw, and the error accumulates. `schedule` and
`APScheduler` solve the general case but pull in a framework for what should be a few lines.
`periodictimer` is the small, typed, zero-dependency middle ground: a repeating timer that
schedules against a fixed monotonic epoch so it does not drift, with an explicit,
documented policy for ticks missed by a slow callback. It depends only on `threading`.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
