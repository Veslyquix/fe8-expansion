"""Tests for the aggregate public registry/counts/dependency manifest."""

import os
import unittest

from scripts.generated_data import manifest as m
from scripts.generated_data import registry  # noqa: F401  (registers schemas)
from scripts.generated_data.schema import REGISTRY

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
COMMITTED_MANIFEST = os.path.join(REPO_ROOT, "reports", "generated_data_manifest.md")


class CollectEntriesTests(unittest.TestCase):
    def test_covers_every_registered_table(self):
        entries = m.collect_entries()
        names = sorted(e.name for e in entries)
        self.assertEqual(names, REGISTRY.all_names())

    def test_record_counts_match_load_records(self):
        entries = m.collect_entries()
        by_name = {e.name: e for e in entries}
        for name in REGISTRY.all_names():
            schema = REGISTRY.resolve(name)
            expected = len(schema.load_records(schema.default_source))
            self.assertEqual(by_name[name].record_count, expected,
                             "record count mismatch for {}".format(name))

    def test_characters_declares_256_budget(self):
        entries = m.collect_entries()
        chars = next(e for e in entries if e.name == "characters")
        self.assertEqual(chars.record_budget, 256)
        self.assertTrue(chars.budget_ok)


class BudgetDiagnosticsTests(unittest.TestCase):
    def test_real_data_has_no_budget_overflow(self):
        entries = m.collect_entries()
        self.assertEqual(m.budget_diagnostics(entries), [])

    def test_overflow_is_reported_actionably(self):
        entries = m.collect_entries()
        chars = next(e for e in entries if e.name == "characters")
        chars.record_count = chars.record_budget + 1
        errors = m.budget_diagnostics(entries)
        self.assertEqual(len(errors), 1)
        message = str(errors[0])
        self.assertIn("characters", message)
        self.assertIn(str(chars.record_budget), message)

    def test_no_budget_declared_never_overflows(self):
        entries = m.collect_entries()
        items = next(e for e in entries if e.name == "items")
        self.assertIsNone(items.record_budget)
        items.record_count = 10 ** 9
        self.assertTrue(items.budget_ok)


class DependencyOrderingTests(unittest.TestCase):
    def test_topo_order_places_deps_before_dependents(self):
        entries = m.collect_entries()
        order = m.aggregate_dependency_graph(entries).topo_order()
        self.assertEqual(sorted(order), REGISTRY.all_names())
        # classes depends on terrainstats/movecost; characters on classes/supports.
        self.assertLess(order.index("terrainstats"), order.index("classes"))
        self.assertLess(order.index("movecost"), order.index("classes"))
        self.assertLess(order.index("classes"), order.index("characters"))
        self.assertLess(order.index("eventscripts"), order.index("eventlists"))
        self.assertLess(order.index("eventlists"), order.index("chapterbundle"))

    def test_digest_is_deterministic(self):
        self.assertEqual(m.manifest_digest(m.collect_entries()),
                         m.manifest_digest(m.collect_entries()))


class CHeaderTests(unittest.TestCase):
    def test_header_is_c89_safe(self):
        header = m.build_manifest_header(m.collect_entries())
        self.assertNotIn("//", header)
        self.assertIn("#ifndef GENERATED_DATA_MANIFEST_H", header)
        self.assertIn("#define GENERATED_DATA_MANIFEST_H", header)
        self.assertIn("#endif", header)

    def test_header_exposes_table_count_and_record_counts(self):
        entries = m.collect_entries()
        header = m.build_manifest_header(entries)
        self.assertIn("#define GENERATED_DATA_TABLE_COUNT {}".format(len(entries)), header)
        for entry in entries:
            macro = entry.name.upper().replace("-", "_")
            self.assertIn(
                "#define GENERATED_DATA_{}_RECORD_COUNT {}".format(macro, entry.record_count),
                header,
            )

    def test_characters_capacity_macro_present(self):
        header = m.build_manifest_header(m.collect_entries())
        self.assertIn("#define GENERATED_DATA_CHARACTERS_CAPACITY 256", header)


class CommittedManifestDriftTests(unittest.TestCase):
    def test_committed_report_matches_generated(self):
        generated = m.build_manifest_report(m.collect_entries())
        with open(COMMITTED_MANIFEST, "r", encoding="utf-8") as handle:
            committed = handle.read()
        self.assertEqual(committed, generated,
                         "reports/generated_data_manifest.md is stale; "
                         "run `make generated-data-manifest`")


if __name__ == "__main__":
    unittest.main()
