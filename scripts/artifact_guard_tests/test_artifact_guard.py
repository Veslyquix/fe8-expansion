import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

GUARD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifact_guard.py")

_spec = importlib.util.spec_from_file_location("artifact_guard", GUARD_PATH)
artifact_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(artifact_guard)


def run_guard(cwd, *args):
    return subprocess.run(
        [sys.executable, GUARD_PATH, *args], cwd=cwd, capture_output=True, text=True,
    )


def git(cwd, *args, input_bytes=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, input=input_bytes, capture_output=True, check=True,
    )


def hash_object(cwd, data):
    return git(cwd, "hash-object", "-w", "--stdin", input_bytes=data).stdout.decode().strip()


def cacheinfo(cwd, mode, oid, path):
    git(cwd, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}")


class ArtifactGuardRepoTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="artifact-guard-test-")
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "artifact-guard-tests@example.invalid")
        git(self.repo, "config", "user.name", "Artifact Guard Tests")

    def write(self, relpath, data):
        full = os.path.join(self.repo, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode())

    def commit(self, message="test commit"):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)

    def commit_index_only(self, message="test commit"):
        """Commit crafted index entries without re-running ``git add``."""
        git(self.repo, "commit", "-q", "-m", message)

    def findings(self, *args):
        result = run_guard(self.repo, *args)
        lines = [line for line in result.stdout.splitlines() if line]
        return result.returncode, lines


class TestImmutability(ArtifactGuardRepoTestCase):
    def test_worktree_mutation_after_commit_is_ignored(self):
        self.write("notes.txt", "safe committed content")
        self.commit()
        elf_bytes = artifact_guard.MAGIC_ELF + b"\x00" * 32
        self.write("notes.txt", elf_bytes)  # mutate worktree only, no re-add/commit

        for args in (("--revision", "HEAD"), ("--index",)):
            code, lines = self.findings(*args)
            self.assertEqual(code, 0, msg=f"{args}: {lines}")
            self.assertEqual(lines, [])


class TestRenamedMagic(ArtifactGuardRepoTestCase):
    def test_disguised_signatures_are_detected_by_content_not_extension(self):
        cases = {
            "elf.dat": (artifact_guard.MAGIC_ELF, "prohibited-magic-elf"),
            "ips.dat": (artifact_guard.MAGIC_IPS, "prohibited-magic-ips-patch"),
            "ups.dat": (artifact_guard.MAGIC_UPS, "prohibited-magic-ups-patch"),
            "bps.dat": (artifact_guard.MAGIC_BPS, "prohibited-magic-bps-patch"),
            "ppf1.dat": (b"PPF10", "prohibited-magic-ppf-patch"),
            "ppf2.dat": (b"PPF20", "prohibited-magic-ppf-patch"),
            "ppf3.dat": (b"PPF30", "prohibited-magic-ppf-patch"),
            "delta.dat": (b"\xD6\xC3\xC4", "prohibited-magic-vcdiff-patch"),
        }
        for path, (magic, _rule) in cases.items():
            self.write(path, magic + b"payload")
        header = bytearray(0xB3)
        header[0:4] = bytes.fromhex("2e0000eb")
        header[4:20] = artifact_guard.GBA_LOGO_PREFIX
        header[0xB2] = 0x96
        self.write("firmware.dat", bytes(header))
        self.commit()
        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        for path, (_magic, rule) in cases.items():
            self.assertIn(f"{path}: {rule}", lines)
        self.assertIn("firmware.dat: prohibited-magic-gba-header", lines)


class TestCaseInsensitiveExtensions(ArtifactGuardRepoTestCase):
    def test_uppercase_prohibited_extensions_are_rejected(self):
        self.write("SAVEFILE.SAV", "save-shaped bytes")
        self.write("Game.GBA", "rom-shaped bytes")
        self.commit()
        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("SAVEFILE.SAV: prohibited-extension", lines)
        self.assertIn("Game.GBA: prohibited-extension", lines)


class TestRootBuildArtifacts(ArtifactGuardRepoTestCase):
    def test_exact_root_names_are_rejected_without_banning_nested_maps(self):
        names = ("fireemblem8.map", "fireemblem8_relocs.map", "objects.lst")
        for name in names:
            self.write(name, "generated")
        self.write("docs/example.map", "source map")
        self.commit()
        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        for name in names:
            self.assertIn(f"{name}: prohibited-root-build-artifact", lines)
        self.assertFalse(any(line.startswith("docs/example.map:") for line in lines))


class TestSymlinkRejection(ArtifactGuardRepoTestCase):
    def test_symlink_entry_is_rejected_without_reading_target(self):
        oid = hash_object(self.repo, b"../outside-the-repo")
        cacheinfo(self.repo, "120000", oid, "link.txt")
        self.commit_index_only()
        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["link.txt: prohibited-symlink"])


class TestGitlinkPolicy(ArtifactGuardRepoTestCase):
    def test_mgfembp_allowed_other_gitlink_rejected(self):
        fake_a = "a" * 40
        fake_b = "b" * 40
        cacheinfo(self.repo, "160000", fake_a, "mgfembp")
        cacheinfo(self.repo, "160000", fake_b, "vendor/thirdparty")
        self.commit_index_only()

        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["vendor/thirdparty: prohibited-gitlink"])


class TestRestrictedSourceAssetAllowance(ArtifactGuardRepoTestCase):
    def test_allowed_only_under_existing_source_roots(self):
        self.write("graphics/tiles/x.png", "png-shaped")
        self.write("assets/x.png", "png-shaped")
        self.write("graphics/tiles/x.map.bin", "map-bin-shaped")
        self.write("graphics/tiles/x.bin", "plain-bin-shaped")
        self.write("preview/shot.png", "png-shaped")
        self.write("sound/theme.mid", "midi-shaped")
        self.write("other/theme.mid", "midi-shaped")
        self.commit()

        code, lines = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        rejected = {line.split(":")[0] for line in lines}
        self.assertIn("assets/x.png", rejected)
        self.assertIn("graphics/tiles/x.bin", rejected)
        self.assertIn("other/theme.mid", rejected)
        self.assertNotIn("graphics/tiles/x.png", rejected)
        self.assertNotIn("graphics/tiles/x.map.bin", rejected)
        self.assertNotIn("preview/shot.png", rejected)
        self.assertNotIn("sound/theme.mid", rejected)


class TestUnmergedIndexEntries(ArtifactGuardRepoTestCase):
    def test_unmerged_stages_are_flagged_without_being_read(self):
        base = hash_object(self.repo, b"base")
        ours = hash_object(self.repo, b"ours")
        theirs = hash_object(self.repo, b"theirs")
        info = f"100644 {base} 1\tconflict.txt\n100644 {ours} 2\tconflict.txt\n100644 {theirs} 3\tconflict.txt\n"
        git(self.repo, "update-index", "--index-info", input_bytes=info.encode())

        code, lines = self.findings("--index")
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["conflict.txt: unmerged-index-entry"])


class TestDeterminismAndNoContentDisclosure(ArtifactGuardRepoTestCase):
    def test_output_is_sorted_and_never_contains_scanned_bytes(self):
        marker = b"SECRET-PAYLOAD-MARKER-DO-NOT-PRINT"
        self.write("z_first.gba", marker + b"\x00" * 16)
        self.write("a_second.elf", artifact_guard.MAGIC_ELF + marker)
        self.commit()

        code, lines_a = self.findings("--revision", "HEAD")
        _, lines_b = self.findings("--revision", "HEAD")
        self.assertEqual(code, 1)
        self.assertEqual(lines_a, lines_b)
        self.assertEqual(lines_a, sorted(lines_a))
        for line in lines_a:
            self.assertNotIn(marker.decode(), line)


class TestCatFileFailures(ArtifactGuardRepoTestCase):
    def test_nonexistent_index_oid_fails_closed_without_traceback(self):
        oid = "f" * 40
        git(self.repo, "update-index", "--add", "--info-only", "--cacheinfo",
            f"100644,{oid},missing.txt")
        result = run_guard(self.repo, "--index")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_and_failing_cat_file_are_git_errors(self):
        oid = "a" * 40
        valid = f"{oid} blob 0\n\n".encode()
        cases = (
            b"malformed\n", f"{oid} missing\n".encode(),
            f"{'b' * 40} blob 0\n\n".encode(), f"{oid} tree 0\n\n".encode(),
            f"{oid} blob nope\n".encode(), f"{oid} blob 2\nx".encode(),
            f"{oid} blob 1\nx!".encode(), valid,
        )
        for output, returncode in zip(cases, (0,) * 7 + (7,)):
            proc = mock.Mock(stdin=io.BytesIO(), stdout=io.BytesIO(output))
            proc.wait.return_value = proc.poll.return_value = returncode
            with mock.patch.object(artifact_guard.subprocess, "Popen", return_value=proc):
                with self.assertRaises(artifact_guard.GitError):
                    artifact_guard.read_blob_heads([oid])


class TestUnexpectedModeHandledSafely(unittest.TestCase):
    def test_unexpected_mode_is_flagged_without_content_read(self):
        entry = artifact_guard.Entry("040000", "0" * 40, "weird-entry", 0)
        findings = artifact_guard.scan([entry])
        self.assertEqual(findings, [("weird-entry", "unexpected-mode")])


class TestCurrentRepositoryHeadPasses(unittest.TestCase):
    def test_current_repository_head_passes(self):
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=here,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        result = run_guard(repo_root, "--revision", "HEAD")
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
