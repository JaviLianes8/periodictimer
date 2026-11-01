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
- [x] QA round 1 fixes: all seven findings addressed; 481 tests pass
- [x] QA round 2 fixes: C3 and E-02 addressed; 500 tests pass
- [x] QA round 3 fixes: C4 and E-03 addressed; 508 tests pass
- [x] QA round 4 fixes: E-04 addressed; 516 tests pass
- [ ] Five QA lenses (item 19, separate stage)
- [ ] Independent reviewer (item 16, separate stage)
- [x] PR #3 opened from `release/1.0.0` to `main`
- [ ] Merge and publication (item 17, separate stage)

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
| 15. Four gates | PASS | Each exits zero; QA round 4 suite 516 passed |
| 16. Independent reviewer | PENDING | Separate stage |
| 17. Merge and publication | PENDING | PR #3 open; merge and publication are separate |
| 18. Mutation contracts | PASS | 18 preparation faults killed; lens e M17, N01, N09 and rounds 3/4 M24 detected |
| 19. Five QA lenses | PENDING | Round 4 finding fixed; independent re-verification pending |

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
most 200 lines while adding examples. Preparation left the fixed-grid math unchanged;
QA round 1 corrects rounded-boundary selection as described below.

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

## Preparation final gates

On 2026-11-01, each command exited 0: `ruff format --check .` (38 files), `ruff check .`,
`mypy --strict src` (9 modules), `mypy --strict src tests` (31 files), and `pytest`
(319 passed, no skips). The pytest run enabled `PERIODICTIMER_E2E=1`,
`PERIODICTIMER_E2E_PYPI=1` and the retrieved-source directory, with `--timeout=300`
and an explicit verification-directory basetemp. It includes strict twine checks,
archive inspection, the 31 doctest examples, installed-wheel typing and PyPI upgrade.

## QA round 1

Reviewed base: `41906152d32c29ab709311e273ef9a38d103267e` on `release/1.0.0`.
Fix commit: `4ef78250060acd263f50ca04f10f9c7c546550c1`
(`fix timer boundary selection and validation contracts`).
All seven submitted findings are addressed. Independent lens re-verification remains
pending; the checks below do not replace those verdicts. No finding is disputed.

| Findings | Change | Contract evidence |
| --- | --- | --- |
| A001, B-002 | Record completion before the post-callback clock read; preserve the clock error for join | `test_completion_contract.py`: both workers, successful and handled failing callbacks, exact error identity and final counters |
| A002 | Async start docstring requires a running event loop in the current thread | The supplied `repro_start_doc.py` succeeds in a `call_soon` callback with no current task and reports one call |
| B-001 | Correct estimated indices against rounded timestamps with exponential bracketing and binary search | `test_grid_contract.py`: both workers, exact/adjacent boundaries, small/large epochs, enormous plateaus and the largest finite timestamp |
| C1 | Require strings, compare underlying text without overridden equality, return canonical policy/mode values | `test_hostile_contract.py`: hostile valid/invalid string subclasses and nonstring equality spoofing on both constructors |
| C2 | Normalize numeric conversion errors and timeout overflow sign-check failures; suppress original exception chains | `test_hostile_contract.py`: int/float subclasses, four exception types, all three numeric options and both timers; bounded messages and rendered tracebacks |
| E-01 | Pin rejection of integer immediate/daemon flags and acceptance of actual booleans | `test_integer_boolean_flags_are_rejected`: 0, 1, -1 and 2 on both immediate options and thread daemon |

The initial 150 new contract cases ran before implementation changes: 54 failed and
96 passed. After fixes, all 150 passed. Twelve additional large-grid cases exposed
an upper-index overflow in both coalesce workers; those two failures were reproduced
before making indices beyond float range yield an infinite target. All 162 added
cases now pass. Public signatures and defaults are unchanged. CHANGELOG records every
runtime change, and GUIDE documents subclass validation behavior.

The supplied correctness tests and hostile-input tests were rerun against the working
source: 936 passed. The supplied 945-case boundary sweep now has zero mismatches,
including the 69 previously failing comparisons. Existing reviewer artifacts were
preserved; new output is under the certification scratch directory's `fix-r1` folder.

| Mutation | Original source | Mutated source | Detecting contract |
| --- | --- | --- | --- |
| Lens e M17: accept integers in `check_flag` | 12 passed | 12 assertion failures, exit 1 | `tests/test_hostile_contract.py::test_integer_boolean_flags_are_rejected` |

M17 ran in a separate scratch source copy. Production flag validation needed no change.
The mutation was detected by expected-TypeError assertions, not collection errors or
timeouts. This identifier is from lens e's independent table, not preparation M17.

On 2026-11-01, CPython 3.14.6 on Windows passed each required gate with exit 0:
`ruff format --check .` (41 files), `ruff check .`, `mypy --strict src` (9 modules),
and `pytest` (481 passed, no skips). The additional `mypy --strict src tests` check
passed for 34 files. Pytest used the 300-second per-test timeout and scratch basetemp,
with wheel/archive checks, installed-wheel typing, the real 0.2.0 upgrade and fetched
reference tests enabled. Other interpreter results above belong to preparation and
were not repeated in this fix round.

## QA round 2

Reviewed base: `0b22e79ce40f971ca019037c4ba8c6c854743c80` on `release/1.0.0`.
Fix commit: `f462acf5ce9487e2723a7f40a0e2fde7b9236085`
(`harden option classification and pin conversion error types`).
Both submitted findings are addressed. No finding is disputed. Independent lens
re-verification remains pending.

| Finding | Change | Contract evidence |
| --- | --- | --- |
| C3 | Classify string, numeric and boolean options using their actual types, without consulting instance-controlled `__class__` properties | `test_option_classification_ignores_instance_class_properties`: 13 cases across both timers, including interval, jitter, join timeout, mode, policy, immediate and thread daemon; exact error types, bounded messages and marker-free rendered tracebacks |
| E-02 | Require exactly TypeError for numeric conversion TypeError failures and ValueError for other conversion failures | `test_numeric_conversion_errors_are_bounded`: int/float subclasses, both timers, interval/jitter/join timeout and four conversion exception classes |

Before production changes, all 13 new C3 contracts failed with RuntimeError; the
74 existing hostile-input cases passed with the stronger E-02 assertions. After the
fix, all 13 pass without accessing the class property. Six additional acceptance
cases preserve registered real-number support for both timers' three numeric options.
Existing string-subclass, Decimal and Fraction contracts also pass. Public signatures
and defaults are unchanged. CHANGELOG records the classification behavior change;
E-02 requires no production exception-type change.

The supplied lens c recheck and scheduling sweep and lens e independent exception-type
tests pass against the fixed source: 65 passed. Evidence and isolated mutation copies
are retained under the certification scratch directory's `fix-r2` folder.

| Mutation | Original source | Mutated source | Detecting contract |
| --- | --- | --- | --- |
| Lens e N01: `_options._real` converts TypeError to ValueError | 48 passed | 8 failed, 40 passed, exit 1 | `test_numeric_conversion_errors_are_bounded`, interval and jitter TypeError cases |
| Lens e N09: `_timeout.check_timeout` converts TypeError to ValueError | 48 passed | 4 failed, 44 passed, exit 1 | `test_numeric_conversion_errors_are_bounded`, timeout TypeError cases |

Each mutation ran alone in a separate scratch source copy. Both were detected by
wrong-exception-type assertions, not collection failures or timeouts. The repository
source was never mutated.

On 2026-11-01, CPython 3.14.6 on Windows passed each required gate with exit 0:
`ruff format --check .` (41 files), `ruff check .`, `mypy --strict src` (9 modules),
and `pytest` (500 passed, no skips). The additional `mypy --strict src tests` check
passed for 34 files. Pytest used a 300-second per-test timeout and scratch basetemp,
with wheel/archive checks, installed-wheel typing, the real 0.2.0 upgrade and fetched
reference tests enabled. The interpreter matrix was not repeated in this fix round.

## QA round 3

Reviewed base: `877e26481cfec2ce24695e46e1d844b0348bc179` on `release/1.0.0`.
Fix commit: `95e867a0b0871ae2e437cb4a9c8f1485794f1221`
(`harden numeric classification and cover infinite joins`).
Both submitted findings are addressed. No finding is disputed. Independent lens
re-verification remains pending.

| Finding | Change | Contract evidence |
| --- | --- | --- |
| C4 | Protect numeric ABC classification and normalize ordinary metaclass failures to bounded, option-specific TypeError with suppressed exception chains | `test_numeric_classification_errors_are_bounded`: hostile metaclass hash, interval/jitter/join timeout, both timers; exact error type, message bounds and marker-free rendered tracebacks |
| E-03 | Require infinite joins to wait for active callback completion and return True | `test_join_infinity_contract.py`: event-controlled callbacks on both timers; thread join checks unlimited delegation before releasing the callback, async join stays pending until release |

Before production changes, all six new C4 cases failed with RuntimeError and both
infinity cases passed. After the fix, all eight pass; the combined new and existing
hostile-input contracts pass 101 cases. Registered real numbers, Decimal, Fraction,
numeric subclasses and existing conversion-error types remain covered. Public
signatures and defaults are unchanged. CHANGELOG records the classification change.
E-03 requires no production behavior change.

The supplied lens c regression checks and 40-probe sweep, plus lens e's independent
infinity probe, pass against the fixed source: 43 passed. Logs and the isolated
mutation copy are under the certification scratch directory's `fix-r3` folder.

| Mutation | Original source | Mutated source | Detecting contract |
| --- | --- | --- | --- |
| Lens e round 3 M24: positive-infinity timeout returns 0.0 instead of None | 2 passed | 2 assertion failures, exit 1 | `test_thread_infinite_join_waits_for_active_callback` and `test_async_infinite_join_waits_for_active_callback` |

The exact mutation ran in a separate scratch source copy. Both failures are contract
assertions, not collection failures or timeouts. The repository source was never
mutated. Callback release and worker cleanup run even when assertions fail.

On 2026-11-01, CPython 3.14.6 on Windows passed each required gate with exit 0:
`ruff format --check .` (43 files), `ruff check .`, `mypy --strict src` (9 modules),
and `pytest` (508 passed, no skips). The additional `mypy --strict src tests` check
passed for 36 files. Pytest used a 300-second per-test timeout and scratch basetemp,
with wheel/archive checks, installed-wheel typing, the real 0.2.0 upgrade and fetched
reference tests enabled. The interpreter matrix was not repeated in this fix round.

## QA round 4

Reviewed base: `4355ebc1fa37acbf0e872721c173965b493d3f59` on `release/1.0.0`.
Fix commit: `40711f4399c33c9cbf6f38b2738e3b89597a41c1`
(`pin negative join polling contracts`).
The submitted finding E-04 is addressed. No finding is disputed. Independent lens
re-verification remains pending.

| Finding | Change | Contract evidence |
| --- | --- | --- |
| E-04 | Require finite negative join timeouts to poll active callbacks and return False | `test_join_negative_contract.py`: both timers, -60.0, -0.25, the smallest negative subnormal and -1e300; zero timeout at the real blocking boundary, callback still active, zero completed calls before release and one after cleanup |

The eight new contracts pass on the reviewed source: this finding concerns missing
regression coverage, not an existing runtime defect. Public API and behavior are
unchanged, so no CHANGELOG behavior entry is needed. Events hold each callback open;
boundary assertions establish polling without elapsed-time thresholds. The real thread
join and asyncio wait still execute. Callback release and worker cleanup run even if
an assertion fails.

| Mutation | Original source | Mutated source | Detecting contract |
| --- | --- | --- | --- |
| Lens e round 4 M24: replace `max(result, 0.0)` with `abs(result)` in timeout normalization | 8 passed | 8 assertion failures, exit 1 | `test_thread_negative_join_polls_active_callback` and `test_async_negative_join_polls_active_callback` |

The exact mutation ran in an isolated scratch source copy, alongside the reviewer's
two independent public-API probes. Combined results: 10 passed on original source,
10 failed on mutated source. All eight new contract failures are explicit zero-timeout
assertions, not collection failures or test timeouts. The reviewer probes separately
confirm that the mutant waits instead of polling. The repository source was never
mutated. Logs and the reproduction script are under the certification scratch
directory's `fix-r4` folder.

On 2026-11-01, CPython 3.14.6 on Windows passed each required gate with exit 0:
`ruff format --check .` (44 files), `ruff check .`, `mypy --strict src` (9 modules),
and `pytest` (516 passed, no skips). The additional `mypy --strict src tests` check
passed for 37 files. Pytest used a 300-second per-test timeout and scratch basetemp,
with wheel/archive checks, installed-wheel typing, the real 0.2.0 upgrade and fetched
reference tests enabled. The interpreter matrix was not repeated in this fix round.

## Later stages

QA lens re-verification and the independent reviewer are pending. Merge and publication
are reserved for the release stage. No passing verdict is claimed for those stages here.
The preparation changes are available in [PR #3](https://github.com/JaviLianes8/periodictimer/pull/3).
