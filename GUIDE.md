# periodictimer guide

## Stable public API

Import `PeriodicTimer` and `AsyncPeriodicTimer` from `periodictimer`. The package also
provides `__version__`. All other modules are implementation details. Python 3.10+
is required. There is no CLI and no runtime dependency.

Both constructors take `interval, fn` positionally or by keyword. All later options
are keyword-only:

| Option | Default | Contract |
| --- | --- | --- |
| `interval` | required | Positive finite seconds, converted to float; bool refused |
| `fn` | required | No-argument callable; asyncio awaits its result |
| `immediate` | `False` | Real bool; first slot at start rather than one interval later |
| `on_missed` | `"skip"` | `"skip"`, `"coalesce"`, or `"burst"` |
| `mode` | `"fixed_rate"` | `"fixed_rate"` or `"fixed_delay"` |
| `jitter` | `0.0` | Finite seconds in the inclusive range zero to interval |
| `rng` | `None` | `random.Random` used for jitter; otherwise a fresh instance |
| `on_error` | `None` | Synchronous callable accepting an `Exception` |
| `name` | `None` | Worker thread/task name; does not affect scheduling |
| `clock` | see below | Zero-argument callable returning a finite monotonic float |
| `daemon` | `True` | Thread timer only; real bool |
| `waiter` | `None` | Thread timer only; callable receiving seconds, returning bool |
| `sleep` | `None` | Async timer only; callable receiving seconds, returning an awaitable |

The type hints use `float` (including Python integers). Runtime numeric validation
also accepts `numbers.Real` and `decimal.Decimal`, converting them to float. Finite
values that underflow to zero are invalid intervals. `rng` is checked for a callable
`uniform` method at runtime; custom RNGs must honor its bounds and return a finite float.

## Lifecycle and state

`start()` anchors `epoch` and creates one worker. A timer starts once, even if it has
finished. Calling `start()` twice or after `stop()` raises `RuntimeError`. The asyncio
timer requires a running loop and is used from that loop only. To stop it from another
thread use `loop.call_soon_threadsafe(timer.stop)`.

`stop()` is idempotent and returns immediately. It interrupts the default wait but lets
an active callback finish. `join(timeout=None)` returns `True` once the worker has ended
and `False` if it is still running when the timeout expires. Await the async version.
Before start, join returns `True`, which does not prevent a later start. After a started
timer has joined successfully no further callback runs. Joining from its own callback
raises `RuntimeError`; call `stop()` there instead. The callback may run on the background
thread before `start()` returns, so assign the timer before calling `start()`.

`None` and positive infinity timeouts mean unlimited waiting; negative timeouts mean
zero. Positive finite timeouts are capped at `threading.TIMEOUT_MAX`. A positive integer
too large to convert to float also means unlimited waiting. Bool and nonnumbers raise
`TypeError`; NaN raises `ValueError`. An async join timeout or cancellation does not
cancel the worker. External cancellation of the worker is treated as completion by
join; `stop()` only withdraws its own pending cancellation where Python supports that.

`with PeriodicTimer(...) as timer` starts, then stops and joins on exit. The async
equivalent is `async with AsyncPeriodicTimer(...) as timer`. `await timer.aclose()`
stops and joins an async timer. A nonterminating callback can therefore prevent context
exit. There is no forced termination of callbacks.

| Read-only state | Meaning |
| --- | --- |
| `interval` | Configured period as float |
| `epoch` | Clock reading at start, or `None` before start |
| `calls` | Finished invocations, including those that raised |
| `missed` | Slots dropped by skip or coalesce; zero for burst or fixed delay |
| `is_running()` | Whether the worker is still alive |

Counters are live observations, not a transaction across fields. Read them after join
for a final snapshot. Timer objects are lifecycle resources, not serializable values.

## Scheduling and numerical limits

Fixed-rate slot `n` is `epoch + n * interval`; the first index is 1, or 0 for immediate
timers. A callback never overlaps another callback of the same timer. Each wake-up
rechecks the clock before invoking the callback.

After a callback ends, skip discards past slots and waits for the first slot not yet
past. Coalesce keeps the latest slot due by now, representing missed work with one late
call. Burst visits every slot in order. If a callback ends exactly at the next slot,
that slot is retained by all policies. Fixed delay ignores the missed-tick policy and
sets the next deadline one interval after the callback finishes.

Jitter adds a uniform delay in `[0, jitter]` to each deadline without moving the grid.
Zero jitter consumes no RNG draws. If jitter or callback duration exceeds the available
time until the next slot, skip/coalesce may drop slots. Burst can run continuously when
work cannot keep up; choose skip if dropping work is preferable to catch-up.
The asyncio worker yields to other tasks between callbacks even when the next slot is
already overdue. This permits external stop requests; a callback that itself blocks
the event loop still prevents cooperative shutdown.

The default clocks are `time.monotonic` and the running loop's `time`. Thread waits are
capped at `threading.TIMEOUT_MAX`. Intervals up to `1e300` seconds are tested. Precision
is limited by floats and the clock: extremely small intervals can map adjacent slots to
the same float. If elapsed time divided by a subnormal interval overflows, the scheduler
advances one slot rather than calculating an unrepresentable missed-slot count. There
is no hard real-time guarantee or promise of exact decimal boundaries.

Custom clocks must remain finite and monotonic; waiters and sleeps must eventually
advance the clock, yield or stop. A thread waiter returns `True` to stop, `False` to
continue. Custom blocking hooks control their own responsiveness to stop. A custom
async sleep must yield to the loop, particularly during burst catch-up.

## Errors

Invalid types raise `TypeError`; invalid numeric values, policies and modes raise
`ValueError`. Messages identify the option without echoing arbitrary input. A coroutine
function cannot be a thread callback or an error handler. Policy and mode accept string
subclasses by their underlying text, without invoking overridden equality. Numeric
conversion failures are normalized to option-specific `TypeError` or `ValueError`
messages without exposing the original exception chain. A returned coroutine is
closed before reporting the mismatch. An async callback returning a non-awaitable is
reported as `TypeError` through the same callback-error path.

An ordinary callback `Exception` goes to `on_error`, or is logged with its traceback on
the `periodictimer` logger. The timer continues unless the handler calls stop or raises.
A raising handler is logged and stops the worker. A handler returning an awaitable is
also an error and stops it. Caller exceptions and their tracebacks are preserved, so
applications handling sensitive data should supply a handler with appropriate logging.
Errors raised by clock, waiter or sleep end the worker and are re-raised by join.
`BaseException` subclasses, including cancellation, are not ordinary callback errors.

## Upgrade from 0.2.0

Install with `python -m pip install --upgrade periodictimer`. Names, signatures, defaults,
scheduling rules and normal callback behavior remain the same. The negative huge-integer
timeout now polls instead of waiting forever. A thread timer with `clock=None` fails
at construction; an async timer still uses the loop clock for `None`. Signalling decimal
NaNs produce option-specific `ValueError` messages. Invalid policy/mode values and type
names are no longer echoed in errors. Do not parse exception message text.
The incidental `annotations` package attribute is removed; it was not an export.
The async timer now yields between callbacks, so other tasks can run during catch-up
even when the callback never suspends. This may change interleaving with other tasks.

## Verification

From a repository checkout, install `.[dev]` and run `scripts/check.ps1`.
`PERIODICTIMER_E2E=1` enables a built-wheel
consumer in a fresh virtual environment. `PERIODICTIMER_E2E_PYPI=1` additionally installs
the published 0.2.0 release before upgrading that environment. No CLI is installed.
`scripts/fetch_upstream.py DIRECTORY` fetches the pinned sources whose metadata is in
`tests/upstream/MANIFEST.json`; set `PERIODICTIMER_UPSTREAM` to that directory for source
integrity checks. The stdlib `sched` oracle runs without downloads. External files are
never included in the distributions.
