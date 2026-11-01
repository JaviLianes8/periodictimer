# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-01

### Stable

- `PeriodicTimer` and `AsyncPeriodicTimer`, their constructor signatures, lifecycle
  methods, read-only counters and scheduling policies are the stable public API.
- Python 3.10 and newer, no runtime dependencies, and a shipped `py.typed` marker.

### Fixed

- String, numeric and boolean option validation uses actual types without invoking
  instance-controlled `__class__` properties. Both timers reject hostile objects with
  bounded, option-specific errors, including join timeouts; real subclasses and
  registered real-number types remain supported.
- Both timers count completed invocations, including handled callback failures, before
  reading the clock again, so a failing clock cannot lose a completed call.
- Skip and coalesce select slots by their rounded grid timestamps, correcting quotient
  rounding at exact boundaries and neighboring floats without walking missed backlogs.
  Indices beyond float range have an infinite target instead of ending the worker
  with `OverflowError` when advancing beyond the largest finite timestamp.
- Policy and mode validation requires strings and ignores overridden subclass equality.
  Nonstring objects can no longer impersonate a valid option through equality.
- Numeric conversion failures for interval, jitter and join timeout produce bounded,
  option-specific `TypeError` or `ValueError` messages with suppressed exception chains.
  Timeout overflow sign checks receive the same protection.
- The async `start()` docstring correctly requires a running event loop in the current
  thread; ordinary event-loop callbacks may start a timer.
- The asyncio worker yields to the event loop between callbacks, including overdue
  bursts and intervals below clock precision, so another task can request stop.
- A negative integer timeout too large for a float now means zero, like other negative
  timeouts; in 0.2.0 it accidentally meant an unlimited wait.
- `PeriodicTimer(clock=None)` raises `TypeError` at construction instead of failing
  later in `start()`. The asyncio timer still accepts `None` for its default loop clock.
- Signalling decimal NaNs now raise `ValueError` naming the invalid interval, jitter
  or timeout instead of exposing the conversion error.

### Changed

- Option validation messages no longer echo invalid policy/mode values or type names.
  This bounds diagnostic size and avoids disclosing caller input. Exception classes
  are unchanged; callback and hook exceptions are still preserved.
- The incidental `annotations` binding is removed from the package namespace; it
  was never part of `__all__`.
- Public class, method and property docstrings include executable examples. The GUIDE
  describes lifecycle, numerical limits, error handling and upgrading from 0.2.0.
- Source distributions contain package sources, metadata, license, user docs and
  Hatch's required ignore file, without development tests or reports.

## [0.2.0]

### Added

- `AsyncPeriodicTimer`: the same timer for asyncio, awaiting an async callback in one task
  on the loop's clock, with `start()`, `stop()`, `await join()`, `await aclose()` and
  `async with`. `stop()` cancels the task only while it sleeps, never mid-callback.
- `on_missed="coalesce"`: one late call stands in for every missed slot.
- `mode="fixed_delay"`: wait `interval` after each call ends.
- `jitter` and `rng`: a bounded random delay per call that never moves the schedule.
- `calls` and `missed` counters, a context manager, a `daemon` option and a `repr`.
- `join(timeout)` returns whether the worker ended.

### Changed

- A callback failure with no `on_error` is now logged on the `periodictimer` logger
  instead of being swallowed. An exception raised by `on_error` is logged and stops the
  timer instead of killing the thread through `threading.excepthook`.
- `epoch` is set by `start()`, so it is known as soon as `start()` returns.
- `skip` no longer drops a slot that is due exactly when the previous call ends.
- `join()` before `start()` returns `True`; `join()` from the callback raises a clear
  `RuntimeError`; `start()` after `stop()` raises. `join()` re-raises an error that ended
  the worker, such as a failing `clock`, on both timers.
- `immediate` and `daemon` must be real bools; `rng` must have a `uniform` method; an
  `async def` `on_error` is refused, and a handler that returns an awaitable stops the
  timer instead of being silently dropped.

### Fixed

- A NaN interval made the worker call the callback in a busy loop; NaN, infinite and
  `bool` intervals are now refused, as are bad jitter, policy and mode values. Numbers too
  large for a float raise `ValueError`, and a subnormal interval no longer overflows the
  slot count.
- An interval above `threading.TIMEOUT_MAX` killed the worker with `OverflowError`; waits
  are now capped.
- A wait that woke up early could start a call before its slot; the clock is now read
  again after every wake-up.
- A coroutine function passed to `PeriodicTimer` is refused instead of never being
  awaited.

## [0.1.0]

- First release.
- `PeriodicTimer(interval, fn)`: run a callback every `interval` seconds on a background
  thread, scheduled against a fixed monotonic epoch so periods do not drift, unlike the
  reschedule-after-each-call pattern built on `threading.Timer` (one-shot) or chained
  `time.sleep`, where the callback's run time accumulates into later ticks.
- `start()`, `stop()` and `join()`; `stop()` interrupts a pending wait so shutdown is prompt.
- Optional immediate first run and a documented missed-tick policy (`skip` or `burst`).
- Callback exceptions are routed to an optional `on_error` handler and never stop the timer.
