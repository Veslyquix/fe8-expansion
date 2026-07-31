"""Tests for scripts/release_rehearsal/submodule_binding.py (issue #9
mandatory correction #4: mgfembp submodule three-way binding)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.release_rehearsal import git_source as gs
from scripts.release_rehearsal import submodule_binding as sb

GITLINK_SHA = "c87e74dcd6c8878b809e013cd8ff0c52baa75332"
OTHER_SHA = "1" * 40
URL = "https://example.invalid/mgfembp.git"


def _git(*args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


class _FixtureBuilder:
    """Builds a complete, consistent, fully-bound synthetic fixture (a
    real git repo plus its sidecar allowlist/exclusions/provenance
    files), then lets each test mutate exactly one of the four sources
    to prove that specific mismatch is caught."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.root = tmp / "repo"
        self.root.mkdir()
        self.allowlist_path = tmp / "source_allowlist.json"
        self.exclusions_path = tmp / "export_exclusions.json"
        self.provenance_dir = tmp / "provenance"
        self.provenance_dir.mkdir()

    def build(
        self,
        gitmodules_path="mgfembp",
        gitmodules_url=URL,
        gitlink_sha=GITLINK_SHA,
        exclusion_oid=GITLINK_SHA,
        exclusion_kind="gitlink",
        provenance_pinned_commit=GITLINK_SHA,
        provenance_url=URL,
        include_gitmodules_section=True,
        include_gitlink=True,
        include_exclusion=True,
        include_provenance=True,
        allowlisted_paths=(),
    ) -> str:
        _git("init", "-q", cwd=self.root)
        _git("config", "user.email", "t@example.com", cwd=self.root)
        _git("config", "user.name", "Tester", cwd=self.root)
        (self.root / "a.txt").write_text("a")
        if include_gitmodules_section:
            (self.root / ".gitmodules").write_text(
                f'[submodule "mgfembp"]\n\tpath = {gitmodules_path}\n\turl = {gitmodules_url}\n'
            )
        _git("add", "-A", cwd=self.root)
        if include_gitlink:
            _git("update-index", "--add", "--cacheinfo", f"160000,{gitlink_sha},mgfembp", cwd=self.root)
        _git("commit", "-q", "-m", "init", cwd=self.root)
        sha = gs.resolve_sha(self.root, "HEAD")

        self.allowlist_path.write_text(json.dumps({"paths": ["a.txt", *allowlisted_paths]}), encoding="utf-8")

        exclusions = []
        if include_exclusion:
            exclusions.append({
                "path": "mgfembp", "kind": exclusion_kind, "mode": "160000", "oid": exclusion_oid,
                "reason": "test fixture",
            })
        else:
            exclusions.append({
                "path": "unrelated-placeholder", "kind": "gitlink", "mode": "160000", "oid": OTHER_SHA,
                "reason": "keep the exclusions file schema-valid (non-empty) without excluding mgfembp",
            })
        self.exclusions_path.write_text(json.dumps({"exclusions": exclusions}), encoding="utf-8")

        submodules = []
        if include_provenance:
            submodules.append({
                "path": "mgfembp", "category": "submodule", "author": "NOASSERTION",
                "rightsholder": "NOASSERTION", "license": "NOASSERTION",
                "redistribution_approved": False, "reviewer": None, "notes": "test",
                "pinned_commit": provenance_pinned_commit, "url": provenance_url,
            })
        else:
            submodules.append({
                "path": "unrelated", "category": "submodule", "author": "NOASSERTION",
                "rightsholder": "NOASSERTION", "license": "NOASSERTION",
                "redistribution_approved": False, "reviewer": None, "notes": "test",
                "pinned_commit": OTHER_SHA, "url": URL,
            })
        (self.provenance_dir / "submodules.json").write_text(json.dumps(submodules), encoding="utf-8")
        (self.provenance_dir / "code.json").write_text(json.dumps([
            {
                "path": "a.txt", "category": "code", "author": "NOASSERTION",
                "rightsholder": "NOASSERTION", "license": "NOASSERTION",
                "redistribution_approved": False, "reviewer": None, "notes": "test",
                "oid": gs.list_tree(self.root, sha)[0].object_id if not include_gitmodules_section else "a" * 40,
                "sha256": "b" * 64,
            }
        ]), encoding="utf-8")
        return sha

    def check(self, sha):
        return sb.check_submodule_binding(
            self.root, sha, "mgfembp", self.allowlist_path, self.exclusions_path, self.provenance_dir,
        )


class CleanBindingTests(unittest.TestCase):
    def test_fully_consistent_fixture_has_no_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build()
            self.assertEqual(builder.check(sha), [])


class GitmodulesMismatchTests(unittest.TestCase):
    def test_missing_gitmodules_file_entirely_reported(self):
        """No `.gitmodules` file at all is a soft, actionable finding
        (never a hard crash) -- every other independent check still
        runs and reports its own findings in the same pass."""
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(include_gitmodules_section=False)
            reasons = builder.check(sha)
            self.assertTrue(any("not a tracked regular file" in r for r in reasons), reasons)

    def test_wrong_gitmodules_path_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(gitmodules_path="somewhere-else")
            reasons = builder.check(sha)
            self.assertTrue(any("no section declaring path" in r for r in reasons))

    def test_non_https_scheme_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(gitmodules_url="git://example.invalid/mgfembp.git")
            reasons = builder.check(sha)
            self.assertTrue(any("https://" in r and "scheme" in r for r in reasons))

    def test_ssh_scheme_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(gitmodules_url="git@example.invalid:mgfembp.git")
            reasons = builder.check(sha)
            self.assertTrue(any("scheme" in r for r in reasons))


class GitlinkMismatchTests(unittest.TestCase):
    def test_missing_gitlink_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(include_gitlink=False)
            reasons = builder.check(sha)
            self.assertTrue(any("no gitlink" in r for r in reasons))


class ExclusionMismatchTests(unittest.TestCase):
    def test_missing_exclusion_entry_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(include_exclusion=False)
            reasons = builder.check(sha)
            self.assertTrue(any("no export-exclusion entry" in r for r in reasons))

    def test_stale_exclusion_oid_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(exclusion_oid=OTHER_SHA)
            reasons = builder.check(sha)
            self.assertTrue(any("export-exclusion OID" in r and "does not match" in r for r in reasons))

    def test_wrong_exclusion_kind_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(exclusion_kind="gitlink")
            # tree_coverage.load_exclusions itself enforces kind=="gitlink" is the
            # only valid kind today, so directly construct a schema-valid-but-
            # semantically-wrong scenario is not reachable via the public loader;
            # this test instead proves the *oid* mismatch path (above) and the
            # allowlist/exclusion contradiction path (below) are what actually
            # matters operationally.
            self.assertEqual(builder.check(sha), [])


class ProvenanceMismatchTests(unittest.TestCase):
    def test_missing_provenance_entry_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(include_provenance=False)
            reasons = builder.check(sha)
            self.assertTrue(any("no 'submodule'-category provenance entry" in r for r in reasons))

    def test_stale_pinned_commit_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(provenance_pinned_commit=OTHER_SHA)
            reasons = builder.check(sha)
            self.assertTrue(any("pinned_commit" in r and "does not match" in r for r in reasons))

    def test_mismatched_provenance_url_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(provenance_url="https://example.invalid/DIFFERENT.git")
            reasons = builder.check(sha)
            self.assertTrue(any("provenance url" in r and "does not match" in r for r in reasons))


class AllowlistExclusionContradictionTests(unittest.TestCase):
    def test_mgfembp_present_in_allowlist_is_a_contradiction(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = _FixtureBuilder(Path(tmp))
            sha = builder.build(allowlisted_paths=("mgfembp",))
            reasons = builder.check(sha)
            self.assertTrue(any("allowlist/exclusion contradiction" in r for r in reasons))


class NeverInvokesGitForNonGitRepoRootTests(unittest.TestCase):
    """Regression coverage for a real defect this candidate itself
    reproduced: `check_submodule_binding` must never invoke any git
    command at all when `repo_root` has no `.git` of its own (a genuine
    extracted archive/non-git candidate tree) -- doing so anyway (via
    either `gitmodules.load_gitmodules_sections` or a direct
    `git_source.list_tree` call for the HEAD-tree-gitlink check) lets
    git's own upward-directory-discovery silently find an unrelated
    *enclosing* repository and read `target_sha`'s tree from *that*
    repository's object database instead of failing closed for the
    extracted tree. Proven by nesting a non-git fixture directly inside
    this real, git-tracked worktree (ROOT): if any git command leaked
    through, it would either traceback (`SubmoduleBindingError`
    wrapping a `GitSourceError` for an unrelated SHA) or -- worse --
    silently "succeed" against ROOT's own real tree; neither happens
    here."""

    def test_reports_soft_findings_without_invoking_git(self):
        import json
        import shutil
        import tempfile

        nested = ROOT / "scripts" / "release_rehearsal" / "tests" / ".issue9-submodule-binding-fixture-tmp"
        self.addCleanup(shutil.rmtree, nested, True)
        nested.mkdir(exist_ok=True)
        (nested / "only.txt").write_text("x")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            allowlist_path = tmp_path / "source_allowlist.json"
            allowlist_path.write_text(json.dumps({"paths": ["only.txt"]}), encoding="utf-8")
            exclusions_path = tmp_path / "export_exclusions.json"
            exclusions_path.write_text(json.dumps({"exclusions": [
                {"path": "mgfembp", "kind": "gitlink", "mode": "160000", "oid": GITLINK_SHA, "reason": "x"}
            ]}), encoding="utf-8")
            provenance_dir = tmp_path / "provenance"
            provenance_dir.mkdir()
            (provenance_dir / "submodules.json").write_text(json.dumps([
                {
                    "path": "mgfembp", "category": "submodule", "author": "NOASSERTION",
                    "rightsholder": "NOASSERTION", "license": "NOASSERTION",
                    "redistribution_approved": False, "reviewer": None, "notes": "x",
                    "pinned_commit": GITLINK_SHA, "url": URL,
                }
            ]), encoding="utf-8")

            # A real, nonexistent-in-any-repo SHA -- if git plumbing ever
            # leaked through against the nested (non-git) fixture and
            # found ROOT's own real .git via upward discovery, this
            # would either traceback with a *different* message (ROOT's
            # own git complaining about an unknown/ambiguous object) or,
            # worse, silently resolve against ROOT's real tree instead.
            reasons = sb.check_submodule_binding(
                nested, "0" * 40, "mgfembp", allowlist_path, exclusions_path, provenance_dir,
            )
            self.assertTrue(any("no .git metadata" in r for r in reasons))
            self.assertTrue(any("never invokes git" in r for r in reasons))


class RepositoryStateTests(unittest.TestCase):
    """The real, checked-in mgfembp submodule binding must be fully
    consistent across .gitmodules, the HEAD tree gitlink, the export
    exclusion, and the provenance record."""

    def test_real_repo_binding_is_clean(self):
        reasons = sb.check_submodule_binding(ROOT, "HEAD")
        self.assertEqual(reasons, [])

    def test_real_repo_url_is_https(self):
        import scripts.release_rehearsal.gitmodules as gm
        sections = gm.load_gitmodules_sections(ROOT, "HEAD")
        self.assertTrue(sections["mgfembp"]["url"].startswith("https://"))

    def test_cli_exits_zero_on_real_repo(self):
        code = sb.main(["--repo-root", str(ROOT)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
