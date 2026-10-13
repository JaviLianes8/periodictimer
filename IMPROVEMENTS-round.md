# periodictimer improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [ ] Strict options: interval, jitter, policy and mode validated; huge intervals safe
- [ ] Scheduler core: fixed rate and fixed delay, skip, coalesce and burst, jitter, counters
- [ ] `PeriodicTimer`: never early, clean lifecycle, context manager, errors never silent
- [ ] `AsyncPeriodicTimer` for asyncio
- [ ] Contracts: reference model, stress invariants, no leaked threads, typing, README examples, installed wheel e2e
- [ ] Mutation run: every guard removed makes the suite fail
- [ ] Docs: README, CHANGELOG, docstrings, packaging metadata
- [ ] Gates: ruff format, ruff check, mypy --strict, pytest
- [ ] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

## Starting point

`0.1.0` ships `PeriodicTimer(interval, fn)`: one daemon thread, ticks at
`epoch + n * interval`, a missed-tick policy (`skip` or `burst`), `on_error`, an injectable
clock and a waiter. The drift-free core is right. Reading it as a user turns up these gaps:

- `interval=float("nan")` passes `interval <= 0` and makes the thread spin, calling the
  callback in a busy loop. `inf` and `bool` are accepted too.
- A very large interval hands `Event.wait` a timeout above `threading.TIMEOUT_MAX`, which
  raises `OverflowError` in the worker: the timer dies and never fires.
- A wait that returns slightly early fires the callback before its target: the loop never
  re-reads the clock after waking.
- `skip` drops a slot that is due exactly at the moment the callback ends, and the README
  calls skipping "coalescing", which it is not: no call is made for the missed ticks.
- Without `on_error`, a failing callback is swallowed in silence.
- An exception raised by `on_error` kills the worker through `threading.excepthook`.
- `join()` before `start()` raises, `join()` from inside the callback raises a bare
  threading error, `stop()` before `start()` is ignored and `start()` still runs.
  No context manager, no way to know whether `join(timeout)` finished.
- `epoch` is only known once the worker has run, so it is `None` right after `start()`.
- Fixed delay (wait `interval` after each call ends) and jitter are common needs with no
  answer; nothing tells the caller how many ticks were dropped.
- Nothing for asyncio.
- Packaging: no Python version classifiers, no wheel test, README examples never run.

## Sources (fetched 2026-10-13, docs.python.org/3 served the 3.15 pages)

- `time`, https://docs.python.org/3/library/time.html: `monotonic()` cannot go backwards
  and is not affected by system clock updates; its reference point is undefined, so only
  differences between two calls mean anything.
- `threading`, https://docs.python.org/3/library/threading.html: `Event.wait(timeout)`
  returns `True` when the flag is set and `False` on timeout; `TIMEOUT_MAX` is the largest
  timeout blocking calls accept, larger values raise `OverflowError`; `join()` on the
  current thread or on a thread not yet started raises `RuntimeError`; a thread can be
  joined many times; an exception escaping `run()` goes to `threading.excepthook`; daemon
  threads are stopped abruptly at shutdown, so a graceful stop needs a signal such as an
  `Event` and a non-daemon thread.
- `asyncio-eventloop`, https://docs.python.org/3/library/asyncio-eventloop.html:
  `loop.time()` is the loop's own monotonic clock; callbacks scheduled with `call_at` may
  run up to one clock resolution early.
- `asyncio-task`, https://docs.python.org/3/library/asyncio-task.html: the loop keeps only
  weak references to tasks, so a background task needs a strong reference; `cancel()`
  throws `CancelledError` into the coroutine at its next suspension point.

Consequences for the design: every wait is capped at `TIMEOUT_MAX` and followed by a fresh
clock read, so no call starts before its target whatever the waiter does. The thread stays
a daemon by default (a forgotten timer must not hang the program) with a `daemon=False`
option and a context manager for a graceful stop. The async timer holds its task, uses
`loop.time()` by default and only cancels its own task while it is sleeping, never while
the callback runs.

## Ranked improvements

1. **Strict options.** `interval` must be a finite positive real number (not `bool`);
   `jitter` finite, `0 <= jitter <= interval`; unknown policies and modes are refused;
   coroutine functions are refused by the thread timer. Waits capped at `TIMEOUT_MAX`.
2. **Never early, never drifting.** After every wake-up the clock is read again and the
   loop waits again if the target is still ahead. Targets stay `epoch + n * interval`.
3. **Missed-tick policies done right.** `skip` (wait for the next slot not yet past),
   `coalesce` (one late call for all the missed slots, then realign), `burst` (one call per
   missed slot, back to back). `missed` and `calls` counters on the timer.
4. **Fixed rate or fixed delay.** `mode="fixed_delay"` waits `interval` after each call
   ends, for work that must rest between runs.
5. **Jitter.** `jitter=` adds a random delay in `[0, jitter]` to each call without moving
   the schedule; `rng=` takes a seeded `random.Random` for reproducible runs.
6. **Errors are never silent.** Without `on_error` the exception is logged on the
   `periodictimer` logger and the timer keeps going; an exception raised by `on_error` is
   logged and stops the timer, which is the documented way to stop on the first failure.
7. **Clean lifecycle.** `epoch` set by `start()`; `stop()` before `start()` makes `start()`
   raise; `join(timeout)` returns whether the worker ended and is safe before `start()`;
   joining from inside the callback raises a clear `RuntimeError`; context manager;
   `daemon=` option. No call ever overlaps another (one worker).
8. **`AsyncPeriodicTimer`.** Same options with an async callback, `loop.time()` clock,
   `stop()`, `await join()`, `await aclose()`, `async with`; injectable `clock` and `sleep`
   for tests that never wait.
9. **Contracts that bite.** Reference model of the scheduler compared on thousands of
   seeded random timelines; fake clock and waiter tests for the thread; stress tests with
   many timers and random callback durations checking never-early, no overlap,
   `calls + missed` bookkeeping and that no thread outlives `join`; typing checked by mypy
   on a snippet; README examples run in the suite; installed wheel e2e; mutation run.
10. **Docs and packaging.** README with runnable examples and every guarantee stated,
    CHANGELOG, classifiers, sdist without this file.

Left out on purpose: wall-clock alignment ("every minute on the minute"), which needs the
system clock the design avoids; cron expressions and multi-job scheduling, which belong to
a scheduler; restarting a stopped timer (make a new one, as with `threading.Thread`).
