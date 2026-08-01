"""Tests for scripts/release_rehearsal/tree_coverage.py (issue #9
mandatory correction #2: exact immutable HEAD tree coverage with
explicit export exclusions)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import allowlist as al
from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import tree_coverage as tc

GITLINK_SHA = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
OTHER_SHA = "0" * 40


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _init_repo_with_gitlink(root: Path, gitlink_sha: str = GITLINK_SHA, gitlink_path: str = "mgfembp") -> str:
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)
    (root / "src").mkdir()
    (root / "src" / "main.c").write_text("int x;")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text("hi")
    _git("add", "-A", cwd=root)
    _git("update-index", "--add", "--cacheinfo", f"160000,{gitlink_sha},{gitlink_path}", cwd=root)
    _git("commit", "-q", "-m", "init", cwd=root)
    return gs.resolve_sha(root, "HEAD")


def _exclusion(path=GITLINK_SHA and "mgfembp", kind="gitlink", mode="160000", oid=GITLINK_SHA, reason="because"):
    return tc.ExclusionEntry(path=path, kind=kind, mode=mode, oid=oid, reason=reason)


CURATED_SELF_REF_PATH = sorted(tc.SELF_REFERENTIAL_EVIDENCE_PATHS)[0]


def _self_ref_exclusion(path=None, mode="100644", oid=None, reason="because"):
    """issue #9 guardian-correction remediation (D2), then R1/R2 fix: a
    `KIND_SELF_REFERENTIAL_EVIDENCE`-kind exclusion fixture builder,
    mirroring `_exclusion` above for the gitlink kind. Defaults now
    match the *enforced* (not merely documented) semantics: `path`
    defaults to the one real, hard-coded, curated
    `SELF_REFERENTIAL_EVIDENCE_PATHS` member (any other path is only
    ever valid when passed explicitly, to exercise the R1 "arbitrary/
    uncurated path" rejection), and `oid` defaults to `None` (this kind
    never carries a real oid value at all -- see R2)."""
    if path is None:
        path = CURATED_SELF_REF_PATH
    return tc.ExclusionEntry(path=path, kind=tc.KIND_SELF_REFERENTIAL_EVIDENCE, mode=mode, oid=oid, reason=reason)


def _init_repo_with_gitlink_and_blob(root: Path) -> str:
    """The same fixture as `_init_repo_with_gitlink`, plus one extra
    tracked ordinary blob at the exact curated self-referential-evidence
    path (`CURATED_SELF_REF_PATH`) to exercise a `KIND_SELF_REFERENTIAL_
    EVIDENCE` exclusion alongside the existing `KIND_GITLINK` one --
    issue #9 R1 fix: this must be the real curated path (not an
    arbitrary synthetic one like the former "docs/evidence.json"), since
    `check_partition` now only ever accepts this kind for an exact
    curated-policy-set member."""
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@example.com", cwd=root)
    _git("config", "user.name", "Tester", cwd=root)
    (root / "src").mkdir()
    (root / "src" / "main.c").write_text("int x;")
    (root / "docs").mkdir()
    (root / "docs" / "readme.md").write_text("hi")
    curated_path = root / Path(CURATED_SELF_REF_PATH)
    curated_path.parent.mkdir(parents=True, exist_ok=True)
    curated_path.write_text("[]")
    _git("add", "-A", cwd=root)
    _git("update-index", "--add", "--cacheinfo", f"160000,{GITLINK_SHA},mgfembp", cwd=root)
    _git("commit", "-q", "-m", "init", cwd=root)
    return gs.resolve_sha(root, "HEAD")


def _write_exclusions(dir_path: Path, entries) -> Path:
    path = dir_path / "export_exclusions.json"
    path.write_text(json.dumps({"exclusions": [
        {"path": e.path, "kind": e.kind, "mode": e.mode, "oid": e.oid, "reason": e.reason} for e in entries
    ]}), encoding="utf-8")
    return path


class LoadExclusionsTests(unittest.TestCase):
    def test_valid_document_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion()])
            entries = tc.load_exclusions(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].path, "mgfembp")

    def test_missing_key_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text(json.dumps({"exclusions": [{"path": "mgfembp", "kind": "gitlink"}]}), encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_invalid_kind_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(kind="directory")])
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.load_exclusions(path)
            self.assertIn("kind", str(ctx.exception))

    def test_gitlink_kind_requires_gitlink_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(mode="100644")])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_malformed_oid_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(oid="abc")])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_uppercase_oid_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(oid="A" * 40)])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_duplicate_path_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_exclusion(), _exclusion()])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_empty_exclusions_array_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text(json.dumps({"exclusions": []}), encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_non_json_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export_exclusions.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_self_referential_evidence_kind_with_safe_blob_mode_loads(self):
        """issue #9 guardian-correction remediation (D2): the second
        exclusion kind, for an ordinary tracked blob (never a gitlink)
        that is structurally self-referential."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_self_ref_exclusion(mode="100644")])
            entries = tc.load_exclusions(path)
            self.assertEqual(entries[0].kind, tc.KIND_SELF_REFERENTIAL_EVIDENCE)

    def test_self_referential_evidence_kind_rejects_gitlink_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_self_ref_exclusion(mode="160000")])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_self_referential_evidence_kind_accepts_executable_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [_self_ref_exclusion(mode="100755")])
            entries = tc.load_exclusions(path)
            self.assertEqual(entries[0].mode, "100755")


class GenerateExclusionsDocumentTests(unittest.TestCase):
    def test_generates_one_entry_per_gitlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            document = tc.generate_exclusions_document(root, sha)
            self.assertEqual(len(document["exclusions"]), 1)
            self.assertEqual(document["exclusions"][0]["path"], "mgfembp")
            self.assertEqual(document["exclusions"][0]["oid"], GITLINK_SHA)
            self.assertEqual(document["exclusions"][0]["mode"], "160000")

    def test_generated_document_uses_accurately_named_documentary_sha_field(self):
        """issue #9 closing-round fix: the generated document's
        generation-basis field is named 'generation_basis_sha' (never
        the old, misleading 'generated_from_sha') -- and, more
        importantly, this field is purely documentary: no check anywhere
        in this repository ever reads it back or cross-checks it against
        anything (every check always re-derives its own live target_sha
        independently -- HEAD, an explicit override, or the staged
        index), so its presence must never be mistaken for a validated
        commit binding."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            document = tc.generate_exclusions_document(root, sha)
            self.assertEqual(document["generation_basis_sha"], sha)
            self.assertNotIn("generated_from_sha", document)

    def test_unknown_gitlink_path_has_no_seed_reason_and_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root, gitlink_path="some-new-submodule")
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.generate_exclusions_document(root, sha)
            self.assertIn("no curated reason", str(ctx.exception))

    def test_no_gitlinks_at_all_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            with self.assertRaises(tc.TreeCoverageError):
                tc.generate_exclusions_document(root, sha)

    def test_generates_both_gitlink_and_self_referential_evidence_entries(self):
        """issue #9 guardian-correction remediation (D2): the real,
        production `SELF_REFERENTIAL_EVIDENCE_PATHS` seed
        (docs/release_data/provenance/code.json) is fanned out
        alongside every mechanically-discovered gitlink."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            provenance_dir = root / "docs" / "release_data" / "provenance"
            provenance_dir.mkdir(parents=True)
            (provenance_dir / "code.json").write_text("[]")
            _git("add", "-A", cwd=root)
            _git("update-index", "--add", "--cacheinfo", f"160000,{GITLINK_SHA},mgfembp", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            document = tc.generate_exclusions_document(root, sha)
            by_path = {e["path"]: e for e in document["exclusions"]}
            self.assertEqual(by_path["mgfembp"]["kind"], "gitlink")
            self.assertEqual(
                by_path["docs/release_data/provenance/code.json"]["kind"],
                "self_referential_evidence",
            )
            self.assertEqual(by_path["docs/release_data/provenance/code.json"]["mode"], "100644")

    def test_self_referential_evidence_seed_path_absent_from_a_generic_tree_is_silently_skipped(self):
        """A generic/synthetic fixture unrelated to this repository's own
        real layout (no docs/release_data/provenance/code.json at all)
        must never fail generation just because it does not happen to
        replicate this one repository's own specific file layout --
        `SELF_REFERENTIAL_EVIDENCE_PATHS` is only ever a "generate this
        extra entry if applicable" seed, never a "this exact path must
        always exist in every tree ever passed to this function"
        requirement. The always-run validation path
        (`check_partition`/`check_non_git_tree`, exercised elsewhere in
        this file) is what actually catches a genuine post-commit
        rename/removal regression against the *committed*
        export-exclusions file -- this generator only ever silently
        omits an inapplicable path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            document = tc.generate_exclusions_document(root, sha)
            self.assertEqual([e["path"] for e in document["exclusions"]], ["mgfembp"])

    def test_self_referential_evidence_seed_path_present_but_wrong_kind_is_actionable(self):
        """The narrower, actually-actionable case: the seed path *does*
        exist in the tree, but is no longer a safe blob (e.g. it became
        a gitlink) -- this must fail loudly, never silently produce a
        malformed exclusion entry."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git("init", "-q", cwd=root)
            _git("config", "user.email", "t@example.com", cwd=root)
            _git("config", "user.name", "Tester", cwd=root)
            (root / "a.txt").write_text("a")
            _git("add", "-A", cwd=root)
            _git(
                "update-index", "--add", "--cacheinfo",
                f"160000,{GITLINK_SHA},docs/release_data/provenance/code.json",
                cwd=root,
            )
            _git("update-index", "--add", "--cacheinfo", f"160000,{GITLINK_SHA},mgfembp", cwd=root)
            _git("commit", "-q", "-m", "init", cwd=root)
            sha = gs.resolve_sha(root, "HEAD")
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.generate_exclusions_document(root, sha)
            self.assertIn("code.json", str(ctx.exception))


class CheckPartitionTests(unittest.TestCase):
    """Core coverage: included allowlist (+) excluded gitlinks == the
    complete tree, disjointly."""

    def test_clean_partition_has_no_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion()], sha)
            self.assertTrue(result.is_clean())
            self.assertEqual(result.reasons(), [])

    def test_new_tracked_file_absent_from_both_sets_fails(self):
        """The literal issue #9 requirement: a new tracked path in
        neither set must fail coverage, never silently vanish."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c"], [_exclusion()], sha)
            self.assertIn("docs/readme.md", result.missing_included)
            self.assertFalse(result.is_clean())

    def test_new_gitlink_absent_from_exclusions_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [], sha)
            self.assertIn("mgfembp", result.missing_excluded)
            self.assertFalse(result.is_clean())

    def test_stale_included_entry_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(
                root, ["src/main.c", "docs/readme.md", "long-gone.txt"], [_exclusion()], sha,
            )
            self.assertEqual(result.stale_included, ["long-gone.txt"])

    def test_stale_excluded_entry_detected(self):
        """An export-exclusion entry whose path is no longer a tracked
        gitlink at all (removed, or never real) is reported stale --
        while the real gitlink, still separately and correctly covered
        by its own entry, is not itself affected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            ghost = tc.ExclusionEntry(path="nonexistent-submodule", kind="gitlink", mode="160000", oid=OTHER_SHA, reason="x")
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion(), ghost], sha)
            self.assertIn("nonexistent-submodule", result.stale_excluded)
            self.assertEqual(result.missing_excluded, [])  # mgfembp is still correctly covered by _exclusion()
            self.assertFalse(result.is_clean())

    def test_stale_oid_on_excluded_entry_detected(self):
        """A gitlink whose pin changed (superproject bumped the
        submodule commit) but whose export-exclusion record was not
        regenerated must fail as a stale mode/OID -- never silently
        "still excluded, so still fine"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            stale = _exclusion(oid=OTHER_SHA)
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [stale], sha)
            self.assertEqual(result.mismatched_excluded, ["mgfembp"])

    def test_overlap_between_included_and_excluded_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(
                root, ["src/main.c", "docs/readme.md", "mgfembp"], [_exclusion()], sha,
            )
            self.assertIn("mgfembp", result.overlap)

    def test_silent_extension_filtering_never_hides_a_new_tracked_file(self):
        """A new tracked file must fail coverage regardless of its
        extension/name -- there is no filename/extension-based silent
        skip anywhere in this partition check (unlike, say, a naive
        checker that only looks at '*.c'/'*.md' files)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            (root / "new.unexpected.ext12345").write_text("x")
            _git("add", "-A", cwd=root)
            _git("commit", "-q", "-m", "add odd file", cwd=root)
            new_sha = gs.resolve_sha(root, "HEAD")
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion()], new_sha)
            self.assertIn("new.unexpected.ext12345", result.missing_included)

    def test_prefix_exclusion_of_a_real_directory_is_rejected(self):
        """Do not broad-prefix exclude directories: an export-exclusion
        entry may never be a directory-prefix ancestor of another
        tracked path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            broad = tc.ExclusionEntry(path="src", kind="gitlink", mode="160000", oid=OTHER_SHA, reason="x")
            result = tc.check_partition(root, ["docs/readme.md"], [_exclusion(), broad], sha)
            self.assertIn("src", result.prefix_exclusions)

    def test_reasons_are_sorted_and_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            result = tc.check_partition(root, ["src/main.c"], [], sha)
            reasons = result.reasons()
            self.assertEqual(reasons, sorted(reasons))
            self.assertTrue(any("docs/readme.md" in r for r in reasons))
            self.assertTrue(any("mgfembp" in r for r in reasons))


class MixedExclusionKindPartitionTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D2): `check_partition`
    with BOTH a gitlink-kind and a self-referential-evidence-kind
    exclusion present together."""

    def test_clean_mixed_kind_partition_has_no_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            exclusions = [_exclusion(), _self_ref_exclusion()]
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], exclusions, sha)
            self.assertTrue(result.is_clean(), result.reasons())

    def test_self_referential_evidence_path_never_required_in_allowlist(self):
        """A blob-kind exclusion is never required to *also* be an
        included allowlist member -- unlike an ordinary tracked blob,
        which would otherwise be flagged missing_included."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            exclusions = [_exclusion(), _self_ref_exclusion()]
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], exclusions, sha)
            self.assertNotIn(CURATED_SELF_REF_PATH, result.missing_included)

    def test_self_referential_evidence_path_in_allowlist_is_overlap(self):
        """The mirror-image: a blob-kind exclusion path must never *also*
        be an included allowlist member -- exactly like a gitlink."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            exclusions = [_exclusion(), _self_ref_exclusion()]
            result = tc.check_partition(
                root, ["src/main.c", "docs/readme.md", CURATED_SELF_REF_PATH], exclusions, sha,
            )
            self.assertIn(CURATED_SELF_REF_PATH, result.overlap)

    def test_missing_self_referential_evidence_blob_is_stale_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            exclusions = [_exclusion(), _self_ref_exclusion(path="never-existed.json", oid=None)]
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], exclusions, sha)
            self.assertIn("never-existed.json", result.stale_excluded)
            # issue #9 R1 fix: an uncurated path is *also* independently
            # flagged invalid, regardless of whether it happens to be
            # live/stale -- both buckets fire together, never just one.
            self.assertIn("never-existed.json", result.invalid_self_referential_evidence)
            self.assertFalse(result.is_clean())

    def test_kind_mismatch_gitlink_declared_as_self_referential_evidence_is_stale_and_missing(self):
        """A path that IS a live gitlink, but whose exclusion record
        wrongly declares kind self_referential_evidence, must be
        reported (never silently trusted as "still excluded, so still
        fine") -- both as a stale (wrong-kind) exclusion entry and as a
        live gitlink with no *gitlink*-kind record of its own. "mgfembp"
        is also not the curated self-referential-evidence path, so it is
        independently flagged invalid too."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            wrong_kind = _self_ref_exclusion(path="mgfembp", mode="100644", oid=None)
            exclusions = [wrong_kind, _self_ref_exclusion()]
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], exclusions, sha)
            self.assertIn("mgfembp", result.stale_excluded)
            self.assertIn("mgfembp", result.missing_excluded)
            self.assertIn("mgfembp", result.invalid_self_referential_evidence)


class ArbitraryPathSelfReferentialEvidenceExclusionRejectionTests(unittest.TestCase):
    """issue #9 R1/R2 fix -- the literal reproduced defects: an arbitrary
    tracked path can no longer be moved out of the included allowlist
    and into a bogus `self_referential_evidence`-kind exclusion row to
    escape tree coverage, and this kind can no longer carry a live/
    stale/fake `oid` value at all. Exercised at both layers: `load_
    exclusions` (the JSON-file schema gate) and `check_partition` (the
    independent, hard-coded-against-the-policy-set validator invariant,
    reachable even if `ExclusionEntry` objects are constructed directly,
    bypassing `load_exclusions` entirely)."""

    def test_arbitrary_blob_moved_to_self_referential_evidence_exclusion_fails_partition(self):
        """The literal R1 reproducer: take a real, ordinary tracked blob
        (the Makefile-like "src/main.c"), remove it from the allowlist,
        and add a self_referential_evidence-kind exclusion row for it
        instead, with a well-formed-looking (but bogus) oid -- this must
        fail coverage, never pass as "still accounted for"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            bogus = tc.ExclusionEntry(
                path="src/main.c", kind=tc.KIND_SELF_REFERENTIAL_EVIDENCE,
                mode="100644", oid="a" * 40, reason="bogus",
            )
            result = tc.check_partition(root, ["docs/readme.md"], [_exclusion(), bogus], sha)
            self.assertFalse(result.is_clean())
            self.assertIn("src/main.c", result.invalid_self_referential_evidence)
            # Defense-in-depth: the underlying blob is *also* still
            # reported missing_included, exactly as if the bogus row did
            # not exist at all.
            self.assertIn("src/main.c", result.missing_included)

    def test_arbitrary_blob_moved_to_self_referential_evidence_exclusion_fails_load_exclusions(self):
        """The same R1 reproducer, but via the on-disk JSON schema gate
        (`load_exclusions`) rather than direct ExclusionEntry
        construction -- an arbitrary path must never even *load* as a
        well-formed self_referential_evidence exclusion."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [
                _exclusion(),
                tc.ExclusionEntry(
                    path="Makefile", kind=tc.KIND_SELF_REFERENTIAL_EVIDENCE,
                    mode="100644", oid="b" * 40, reason="bogus",
                ),
            ])
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.load_exclusions(path)
            self.assertIn("Makefile", str(ctx.exception))

    def test_extra_curated_kind_row_for_a_second_arbitrary_path_fails(self):
        """An *additional* self_referential_evidence row alongside the
        one legitimate curated entry -- for some other, arbitrary path --
        must fail exactly the same way; the curated set is a ceiling,
        not merely a floor."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            extra = tc.ExclusionEntry(
                path="docs/readme.md", kind=tc.KIND_SELF_REFERENTIAL_EVIDENCE,
                mode="100644", oid=None, reason="extra bogus row",
            )
            exclusions = [_exclusion(), _self_ref_exclusion(), extra]
            result = tc.check_partition(root, ["src/main.c"], exclusions, sha)
            self.assertIn("docs/readme.md", result.invalid_self_referential_evidence)
            self.assertFalse(result.is_clean())

    def test_missing_curated_exclusion_for_code_json_fails_via_real_repo_style_fixture(self):
        """The 'missing curated exclusion' scenario: the curated path is
        a live blob, correctly absent from the allowlist, but its
        exclusion row is entirely missing (dropped) -- this is caught by
        the existing missing_included bucket (no bespoke bijection check
        is needed inside load_exclusions itself: check_partition's
        cross-check against the live tree already fully covers it)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            # Only the gitlink exclusion -- the curated self-referential-
            # evidence row for CURATED_SELF_REF_PATH is missing entirely.
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], [_exclusion()], sha)
            self.assertIn(CURATED_SELF_REF_PATH, result.missing_included)
            self.assertFalse(result.is_clean())

    def test_supplied_oid_for_self_referential_evidence_is_rejected_by_load_exclusions(self):
        """The literal R2 reproducer: a supplied oid (even one that
        happens to match the live blob's real oid) is rejected outright
        -- this kind never carries a real oid value, matching or not."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [
                _exclusion(),
                _self_ref_exclusion(oid="c" * 40),
            ])
            with self.assertRaises(tc.TreeCoverageError) as ctx:
                tc.load_exclusions(path)
            self.assertIn("oid", str(ctx.exception))

    def test_stale_oid_for_self_referential_evidence_never_silently_trusted(self):
        """A companion to the above using the exact, real, historically-
        stale oid this repository's own export_exclusions.json once
        carried for code.json (issue #9 R2's literal reproduction) --
        rejected exactly the same way as any other supplied oid value,
        never specially trusted merely because it once was real."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_exclusions(Path(tmp), [
                _exclusion(),
                _self_ref_exclusion(oid="1b1e77d300c6464c14915d4369927991fd2f2bfa"),
            ])
            with self.assertRaises(tc.TreeCoverageError):
                tc.load_exclusions(path)

    def test_code_json_content_change_is_never_masked_by_a_stale_oid(self):
        """issue #9 R2: since this kind's oid is never recorded/
        cross-checked at all any more, a committed content change to the
        curated path is detected purely via the ordinary tree-membership
        contract (it remains a live, correctly-kinded, correctly-moded
        blob, so the partition stays clean) -- there is no oid field
        left to go stale/lie about content identity in the first place."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink_and_blob(root)
            curated_path = root / Path(CURATED_SELF_REF_PATH)
            curated_path.write_text('["changed content"]')
            # A *targeted* `add` (never `-a`/`-A`): this fixture's
            # "mgfembp" gitlink was injected purely via `update-index
            # --add --cacheinfo` and has no real on-disk directory at
            # all, so a broad `git commit -a`/`git add -A` here would
            # itself (spuriously) drop it from the new tree, entirely
            # unrelated to anything this test is actually exercising.
            _git("add", CURATED_SELF_REF_PATH, cwd=root)
            _git("commit", "-q", "-m", "change curated path content", cwd=root)
            new_sha = gs.resolve_sha(root, "HEAD")
            exclusions = [_exclusion(), _self_ref_exclusion()]
            result = tc.check_partition(root, ["src/main.c", "docs/readme.md"], exclusions, new_sha)
            self.assertTrue(result.is_clean(), result.reasons())


class CheckEndToEndTests(unittest.TestCase):
    def test_check_reads_files_and_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sha = _init_repo_with_gitlink(root)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["src/main.c", "docs/readme.md"]}), encoding="utf-8")
            exclusions_path = _write_exclusions(root, [_exclusion()])
            self.assertEqual(tc.check(root, allowlist_path, exclusions_path, sha), [])

    def test_check_reports_malformed_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text("{not json", encoding="utf-8")
            exclusions_path = _write_exclusions(root, [_exclusion()])
            reasons = tc.check(root, allowlist_path, exclusions_path, "HEAD")
            self.assertTrue(reasons)

    def test_check_reports_malformed_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowlist_path = root / "allow.json"
            allowlist_path.write_text(json.dumps({"paths": ["a.txt"]}), encoding="utf-8")
            exclusions_path = root / "export_exclusions.json"
            exclusions_path.write_text("{not json", encoding="utf-8")
            reasons = tc.check(root, allowlist_path, exclusions_path, "HEAD")
            self.assertTrue(reasons)


class ArchiveMembershipExactTests(unittest.TestCase):
    def test_exact_match_has_no_findings(self):
        missing, extra = tc.check_archive_membership_exact(["a.txt", "b.txt"], ["a.txt", "b.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_missing_member_detected(self):
        missing, extra = tc.check_archive_membership_exact(["a.txt"], ["a.txt", "b.txt"])
        self.assertEqual(missing, ["b.txt"])
        self.assertEqual(extra, [])

    def test_extra_member_detected(self):
        """An archive containing something beyond the included set (e.g.
        a gitlink that slipped through) must be reported, never silently
        accepted as "a superset is fine"."""
        missing, extra = tc.check_archive_membership_exact(["a.txt", "mgfembp"], ["a.txt"])
        self.assertEqual(missing, [])
        self.assertEqual(extra, ["mgfembp"])


class CheckNonGitTreeTests(unittest.TestCase):
    """The closed-world, no-.git-at-all analogue -- a genuine extracted
    candidate tree (e.g. a real 'git archive HEAD | tar -x' extraction)."""

    def test_clean_extraction_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()  # git archive materializes a gitlink as an empty dir
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertTrue(result.is_clean())

    def test_missing_included_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mgfembp").mkdir()
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("src/main.c", result.missing)

    def test_missing_excluded_directory_detected(self):
        """The precise 'missing/unrepresented gitlink' blocker: if even
        the empty directory mountpoint is absent, that is reported."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.missing)

    def test_extra_unlisted_file_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "new_unreviewed.txt").write_text("new")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("new_unreviewed.txt", result.extra)

    def test_excluded_path_materialized_as_a_file_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").write_text("not a directory!")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.unsafe)

    def test_included_path_materialized_as_a_symlink_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "src.c").symlink_to("real.txt")
            (root / "mgfembp").mkdir()
            result = tc.check_non_git_tree(root, ["src.c"], [_exclusion()])
            self.assertIn("src.c", result.unsafe)

    def test_excluded_path_materialized_as_a_symlink_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "real_dir").mkdir()
            (root / "mgfembp").symlink_to("real_dir")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("mgfembp", result.unsafe)

    def test_never_invokes_git(self):
        """Mirrors allowlist.py's own non-git regression: nesting the
        fixture inside this real repository must never leak an outer
        git invocation (there simply is none in this function at all)."""
        import shutil
        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / ".issue9-tree-coverage-fixture-tmp"
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        (nested / "only.txt").write_text("x")
        (nested / "mgfembp").mkdir()
        result = tc.check_non_git_tree(nested, ["only.txt"], [_exclusion()])
        self.assertTrue(result.is_clean())


class CheckNonGitTreeSelfReferentialEvidenceTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D2): a self-referential-
    evidence (non-gitlink) exclusion was never part of the archive at
    all -- unlike a gitlink mountpoint, there is no "empty placeholder
    directory" convention for it; a genuine extracted candidate must
    never contain it, in any form."""

    def test_absent_self_referential_evidence_path_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            exclusions = [_exclusion(), _self_ref_exclusion(path="docs/evidence.json")]
            result = tc.check_non_git_tree(root, ["src/main.c"], exclusions)
            self.assertTrue(result.is_clean(), result.reasons())

    def test_present_self_referential_evidence_path_as_file_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "evidence.json").write_text("[]")
            exclusions = [_exclusion(), _self_ref_exclusion(path="docs/evidence.json")]
            result = tc.check_non_git_tree(root, ["src/main.c"], exclusions)
            self.assertIn("docs/evidence.json", result.unsafe)

    def test_present_self_referential_evidence_path_as_directory_is_unsafe(self):
        """Unlike a gitlink mountpoint (an empty directory is the
        *expected* shape), an empty directory at a self-referential-
        evidence path is still unsafe -- it was never part of the
        archive at all, so nothing should be there in any shape."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "docs" / "evidence.json").mkdir(parents=True)
            exclusions = [_exclusion(), _self_ref_exclusion(path="docs/evidence.json")]
            result = tc.check_non_git_tree(root, ["src/main.c"], exclusions)
            self.assertIn("docs/evidence.json", result.unsafe)

    def test_present_self_referential_evidence_path_as_symlink_is_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "real.json").write_text("[]")
            (root / "evidence.json").symlink_to("real.json")
            exclusions = [_exclusion(), _self_ref_exclusion(path="evidence.json")]
            result = tc.check_non_git_tree(root, ["src/main.c"], exclusions)
            self.assertIn("evidence.json", result.unsafe)


class ClosedWorldSymlinkNeverSkippedTests(unittest.TestCase):
    """issue #9 guardian-correction remediation (D5): a fresh,
    independent review found `_present_regular_files` (the non-git
    closed-world enumeration `check_non_git_tree` uses) `continue`d
    straight past any symlink it found -- a stray, unlisted symlink at
    any path was therefore completely invisible to both the `extra` and
    `missing` accounting. `_present_paths` (its replacement) never skips
    any filesystem entry by kind; only a genuine, non-symlink directory
    is ever walked through rather than reported."""

    def test_stray_symlink_at_an_unaccounted_for_path_is_reported_as_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.c").write_text("x")
            (root / "mgfembp").mkdir()
            (root / "real.txt").write_text("real")
            (root / "stray-symlink.txt").symlink_to("real.txt")
            result = tc.check_non_git_tree(root, ["src/main.c"], [_exclusion()])
            self.assertIn("stray-symlink.txt", result.extra)
            self.assertNotIn("stray-symlink.txt", result.missing)

    def test_present_paths_includes_symlinks_not_just_regular_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.txt").write_text("real")
            (root / "link.txt").symlink_to("real.txt")
            present = tc._present_paths(root)
            self.assertIn("link.txt", present)
            self.assertIn("real.txt", present)

    def test_present_paths_walks_through_real_directories_only(self):
        """A genuine, non-symlink directory is still only ever walked
        through -- never itself reported as a leaf entry."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "sub" / "nested.txt").write_text("x")
            present = tc._present_paths(root)
            self.assertIn("sub/nested.txt", present)
            self.assertNotIn("sub", present)


class CombinedRequiredPathsTests(unittest.TestCase):
    def test_union_of_both_sets(self):
        combined = tc.combined_required_paths(["a.txt", "b.txt"], ["mgfembp"])
        self.assertEqual(combined, ["a.txt", "b.txt", "mgfembp"])

    def test_no_duplicates_on_pathological_overlap_input(self):
        combined = tc.combined_required_paths(["a.txt"], ["a.txt"])
        self.assertEqual(combined, ["a.txt"])


class RepositoryStateTests(unittest.TestCase):
    """The real, checked-in source_allowlist.json and export_exclusions.json
    must together be an exact, disjoint partition of this repository's own
    HEAD tree."""

    def test_real_repo_is_an_exact_disjoint_partition(self):
        allowlist_paths = al.load_allowlist_paths(ROOT / "docs" / "release_data" / "source_allowlist.json")
        exclusion_entries = tc.load_exclusions(ROOT / "docs" / "release_data" / "export_exclusions.json")
        result = tc.check_partition(ROOT, allowlist_paths, exclusion_entries, "HEAD")
        self.assertEqual(result.reasons(), [])
        self.assertTrue(result.is_clean())

    def test_real_repo_exclusions_contains_exactly_mgfembp_and_code_json(self):
        """issue #9 guardian-correction remediation (D2), then R1/R2
        fix: the real, committed export exclusions now contain exactly
        two entries -- the pre-existing mgfembp gitlink, and the
        self-referential-evidence docs/release_data/provenance/
        code.json -- and code.json's own record is a curated
        path-only-plus-mode exclusion with no oid claimed at all."""
        exclusion_entries = tc.load_exclusions(ROOT / "docs" / "release_data" / "export_exclusions.json")
        by_path = {e.path: e for e in exclusion_entries}
        self.assertEqual(
            sorted(by_path), sorted(["mgfembp", "docs/release_data/provenance/code.json"])
        )
        self.assertEqual(by_path["mgfembp"].oid, GITLINK_SHA)
        self.assertEqual(by_path["mgfembp"].kind, "gitlink")
        self.assertEqual(
            by_path["docs/release_data/provenance/code.json"].kind, "self_referential_evidence"
        )
        self.assertEqual(by_path["docs/release_data/provenance/code.json"].mode, "100644")
        self.assertIsNone(
            by_path["docs/release_data/provenance/code.json"].oid,
            "code.json is a curated path-only+mode exclusion -- it must never carry a live, "
            "stale, or fabricated oid (issue #9 R2 fix)",
        )

    def test_real_repo_code_json_is_not_in_the_included_allowlist(self):
        allowlist_paths = al.load_allowlist_paths(ROOT / "docs" / "release_data" / "source_allowlist.json")
        self.assertNotIn("docs/release_data/provenance/code.json", allowlist_paths)

    def test_real_exclusions_check_via_cli_helper(self):
        reasons = tc.check(
            ROOT,
            ROOT / "docs" / "release_data" / "source_allowlist.json",
            ROOT / "docs" / "release_data" / "export_exclusions.json",
            "HEAD",
        )
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
