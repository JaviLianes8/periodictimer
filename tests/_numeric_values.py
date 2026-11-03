"""Hostile and ordinary numeric values the domain table is built from.

Subclasses of every numeric type, registered reals whose conversion or sign is chosen by
the test, and classes whose metaclass hooks raise.
"""

from __future__ import annotations

import numbers
from decimal import Decimal
from fractions import Fraction
from typing import Any

MARKER = "private-marker"


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


class AbortMeta(type):
    def __hash__(cls) -> int:
        raise Abort("stop")


class AbortingClass(metaclass=AbortMeta):
    pass


@numbers.Real.register
class Huge:
    """A registered real too large for a float that compares by its true value."""

    def __init__(self, value: float) -> None:
        self.value = value

    def __float__(self) -> float:
        raise OverflowError

    def __lt__(self, other: float) -> bool:
        return self.value < other


class Truth:
    def __init__(self, value: Any) -> None:
        self.value = value

    def __bool__(self) -> bool:
        if isinstance(self.value, BaseException):
            raise self.value
        return bool(self.value)


def boom(kind: type[BaseException]) -> BaseException:
    return kind(MARKER + "x" * 100_000)
