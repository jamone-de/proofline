"""Tests for proofline.scanner - autonomy classifier with synthetic modules.

Provides 3 synthetic module snapshots with known expected colors:

* ``simple_module``   - 2 branches, 90 % coverage, 5 commits  → GREEN
* ``medium_module``   - 8 branches, 45 % coverage, 1 commit   → YELLOW
* ``complex_module``  - 20 branches, 0 % coverage, 0 commits  → RED

MIT License.
"""
from __future__ import annotations

import ast
import textwrap

from proofline.scanner import _score, GREEN_MAX_COMPLEXITY, YELLOW_MAX_COMPLEXITY


# ---------------------------------------------------------------------------
# Synthetic modules (source strings for complexity measurement)
# ---------------------------------------------------------------------------

_SIMPLE_SRC = textwrap.dedent("""
    def calc(x):
        if x > 0:
            return x
        return 0

    def add(a, b):
        return a + b
""")

_MEDIUM_SRC = textwrap.dedent("""
    def process(items):
        result = []
        for item in items:
            if item > 0:
                result.append(item)
            elif item == 0:
                pass
            else:
                result.append(-item)
        return result

    def lookup(d, key):
        if key in d:
            if d[key] is None:
                return 0
            return d[key]
        return -1
""")

# 20 branches/loops across functions → RED territory
_COMPLEX_SRC = textwrap.dedent("""
    def mega(a, b, c, d, e):
        if a: pass
        if b: pass
        if c: pass
        if d: pass
        if e: pass
        for i in range(a):
            if i > 0:
                if i > 5:
                    pass
        while b:
            if b > 0:
                if b > 10:
                    pass
            b -= 1
        for j in range(c):
            if j % 2 == 0:
                pass
        if a and b: pass
        if c or d: pass
        if e and not a: pass
        return a + b + c + d + e
""")


def _complexity_of(src: str) -> int:
    """Compute total branch+loop complexity from a source string."""
    from proofline.scanner import _branch_complexity
    tree = ast.parse(src)
    return sum(_branch_complexity(tree).values())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoreFunction:
    """Unit tests for the _score() classifier using synthetic metrics."""

    def test_green_module(self) -> None:
        complexity = _complexity_of(_SIMPLE_SRC)
        assert complexity <= GREEN_MAX_COMPLEXITY, (
            f"Expected simple module complexity <= {GREEN_MAX_COMPLEXITY}, got {complexity}"
        )
        color, reason = _score(complexity, 90.0, 5)
        assert color == "GREEN", f"Expected GREEN, got {color}. Reason: {reason}"
        assert "complexity" in reason
        assert "coverage" in reason

    def test_yellow_module_by_coverage(self) -> None:
        complexity = _complexity_of(_MEDIUM_SRC)
        assert complexity <= YELLOW_MAX_COMPLEXITY, (
            f"Expected medium complexity <= {YELLOW_MAX_COMPLEXITY}, got {complexity}"
        )
        color, reason = _score(complexity, 45.0, 1)
        assert color == "YELLOW", f"Expected YELLOW, got {color}. Reason: {reason}"

    def test_yellow_module_by_commits_only(self) -> None:
        """A module with no coverage data but commits>0 and low complexity → YELLOW."""
        color, reason = _score(10, "unknown", 3)
        assert color == "YELLOW", f"Expected YELLOW, got {color}"

    def test_red_module_high_complexity(self) -> None:
        complexity = _complexity_of(_COMPLEX_SRC)
        assert complexity > YELLOW_MAX_COMPLEXITY, (
            f"Expected complex module complexity > {YELLOW_MAX_COMPLEXITY}, got {complexity}"
        )
        color, reason = _score(complexity, "unknown", 0)
        assert color == "RED", f"Expected RED, got {color}. Reason: {reason}"

    def test_red_no_coverage_no_commits(self) -> None:
        """Low complexity but unknown coverage and 0 commits → RED."""
        color, reason = _score(3, "unknown", 0)
        assert color == "RED", f"Expected RED, got {color}"

    def test_red_low_coverage_many_branches(self) -> None:
        color, reason = _score(20, 5.0, 10)
        assert color == "RED", f"Expected RED for high complexity, got {color}"

    def test_green_boundary(self) -> None:
        """Exactly at the boundary values → still GREEN."""
        color, _ = _score(GREEN_MAX_COMPLEXITY, 80.0, 2)
        assert color == "GREEN"

    def test_yellow_just_above_green_complexity(self) -> None:
        """One step above GREEN complexity but OK coverage/commits → YELLOW."""
        color, _ = _score(GREEN_MAX_COMPLEXITY + 1, 50.0, 2)
        assert color == "YELLOW"
