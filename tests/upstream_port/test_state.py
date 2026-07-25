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
