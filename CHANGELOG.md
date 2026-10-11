# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- First release.
- `PeriodicTimer(interval, fn)`: run a callback every `interval` seconds on a background
  thread, scheduled against a fixed monotonic epoch so periods do not drift, unlike the
  reschedule-after-each-call pattern built on `threading.Timer` (one-shot) or chained
  `time.sleep`, where the callback's run time accumulates into later ticks.
- `start()`, `stop()` and `join()`; `stop()` interrupts a pending wait so shutdown is prompt.
- Optional immediate first run and a documented missed-tick policy (`skip` or `burst`).
- Callback exceptions are routed to an optional `on_error` handler and never stop the timer.
