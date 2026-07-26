"""Coverage for the output-safety audit findings (B: scan/drift --output,
C: report symlink containment).

All of these prove the single shared primitive
`output_safety.validate_output_target` -- and every write caller that now
goes through it (`scan --output`, `drift --output`, `report --out-dir`) --
fails closed for:

  - a tracked, unignored path inside the repo (e.g. a README.md-like file)
  - a path outside the repository root entirely
  - a symlink anywhere on the path (the target itself, or an ignored
    directory that is itself a symlink to somewhere outside *or* inside the
    repo)

...while still succeeding for a plain, real, gitignored path, and never
mutating anything (including a rejected tracked file's content, and never
writing through/into a rejected symlink's destination) before/if it fails.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest

from scripts.upstream_port import cli, output_safety, report as report_mod
from tests.upstream_port import helpers as h


def _run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _git_status(cwd):
    return subprocess.run(
        ["git", "status", "--short"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def _git_commit_all(cwd, message):
    subprocess.run(["git", "add", "-A"], cwd=cwd, check=True)
    subprocess.run(
        ["git", "-c", "user.name=x", "-c", "user.email=x@x.invalid", "commit", "-q", "-m", message],
        cwd=cwd, check=True,
    )


class ScanDriftOutputSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        h.write_files(
            self.fixture.fork_dir,
            {"README.md": "tracked readme\n", ".gitignore": "/build/upstream-port/\n"},
        )
        _git_commit_all(self.fixture.fork_dir, "add readme + gitignore")
        self.state_path = os.path.join(self._tmp.name, "state.json")
        code, _, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "init-state", "--ref", "decomp/master"]
        )
        self.assertEqual(code, 0, err)
        h.commit(self.fixture.upstream_dir, {"a.txt": "1\n"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)

    def _readme_path(self):
        return os.path.join(self.fixture.fork_dir, "README.md")

    def test_scan_output_rejects_tracked_readme_and_leaves_it_byte_identical(self):
        readme = self._readme_path()
        with open(readme, "rb") as fh:
            before = fh.read()

        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "scan", "--ref", "decomp/master", "--format", "json", "--output", readme]
        )
        self.assertEqual(code, 1)
        self.assertIn("not covered by .gitignore", err)
        self.assertEqual(out, "")

        with open(readme, "rb") as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_drift_output_rejects_tracked_readme_and_leaves_it_byte_identical(self):
        readme = self._readme_path()
        with open(readme, "rb") as fh:
            before = fh.read()

        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "drift", "--ref", "decomp/master", "--format", "json", "--output", readme]
        )
        self.assertEqual(code, 1)
        self.assertIn("not covered by .gitignore", err)

        with open(readme, "rb") as fh:
            after = fh.read()
        self.assertEqual(before, after)

    def test_scan_output_rejects_path_outside_repo_root(self):
        outside = os.path.join(self._tmp.name, "outside-scan.json")
        self.assertFalse(os.path.exists(outside))

        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "scan", "--ref", "decomp/master", "--format", "json", "--output", outside]
        )
        self.assertEqual(code, 1)
        self.assertIn("outside the repository root", err)
        self.assertFalse(os.path.exists(outside))

    def test_scan_output_succeeds_for_ignored_repo_contained_path_and_status_stays_clean(self):
        target = os.path.join(self.fixture.fork_dir, "build", "upstream-port", "scan-report.json")
        before_status = _git_status(self.fixture.fork_dir)

        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "scan", "--ref", "decomp/master", "--format", "json", "--output", target]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")
        self.assertTrue(os.path.exists(target))
        with open(target) as fh:
            payload = json.load(fh)
        self.assertEqual(payload["unreviewed_count"], 1)

        # An ignored, untracked new file must not appear in `git status`.
        self.assertEqual(_git_status(self.fixture.fork_dir), before_status)

    def test_drift_output_succeeds_for_ignored_repo_contained_path(self):
        target = os.path.join(self.fixture.fork_dir, "build", "upstream-port", "drift-report.json")
        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "drift", "--ref", "decomp/master", "--format", "json", "--output", target]
        )
        self.assertIn(code, (0, 2, 3))
        self.assertTrue(os.path.exists(target))

    def test_scan_output_rejects_existing_symlink_target(self):
        outside_dir = os.path.join(self._tmp.name, "outside-dir")
        os.makedirs(outside_dir, exist_ok=True)
        ignored_dir = os.path.join(self.fixture.fork_dir, "build", "upstream-port")
        os.makedirs(ignored_dir, exist_ok=True)
        link_path = os.path.join(ignored_dir, "scan-link.json")
        outside_target = os.path.join(outside_dir, "scan-link.json")
        os.symlink(outside_target, link_path)

        code, out, err = _run_cli(
            ["--repo", self.fixture.fork_dir, "--state", self.state_path,
             "scan", "--ref", "decomp/master", "--format", "json", "--output", link_path]
        )
        self.assertEqual(code, 1)
        self.assertIn("symlink", err)
        self.assertFalse(os.path.exists(outside_target))


class ReportSymlinkContainmentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        h.write_files(self.fixture.fork_dir, {".gitignore": "/build/upstream-port/\n"})
        _git_commit_all(self.fixture.fork_dir, "add gitignore")
        self.sha1 = h.commit(
            self.fixture.upstream_dir, {"src/battle.c": "int x;\n"}, "code: add battle",
            seconds_offset=10,
        )
        h.refetch(self.fixture)

    def test_rejects_ignored_symlink_directory_pointing_outside_repo(self):
        outside_dir = os.path.join(self._tmp.name, "outside-target")
        os.makedirs(outside_dir, exist_ok=True)
        ignored_parent = os.path.join(self.fixture.fork_dir, "build", "upstream-port")
        os.makedirs(ignored_parent, exist_ok=True)
        symlinked_out_dir = os.path.join(ignored_parent, "evil-batch")
        os.symlink(outside_dir, symlinked_out_dir)

        before_listing = sorted(os.listdir(outside_dir))
        with self.assertRaises(output_safety.OutputSafetyError) as ctx:
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master",
                [self.sha1], symlinked_out_dir,
            )
        self.assertIn("symlink", str(ctx.exception))
        # Nothing must have been written through the symlink into the
        # directory it points at, outside the repo.
        self.assertEqual(sorted(os.listdir(outside_dir)), before_listing)

    def test_rejects_ignored_symlink_directory_pointing_inside_repo_elsewhere(self):
        real_target = os.path.join(self.fixture.fork_dir, "build", "upstream-port", "real-batch")
        os.makedirs(real_target, exist_ok=True)
        symlinked_out_dir = os.path.join(
            self.fixture.fork_dir, "build", "upstream-port", "alias-batch"
        )
        os.symlink(real_target, symlinked_out_dir)

        with self.assertRaises(output_safety.OutputSafetyError) as ctx:
            report_mod.generate(
                self.fixture.fork_dir, self.fixture.remote_name, "decomp/master",
                [self.sha1], symlinked_out_dir,
            )
        self.assertIn("symlink", str(ctx.exception))
        self.assertEqual(os.listdir(real_target), [])

    def test_succeeds_for_normal_ignored_real_directory(self):
        out_dir = os.path.join(self.fixture.fork_dir, "build", "upstream-port", "plain-batch")
        report = report_mod.generate(
            self.fixture.fork_dir, self.fixture.remote_name, "decomp/master", [self.sha1], out_dir
        )
        self.assertEqual(report["selected_count"], 1)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "report.json")))


if __name__ == "__main__":
    unittest.main()
