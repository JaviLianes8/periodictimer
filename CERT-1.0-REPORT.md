# periodictimer 1.0.0 certification report

Preparation started 2026-11-01 from main `b076653088607e80d34b9d442769a049c1471dc8`.
PyPI JSON and the published 0.2.0 wheel were fetched on that date. All eight Python
modules in that wheel are byte-identical to the starting tree.

Progress:
- [x] Baseline: format, lint, strict types; 248 tests passed, one opt-in e2e skipped
- [x] API stability, bounded errors, executable docstrings and strict typing (items 1-5)
- [x] Public contracts and seeded properties (items 6, 9)
- [x] Live reference retrieval and independent scheduler comparison (item 7)
- [x] README, GUIDE, dated CHANGELOG and stable metadata (items 11-13)
- [ ] Built-wheel consumer, PyPI upgrade and inspected archives (items 8, 14)
- [ ] Every available supported interpreter (item 10)
- [ ] Mutation round with at least ten killed faults (item 18)
- [ ] Final four gates (item 15)
- [ ] Five QA lenses (item 19, separate stage)
- [ ] Independent reviewer (item 16, separate stage)
- [ ] PR ready; merge and publication (item 17, separate stage)

## API and behavior

The two exported classes retain the 0.2.0 constructor signatures, parameter names and
defaults. Contract tests pin constructors, methods, read-only properties and `__all__`.
Each public class, ordinary method and property has a runnable example; doctests include
the inherited properties. The classes keep their original module identity.

Changes against 0.2.0, all documented in CHANGELOG and GUIDE: huge negative integer join
timeouts now mean zero; `PeriodicTimer(clock=None)` fails at construction; signalling
decimal NaNs name the invalid option; validation no longer echoes policy/mode values or
type names. Callback and hook exceptions retain their identity. Logging caller errors
can expose caller-provided data, as documented. No parser, codec or CLI is provided.

The asyncio worker was separated into a private module to keep each source file at
most 200 lines while adding examples. No scheduling algorithm was changed.

## Ground truth

Retrieved live on 2026-11-01: CPython v3.14.6 `Lib/sched.py` and the `sched`, `threading`,
`time`, and `asyncio-task` documentation sources. Exact URLs, revisions, sizes, SHA-256
hashes and licenses are in `tests/upstream/MANIFEST.json`. `scripts/fetch_upstream.py`
re-fetches and verifies them. External content stays outside the repository and both
archives. Optional reference tests skip if no retrieval directory is supplied.

`tests/test_reference.py` executes both the installed stdlib scheduler and the fetched
CPython scheduler as independent reference implementations. For fixed-rate burst it
queues absolute deadlines; for fixed delay it queues the next callback after completion.
Both public timers must reproduce the resulting real program output exactly. Synthetic
workloads are explicitly labeled; they are not presented as upstream vectors.

Skip and coalesce are project-defined contracts, tested against the existing exhaustive
slot-walking model: 40 seeds, 50 timelines per seed, three policies and 30 callbacks per
timeline. Additional properties cover jitter, decimal intervals and cancellation. Three
new seeds exercise 12,000 invalid-option calls, including controls and lone surrogates.

## Remaining verification

Packaging, interpreter matrix, mutation results and final gates will be recorded below
when run. QA lens and independent reviewer verdicts are pending; this preparation report
does not substitute for those stages.
