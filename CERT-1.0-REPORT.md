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
- [x] Built-wheel consumer, PyPI upgrade and inspected archives (items 8, 14)
- [x] Every available supported interpreter (item 10): 12 distinct builds
- [x] Mutation round: 18 faults, 18 killed (item 18)
- [x] Final four gates (item 15): 319 tests pass with e2e and upgrade enabled
- [ ] Five QA lenses (item 19, separate stage)
- [ ] Independent reviewer (item 16, separate stage)
- [ ] PR ready; merge and publication (item 17, separate stage)

## Scorecard

| Item | Result | Evidence |
| --- | --- | --- |
| 1. Stable API | PASS | Constructors, methods, defaults and error classes reviewed and pinned |
| 2. Exact exports | PASS | Two names in `__all__`, package namespace contract, public imports in docs |
| 3. Executable docstrings | PASS | 31 doctest examples; five README examples execute and match output |
| 4. Strict types | PASS | `mypy --strict src tests`, installed-wheel typed consumer, `py.typed` |
| 5. Typed, bounded errors | PASS | Validation contracts and installed 0.2.0/1.0.0 comparison |
| 6. Complete contracts | PASS | Both timers, scheduling, lifecycle, options, errors and cancellation |
| 7. Real ground truth | PASS | Live CPython source retrieval, stdlib and fetched scheduler execution |
| 8. Installed wheel e2e | PASS | Fresh venv, isolated consumer, real thread/task behavior, upgrade; no CLI |
| 9. Seeded properties | PASS | Model timelines, reference timelines, malformed options, stress and fairness |
| 10. Supported Python | PASS | Twelve distinct installed builds, including embedded and free-threaded |
| 11. README | PASS | Problem, alternatives, install, examples, absolute links and strict twine check |
| 12. CHANGELOG | PASS | 1.0.0 dated 2026-11-01; all runtime changes listed |
| 13. Metadata | PASS | 1.0.0, Production/Stable, Python classifiers, MIT, URLs, no runtime dependencies |
| 14. Archives | PASS | Exact member lists, license and type marker; wheel rebuilt from sdist |
| 15. Four gates | PASS | Each exits zero; final suite 319 passed |
| 16. Independent reviewer | PENDING | Separate stage |
| 17. Merge and publication | PENDING | Separate stage |
| 18. Mutation contracts | PASS | 18 injected faults, all killed by assertions |
| 19. Five QA lenses | PENDING | Separate stage; no verdict recorded |

## API and behavior

The two exported classes retain the 0.2.0 constructor signatures, parameter names and
defaults. Contract tests pin constructors, methods, read-only properties and `__all__`.
Each public class, ordinary method and property has a runnable example; 31 doctest
examples include the inherited properties. The classes keep their original module identity.

Changes against 0.2.0, all documented in CHANGELOG and GUIDE: huge negative integer join
timeouts now mean zero; `PeriodicTimer(clock=None)` fails at construction; signalling
decimal NaNs name the invalid option; validation no longer echoes policy/mode values or
type names. The incidental `annotations` binding is removed. Async workers now yield
between callbacks so continuous catch-up cannot monopolize the loop. Callback and hook
exceptions retain their identity. Logging caller errors can expose caller-provided data,
as documented. No parser, codec or CLI is provided.

The asyncio worker was separated into a private module to keep each source file at
most 200 lines while adding examples. The fixed-grid and missed-slot math is unchanged.

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
There are 640 stdlib and 200 fetched-reference timelines, each with 40 callbacks on both
public timers: 67,200 start-time comparisons. A captured example with epoch 8, interval
0.5 and callback durations `[3.5, 0, 0, 0]` produced `[8.5, 12, 12, 12]` for burst and
`[8.5, 12.5, 13, 13.5]` for fixed delay, identically in the reference and thread timer.

Skip and coalesce are project-defined contracts, tested against the existing exhaustive
slot-walking model: 40 seeds, 50 timelines per seed, three policies and 30 callbacks per
timeline. Additional properties cover jitter, decimal intervals and cancellation. Three
new seeds exercise 12,000 invalid-option calls, including controls and lone surrogates.

## Packaging and upgrade

The wheel was built, installed into a fresh venv and consumed from an empty directory
with isolated Python. Both timers, real clocks, missed ticks, invalid inputs, counters,
shutdown and the type marker were exercised. A strict typed external consumer passed
against that installation. No console entry point is declared or installed.

The actual PyPI 0.2.0 release passed the same consumer before an in-place wheel upgrade
to 1.0.0. Separate installed-version probes confirmed every runtime difference above:
the large negative async timeout changes from timing out to returning False; catch-up
permits another task after one callback instead of five in a bounded reproduction;
invalid policy and mode messages shrink from 600,054/600,051 characters to 46/43 without
echoing input; signalling NaNs name their option; `clock=None` fails at construction;
the incidental namespace binding is absent. All are documented in CHANGELOG.

`python -m build` produced both archives and rebuilt the wheel from the sdist.
`twine check --strict` passed for both. Exact archive contents are asserted by
`tests/test_archives.py`: wheel package files, type marker, metadata and MIT license;
sdist package sources, README, GUIDE, CHANGELOG, license, pyproject, PKG-INFO and Hatch's
required `.gitignore`. No tests, reports, caches, scratch files or fetched content ship.

## Supported interpreters

The Windows launcher contains stale paths, so live installations were also discovered
on disk. Full-suite results for each distinct available version are recorded below.
Embedded runtimes are copied into the verification directory with isolated dependencies;
the opt-in wheel test imports `venv` only when enabled because embedded Python omits it.
The stress test compares the final task set with its initial task set: on Python 3.10
and 3.11, `asyncio.wait_for` adds a wrapper task which is not a leaked timer worker.

| CPython | Passed | Skipped |
| --- | --- | --- |
| 3.10.11 | 312 | 7 |
| 3.10.22 | 312 | 7 |
| 3.11.9 | 316 | 3 |
| 3.11.11 | 316 | 3 |
| 3.11.18 | 316 | 3 |
| 3.12.10 | 317 | 2 |
| 3.12.16 | 317 | 2 |
| 3.13.2 | 317 | 2 |
| 3.13.18 | 317 | 2 |
| 3.14.6 | 317 | 2 |
| 3.14.10 | 317 | 2 |
| 3.14.10t | 317 | 2 |

The two opt-in packaging tests are skipped in the matrix and run in the final gate.
Python 3.11 also skips the eager task factory test; Python 3.10 additionally skips four
cancellation-count tests requiring Python 3.11. The 3.14.10t run used `PYTHON_GIL=0`.
No discovered supported version was left untested. Python 3.13t and 3.15 were not present.

## Mutation round

Each mutation was injected alone into a separate source copy and run against the named
contract test. All 18 exited 1 with a contract failure, not a collection failure or
timeout. Production files were never replaced by mutations. The final suite passes
without these faults. No surviving mutation remains.

| ID | Mutation | Result | Detecting contract |
| --- | --- | --- | --- |
| M01 | immediate starts one slot late | killed | `tests/test_timer_fake.py::test_immediate_fires_at_the_epoch` |
| M02 | drop the epoch from deadlines | killed | `tests/test_timer_fake.py::test_calls_land_exactly_on_the_slots` |
| M03 | skip rounds down | killed | `tests/test_timer_fake.py::test_missed_slot_policies[skip-expected0-3]` |
| M04 | coalesce rounds up | killed | `tests/test_timer_fake.py::test_missed_slot_policies[coalesce-expected1-2]` |
| M05 | double the calls counter | killed | `tests/test_timer_fake.py::test_calls_land_exactly_on_the_slots` |
| M06 | count the next slot as missed | killed | `tests/test_timer_fake.py::test_missed_slot_policies[skip-expected0-3]` |
| M07 | fixed delay omits the interval | killed | `tests/test_reference.py::test_both_timers_match_real_stdlib_scheduler[False-True-0]` |
| M08 | discard the jitter sample | killed | `tests/test_timer_fake.py::test_jitter_delays_calls_without_moving_the_slots` |
| M09 | halve the maximum thread wait | killed | `tests/test_timer_fake.py::test_waits_are_capped_at_the_threading_limit` |
| M10 | accept bool as an interval | killed | `tests/test_options.py::test_rejects_an_interval_that_is_not_a_real_number[True-PeriodicTimer]` |
| M11 | wrong exception for noncallable hooks | killed | `tests/test_options.py::test_rejects_a_hook_that_cannot_be_called[fn-PeriodicTimer]` |
| M12 | unstarted join reports false | killed | `tests/test_lifecycle.py::test_join_before_start_returns_true_at_once` |
| M13 | async join lies about a live task | killed | `tests/test_atimer_lifecycle.py::test_stop_never_cancels_a_running_callback` |
| M14 | keep running after error-handler failure | killed | `tests/test_errors.py::test_a_raising_handler_is_logged_and_stops_the_timer` |
| M15 | huge negative timeout waits forever | killed | `tests/test_contract_v1.py::test_thread_join_normalizes_an_overflowing_negative_timeout` |
| M16 | restore unbounded policy messages | killed | `tests/test_validation_v1.py::test_policy_errors_never_echo_input[on_missed-PeriodicTimer]` |
| M17 | remove asyncio fairness yield | killed | `tests/test_async_fairness.py::test_every_callback_yields_to_allow_stop[1.0-fixed_rate-2.0]` |
| M18 | restore incidental package export | killed | `tests/test_contract.py::test_all_lists_exactly_the_public_api` |

## Final gates

On 2026-11-01, each command exited 0: `ruff format --check .` (38 files), `ruff check .`,
`mypy --strict src` (9 modules), `mypy --strict src tests` (31 files), and `pytest`
(319 passed, no skips). The pytest run enabled `PERIODICTIMER_E2E=1`,
`PERIODICTIMER_E2E_PYPI=1` and the retrieved-source directory, with `--timeout=300`
and an explicit verification-directory basetemp. It includes strict twine checks,
archive inspection, the 31 doctest examples, installed-wheel typing and PyPI upgrade.

## Later stages

QA lenses a-e and the independent reviewer are pending. Merge and publication are
reserved for the release stage. No verdict is claimed for those stages here.
