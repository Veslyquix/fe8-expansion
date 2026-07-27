import json
import os
import tempfile
import unittest

from scripts.upstream_port import constants, git_utils, state as state_mod
from tests.upstream_port import helpers as h


class DefaultStateTests(unittest.TestCase):
    def test_default_state_shape(self):
        sha = "a" * 40
        st = state_mod.default_state(constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", sha)
        self.assertEqual(st["schema_version"], constants.STATE_SCHEMA_VERSION)
        self.assertEqual(st["canonical_upstream_url"], constants.CANONICAL_UPSTREAM_URL)
        self.assertEqual(st["last_scanned"], {"ref": "decomp/master", "sha": sha})
        self.assertEqual(st["last_ported"], {"ref": "decomp/master", "sha": sha})
        self.assertEqual(st["commits"], {})

    def test_default_state_rejects_short_sha(self):
        with self.assertRaises(state_mod.StateError):
            state_mod.default_state(constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", "abc123")


class LoadSaveRoundTripTests(unittest.TestCase):
    def test_round_trip(self):
        sha = "b" * 40
        st = state_mod.default_state(constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", sha)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            state_mod.save_state(path, st)
            loaded = state_mod.load_state(path)
            self.assertEqual(loaded, st)
            # Deterministic formatting: sorted keys, trailing newline.
            with open(path) as fh:
                raw = fh.read()
            self.assertTrue(raw.endswith("\n"))
            reparsed = json.loads(raw)
            self.assertEqual(reparsed, st)

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(os.path.join(td, "nope.json"))

    def test_bad_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w") as fh:
                fh.write("{not json")
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_wrong_schema_version_raises(self):
        sha = "c" * 40
        st = state_mod.default_state(constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", sha)
        st["schema_version"] = 999
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w") as fh:
                json.dump(st, fh)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_wrong_canonical_url_raises(self):
        sha = "d" * 40
        st = state_mod.default_state(constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", sha)
        st["canonical_upstream_url"] = "https://example.invalid/not-canonical.git"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w") as fh:
                json.dump(st, fh)
            with self.assertRaises(state_mod.StateError):
                load = state_mod.load_state(path)


class CommitRecordSchemaTests(unittest.TestCase):
    """Adversarial coverage for the strict commit-record schema fix: every
    `commits[sha]` record must have the EXACT allowed field set, correct
    types, a legal `status`, non-empty commit-provenance fields, and
    non-empty rationale/validation_evidence for every non-pending status.
    A malformed record must fail at `load_state` time -- before any
    dependent command produces output, scans git, or writes a file -- and
    a legitimate pending/terminal record must load cleanly."""

    def setUp(self):
        self.sha = "1" * 40
        self.base_state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", "2" * 40
        )

    def _valid_terminal_record(self):
        return {
            "status": "ported",
            "author_name": "Real Author",
            "author_email": "real@example.invalid",
            "subject": "a real subject",
            "rationale": "reviewed by hand",
            "validation_evidence": "ran the test suite",
            "updated_at": "2024-01-01T00:00:00Z",
        }

    def _valid_pending_record(self):
        return {
            "status": "pending",
            "author_name": "Real Author",
            "author_email": "real@example.invalid",
            "subject": "a real subject",
            "rationale": "",
            "validation_evidence": "",
            "updated_at": "2024-01-01T00:00:00Z",
        }

    def _load_with_record(self, record, tmpdir):
        state = json.loads(json.dumps(self.base_state))
        state["commits"][self.sha] = record
        path = os.path.join(tmpdir, "state.json")
        with open(path, "w") as fh:
            json.dump(state, fh)
        return path

    def test_valid_terminal_record_loads_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(self._valid_terminal_record(), td)
            loaded = state_mod.load_state(path)
            self.assertEqual(loaded["commits"][self.sha]["status"], "ported")

    def test_valid_pending_record_with_empty_rationale_evidence_loads_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(self._valid_pending_record(), td)
            loaded = state_mod.load_state(path)
            self.assertEqual(loaded["commits"][self.sha]["status"], "pending")

    def test_all_four_non_pending_statuses_require_evidence_and_load_ok_with_it(self):
        for status in ("ported", "skipped", "superseded", "conflict"):
            with self.subTest(status=status):
                record = self._valid_terminal_record()
                record["status"] = status
                with tempfile.TemporaryDirectory() as td:
                    path = self._load_with_record(record, td)
                    loaded = state_mod.load_state(path)
                    self.assertEqual(loaded["commits"][self.sha]["status"], status)

    def test_missing_author_name_rejected(self):
        record = self._valid_terminal_record()
        del record["author_name"]
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("author_name", str(ctx.exception))

    def test_missing_field_on_pending_record_rejected(self):
        record = self._valid_pending_record()
        del record["updated_at"]
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("updated_at", str(ctx.exception))

    def test_extra_field_rejected(self):
        record = self._valid_terminal_record()
        record["extra_bogus_field"] = "should not be here"
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("extra_bogus_field", str(ctx.exception))

    def test_redundant_sha_field_rejected_as_extra(self):
        """A record must not carry its own redundant `sha` field (the dict
        key IS the SHA) -- if present, it's rejected as an unexpected extra
        field rather than silently tolerated or trusted over the key."""
        record = self._valid_terminal_record()
        record["sha"] = self.sha
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("sha", str(ctx.exception))

    def test_wrong_type_status_rejected(self):
        record = self._valid_terminal_record()
        record["status"] = 123
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_wrong_type_updated_at_rejected(self):
        record = self._valid_terminal_record()
        record["updated_at"] = 20240101
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_wrong_type_rationale_rejected(self):
        record = self._valid_terminal_record()
        record["rationale"] = None
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_unknown_status_rejected(self):
        record = self._valid_terminal_record()
        record["status"] = "definitely-not-a-real-status"
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("illegal status", str(ctx.exception))

    def test_terminal_status_with_empty_rationale_rejected(self):
        record = self._valid_terminal_record()
        record["rationale"] = ""
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("rationale", str(ctx.exception))

    def test_terminal_status_with_empty_validation_evidence_rejected(self):
        record = self._valid_terminal_record()
        record["validation_evidence"] = "   "
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("validation_evidence", str(ctx.exception))

    def test_empty_author_name_rejected_even_for_pending(self):
        record = self._valid_pending_record()
        record["author_name"] = "   "
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("author_name", str(ctx.exception))

    def test_empty_subject_rejected(self):
        record = self._valid_terminal_record()
        record["subject"] = ""
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_implausible_author_email_rejected(self):
        record = self._valid_terminal_record()
        record["author_email"] = "not-an-email"
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("author_email", str(ctx.exception))

    def test_malformed_updated_at_format_rejected(self):
        record = self._valid_terminal_record()
        record["updated_at"] = "01/01/2024"
        with tempfile.TemporaryDirectory() as td:
            path = self._load_with_record(record, td)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("updated_at", str(ctx.exception))

    def test_non_full_sha_key_rejected(self):
        state = json.loads(json.dumps(self.base_state))
        state["commits"]["shortsha"] = self._valid_terminal_record()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w") as fh:
                json.dump(state, fh)
            with self.assertRaises(state_mod.StateError) as ctx:
                state_mod.load_state(path)
            self.assertIn("shortsha", str(ctx.exception))

    def test_record_not_an_object_rejected(self):
        state = json.loads(json.dumps(self.base_state))
        state["commits"][self.sha] = "not-a-dict"
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            with open(path, "w") as fh:
                json.dump(state, fh)
            with self.assertRaises(state_mod.StateError):
                state_mod.load_state(path)

    def test_malformed_state_never_produces_side_effects_via_cli(self):
        """A malformed loaded state must fail before any dependent CLI
        command (here: `scan`) produces output, touches git beyond a
        trivial resolve, or writes a file -- and the malformed state file
        itself must remain byte-for-byte unchanged."""
        import contextlib
        import io

        from scripts.upstream_port import cli

        with tempfile.TemporaryDirectory() as td:
            record = self._valid_terminal_record()
            record["rationale"] = ""  # invalid: terminal status needs rationale
            path = self._load_with_record(record, td)
            with open(path) as fh:
                before = fh.read()

            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(
                    ["--repo", os.getcwd(), "--state", path, "scan", "--ref", "HEAD"]
                )
            self.assertEqual(code, 1)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("rationale", err.getvalue())
            with open(path) as fh:
                after = fh.read()
            self.assertEqual(before, after)


class UpsertCommitStatusTests(unittest.TestCase):
    def setUp(self):
        self.sha = "e" * 40
        self.state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL, "decomp", "decomp/master", "f" * 40
        )

    def _mark(self, status, rationale="because", evidence="tested", force=False):
        return state_mod.upsert_commit_status(
            self.state,
            self.sha,
            new_status=status,
            author_name="A",
            author_email="a@example.invalid",
            subject="subject",
            rationale=rationale,
            validation_evidence=evidence,
            updated_at="2024-01-01T00:00:00Z",
            force=force,
        )

    def test_pending_to_ported_allowed(self):
        self._mark("ported")
        self.assertEqual(self.state["commits"][self.sha]["status"], "ported")

    def test_pending_to_pending_is_a_noop_default(self):
        self._mark("pending", rationale="", evidence="")
        self.assertEqual(self.state["commits"][self.sha]["status"], "pending")

    def test_ported_requires_rationale(self):
        with self.assertRaises(state_mod.StateError):
            self._mark("ported", rationale="", evidence="tested")

    def test_ported_requires_evidence(self):
        with self.assertRaises(state_mod.StateError):
            self._mark("ported", rationale="because", evidence="")

    def test_ported_to_pending_rejected(self):
        self._mark("ported")
        with self.assertRaises(state_mod.StateError):
            self._mark("pending", rationale="", evidence="")

    def test_ported_to_pending_allowed_with_force(self):
        self._mark("ported")
        self._mark("pending", rationale="", evidence="", force=True)
        self.assertEqual(self.state["commits"][self.sha]["status"], "pending")

    def test_superseded_is_terminal(self):
        self._mark("superseded")
        with self.assertRaises(state_mod.StateError):
            self._mark("ported")

    def test_conflict_to_ported_allowed(self):
        self._mark("conflict")
        self._mark("ported")
        self.assertEqual(self.state["commits"][self.sha]["status"], "ported")

    def test_illegal_status_value_rejected(self):
        with self.assertRaises(state_mod.StateError):
            self._mark("bogus-status")

    def test_non_full_sha_rejected(self):
        with self.assertRaises(state_mod.StateError):
            state_mod.upsert_commit_status(
                self.state,
                "shortsha",
                new_status="ported",
                author_name="A",
                author_email="a@example.invalid",
                subject="s",
                rationale="r",
                validation_evidence="e",
                updated_at="2024-01-01T00:00:00Z",
            )


class BoundaryAdvanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fixture = h.build_fixture(self._tmp.name)
        self.state = state_mod.default_state(
            constants.CANONICAL_UPSTREAM_URL,
            self.fixture.remote_name,
            "decomp/master",
            self.fixture.base_sha,
        )

    def test_record_scan_forward_ok(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.record_scan(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        self.assertEqual(self.state["last_scanned"]["sha"], sha1)

    def test_record_scan_backward_rejected(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        h.refetch(self.fixture)
        state_mod.record_scan(self.state, "decomp/master", sha1, self.fixture.fork_dir)
        with self.assertRaises(state_mod.StateError):
            state_mod.record_scan(self.state, "decomp/master", self.fixture.base_sha, self.fixture.fork_dir)

    def test_advance_last_ported_blocks_on_unaccounted_commits(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        h.refetch(self.fixture)
        with self.assertRaises(state_mod.StateError) as ctx:
            state_mod.advance_last_ported(self.state, "decomp/master", sha2, self.fixture.fork_dir)
        self.assertIn(sha1, str(ctx.exception))
        self.assertIn(sha2, str(ctx.exception))

    def test_advance_last_ported_succeeds_once_all_accounted(self):
        sha1 = h.commit(self.fixture.upstream_dir, {"a.txt": "1"}, "c1", seconds_offset=10)
        sha2 = h.commit(self.fixture.upstream_dir, {"b.txt": "2"}, "c2", seconds_offset=20)
        h.refetch(self.fixture)
        state_mod.upsert_commit_status(
            self.state, sha1, new_status="ported", author_name="A", author_email="a@x.invalid",
            subject="s", rationale="r", validation_evidence="e", updated_at="2024-01-01T00:00:00Z",
        )
        state_mod.upsert_commit_status(
            self.state, sha2, new_status="skipped", author_name="A", author_email="a@x.invalid",
            subject="s", rationale="r", validation_evidence="e", updated_at="2024-01-01T00:00:00Z",
        )
        state_mod.advance_last_ported(self.state, "decomp/master", sha2, self.fixture.fork_dir)
        self.assertEqual(self.state["last_ported"]["sha"], sha2)


if __name__ == "__main__":
    unittest.main()
