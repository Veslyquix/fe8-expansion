"""Stdlib-only release/publication rehearsal tooling (issue #9).

Every module here is read-only with respect to git refs/tags/releases: none
of this package ever creates, moves, or deletes a tag, branch, or GitHub
release, and none of it uploads anything anywhere. See
docs/release_process.md for the full contract and
docs/issue-resolution-policy.md for why Wave 0 deliberately deferred this
work to this issue.
"""
