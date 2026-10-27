"""Pure-Python re-implementation of java.util.Random's 48-bit LCG.

SYNTHETIC educational replica (P3 v2, queueing-analyst deliverable). Implements exactly the
algorithm documented in the JDK: next(bits), nextDouble(), nextInt(bound) including the
power-of-two fast path and the rejection-loop branch for non-power-of-two bounds. No other
java.util.Random methods are needed by the v2 model (only nextDouble and nextInt(bound) are
used by the AnyLogic .alp, confirmed by reading the embedded Java source in
P3_Assembly_Flow.alp â€” see docs/v2-queueing-math.md section 0 for provenance).
"""
from __future__ import annotations

_MASK48 = (1 << 48) - 1
_MULTIPLIER = 0x5DEECE66D
_ADDEND = 0xB


class JavaRandom:
    """Re-implements java.util.Random(long seed) bit-for-bit."""

    __slots__ = ("_seed",)

    def __init__(self, seed: int) -> None:
        self.set_seed(seed)

    def set_seed(self, seed: int) -> None:
        # Java: (seed ^ 0x5DEECE66DL) & ((1L << 48) - 1)
        self._seed = (seed ^ _MULTIPLIER) & _MASK48

    def _next(self, bits: int) -> int:
        self._seed = (self._seed * _MULTIPLIER + _ADDEND) & _MASK48
        value = self._seed >> (48 - bits)
        # Java's next(bits) returns a signed int; emulate for bits==32 callers (not used here,
        # but kept correct for completeness / future nextInt() with no bound).
        if bits == 32 and value >= (1 << 31):
            value -= 1 << 32
        return value

    def next_double(self) -> float:
        high = self._next(26)
        low = self._next(27)
        return ((high << 27) + low) * (2.0 ** -53)

    def next_int(self, bound: int) -> int:
        if bound <= 0:
            raise ValueError("bound must be positive")
        if (bound & -bound) == bound:  # power of two
            return (bound * self._next(31)) >> 31
        while True:
            bits = self._next(31)
            val = bits % bound
            # Java rejects if the signed 32-bit sum overflows negative.
            if bits - val + (bound - 1) < (1 << 31):
                return val
