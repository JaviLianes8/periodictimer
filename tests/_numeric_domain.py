"""The numeric domain every timing argument is pinned over.

Each row gives a value and, written out by hand, what the shared conversion must make
of it: an exact float (possibly infinite) or the exception class it must raise.
``Abort`` rows must propagate unchanged. The range rules live in ``_numeric_rules``.
"""

from __future__ import annotations

import math
import numbers
import sys
import threading
from decimal import Decimal
from fractions import Fraction
from typing import Any

MAX = sys.float_info.max
HALF_ULP_ABOVE_MAX = 2**1024 - 2**970  # the smallest integer that rounds to infinity
MARKER = "private-marker"
ABOVE_TIMEOUT_MAX = math.nextafter(threading.TIMEOUT_MAX, math.inf)


class Abort(BaseException):
    """Not an Exception: a validator must let it through untouched."""


class Int(int):
    pass


class IndexlessInt(int):
    def __index__(self) -> int:
        raise RuntimeError(MARKER)


class Float(float):
    pass


class LyingFloat(float):
    def __float__(self) -> float:
        return 2.5


class Dec(Decimal):
    pass


class Frac(Fraction):
    pass


class LiarMeta(type):
    def __hash__(cls) -> int:
        raise RuntimeError(MARKER)


class Unhashable(metaclass=LiarMeta):
    pass


class ClassLiar:
    @property  # type: ignore[misc]
    def __class__(self) -> type:
        return float


@numbers.Real.register
class Real:
    """A registered real whose conversion and sign come from its arguments."""

    def __init__(self, convert: Any, below_zero: Any = None) -> None:
        self.convert = convert
        self.below_zero = below_zero

    def __float__(self) -> float:
        if isinstance(self.convert, BaseException):
            raise self.convert
        return self.convert  # type: ignore[no-any-return]

    def __lt__(self, other: object) -> Any:
        if isinstance(self.below_zero, BaseException):
            raise self.below_zero
        return self.below_zero


class Truth:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __bool__(self) -> bool:
        if isinstance(self.value, BaseException):
            raise self.value
        return bool(self.value)


def boom(kind: type[BaseException]) -> BaseException:
    return kind(MARKER + "x" * 100_000)


ROWS: list[tuple[str, Any, Any]] = [
    # bool and non-numbers
    ("True", True, TypeError),
    ("False", False, TypeError),
    ("str", "1", TypeError),
    ("bytes", b"1", TypeError),
    ("complex", 1 + 0j, TypeError),
    ("list", [1], TypeError),
    ("object", object(), TypeError),
    ("class-liar", ClassLiar(), TypeError),
    ("hash-raising-metaclass", Unhashable(), TypeError),
    # ints and int subclasses
    ("zero", 0, 0.0),
    ("one", 1, 1.0),
    ("minus-one", -1, -1.0),
    ("int-subclass", Int(3), 3.0),
    ("int-index-raises", IndexlessInt(3), 3.0),
    ("int-largest-finite", HALF_ULP_ABOVE_MAX - 1, MAX),
    ("int-overflow", HALF_ULP_ABOVE_MAX, math.inf),
    ("int-huge", 10**400, math.inf),
    ("int-huge-negative", -(10**400), -math.inf),
    # floats
    ("0.0", 0.0, 0.0),
    ("-0.0", -0.0, -0.0),
    ("subnormal", 5e-324, 5e-324),
    ("negative-subnormal", -5e-324, -5e-324),
    ("fraction-0.75", 0.75, 0.75),
    ("below-one", 0.9999999999999999, 0.9999999999999999),
    ("above-one", 1.0000000000000002, 1.0000000000000002),
    ("-0.25", -0.25, -0.25),
    ("-60", -60.0, -60.0),
    ("timeout-max", threading.TIMEOUT_MAX, threading.TIMEOUT_MAX),
    ("above-timeout-max", ABOVE_TIMEOUT_MAX, ABOVE_TIMEOUT_MAX),
    ("1e300", 1e300, 1e300),
    ("float-max", MAX, MAX),
    ("-float-max", -MAX, -MAX),
    ("inf", math.inf, math.inf),
    ("-inf", -math.inf, -math.inf),
    ("nan", math.nan, ValueError),
    ("-nan", -math.nan, ValueError),
    ("float-subclass", Float(0.5), 0.5),
    ("float-subclass-own-float", LyingFloat(9.0), 2.5),
    ("float-subclass-inf", Float(math.inf), math.inf),
    # fractions and decimals
    ("third", Fraction(1, 3), 1 / 3),
    ("minus-third", Fraction(-1, 3), -1 / 3),
    ("fraction-subclass", Frac(3, 4), 0.75),
    ("fraction-underflow", Fraction(1, 10**400), 0.0),
    ("fraction-negative-underflow", Fraction(-1, 10**400), -0.0),
    ("fraction-overflow", Fraction(10**400, 3), math.inf),
    ("fraction-negative-overflow", Fraction(-(10**400), 3), -math.inf),
    ("decimal", Decimal("0.1"), 0.1),
    ("decimal-subclass", Dec("2.5"), 2.5),
    ("decimal-negative-zero", Decimal("-0"), -0.0),
    ("decimal-underflow", Decimal("1e-400"), 0.0),
    ("decimal-huge", Decimal("1e400"), math.inf),
    ("decimal-inf", Decimal("Infinity"), math.inf),
    ("decimal-negative-inf", Decimal("-Infinity"), -math.inf),
    ("decimal-nan", Decimal("NaN"), ValueError),
    ("decimal-snan", Decimal("sNaN"), ValueError),
    # registered reals with hostile conversion or sign
    ("real", Real(0.5), 0.5),
    ("real-returns-nan", Real(math.nan), ValueError),
    ("real-returns-str", Real("0.5"), TypeError),
    ("real-type-error", Real(boom(TypeError)), TypeError),
    ("real-value-error", Real(boom(ValueError)), ValueError),
    ("real-zero-division", Real(boom(ZeroDivisionError)), ValueError),
    ("real-runtime-error", Real(boom(RuntimeError)), ValueError),
    ("real-attribute-error", Real(boom(AttributeError)), ValueError),
    ("real-lookup-error", Real(boom(LookupError)), ValueError),
    ("real-os-error", Real(boom(OSError)), ValueError),
    ("real-plain-exception", Real(boom(Exception)), ValueError),
    ("real-abort", Real(Abort("stop")), Abort),
    ("overflow-positive", Real(OverflowError(), False), math.inf),
    ("overflow-negative", Real(OverflowError(), True), -math.inf),
    ("overflow-truthy-sign", Real(OverflowError(), Truth(1)), -math.inf),
    ("overflow-falsy-sign", Real(OverflowError(), Truth(0)), math.inf),
    ("overflow-sign-raises", Real(OverflowError(), boom(RuntimeError)), ValueError),
    ("overflow-sign-type-error", Real(OverflowError(), boom(TypeError)), ValueError),
    ("overflow-sign-bool-raises", Real(OverflowError(), Truth(boom(TypeError))), ValueError),
    ("overflow-sign-abort", Real(OverflowError(), Abort("stop")), Abort),
]
