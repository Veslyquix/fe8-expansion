"""Tests for the single-source extensible ID / count / cap contract (Issue #10)."""

import os
import unittest

from scripts.generated_data import idspace


REPO_ROOT = idspace.REPO_ROOT


class ModelShapeTests(unittest.TestCase):
    def test_six_expected_domains(self):
        keys = sorted(d.key for d in idspace.DOMAINS)
        self.assertEqual(
            keys, ["chapter", "character", "class", "event", "item", "unit"])

    def test_every_evidence_path_exists(self):
        for domain in idspace.DOMAINS:
            for ev in domain.evidence:
                path = os.path.join(REPO_ROOT, ev.path)
                self.assertTrue(os.path.exists(path),
                                "missing evidence path: {}".format(ev.path))

    def test_required_categories_all_covered(self):
        seen = {r["category"] for r in idspace.consumer_rows()}
        for category in idspace.REQUIRED_CATEGORIES:
            self.assertIn(category, seen,
                          "audit is missing required category {}".format(category))

    def test_consumer_rows_are_sorted(self):
        rows = idspace.consumer_rows()
        keys = [(r["domain"], r["category"], r["path"], r["kind"], r["symbol"]) for r in rows]
        self.assertEqual(keys, sorted(keys))

    def test_consumer_rows_come_from_the_source_census(self):
        # The audit consumer table is generated from the source scan + the
        # tracked classification, never hand-curated: a hand-written row would
        # have no scanner key and would break this 1:1 identity.
        from scripts.generated_data import consumer_census
        audit_keys = [r["key"] for r in idspace.consumer_rows()]
        census_keys = [r["key"] for r in consumer_census.classified_rows()]
        self.assertEqual(sorted(audit_keys), sorted(census_keys))
        self.assertGreater(len(audit_keys), 500,
                           "the census must audit the whole source surface, not a sample")

    def test_curated_evidence_is_a_subset_not_the_coverage_proof(self):
        evidence = idspace.evidence_rows()
        self.assertTrue(evidence)
        self.assertLess(len(evidence), len(idspace.consumer_rows()))

    def test_digest_is_deterministic(self):
        self.assertEqual(idspace.digest(), idspace.digest())


class CapValidationTests(unittest.TestCase):
    def test_configured_caps_all_valid(self):
        idspace.validate_all_configured_caps()  # must not raise

    def test_class_0x80_valid_now_a_full_byte(self):
        # Widened by the Camp/Tent structures feature: GameSavePackedUnit.jid
        # is a full byte when FE8_PURCHASE_GENERICS is enabled (bmsave.h), so
        # the class domain's technical max is now 0xFF, not 0x7F.
        cls = idspace.domain_by_key("class")
        idspace.validate_domain_cap(cls, 0x80)  # must not raise
        idspace.validate_domain_cap(cls, 0xFF)  # storage ceiling, must not raise

    def test_class_0x100_rejected_actionably(self):
        cls = idspace.domain_by_key("class")
        with self.assertRaises(idspace.CapError) as ctx:
            idspace.validate_domain_cap(cls, 0x100)
        message = str(ctx.exception)
        self.assertIn("0x100", message)
        self.assertIn("0xFF", message)
        self.assertIn("truncate", message)

    def test_unit_0x40_collides_with_faction_stride(self):
        unit = idspace.domain_by_key("unit")
        with self.assertRaises(idspace.CapError) as ctx:
            idspace.validate_domain_cap(unit, 0x40)
        self.assertIn("0x3F", str(ctx.exception))
        idspace.validate_domain_cap(unit, 0x3F)  # last valid slot is fine

    def test_character_cap_bounded_by_capacity(self):
        char = idspace.domain_by_key("character")
        idspace.validate_domain_cap(char, 0xFF)  # 256 records == capacity
        with self.assertRaises(idspace.CapError):
            idspace.validate_domain_cap(char, 0x100)

    def test_chapter_negative_and_positive_bounds(self):
        chap = idspace.domain_by_key("chapter")
        idspace.validate_domain_cap(chap, 0x7F)
        with self.assertRaises(idspace.CapError):
            idspace.validate_domain_cap(chap, 0x80)
        with self.assertRaises(idspace.CapError):
            idspace.validate_domain_cap(chap, -1)


class ItemCapBoundaryTests(unittest.TestCase):
    def test_item_boundaries(self):
        item = idspace.domain_by_key("item")
        for cap in (0x00, 0xCD, 0xCE, 0xFF):
            idspace.validate_domain_cap(item, cap)
        with self.assertRaises(idspace.CapError):
            idspace.validate_domain_cap(item, 0x100)
        with self.assertRaises(idspace.CapError):
            idspace.validate_domain_cap(item, -1)

    def test_item_fits_14bit_save_field(self):
        item = idspace.domain_by_key("item")
        self.assertLessEqual(item.technical_max, 0x3FFF)

    def test_resolve_item_cap_default_is_vanilla(self):
        self.assertEqual(idspace.resolve_item_id_cap(env={}), idspace.ITEM_DEFAULT_CAP)
        self.assertEqual(idspace.ITEM_DEFAULT_CAP, 0xCD)

    def test_resolve_item_cap_env_opt_in(self):
        self.assertEqual(
            idspace.resolve_item_id_cap(env={idspace.ITEM_CAP_ENV: "0xCE"}), 0xCE)

    def test_resolve_item_cap_rejects_over_storage(self):
        with self.assertRaises(idspace.CapError):
            idspace.resolve_item_id_cap(env={idspace.ITEM_CAP_ENV: "0x100"})

    def test_resolve_item_cap_rejects_garbage(self):
        with self.assertRaises(idspace.CapError):
            idspace.resolve_item_id_cap(env={idspace.ITEM_CAP_ENV: "later"})


class OutputDriftTests(unittest.TestCase):
    def test_committed_outputs_match_model(self):
        rc = idspace.cmd_check(None)
        self.assertEqual(rc, 0, "committed id-space outputs drifted; run idspace generate")

    def test_c_header_uses_block_comments_only(self):
        text = idspace.render_c_header()
        self.assertNotIn("//", text)
        self.assertIn("GUARD_ID_SPACE_H", text)
        self.assertIn("typedef u8 ItemId;", text)
        # The item cap is a build-time-overridable macro keyed to
        # FE8_ITEM_ID_CAP (default 0xCD), not a baked-in literal, so the
        # committed header is cap-invariant and the compiled consumer and the
        # data generator resolve one single cap. See render_c_header().
        self.assertIn("#ifndef FE8_ITEM_ID_CAP", text)
        self.assertIn("#define FE8_ITEM_ID_CAP 0xCD", text)
        self.assertIn("#define ITEM_ID_CONFIGURED_CAP FE8_ITEM_ID_CAP", text)
        # Frozen domains stay literal.
        self.assertIn("CLASS_ID_CONFIGURED_CAP 0xFF", text)

    def test_audit_json_carries_digest(self):
        import json
        payload = json.loads(idspace.render_audit_json())
        self.assertEqual(payload["digest"], idspace.digest())
        self.assertEqual(len(payload["domains"]), 6)

    def test_audit_json_is_labelled_default_and_carries_the_census(self):
        import json
        from scripts.generated_data import consumer_census
        payload = json.loads(idspace.render_audit_json())
        self.assertEqual(payload["contract"], "default")
        self.assertEqual(payload["default_item_cap"], 0xCD)
        self.assertEqual(payload["default_item_record_count"], 206)
        self.assertEqual(payload["census_digest"], consumer_census.census_digest())
        self.assertIn("coverage_limitations", payload["census"])
        for key, entry in payload["domain_record_counts"].items():
            if entry["record_count_status"] == "n/a":
                self.assertTrue((entry["record_count_note"] or "").strip(), key)


if __name__ == "__main__":
    unittest.main()
