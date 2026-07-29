"""Tests for the source-driven extensible-ID consumer census (Issue #10).

These deliberately do *not* assert 'each category appears once' -- that is what a
curated sample can already fake. They assert the census is reproducible, that
every scanned hit is classified 1:1, that a *new* consumer in the source tree
fails the gate, and that a classified row which disappears fails as stale.
"""

import json
import os
import shutil
import tempfile
import unittest

from scripts.generated_data import consumer_census as census


class TokenizationTests(unittest.TestCase):
    def test_camel_snake_and_digit_splitting(self):
        self.assertEqual(census.tokenize('gConvoyItemArray'), ['g', 'convoy', 'item', 'array'])
        self.assertEqual(census.tokenize('item1'), ['item', '1'])
        self.assertEqual(census.tokenize('ShopList_Tower5_0'),
                         ['shop', 'list', 'tower', '5', '0'])

    def test_substring_lookalikes_are_not_hits(self):
        # MapIdle contains the literal substring "pid"; a substring matcher
        # reported it as a character-ID consumer. Token matching must not.
        self.assertEqual(census.domains_for('DebugMenuMapIdleCore'), ())
        self.assertEqual(census.domains_for('hasItemEffectTarget'), ())

    def test_real_id_declarations_are_hits(self):
        self.assertIn('item', census.domains_for('itemId'))
        self.assertIn('item', census.domains_for('gConvoyItemArray'))
        self.assertIn('item', census.domains_for('WriteSupplyItems'))
        self.assertIn('character', census.domains_for('pid'))
        self.assertIn('class', census.domains_for('classIndex'))


class ScanReproducibilityTests(unittest.TestCase):
    def test_scan_is_deterministic_and_sorted(self):
        census.reset_cache()
        first = [hit.key for hit in census.scan()]
        census.reset_cache()
        second = [hit.key for hit in census.scan()]
        self.assertEqual(first, second)
        rows = census.classified_rows()
        keys = [(r['domain'], r['category'], r['path'], r['kind'], r['symbol']) for r in rows]
        self.assertEqual(keys, sorted(keys))

    def test_hit_keys_are_unique_and_line_free(self):
        keys = [hit.key for hit in census.scan()]
        self.assertEqual(len(keys), len(set(keys)), 'duplicate scanner hit keys')
        for key in keys:
            # Identity must survive re-indentation: no line numbers in the key.
            self.assertNotRegex(key, r':\d+$')

    def test_digest_is_stable_and_content_sensitive(self):
        rows = census.classified_rows()
        self.assertEqual(census.census_digest(rows), census.census_digest(rows))
        mutated = [dict(row) for row in rows]
        mutated[0]['category'] = 'link-network'
        self.assertNotEqual(census.census_digest(rows), census.census_digest(mutated))


class ClassificationCoverageTests(unittest.TestCase):
    def test_every_hit_is_classified_and_no_row_is_stale(self):
        problems = census.coverage_problems()
        self.assertEqual(problems, [], '\n'.join(problems[:20]))

    def test_classification_is_1_to_1_with_the_scan(self):
        hits = {hit.key for hit in census.scan()}
        classified = set(census.load_classification())
        self.assertEqual(hits, classified)

    def test_every_exclusion_states_a_reason(self):
        for row in census.classified_rows():
            if row['category'] == census.EXCLUSION_CATEGORY:
                self.assertTrue((row['reason'] or '').strip(),
                                'reviewed exclusion without a reason: ' + row['key'])

    def test_categories_are_all_known(self):
        for row in census.classified_rows():
            self.assertIn(row['category'], census.ALL_CATEGORIES)

    def test_duplicate_classification_keys_are_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'dupes.json')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('{"entries": {"a|b|c|d": {"category": "runtime-struct"}, '
                             '"a|b|c|d": {"category": "save-field"}}}')
            with self.assertRaises(census.CensusError):
                census.load_classification(path)

    def test_exclusion_without_reason_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'bad.json')
            payload = {'entries': {'x|y|z|w': {'category': census.EXCLUSION_CATEGORY, 'reason': ''}}}
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle)
            with self.assertRaises(census.CensusError):
                census.load_classification(path)


class RequiredExemplarTests(unittest.TestCase):
    """The consumers an earlier hand-curated audit silently omitted."""

    EXEMPLARS = (
        ('include/bonusclaim.h', 'BonusClaimEnt.itemId'),
        ('include/bmunit.h', 'UnitDefinition.charIndex'),
        ('include/bmunit.h', 'UnitDefinition.classIndex'),
        ('include/bmunit.h', 'UnitDefinition.items'),
        ('include/bmunit.h', 'Unit.items'),
        ('include/bmshop.h', 'gDefaultShopInventory'),
        ('include/variables.h', 'gConvoyItemArray'),
        ('include/bmsave.h', 'WriteSupplyItems'),
        ('include/bmsave.h', 'ReadSupplyItems'),
        ('include/bmarena.h', 'ArenaData.playerClassId'),
        ('include/bmarena.h', 'ArenaData.opponentClassId'),
        ('include/opinfo.h', 'ClassReelEnt.classId'),
        ('include/opinfo.h', 'OpInfoIconProc.classId'),
        ('include/opinfo.h', 'OpInfoViewProc.charIndex'),
        ('include/uisupport.h', 'GetSupportScreenCharIdAt'),
        ('include/monstergen.h', 'MonsterItemsByClassEntry.classId'),
        ('include/worldmap.h', 'GMapNodeData.chapteridx_eirika'),
        ('include/worldmap.h', 'GmapTimeMonsConf.jid'),
    )

    def setUp(self):
        self.rows = census.classified_rows()
        self.index = {(row['path'], row['symbol']): row for row in self.rows}

    def test_named_omissions_are_now_audited(self):
        for path, symbol in self.EXEMPLARS:
            row = self.index.get((path, symbol))
            self.assertIsNotNone(row, 'census is missing {} in {}'.format(symbol, path))
            self.assertNotEqual(row['category'], census.EXCLUSION_CATEGORY,
                                '{} must be audited, not excluded'.format(symbol))

    def test_every_shop_and_convoy_representation_is_present(self):
        shop_lists = {row['symbol'] for row in self.rows if row['symbol'].startswith('ShopList_')}
        self.assertGreaterEqual(len(shop_lists), 15, sorted(shop_lists))
        worldmap_lists = {row['symbol'] for row in self.rows if row['symbol'].startswith('ItemList_WM_')}
        self.assertGreaterEqual(len(worldmap_lists), 15, sorted(worldmap_lists))
        convoy = {row['symbol'] for row in self.rows if 'Convoy' in row['symbol']}
        self.assertIn('gConvoyItemArray', convoy)
        self.assertIn('gConvoyItemCount', convoy)

    def test_monster_lookup_table_is_present(self):
        symbols = {row['symbol'] for row in self.rows}
        self.assertIn('gMonsterItemTable', symbols)


class MutationTests(unittest.TestCase):
    """A changed source tree must move the census, not be silently absorbed."""

    def _fixture_tree(self, tmp, header_text):
        os.makedirs(os.path.join(tmp, 'include'), exist_ok=True)
        with open(os.path.join(tmp, 'include', 'fixture.h'), 'w', encoding='utf-8') as handle:
            handle.write(header_text)
        census.reset_cache()
        return census.scan(repo_root=tmp)

    def tearDown(self):
        census.reset_cache()

    def test_new_source_consumer_is_detected_and_unclassified(self):
        with tempfile.TemporaryDirectory() as tmp:
            hits = self._fixture_tree(tmp, 'struct FixtureSave\n{\n    u8 itemId;\n};\n')
            keys = [hit.key for hit in hits]
            self.assertIn('include/fixture.h|struct-field|item|FixtureSave.itemId', keys)
            problems = census.coverage_problems(hits=hits, classification={})
            self.assertTrue(any('unclassified' in problem for problem in problems))
            self.assertTrue(any('FixtureSave.itemId' in problem for problem in problems))

    def test_removed_consumer_is_reported_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            hits = self._fixture_tree(tmp, 'struct FixtureSave\n{\n    u8 itemId;\n};\n')
            classification = {
                hits[0].key: {'category': 'runtime-struct', 'reason': None},
                'include/gone.h|struct-field|item|Gone.itemId': {'category': 'runtime-struct'},
            }
            problems = census.coverage_problems(hits=hits, classification=classification)
            self.assertEqual(len(problems), 1, problems)
            self.assertIn('stale', problems[0])
            self.assertIn('include/gone.h', problems[0])

    def test_edited_declaration_keeps_its_key_but_moves_the_evidence_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self._fixture_tree(tmp, 'struct FixtureSave\n{\n    u8 itemId;\n};\n')
            second = self._fixture_tree(
                tmp, '/* a new comment line */\n\nstruct FixtureSave\n{\n    u8 itemId;\n};\n')
            self.assertEqual(first[0].key, second[0].key)
            self.assertNotEqual(first[0].line, second[0].line)

    def test_classified_rows_raise_on_an_unclassified_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            hits = self._fixture_tree(tmp, 'struct FixtureSave\n{\n    u8 itemId;\n};\n')
            with self.assertRaises(census.CensusError):
                census.classified_rows(hits=hits, classification={})


class ScopeTrackingTests(unittest.TestCase):
    """RCA (Issue #10 fresh review P2): struct-field matching must fire only
    inside a real struct/union definition body. A function signature whose
    parameter is a struct type must not turn body-local ID-like variables into
    fabricated ``StructName.field`` hits, and function bodies are not analysed.
    """

    def _scan(self, text, name='fixture.h'):
        import os
        import tempfile
        tmp = tempfile.mkdtemp()
        self._tmp = tmp
        os.makedirs(os.path.join(tmp, 'include'), exist_ok=True)
        with open(os.path.join(tmp, 'include', name), 'w', encoding='utf-8') as handle:
            handle.write(text)
        census.reset_cache()
        return census.scan(repo_root=tmp)

    def tearDown(self):
        import shutil
        census.reset_cache()
        tmp = getattr(self, '_tmp', None)
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    def _struct_field_symbols(self, hits):
        return {h.symbol for h in hits if h.kind == 'struct-field'}

    # -- the exact fabrications the fresh review named -------------------

    def test_function_body_local_is_not_a_struct_field(self):
        text = (
            "u8 SupplyUsability(const struct MenuItemDef * def, int number)\n"
            "{\n"
            "    int pid;\n"
            "    if (!HasConvoyAccess())\n"
            "    {\n"
            "        int item;\n"
            "        return item;\n"
            "    }\n"
            "    return pid;\n"
            "}\n")
        fields = self._struct_field_symbols(self._scan(text))
        self.assertNotIn('MenuItemDef.pid', fields)
        self.assertNotIn('MenuItemDef.item', fields)
        self.assertNotIn('anonymous.pid', fields)
        self.assertNotIn('anonymous.item', fields)
        self.assertEqual(fields, set())

    def test_struct_pointer_parameter_body_local_array(self):
        text = (
            "void ShopDrawBuyItemLine(struct ProcShop * proc, int itemIndex)\n"
            "{\n"
            "    u16 item;\n"
            "    u16 itemList[6];\n"
            "    int index = DivRem(itemIndex, 6);\n"
            "}\n")
        hits = self._scan(text)
        self.assertEqual(self._struct_field_symbols(hits), set())
        self.assertEqual({h.kind for h in hits} - {'function-signature'}, set(),
                         'function bodies must not yield data-symbols/struct-fields')

    def test_plain_function_body_yields_no_scoped_declarations(self):
        text = (
            "int CountConvoyItems(void)\n"
            "{\n"
            "    int items[5];\n"
            "    u8 chapterId = 3;\n"
            "    return items[chapterId];\n"
            "}\n")
        hits = self._scan(text)
        self.assertEqual(self._struct_field_symbols(hits), set())
        self.assertNotIn('data-symbol', {h.kind for h in hits})

    def test_nested_blocks_do_not_open_struct_scope(self):
        text = (
            "void Loop(struct Unit * unit)\n"
            "{\n"
            "    for (int i = 0; i < 5; i++)\n"
            "    {\n"
            "        while (unit)\n"
            "        {\n"
            "            int itemId;\n"
            "        }\n"
            "    }\n"
            "}\n")
        self.assertEqual(self._struct_field_symbols(self._scan(text)), set())

    # -- real declarations must still be captured -----------------------

    def test_named_struct_field_is_captured(self):
        text = "struct FixtureSave {\n    u8 itemId;\n    u8 chapterId;\n};\n"
        fields = self._struct_field_symbols(self._scan(text))
        self.assertIn('FixtureSave.itemId', fields)
        self.assertIn('FixtureSave.chapterId', fields)

    def test_multiline_brace_style_named_struct(self):
        text = (
            "struct ArenaData\n"
            "{\n"
            "    u8 playerClassId;\n"
            "    u8 opponentClassId;\n"
            "};\n")
        fields = self._struct_field_symbols(self._scan(text))
        self.assertIn('ArenaData.playerClassId', fields)
        self.assertIn('ArenaData.opponentClassId', fields)

    def test_typedef_anonymous_struct_uses_the_closing_alias(self):
        text = (
            "typedef struct {\n"
            "    u8 itemId;\n"
            "} FixtureItemDef;\n")
        fields = self._struct_field_symbols(self._scan(text))
        self.assertIn('FixtureItemDef.itemId', fields)
        self.assertNotIn('anonymous.itemId', fields)

    def test_typedef_struct_tag_before_multiline_brace(self):
        text = (
            "typedef struct FixtureTag\n"
            "{\n"
            "    u8 classId;\n"
            "} FixtureAlias;\n")
        fields = self._struct_field_symbols(self._scan(text))
        self.assertIn('FixtureTag.classId', fields)

    def test_union_definition_body_is_a_struct_scope(self):
        text = (
            "union FixtureUnion {\n"
            "    u8 itemId;\n"
            "    u16 raw;\n"
            "};\n")
        self.assertIn('FixtureUnion.itemId', self._struct_field_symbols(self._scan(text)))

    def test_nested_anonymous_union_inherits_named_ancestor(self):
        text = (
            "struct FixtureOuter {\n"
            "    u8 base;\n"
            "    union {\n"
            "        u8 itemId;\n"
            "        u16 raw;\n"
            "    } payload;\n"
            "};\n")
        fields = self._struct_field_symbols(self._scan(text))
        self.assertIn('FixtureOuter.itemId', fields)
        self.assertNotIn('anonymous.itemId', fields)

    # -- struct *uses* must never open a definition body ----------------

    def test_forward_declaration_and_parameter_and_cast_and_sizeof(self):
        text = (
            "struct FixtureCfg;\n"
            "extern struct FixtureCfg gCfg;\n"
            "void Consume(struct FixtureCfg * cfg)\n"
            "{\n"
            "    u8 itemId = *(u8 *)(struct FixtureCfg *) cfg;\n"
            "    int n = sizeof(struct FixtureCfg);\n"
            "}\n")
        self.assertEqual(self._struct_field_symbols(self._scan(text)), set(),
                         'a struct *use* must never be treated as a definition body')

    def test_initializer_braces_are_not_struct_scopes(self):
        text = (
            "struct FixtureCfg gTable[] =\n"
            "{\n"
            "    { .itemId = 1 },\n"
            "    { .itemId = 2 },\n"
            "};\n")
        self.assertEqual(self._struct_field_symbols(self._scan(text)), set())


class ScopeReportingTests(unittest.TestCase):
    def test_scope_is_self_describing(self):
        scope = census.scan_scope()
        roots = {entry['root'] for entry in scope['roots']}
        self.assertTrue({'include', 'src', 'asm'}.issubset(roots))
        excluded = {entry['prefix'] for entry in scope['excluded']}
        self.assertIn('build/', excluded)
        for entry in scope['excluded']:
            self.assertTrue(entry['reason'].strip())
        self.assertTrue(scope['coverage_limitations'])


if __name__ == '__main__':
    unittest.main()
