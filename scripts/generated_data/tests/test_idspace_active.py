"""Tests for the build-local ACTIVE cap/count contract (Issue #10).

The committed DEFAULT contract (reports/id_space_audit.*, include/id_space.h)
must stay byte-identical at every cap; the ACTIVE contract under
build/generated/data must report exactly what this configured build resolved
(0xCD/206 by default, 0xCE/207 when FE8_ITEM_ID_CAP opts in) and must be
consumed by a real compiled translation unit.
"""

import argparse
import contextlib
import io
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


class ActiveHealProbeTests(unittest.TestCase):
    """The cheap `active-heal` probe: no source walk on a warm no-op, one full
    render (all three surfaces) only when a surface is missing/stale, and loud
    propagation of cap/schema/IO errors (never a swallowed exit-1 / `|| true`)."""

    def _seed(self, tmp, env=None):
        """Render the three surfaces once with the real census."""
        if env is None:
            idspace.cmd_active_generate(_args(tmp))
        else:
            with mock.patch.dict(os.environ, env, clear=False):
                idspace.cmd_active_generate(_args(tmp))

    def _mtimes(self, tmp):
        return {name: os.stat(os.path.join(tmp, name)).st_mtime_ns
                for name in sorted(os.listdir(tmp))}

    def test_warm_no_op_never_walks_the_consumer_source_scan(self):
        # A poisoned scan proves the warm probe is census-free: if the no-op
        # heal touched the ~15 MB source walk this would raise, not pass.
        from scripts.generated_data import consumer_census
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            consumer_census._SCAN_CACHE.clear()
            with mock.patch.object(
                    consumer_census, 'scan',
                    side_effect=AssertionError('warm active-heal must not run the census scan')):
                self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)

    def test_warm_no_op_writes_nothing_and_preserves_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            before = self._mtimes(tmp)
            self.assertEqual(idspace.active_heal_reasons(tmp), [])
            self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            self.assertEqual(self._mtimes(tmp), before)

    def test_stale_cap_flip_regenerates_all_three_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)  # default 0xCD/206 on disk
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}, clear=False):
                self.assertTrue(idspace.active_heal_reasons(tmp),
                                'a 0xCE build over a 0xCD-on-disk header must be stale')
                self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            header = open(os.path.join(tmp, idspace.ACTIVE_HEADER_NAME), encoding='utf-8').read()
            self.assertIn('ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCE', header)
            self.assertIn('ITEM_ID_ACTIVE_RECORD_COUNT 207', header)
            payload = json.loads(
                open(os.path.join(tmp, idspace.ACTIVE_JSON_NAME), encoding='utf-8').read())
            item = [d for d in payload['domains'] if d['key'] == 'item'][0]
            self.assertEqual(item['active_configured_cap'], 0xCE)
            self.assertEqual(item['active_record_count'], 207)
            md = open(os.path.join(tmp, idspace.ACTIVE_MD_NAME), encoding='utf-8').read()
            self.assertIn('0xCE', md)
            self.assertIn('207', md)

    def test_stale_cap_flip_is_detected_without_the_census(self):
        # Detection (the reason list) must itself be census-free -- only the
        # *regen* leg is allowed to walk the source scan.
        from scripts.generated_data import consumer_census
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            consumer_census._SCAN_CACHE.clear()
            with mock.patch.object(
                    consumer_census, 'scan',
                    side_effect=AssertionError('the heal probe must not scan to detect staleness')):
                with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0xCE'}, clear=False):
                    self.assertTrue(idspace.active_heal_reasons(tmp))

    def test_out_of_band_header_desync_heals_back_to_the_resolved_cap(self):
        # The reported first-fail: an out-of-band 0xCE render on disk, resolved
        # cap still default 0xCD -> stale -> one heal restores 0xCD/206.
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp, env={idspace.ITEM_CAP_ENV: '0xCE'})  # disk holds 0xCE/207
            self.assertTrue(idspace.active_heal_reasons(tmp),
                            'a 0xCE-on-disk header on a default build must be stale')
            self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            header = open(os.path.join(tmp, idspace.ACTIVE_HEADER_NAME), encoding='utf-8').read()
            self.assertIn('ITEM_ID_ACTIVE_CONFIGURED_CAP 0xCD', header)
            self.assertIn('ITEM_ID_ACTIVE_RECORD_COUNT 206', header)

    def test_missing_surface_triggers_regen(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            os.remove(os.path.join(tmp, idspace.ACTIVE_HEADER_NAME))
            reasons = idspace.active_heal_reasons(tmp)
            self.assertTrue(any('missing' in r for r in reasons), reasons)
            self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)))

    def test_corrupt_json_metadata_triggers_regen_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            with open(os.path.join(tmp, idspace.ACTIVE_JSON_NAME), 'w', encoding='utf-8') as h:
                h.write('{ this is not valid json')
            reasons = idspace.active_heal_reasons(tmp)
            self.assertTrue(any('unparseable' in r for r in reasons), reasons)
            self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            # Regen restored a well-formed audit.
            json.loads(open(os.path.join(tmp, idspace.ACTIVE_JSON_NAME), encoding='utf-8').read())

    def test_corrupt_header_invalid_utf8_triggers_regen_not_a_crash(self):
        # An out-of-band write can leave the header as raw, non-UTF-8 bytes
        # (truncated build, disk corruption, a bad merge). That must be an
        # actionable "unparseable" heal reason -- not an unhandled
        # UnicodeDecodeError blowing up the probe.
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            header_path = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            with open(header_path, 'wb') as handle:
                handle.write(b'#define ITEM_ID_ACTIVE_RECORD_COUNT 206\n\xff\xfe\x00garbage')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                reasons = idspace.active_heal_reasons(tmp)
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_HEADER_NAME in r for r in reasons),
                    reasons)
                self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            self.assertNotIn('Traceback', stdout.getvalue())
            # All three surfaces recovered, not just the corrupt one.
            header = open(header_path, encoding='utf-8').read()
            self.assertIn('ITEM_ID_ACTIVE_RECORD_COUNT 206', header)
            json.loads(open(os.path.join(tmp, idspace.ACTIVE_JSON_NAME), encoding='utf-8').read())
            md = open(os.path.join(tmp, idspace.ACTIVE_MD_NAME), encoding='utf-8').read()
            self.assertIn('0xCD', md)

    def test_corrupt_md_invalid_utf8_triggers_regen_not_a_crash(self):
        # Same failure mode as the header case, but for the human-readable
        # Markdown surface: raw non-UTF-8 bytes on disk must be diagnosed as
        # an actionable reason, never an unhandled UnicodeDecodeError.
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            md_path = os.path.join(tmp, idspace.ACTIVE_MD_NAME)
            with open(md_path, 'wb') as handle:
                handle.write(b'# ACTIVE contract\n\xff\xfe\x00garbage')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                reasons = idspace.active_heal_reasons(tmp)
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_MD_NAME in r for r in reasons),
                    reasons)
                self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            self.assertNotIn('Traceback', stdout.getvalue())
            md = open(md_path, encoding='utf-8').read()
            self.assertIn('0xCD', md)
            self.assertIn('206', md)

    def test_all_three_surfaces_corrupt_recover_in_one_heal(self):
        # Header and Markdown poisoned with raw non-UTF-8 bytes, JSON poisoned
        # with invalid JSON, all at once. One heal call must diagnose all
        # three (no crash) and restore all three to a matching, valid state.
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            header_path = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            json_path = os.path.join(tmp, idspace.ACTIVE_JSON_NAME)
            md_path = os.path.join(tmp, idspace.ACTIVE_MD_NAME)
            with open(header_path, 'wb') as handle:
                handle.write(b'\xff\xfe not utf-8 at all')
            with open(json_path, 'w', encoding='utf-8') as handle:
                handle.write('{ not valid json')
            with open(md_path, 'wb') as handle:
                handle.write(b'\xff\xfe not utf-8 at all')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                reasons = idspace.active_heal_reasons(tmp)
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_HEADER_NAME in r for r in reasons),
                    reasons)
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_JSON_NAME in r for r in reasons),
                    reasons)
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_MD_NAME in r for r in reasons),
                    reasons)
                self.assertEqual(idspace.cmd_active_heal(_args(tmp)), 0)
            self.assertNotIn('Traceback', stdout.getvalue())
            header = open(header_path, encoding='utf-8').read()
            self.assertIn('ITEM_ID_ACTIVE_RECORD_COUNT 206', header)
            payload = json.loads(open(json_path, encoding='utf-8').read())
            item = [d for d in payload['domains'] if d['key'] == 'item'][0]
            self.assertEqual(item['active_record_count'], 206)
            md = open(md_path, encoding='utf-8').read()
            self.assertIn('0xCD', md)
            self.assertIn('206', md)

    def test_unreadable_header_is_reported_honestly_and_write_error_propagates(self):
        # A stale header the OS refuses to let us read (permission denied) is
        # a real IO error, not a parse error: the probe must still classify it
        # as an actionable, non-crashing reason (recoverable diagnosis), but
        # the follow-up regen write is genuinely blocked by the OS and that
        # failure must propagate -- never be swallowed into a false "healed"
        # success.
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            header_path = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            os.chmod(header_path, 0o000)
            try:
                reasons = idspace.active_heal_reasons(tmp)  # must not raise
                self.assertTrue(
                    any('unparseable' in r and idspace.ACTIVE_HEADER_NAME in r
                        for r in reasons),
                    reasons)
                with self.assertRaises(OSError):
                    idspace.cmd_active_heal(_args(tmp))
            finally:
                os.chmod(header_path, 0o644)

    def test_schema_version_bump_marks_surfaces_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            with mock.patch.object(idspace, 'SCHEMA_VERSION', idspace.SCHEMA_VERSION + 1):
                reasons = idspace.active_heal_reasons(tmp)
            self.assertTrue(any('schema_version' in r for r in reasons), reasons)

    def test_corrupt_header_cap_line_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            header_path = os.path.join(tmp, idspace.ACTIVE_HEADER_NAME)
            text = open(header_path, encoding='utf-8').read().replace(
                '#define ITEM_ID_ACTIVE_RECORD_COUNT 206',
                '#define ITEM_ID_ACTIVE_RECORD_COUNT 999')
            open(header_path, 'w', encoding='utf-8').write(text)
            reasons = idspace.active_heal_reasons(tmp)
            self.assertTrue(any('ITEM_ID_ACTIVE_RECORD_COUNT' in r for r in reasons), reasons)

    def test_bad_cap_env_fails_loudly_and_is_not_swallowed(self):
        # No exit-1 mask / no `|| true`: a bad cap raises straight out of the
        # probe rather than silently reporting "current".
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0x999'}, clear=False):
                with self.assertRaises(idspace.CapError):
                    idspace.active_heal_reasons(tmp)
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: 'notanint'}, clear=False):
                with self.assertRaises(idspace.CapError):
                    idspace.cmd_active_heal(_args(tmp))

    def test_cli_active_heal_bad_cap_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._seed(tmp)
            with mock.patch.dict(os.environ, {idspace.ITEM_CAP_ENV: '0x999'}, clear=False):
                rc = idspace.main(['active-heal', '--out-dir', tmp])
            self.assertEqual(rc, 1)


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
