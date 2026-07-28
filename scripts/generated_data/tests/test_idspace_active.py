"""Tests for the build-local ACTIVE cap/count contract (Issue #10).

The committed DEFAULT contract (reports/id_space_audit.*, include/id_space.h)
must stay byte-identical at every cap; the ACTIVE contract under
build/generated/data must report exactly what this configured build resolved
(0xCD/206 by default, 0xCE/207 when FE8_ITEM_ID_CAP opts in) and must be
consumed by a real compiled translation unit.
"""

import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

from scripts.generated_data import idspace


EXPANDED_ENV = {idspace.ITEM_CAP_ENV: '0xCE'}


def _args(out_dir):
    return argparse.Namespace(out_dir=out_dir)


class ActiveContractModelTests(unittest.TestCase):
    def test_default_contract_is_vanilla_206_at_0xCD(self):
        payload = idspace.active_contract(env={})
        item = [d for d in payload['domains'] if d['key'] == 'item'][0]
        self.assertEqual(item['default_cap'], 0xCD)
        self.assertEqual(item['default_record_count'], 206)
        self.assertEqual(item['active_configured_cap'], 0xCD)
        self.assertEqual(item['active_record_count'], 206)
        self.assertFalse(item['expanded_past_default'])

    def test_configured_contract_is_207_at_0xCE(self):
        payload = idspace.active_contract(env=EXPANDED_ENV)
        item = [d for d in payload['domains'] if d['key'] == 'item'][0]
        self.assertEqual(item['active_configured_cap'], 0xCE)
        self.assertEqual(item['active_record_count'], 207)
        self.assertEqual(item['active_configured_cap_hex'], '0xCE')
        self.assertEqual(item['default_cap_hex'], '0xCD')
        self.assertTrue(item['expanded_past_default'])
        # The DEFAULT half of the same payload never moves.
        self.assertEqual(item['default_cap'], 0xCD)
        self.assertEqual(item['default_record_count'], 206)

    def test_all_six_domains_carry_honest_cap_and_count_fields(self):
        payload = idspace.active_contract(env=EXPANDED_ENV)
        self.assertEqual(len(payload['domains']), 6)
        for domain in payload['domains']:
            self.assertIsInstance(domain['default_cap'], int)
            self.assertIsInstance(domain['active_configured_cap'], int)
            if domain['record_count_status'] == 'counted':
                self.assertIsInstance(domain['default_record_count'], int)
                self.assertIsInstance(domain['active_record_count'], int)
                self.assertIsNotNone(domain['record_table'])
            else:
                self.assertEqual(domain['record_count_status'], 'n/a')
                self.assertTrue((domain['record_count_note'] or '').strip(),
                                'n/a record count without a reason: ' + domain['key'])

    def test_only_the_item_domain_is_a_build_input(self):
        default_caps = idspace.active_caps(env={})
        expanded_caps = idspace.active_caps(env=EXPANDED_ENV)
        moved = [key for key in default_caps if default_caps[key] != expanded_caps[key]]
        self.assertEqual(moved, ['item'])

    def test_consumer_rows_are_shared_between_default_and_active(self):
        default_rows = idspace.consumer_rows()
        active_rows = idspace.active_contract(env=EXPANDED_ENV)['consumers']
        self.assertEqual([r['key'] for r in default_rows], [r['key'] for r in active_rows])
        item_default = [r for r in default_rows if r['domain'] == 'item'][0]
        item_active = [r for r in active_rows if r['domain'] == 'item'][0]
        self.assertEqual(item_default['configured_cap'], 0xCD)
        self.assertEqual(item_active['configured_cap'], 0xCE)
        self.assertEqual(item_active['record_count'], 207)

    def test_active_manifest_reports_the_real_registry_count(self):
        default_rows = {r['table']: r for r in idspace.active_manifest_rows(env={})}
        self.assertEqual(default_rows['items']['committed_record_count'], 206)
        self.assertEqual(default_rows['items']['active_record_count'], 206)
        self.assertFalse(default_rows['items']['differs_from_committed'])
        expanded_rows = {r['table']: r for r in idspace.active_manifest_rows(env=EXPANDED_ENV)}
        # The committed manifest stays 206 on purpose; the ACTIVE view must not.
        self.assertEqual(expanded_rows['items']['committed_record_count'], 206)
        self.assertEqual(expanded_rows['items']['active_record_count'], 207)
        self.assertTrue(expanded_rows['items']['differs_from_committed'])
        for table, row in expanded_rows.items():
            if table != 'items':
                self.assertFalse(row['differs_from_committed'], table)

    def test_impossible_cap_count_pair_is_rejected(self):
        payload = idspace.active_contract(env={})
        for domain in payload['domains']:
            if domain['key'] == 'item':
                domain['active_record_count'] = 999
        with self.assertRaises(idspace.CapError):
            idspace.validate_active_contract(payload)


class ActiveOutputTests(unittest.TestCase):
    def test_header_carries_default_and_active_numbers(self):
        default_header = idspace.render_active_header(env={})
        self.assertIn('#define ITEM_ID_DEFAULT_CAP 0xCD', default_header)
        self.assertIn('#define ITEM_ID_DEFAULT_RECORD_COUNT 206', default_header)
        self.assertIn('#define ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD', default_header)
        self.assertIn('#define ITEM_ID_ACTIVE_RECORD_COUNT 206', default_header)
        expanded_header = idspace.render_active_header(env=EXPANDED_ENV)
        self.assertIn('#define ITEM_ID_DEFAULT_CAP 0xCD', expanded_header)
        self.assertIn('#define ITEM_ID_DEFAULT_RECORD_COUNT 206', expanded_header)
        self.assertIn('#define ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCE', expanded_header)
        self.assertIn('#define ITEM_ID_ACTIVE_RECORD_COUNT 207', expanded_header)

    def test_header_is_c89_agbcc_safe(self):
        header = idspace.render_active_header(env=EXPANDED_ENV)
        self.assertNotIn('//', header)
        self.assertIn('#ifndef GUARD_ID_SPACE_ACTIVE_H', header)
        for domain in idspace.DOMAINS:
            self.assertIn('#define {}_ID_ACTIVE_CONFIGURED_CAP'.format(domain.macro), header)

    def test_machine_and_human_audits_agree_with_the_header(self):
        payload = json.loads(idspace.render_active_json(env=EXPANDED_ENV))
        item = [d for d in payload['domains'] if d['key'] == 'item'][0]
        self.assertEqual(item['active_configured_cap'], 0xCE)
        self.assertEqual(item['active_record_count'], 207)
        self.assertEqual(item['active_configured_cap_hex'], '0xCE')
        markdown = idspace.render_active_markdown(env=EXPANDED_ENV)
        self.assertIn('ACTIVE contract', markdown)
        self.assertIn('0xCE', markdown)
        self.assertIn('207', markdown)
        self.assertIn('0xCD', markdown)
        self.assertIn('206', markdown)

    def test_generation_is_byte_identical_when_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(idspace.cmd_active_generate(_args(tmp)), 0)
            first = {name: open(os.path.join(tmp, name), 'rb').read()
                     for name in sorted(os.listdir(tmp))}
            self.assertEqual(idspace.cmd_active_generate(_args(tmp)), 0)
            second = {name: open(os.path.join(tmp, name), 'rb').read()
                      for name in sorted(os.listdir(tmp))}
            self.assertEqual(first, second)
            self.assertEqual(sorted(first), sorted([
                idspace.ACTIVE_HEADER_NAME, idspace.ACTIVE_JSON_NAME, idspace.ACTIVE_MD_NAME]))

    def test_cap_flip_and_flip_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            idspace.cmd_active_generate(_args(tmp))
            self.assertIn('ACTIVE_RECORD_COUNT 206', open(header, encoding='utf-8').read())
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}):
                idspace.cmd_active_generate(_args(tmp))
                text = open(header, encoding='utf-8').read()
                self.assertIn('ACTIVE_RECORD_COUNT 207', text)
                self.assertIn('ACTIVE_CONFIGURED_CAP 0xCE', text)
            idspace.cmd_active_generate(_args(tmp))
            text = open(header, encoding='utf-8').read()
            self.assertIn('ACTIVE_RECORD_COUNT 206', text)
            self.assertIn('ACTIVE_CONFIGURED_CAP 0xCD', text)

    def test_active_check_heals_an_out_of_band_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            idspace.cmd_active_generate(_args(tmp))
            header = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            with open(header, 'w', encoding='utf-8') as handle:
                handle.write('/* poisoned out of band */\n')
            self.assertEqual(idspace.cmd_active_check(_args(tmp)), 0)
            self.assertIn('ITEM_ID_ACTIVE_RECORD_COUNT 206', open(header, encoding='utf-8').read())

    def test_active_check_reports_the_active_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}):
                self.assertEqual(idspace.cmd_active_check(_args(tmp)), 0)
                payload = json.loads(
                    open(os.path.join(tmp, idspace.ACTIVE_JSON_NAME), encoding='utf-8').read())
            item = [d for d in payload['domains'] if d['key'] == 'item'][0]
            self.assertEqual(item['active_record_count'], 207)


class CommittedDefaultStabilityTests(unittest.TestCase):
    def test_committed_surfaces_never_move_with_the_env(self):
        default_json = idspace.render_audit_json()
        default_md = idspace.render_audit_markdown()
        default_header = idspace.render_c_header()
        with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}):
            self.assertEqual(idspace.render_audit_json(), default_json)
            self.assertEqual(idspace.render_audit_markdown(), default_md)
            self.assertEqual(idspace.render_c_header(), default_header)

    def test_committed_files_on_disk_are_the_default_contract(self):
        with open(idspace.AUDIT_JSON_PATH, encoding='utf-8') as handle:
            payload = json.load(handle)
        self.assertEqual(payload['contract'], 'default')
        self.assertEqual(payload['default_item_cap'], 0xCD)
        self.assertEqual(payload['default_item_record_count'], 206)
        with open(idspace.AUDIT_MD_PATH, encoding='utf-8') as handle:
            markdown = handle.read()
        self.assertIn('DEFAULT contract', markdown)
        self.assertIn('0xCD', markdown)
        self.assertIn('206', markdown)

    def test_manifest_record_count_stays_at_the_committed_default(self):
        from scripts.generated_data import manifest as manifest_mod
        with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}):
            entries = {entry.name: entry for entry in manifest_mod.collect_entries()}
        self.assertEqual(entries['items'].record_count, 206)


class LiveConsumerTests(unittest.TestCase):
    """The active header must be compiled, not merely generated."""

    def _generated_items_source(self, env):
        from scripts.generated_data.items import schema as items_schema
        from scripts.generated_data.items import generate as items_generate
        records = items_schema.load_records(
            items_schema.ItemsTableSchema.default_source,
            item_cap=idspace.resolve_item_id_cap(env),
            overlay_source=items_schema.ITEMS_EXPANSION_SOURCE)
        return items_generate.generate_c_source(records, items_schema.ItemsTableSchema.default_source)

    def test_generated_table_includes_and_asserts_the_active_contract(self):
        source = self._generated_items_source({})
        self.assertIn('#include "id_space.h"', source)
        self.assertIn('#include "id_space_active.h"', source)
        self.assertIn('ITEM_ID_CONFIGURED_CAP == ITEM_ID_ACTIVE_CONFIGURED_CAP', source)
        self.assertIn('sizeof(gItemData) / sizeof(gItemData[0]) == ITEM_ID_ACTIVE_RECORD_COUNT',
                      source)

    def test_generated_table_record_count_tracks_the_active_cap(self):
        default_source = self._generated_items_source({})
        expanded_source = self._generated_items_source(EXPANDED_ENV)
        self.assertEqual(default_source.count('\n\t[ITEM'), 206)
        self.assertEqual(expanded_source.count('\n\t[ITEM'), 207)


if __name__ == '__main__':
    unittest.main()
