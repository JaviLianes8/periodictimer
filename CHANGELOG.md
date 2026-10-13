# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
  `RuntimeError`; `start()` after `stop()` raises.

### Fixed

- A NaN interval made the worker call the callback in a busy loop; NaN, infinite and
  `bool` intervals are now refused, as are bad jitter, policy and mode values.
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
