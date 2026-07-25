import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
QUICKSTART = ROOT / "scripts" / "quickstart.sh"
README = ROOT / "README.md"
QUICKSTART_DOC = ROOT / "docs" / "quickstart.md"


class QuickstartTests(unittest.TestCase):
    def helper_environment(self, commands: dict[str, str]) -> Path:
        temporary = Path(self.temporary.name)
        bin_dir = temporary / "fixture bin"
        bin_dir.mkdir()
        for name, body in commands.items():
            command = bin_dir / name
            command.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            command.chmod(0o755)
        return bin_dir

    def run_helper(
        self, helper: str, commands: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        bin_dir = self.helper_environment(commands)
        return subprocess.run(
            [
                "/bin/bash",
                "-c",
                'source "$1"; PATH="$2"; "$3"',
                "quickstart-test",
                str(QUICKSTART),
                str(bin_dir),
                helper,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def run_snippet(
        self, snippet: str, commands: dict[str, str]
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        """Source quickstart.sh and evaluate `snippet` with a fake command
        PATH ($2) and an isolated fixture project directory ($3). Returns
        (result, log_path, project_dir); log_path is where fake commands are
        expected to append their invocation, one per line."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        bin_dir = self.helper_environment(commands)
        project_dir = temporary / "fixture project"
        project_dir.mkdir()
        result = subprocess.run(
            [
                "/bin/bash",
                "-c",
                snippet,
                "quickstart-test",
                str(QUICKSTART),
                str(bin_dir),
                str(project_dir),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return result, log_path, project_dir

    def logging_command(self, log_path: Path, label: str) -> str:
        return f'printf "{label} %s\\n" "$*" >> "{log_path}"\nexit 0'

    def test_parallel_job_fallback_order(self):
        nproc = self.run_helper(
            "job_count",
            {"nproc": 'printf "%s\\n" 7', "sysctl": 'printf "%s\\n" 9'},
        )
        self.assertEqual((nproc.returncode, nproc.stdout), (0, "7\n"))

        sysctl = self.run_helper(
            "job_count", {"sysctl": 'printf "%s\\n" 6'}
        )
        self.assertEqual((sysctl.returncode, sysctl.stdout), (0, "6\n"))

        single = self.run_helper("job_count", {})
        self.assertEqual((single.returncode, single.stdout), (0, "1\n"))

    def test_package_commands_and_shell_syntax(self):
        syntax = subprocess.run(
            ["/bin/bash", "-n", str(QUICKSTART)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(syntax.returncode, 0, syntax.stdout)

        script = QUICKSTART.read_text(encoding="utf-8")
        self.assertIn(
            "binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi",
            script,
        )
        self.assertIn("pacman -S --needed --noconfirm", script)
        self.assertNotIn("pacman -Sy", script)
        self.assertIn("brew install --cask gcc-arm-embedded", script)
        self.assertIn("brew uninstall arm-none-eabi-gcc", script)
        self.assertNotRegex(script, re.compile(r"make [^\n]*\$\(nproc\)"))
        # The mgfembp-agbcc note is archival/legacy-only now; the old
        # unconditional wording must not remain.
        self.assertNotIn(
            "(first build also fetches/builds the mgfembp agbcc variant for the FE6 SIO payload)",
            script,
        )

    def test_parse_args_legacy_and_refresh_agbcc_flags(self):
        def flags(*args: str) -> tuple[int, str]:
            snippet = (
                'source "$1"; parse_args ' + " ".join(args) + " "
                '&& printf "LEGACY_MODE=%s FORCE_AGBCC_UPDATE=%s\\n" '
                '"$LEGACY_MODE" "$FORCE_AGBCC_UPDATE"'
            )
            result = subprocess.run(
                ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            state_line = next(
                line for line in result.stdout.splitlines() if line.startswith("LEGACY_MODE=")
            )
            return result.returncode, state_line

        default_rc, default_out = flags()
        self.assertEqual((default_rc, default_out), (0, "LEGACY_MODE=0 FORCE_AGBCC_UPDATE=0"))

        legacy_rc, legacy_out = flags("--legacy")
        self.assertEqual((legacy_rc, legacy_out), (0, "LEGACY_MODE=1 FORCE_AGBCC_UPDATE=0"))

        # --refresh-agbcc alone must predictably imply --legacy.
        refresh_rc, refresh_out = flags("--refresh-agbcc")
        self.assertEqual((refresh_rc, refresh_out), (0, "LEGACY_MODE=1 FORCE_AGBCC_UPDATE=1"))

        both_rc, both_out = flags("--legacy", "--refresh-agbcc")
        self.assertEqual((both_rc, both_out), (0, "LEGACY_MODE=1 FORCE_AGBCC_UPDATE=1"))

    def test_build_project_default_runs_modern_release_boot_check_only(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "git": self.logging_command(log_path, "git"),
            "make": self.logging_command(log_path, "make"),
            "nproc": 'printf "%s\\n" 4',
        }
        bin_dir = self.helper_environment(commands)
        project_dir = temporary / "fixture project"
        project_dir.mkdir()
        build_tools = project_dir / "build_tools.sh"
        build_tools.write_text(
            f'#!/bin/sh\nprintf "build_tools\\n" >> "{log_path}"\nexit 0\n',
            encoding="utf-8",
        )
        build_tools.chmod(0o755)

        snippet = (
            'source "$1"; PATH="$2"; PROJECT_DIR="$3"; '
            "parse_args; build_project"
        )
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir), str(project_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

        self.assertIn("build_tools\n", log)
        self.assertIn("make expansion-modern-toolchain-check\n", log)
        self.assertIn(
            "make expansion-modern-boot-check MODERN_CONFIG=release MODERN_ABI=aapcs -j4\n",
            log,
        )
        # The default path must never fall back to the bare legacy build.
        self.assertNotIn("make -j4\n", log)

    def test_build_project_legacy_calls_make_legacy_target_by_name(self):
        # Issue #15: the archival lane is reached by naming the `legacy`
        # target directly (`make legacy -j<jobs>`), never via a bare
        # `make -j<jobs>` plus an environment-variable lane switch, so this
        # mocked-`make` log line is unambiguous evidence on its own (unlike
        # a bare "make -j4\n", which a silently broken/removed
        # lane-selection mechanism could still have produced identically);
        # see scripts/modernize/tests/test_build_default_lane.py for the
        # real-make coverage of the actual Makefile/quickstart.sh glue.
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "git": self.logging_command(log_path, "git"),
            "make": self.logging_command(log_path, "make"),
            "nproc": 'printf "%s\\n" 4',
        }
        bin_dir = self.helper_environment(commands)
        project_dir = temporary / "fixture project"
        project_dir.mkdir()
        build_tools = project_dir / "build_tools.sh"
        build_tools.write_text(
            f'#!/bin/sh\nprintf "build_tools\\n" >> "{log_path}"\nexit 0\n',
            encoding="utf-8",
        )
        build_tools.chmod(0o755)

        snippet = (
            'source "$1"; PATH="$2"; PROJECT_DIR="$3"; '
            "parse_args --legacy; build_project"
        )
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir), str(project_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

        self.assertIn("build_tools\n", log)
        self.assertIn("make legacy -j4\n", log)
        self.assertNotIn("expansion-modern", log)

    def test_install_deps_apt_default_adds_libmgba_dev_legacy_omits_it(self):
        for legacy_args, expect_mgba in (("", True), ("--legacy", False)):
            with self.subTest(legacy_args=legacy_args or "(default)"):
                self.temporary = tempfile.TemporaryDirectory()
                self.addCleanup(self.temporary.cleanup)
                temporary = Path(self.temporary.name)
                log_path = temporary / "invocations.log"
                commands = {
                    "apt-get": self.logging_command(log_path, "apt-get"),
                    "sudo": 'exec "$@"',
                    "pip3": "exit 0",
                    "arm-none-eabi-gcc": "exit 0",
                    "arm-none-eabi-as": "exit 0",
                    "arm-none-eabi-ld": "exit 0",
                }
                bin_dir = self.helper_environment(commands)
                snippet = (
                    'source "$1"; PATH="$2"; '
                    f"parse_args {legacy_args}; install_deps"
                )
                result = subprocess.run(
                    ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                install_lines = [line for line in log.splitlines() if "install -y" in line]
                self.assertTrue(install_lines, log)
                self.assertEqual(
                    expect_mgba,
                    any("libmgba-dev" in line for line in install_lines),
                    log,
                )

    def test_install_deps_pacman_default_adds_mgba_legacy_omits_it(self):
        for legacy_args, expect_mgba in (("", True), ("--legacy", False)):
            with self.subTest(legacy_args=legacy_args or "(default)"):
                self.temporary = tempfile.TemporaryDirectory()
                self.addCleanup(self.temporary.cleanup)
                temporary = Path(self.temporary.name)
                log_path = temporary / "invocations.log"
                commands = {
                    "pacman": self.logging_command(log_path, "pacman"),
                    "sudo": 'exec "$@"',
                    "arm-none-eabi-gcc": "exit 0",
                    "arm-none-eabi-as": "exit 0",
                    "arm-none-eabi-ld": "exit 0",
                }
                bin_dir = self.helper_environment(commands)
                snippet = (
                    'source "$1"; PATH="$2"; '
                    f"parse_args {legacy_args}; install_deps"
                )
                result = subprocess.run(
                    ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                self.assertIn("pacman", log)
                self.assertEqual(expect_mgba, bool(re.search(r"\bmgba\b", log)), log)

    def test_install_deps_brew_default_installs_mgba_legacy_omits_it(self):
        for legacy_args, expect_mgba in (("", True), ("--legacy", False)):
            with self.subTest(legacy_args=legacy_args or "(default)"):
                self.temporary = tempfile.TemporaryDirectory()
                self.addCleanup(self.temporary.cleanup)
                temporary = Path(self.temporary.name)
                log_path = temporary / "invocations.log"
                brew_body = (
                    'case "$1" in\n'
                    f'  list) printf "brew %s\\n" "$*" >> "{log_path}"; exit 1 ;;\n'
                    f'  install) printf "brew %s\\n" "$*" >> "{log_path}"; exit 0 ;;\n'
                    f'  update) printf "brew %s\\n" "$*" >> "{log_path}"; exit 0 ;;\n'
                    "  *) exit 0 ;;\n"
                    "esac"
                )
                commands = {
                    "brew": brew_body,
                    "arm-none-eabi-gcc": "exit 0",
                    "arm-none-eabi-as": "exit 0",
                    "arm-none-eabi-ld": "exit 0",
                }
                bin_dir = self.helper_environment(commands)
                snippet = (
                    'source "$1"; PATH="$2"; '
                    f"parse_args {legacy_args}; install_deps"
                )
                result = subprocess.run(
                    ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                self.assertEqual(
                    expect_mgba,
                    "brew install mgba\n" in log,
                    log,
                )

    def test_install_deps_apt_legacy_skips_modern_gcc_when_absent(self):
        # A --legacy environment with no arm-none-eabi-gcc/newlib at all
        # (only binutils-grade tools) must install just binutils and the
        # base packages -- never probe for or request modern GCC/newlib --
        # and must succeed.
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "apt-get": self.logging_command(log_path, "apt-get"),
            "sudo": 'exec "$@"',
            "pip3": "exit 0",
            "arm-none-eabi-as": "exit 0",
            "arm-none-eabi-ld": "exit 0",
        }
        bin_dir = self.helper_environment(commands)
        snippet = 'source "$1"; PATH="$2"; parse_args --legacy; install_deps'
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        install_lines = [line for line in log.splitlines() if "install -y" in line]
        self.assertTrue(install_lines, log)
        self.assertFalse(any("gcc-arm-none-eabi" in line for line in install_lines), log)
        self.assertFalse(any("libnewlib-arm-none-eabi" in line for line in install_lines), log)
        self.assertFalse(any("libmgba-dev" in line for line in install_lines), log)

    def test_install_deps_apt_legacy_installs_binutils_when_missing(self):
        # With neither arm-none-eabi-gcc nor arm-none-eabi-as/ld present,
        # --legacy must request binutils-arm-none-eabi (still no GCC/newlib).
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "apt-get": self.logging_command(log_path, "apt-get"),
            "sudo": 'exec "$@"',
            "pip3": "exit 0",
        }
        bin_dir = self.helper_environment(commands)
        snippet = 'source "$1"; PATH="$2"; parse_args --legacy; install_deps'
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        # No real binutils is ever installed by the fake apt-get, so the
        # final have_arm_binutils re-check must fail actionably.
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("arm-none-eabi-as/arm-none-eabi-ld are still unavailable", result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        install_lines = [line for line in log.splitlines() if "install -y" in line]
        self.assertTrue(any("binutils-arm-none-eabi" in line for line in install_lines), log)
        self.assertFalse(any("gcc-arm-none-eabi" in line for line in install_lines), log)
        self.assertFalse(any("libnewlib-arm-none-eabi" in line for line in install_lines), log)

    def test_install_deps_pacman_legacy_skips_modern_gcc_when_absent(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "pacman": self.logging_command(log_path, "pacman"),
            "sudo": 'exec "$@"',
            "arm-none-eabi-as": "exit 0",
            "arm-none-eabi-ld": "exit 0",
        }
        bin_dir = self.helper_environment(commands)
        snippet = 'source "$1"; PATH="$2"; parse_args --legacy; install_deps'
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        self.assertIn("pacman", log)
        self.assertNotRegex(log, re.compile(r"\barm-none-eabi-gcc\b"))
        self.assertNotRegex(log, re.compile(r"\barm-none-eabi-newlib\b"))
        self.assertNotRegex(log, re.compile(r"\bmgba\b"))

    def test_install_deps_brew_legacy_skips_modern_gcc_when_absent(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        brew_body = (
            'case "$1" in\n'
            f'  list) printf "brew %s\\n" "$*" >> "{log_path}"; exit 1 ;;\n'
            f'  install) printf "brew %s\\n" "$*" >> "{log_path}"; exit 0 ;;\n'
            f'  update) printf "brew %s\\n" "$*" >> "{log_path}"; exit 0 ;;\n'
            "  *) exit 0 ;;\n"
            "esac"
        )
        commands = {
            "brew": brew_body,
            "arm-none-eabi-as": "exit 0",
            "arm-none-eabi-ld": "exit 0",
        }
        bin_dir = self.helper_environment(commands)
        snippet = 'source "$1"; PATH="$2"; parse_args --legacy; install_deps'
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        self.assertNotIn("brew install --cask gcc-arm-embedded", log)
        self.assertNotIn("brew install mgba", log)

    def test_install_deps_default_fails_actionably_when_toolchain_stays_broken(self):
        # Default (modern) mode must still probe for and require a working
        # arm-none-eabi-gcc/newlib; if it remains unavailable after the
        # install attempt, install_deps must fail with the actionable
        # diagnostic (never silently succeed or fall back to --legacy).
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        log_path = temporary / "invocations.log"
        commands = {
            "apt-get": self.logging_command(log_path, "apt-get"),
            "sudo": 'exec "$@"',
            "pip3": "exit 0",
            # No arm-none-eabi-gcc/as anywhere: the fake apt-get does not
            # actually install a working compiler, so the toolchain stays
            # broken across both probe attempts.
        }
        bin_dir = self.helper_environment(commands)
        snippet = 'source "$1"; PATH="$2"; parse_args; install_deps'
        result = subprocess.run(
            ["/bin/bash", "-c", snippet, "quickstart-test", str(QUICKSTART), str(bin_dir)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(
            "arm-none-eabi-gcc still cannot parse <stdlib.h> and include/global.h",
            result.stdout,
        )
        log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        install_lines = [line for line in log.splitlines() if "install -y" in line]
        self.assertTrue(any("gcc-arm-none-eabi" in line for line in install_lines), log)

    def test_readme_and_docs_flags_match_script_usage(self):
        usage_snippet = 'source "$1"; usage'
        result = subprocess.run(
            ["/bin/bash", "-c", usage_snippet, "quickstart-test", str(QUICKSTART)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        script_flags = set(re.findall(r"--[a-z-]+(?:=)?", result.stdout))
        script_flags = {flag.rstrip("=") for flag in script_flags}
        self.assertIn("--legacy", script_flags)
        self.assertIn("--refresh-agbcc", script_flags)
        self.assertIn("--rom", script_flags)

        readme_text = README.read_text(encoding="utf-8")
        docs_text = QUICKSTART_DOC.read_text(encoding="utf-8")

        def flags_in_usage_line(text: str) -> set[str]:
            match = re.search(r"\./scripts/quickstart\.sh ([^\n`]*)", text)
            self.assertIsNotNone(match, text[:200])
            return {flag.rstrip("=") for flag in re.findall(r"--[a-z-]+(?:=)?", match.group(1))}

        readme_flags = flags_in_usage_line(readme_text)
        docs_flags = flags_in_usage_line(docs_text)

        self.assertEqual(script_flags, readme_flags)
        self.assertEqual(script_flags, docs_flags)

    def test_docs_and_readme_do_not_claim_unconditional_agbcc_default(self):
        readme_text = README.read_text(encoding="utf-8")
        docs_text = QUICKSTART_DOC.read_text(encoding="utf-8")
        # Both docs must describe --legacy as the archival path, and any
        # unconditional-sounding agbcc-fetch language must live strictly
        # under an archival/legacy heading, not the default Quick Start flow.
        self.assertIn("--legacy", readme_text)
        self.assertIn("--legacy", docs_text)

        def assert_scoped_to_archival(text: str, phrase: str, archival_marker: str) -> None:
            index = text.find(phrase)
            if index == -1:
                return
            marker_index = text.rfind(archival_marker, 0, index)
            self.assertNotEqual(
                marker_index,
                -1,
                f"{phrase!r} appears before any {archival_marker!r} heading",
            )

        assert_scoped_to_archival(
            readme_text,
            "the first `make` also fetches/builds its own agbcc variant for it",
            "archival",
        )
        assert_scoped_to_archival(
            docs_text,
            "The first build also fetches/builds mgfembp's own agbcc variant",
            "Archival",
        )


if __name__ == "__main__":
    unittest.main()
