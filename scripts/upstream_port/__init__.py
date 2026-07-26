"""Read-only-by-default canonical upstream port tooling (Issue #12).

Python-stdlib-only CLI for tracking drift against the canonical upstream
decomp repository, classifying unreviewed commits, and letting a human
maintainer explicitly select, review, and manually apply upstream patches.

Nothing in this package fetches, applies, cherry-picks, merges, commits, or
executes upstream code. See docs/upstream-porting.md for the full workflow.
"""

__all__ = []
