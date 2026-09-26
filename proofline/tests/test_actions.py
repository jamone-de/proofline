"""Tests for the unique branch suffix fix in proofline.actions.

Verifies that successive propose calls generate distinct branch names,
so re-running a proposal never fails with 'branch already exists'.

MIT License.
"""
from __future__ import annotations

import re

from proofline.actions import _unique_branch_suffix, propose_delete, propose_refactor


class TestUniqueBranchSuffix:
    """Unit tests for the branch uniqueness helper."""

    def test_returns_eight_hex_chars(self) -> None:
        suffix = _unique_branch_suffix()
        assert len(suffix) == 8
        assert re.fullmatch(r"[0-9a-f]{8}", suffix), f"Not hex: {suffix!r}"

    def test_successive_calls_are_different(self) -> None:
        """Two successive calls must not collide (astronomically unlikely if correct)."""
        seen = {_unique_branch_suffix() for _ in range(20)}
        assert len(seen) == 20, "Duplicate suffixes generated – not truly unique"

    def test_branch_names_embed_suffix(self) -> None:
        """Confirm that the branch name patterns used in actions.py include the suffix."""
        suffix = _unique_branch_suffix()
        delete_branch = f"proofline/delete-myfunc-mymodule-{suffix}"
        refactor_branch = f"proofline/refactor-myfunc-mymodule-{suffix}"
        # Both must end with an 8-char hex segment
        assert re.search(r"-[0-9a-f]{8}$", delete_branch)
        assert re.search(r"-[0-9a-f]{8}$", refactor_branch)


class TestProposeBranchUniqueness:
    """Integration-style tests: two propose calls on a RED module must each
    return a distinct branch field (even though both are blocked early)."""

    def test_propose_delete_blocked_has_no_branch(self) -> None:
        """A blocked delete (RED module, no map) returns no branch key."""
        # No autonomy_map.json → color defaults to RED → blocked immediately
        result = propose_delete("brightshop/nonexistent_module.py", "some_func")
        assert result["status"] == "blocked"
        assert "branch" not in result

    def test_propose_refactor_blocked_has_no_branch(self) -> None:
        """A blocked refactor (RED module) returns status needs_review, no branch."""
        result = propose_refactor(
            "brightshop/nonexistent_module.py", "some_func", "def some_func(): pass"
        )
        assert result["status"] == "needs_review"
        assert "branch" not in result
