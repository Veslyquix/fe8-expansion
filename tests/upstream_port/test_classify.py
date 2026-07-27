import unittest

from scripts.upstream_port import classify


class ClassifyPathTests(unittest.TestCase):
    def test_code_paths(self):
        self.assertEqual(classify.classify_path("src/battle.c"), "code")
        self.assertEqual(classify.classify_path("include/battle.h"), "code")
        self.assertEqual(classify.classify_path("asm/nonmatching/foo.s"), "code")

    def test_data_paths(self):
        self.assertEqual(classify.classify_path("src/data/chapter1.s"), "data")
        self.assertEqual(classify.classify_path("graphics/map/tile.png"), "data")
        self.assertEqual(classify.classify_path("texts/english.json"), "data")

    def test_symbol_paths(self):
        self.assertEqual(classify.classify_path("sym_iwram.txt"), "symbol")
        self.assertEqual(classify.classify_path("fireemblem8.map"), "symbol")

    def test_docs_paths(self):
        self.assertEqual(classify.classify_path("README.md"), "docs")
        self.assertEqual(classify.classify_path("docs/upstream-porting.md"), "docs")
        self.assertEqual(classify.classify_path("CONTRIBUTING.md"), "docs")

    def test_tools_paths(self):
        self.assertEqual(classify.classify_path("scripts/dump_bgs.py"), "tools")
        self.assertEqual(classify.classify_path("tools/bin2c/main.c"), "tools")

    def test_build_paths(self):
        self.assertEqual(classify.classify_path("Makefile"), "build")
        self.assertEqual(classify.classify_path("modern.mk"), "build")
        self.assertEqual(classify.classify_path("build_tools.sh"), "build")

    def test_linker_paths(self):
        self.assertEqual(classify.classify_path("ldscript.txt"), "linker")
        self.assertEqual(classify.classify_path("linker_script_banim.txt"), "linker")

    def test_config_paths(self):
        self.assertEqual(classify.classify_path(".github/workflows/build.yml"), "config")
        self.assertEqual(classify.classify_path("buddy.yml"), "config")

    def test_other_fallback(self):
        self.assertEqual(classify.classify_path("random-top-level-file"), "other")

    def test_priority_linker_before_build(self):
        # linker/* wins over any *.mk-style build heuristic collision.
        self.assertEqual(classify.classify_path("linker_script_sound.txt"), "linker")

    def test_category_summary_counts(self):
        summary = classify.category_summary(["Makefile", "Makefile", "README.md"])
        self.assertEqual(summary, {"build": 2, "docs": 1})


class RiskFlagTests(unittest.TestCase):
    def test_makefile_is_build_divergence_and_hotspot(self):
        flags = classify.risk_flags_for_paths(["Makefile"])
        self.assertIn("modern-build-divergence-risk", flags)
        self.assertIn("known-fork-divergence-hotspot", flags)

    def test_linker_script_is_linker_conflict_and_hotspot(self):
        flags = classify.risk_flags_for_paths(["ldscript.txt"])
        self.assertIn("linker-conflict-risk", flags)
        self.assertIn("known-fork-divergence-hotspot", flags)

    def test_symbol_file_flagged(self):
        flags = classify.risk_flags_for_paths(["sym_iwram.txt"])
        self.assertIn("symbol-table-conflict-risk", flags)

    def test_plain_code_change_has_no_risk_flags(self):
        flags = classify.risk_flags_for_paths(["src/battle.c", "include/battle.h"])
        self.assertEqual(flags, [])

    def test_flags_sorted_and_deduplicated(self):
        flags = classify.risk_flags_for_paths(["Makefile", "modern.mk", "src/battle.c"])
        self.assertEqual(flags, sorted(set(flags)))


if __name__ == "__main__":
    unittest.main()
