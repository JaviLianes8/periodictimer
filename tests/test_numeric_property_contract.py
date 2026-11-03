"""Seeded property contracts: timing arguments against an exact-arithmetic oracle.

Random ints, floats (any bit pattern, so subnormals, zeros, infinities and NaNs),
fractions and decimals, plain or wrapped in subclasses, go through every timing
argument of both timers. The oracle converts each value exactly with ``Fraction`` and
rounds once, independently of the library, then applies the documented range rule.
"""

from __future__ import annotations

import asyncio
import math
import random
import struct
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest
from _numeric_domain import Dec, Float, Frac, Int
from _numeric_probes import TIMERS, AsyncJoinProbe, ThreadJoinProbe, interval_of, jitter_draws, same
from _numeric_rules import interval_rule, jitter_rule, timeout_rule

SEEDS = [3, 1729, 20261102]
COUNT = 1000


def draw(rng: random.Random) -> Any:
    kind = rng.randrange(6)
    if kind == 0:
        value: Any = struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0]
    elif kind == 1:
        value = rng.choice([-1, 1]) * rng.uniform(0, 10) ** rng.randrange(-5, 5)
    elif kind == 2:
        value = rng.choice([-1, 1]) * rng.getrandbits(rng.choice([1, 8, 53, 1023, 1024, 1100]))
    elif kind == 3:
        value = Fraction(rng.randrange(-(10**6), 10**6), rng.randrange(1, 10**6))
    elif kind == 4:
        digits = rng.randrange(10**12)
        value = Decimal(f"{rng.choice('+-')}{digits}E{rng.randrange(-400, 400)}")
    else:
        value = Decimal(rng.choice(["NaN", "-NaN", "sNaN", "Infinity", "-Infinity", "0", "-0"]))
    wrap = {float: Float, int: Int, Fraction: Frac, Decimal: Dec}.get(type(value))
    if wrap is not None and rng.random() < 0.3:
        value = wrap(value)
    return value


def exact(value: Any) -> Any:
    """The oracle: the float nearest the exact value, or the documented exception class."""
    if isinstance(value, Decimal) and not value.is_finite():
        return ValueError if value.is_nan() else math.copysign(math.inf, value)
    if isinstance(value, float) and not math.isfinite(value):
        return ValueError if math.isnan(value) else math.copysign(math.inf, value)
    ratio = Fraction(value)
    try:
        result = float(ratio)
    except OverflowError:
        return math.inf if ratio > 0 else -math.inf
    return result if ratio >= 0 else -abs(result)


def domain(seed: int) -> list[Any]:
    rng = random.Random(seed)
    return [draw(rng) for _ in range(COUNT)]


def outcome(action: Any) -> Any:
    try:
        return action()
    except Exception as exc:
        return exc


def matches(observed: Any, expected: Any) -> bool:
    if isinstance(expected, type):
        return type(observed) is expected
    return not isinstance(observed, Exception) and same(observed, expected)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("timer", TIMERS)
def test_interval_matches_the_oracle(seed: int, timer: Any) -> None:
    for value in domain(seed):
        expected = interval_rule(exact(value))
        observed = outcome(lambda value=value: interval_of(timer, value))
        assert matches(observed, expected), (repr(value), observed, expected)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("timer", TIMERS)
def test_jitter_matches_the_oracle(seed: int, timer: Any) -> None:
    rng = random.Random(seed + 1)
    for value in domain(seed)[:300]:
        interval = rng.choice([1.0, 0.5, 1e-3, 7.25, 1e6])
        expected = jitter_rule(exact(value), interval)
        observed = outcome(
            lambda value=value, interval=interval: jitter_draws(timer, value, interval)
        )
        if isinstance(expected, type) or isinstance(observed, Exception):
            assert matches(observed, expected), (repr(value), observed, expected)
        elif expected == 0:
            assert observed == [], (repr(value), observed)
        else:
            assert len(observed) == 1, (repr(value), observed)
            assert same(observed[0][1], expected), (repr(value), observed, expected)


@pytest.mark.parametrize("seed", SEEDS)
def test_thread_join_timeout_matches_the_oracle(seed: int) -> None:
    with ThreadJoinProbe() as probe:
        for value in domain(seed):
            expected = timeout_rule(value, exact(value))
            observed = outcome(lambda value=value: probe(value))
            assert matches(observed, expected), (repr(value), observed, expected)


@pytest.mark.parametrize("seed", SEEDS)
def test_async_join_timeout_matches_the_oracle(seed: int) -> None:
    async def main() -> None:
        async with AsyncJoinProbe() as probe:
            for value in domain(seed):
                expected = timeout_rule(value, exact(value))
                try:
                    observed: Any = await probe(value)
                except Exception as exc:
                    observed = exc
                assert matches(observed, expected), (repr(value), observed, expected)

    asyncio.run(main())


def test_the_domain_reaches_every_class_of_value() -> None:
    seen = {
        interval_rule(exact(value)) if isinstance(exact(value), type) else exact(value)
        for seed in SEEDS
        for value in domain(seed)
    }
    finite = [value for value in seen if isinstance(value, float) and math.isfinite(value)]
    assert ValueError in seen and math.inf in seen and -math.inf in seen
    assert any(value < 0 for value in finite) and any(0 < value < 1 for value in finite)
    assert any(value > 1e300 for value in finite) and 0.0 in seen
