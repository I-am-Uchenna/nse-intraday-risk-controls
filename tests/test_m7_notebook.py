"""Check M7 controls with synthetic records; never open market prices or final results."""
import ast
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import unittest

from path_robust.paths import NOTEBOOK as NOTEBOOKS
NOTEBOOK = NOTEBOOKS['M7']


def notebook():
    return json.loads(NOTEBOOK.read_text(encoding='utf-8'))


def code_cells():
    return {c['id']: ''.join(c['source']) for c in notebook()['cells'] if c['cell_type'] == 'code'}


def bundle_hash(book):
    controls = 'RUN_STAGE|FINAL_ACCESS_APPROVED|CONNECT_DRIVE|CASH_FOLDER|INDEX_FOLDER|SAVE_FOLDER|READY_TO_FREEZE|PUBLISH_RUN|PUBLISH_RUN_ID'
    payload = []
    for c in book['cells']:
        if c['cell_type'] != 'code':
            continue
        value = ''.join(c['source'])
        value = re.sub(r'(?m)^M7_CODE_BUNDLE_SHA256 = .*$', 'M7_CODE_BUNDLE_SHA256 = "<self>"', value)
        value = re.sub(r'(?m)^(' + controls + r') = .*$', r'\1 = "<runtime-control>"', value)
        payload.append(dict(id=c['id'], source=value))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def controls():
    tree = ast.parse(code_cells()['m7-review-and-protocol'])
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    scope = dict(Path=Path, json=json, hashlib=hashlib, datetime=datetime, timezone=timezone, math=math)
    exec(compile(ast.Module(body=definitions, type_ignores=[]), '<M7 synthetic gate>', 'exec'), scope)
    return scope


def validation_record(scope):
    settings = ['reference', 'cost_5', 'cost_25', 'stop_slippage_5', 'stop_slippage_10', 'delay_2', 'delay_5']
    science = dict(settings=[dict(name=n) for n in settings], source_reverification=True,
                   parsed_data_sha256='synthetic-no-prices', implementation_sha256='synthetic-code',
                   declared_notebook_code_sha256='synthetic-analysis')
    manifest = dict(stage='validation', raw_inputs_reverified=True, independent_economic_failure=False,
                    completed_utc='2000-01-01T00:00:00+00:00', run_id='synthetic-validation',
                    protocol_sha256=scope['m7_digest'](science))
    checks = [dict(timestamp_label=label, setting=s, status='PASS')
              for label in ('start', 'end') for s in settings]
    return science, manifest, checks


class M7NotebookTests(unittest.TestCase):
    def test_clean_source_identity_and_unchanged_trading_core(self):
        book = notebook(); cells = code_cells()
        self.assertEqual(len(cells), 28)
        self.assertIn('RUN_STAGE = "validation"', cells['research-002'])
        self.assertIn('FINAL_ACCESS_APPROVED = False', cells['research-002'])
        declared = next(n.value.value for n in ast.parse(cells['m7-review-and-protocol']).body
                        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                        and n.targets[0].id == 'M7_CODE_BUNDLE_SHA256')
        self.assertEqual(bundle_hash(book), declared)
        for c in book['cells']:
            if c['cell_type'] == 'code':
                ast.parse(''.join(c['source']))
                self.assertIsNone(c['execution_count'])
                self.assertFalse(c['outputs'])
        old = json.loads((NOTEBOOKS['M6']).read_text(encoding='utf-8'))
        old_cells = {c['id']: ''.join(c['source']) for c in old['cells']}
        for cid in ['research-004', 'research-008', 'research-009', 'research-010',
                    'research-019', 'research-021', 'research-023', 'research-025',
                    'research-027', 'research-031', 'research-037', 'research-039',
                    'research-041', 'research-043']:
            self.assertEqual(cells[cid], old_cells[cid], cid)
        # Functions defined after the replay gate caused the old freeze trap.
        seen = []; before_gate = True
        for c in book['cells']:
            if c['cell_type'] != 'code':
                continue
            defs = [n.name for n in ast.parse(''.join(c['source'])).body if isinstance(n, ast.FunctionDef)]
            if before_gate:
                seen.extend(defs)
            else:
                self.assertFalse(defs, c['id'])
            if c['id'] == 'research-033':
                before_gate = False
        names = next(ast.literal_eval(n.value) for n in ast.parse(cells['research-033']).body
                     if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                     and n.targets[0].id == 'M7_SCIENTIFIC_FUNCTIONS')
        self.assertEqual(tuple(seen), names)
        self.assertIn('peer_review_tables', names)
        self.assertIn('m7_conclusions', names)

    def test_stage_and_approval_boundaries(self):
        check = controls()['m7_check_stage']
        partitions = dict(development=[date(2021,1,4)], validation=[date(2022,1,3)], final=[date(2023,1,2)])
        check('validation', partitions['validation'], partitions)
        check('final', partitions['final'], partitions, True)
        for stage, dates, approved in [('final', partitions['final'], False),
                                       ('validation', partitions['final'], True),
                                       ('pilot', partitions['final'], True), ('final', [], True)]:
            with self.subTest(stage=stage, dates=dates), self.assertRaises(RuntimeError):
                check(stage, dates, partitions, approved)

    def test_freeze_requires_reviewed_unchanged_completed_validation(self):
        scope = controls(); science, manifest, checks = validation_record(scope)
        freeze = scope['m7_freeze_validation']
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'freeze.json'
            for changes in [dict(stage='final'), dict(raw_inputs_reverified=False),
                            dict(independent_economic_failure=True), dict(completed_utc=None)]:
                with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                    freeze(p, science, science, {**manifest, **changes}, checks)
                self.assertFalse(p.exists())
            for bad in [checks[:-1], [{**r, 'status':'FAIL'} for r in checks], [checks[0]]*14]:
                with self.assertRaisesRegex(RuntimeError, 'fourteen'):
                    freeze(p, science, science, manifest, bad)
            altered = {**science, 'implementation_sha256':'changed'}
            with self.assertRaisesRegex(RuntimeError, 'changed after validation'):
                freeze(p, science, altered, manifest, checks)
            first = freeze(p, science, science, manifest, checks)
            raw = p.read_bytes()
            self.assertEqual(freeze(p, science, science, manifest, checks), first)
            self.assertEqual(p.read_bytes(), raw)
            changed_manifest = {**manifest,'protocol_sha256':scope['m7_digest'](altered)}
            with self.assertRaisesRegex(RuntimeError,'Existing freeze differs'):
                freeze(p, altered, altered, changed_manifest, checks)
            self.assertEqual(p.read_bytes(), raw)

    def test_final_requires_matching_freeze_and_records_access_once(self):
        scope = controls(); science, manifest, checks = validation_record(scope)
        access = scope['m7_record_final_access']
        dates = [date(2023,5,26), date(2023,12,29)]
        with tempfile.TemporaryDirectory() as d:
            freeze, log = Path(d)/'freeze.json', Path(d)/'access.json'
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                access(freeze, science, True, None, log, 'synthetic-final', dates)
            self.assertFalse(log.exists())
            scope['m7_freeze_validation'](freeze, science, science, manifest, checks)
            for payload, approved, cached in [(science, False, None), (science, True, 'cached.sqlite'),
                                              ({**science,'source_reverification':False}, True, None),
                                              ({**science,'parsed_data_sha256':'changed'}, True, None),
                                              ({**science,'declared_notebook_code_sha256':'changed'}, True, None)]:
                with self.assertRaises(RuntimeError):
                    access(freeze, payload, approved, cached, log, 'synthetic-final', dates)
                self.assertFalse(log.exists())
            result = access(freeze, science, True, None, log, 'synthetic-final', dates)
            self.assertEqual(result['validation_run_id'], 'synthetic-validation')
            raw = log.read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'already recorded'):
                access(freeze, science, True, None, log, 'another-attempt', dates)
            self.assertEqual(log.read_bytes(), raw)

    def test_final_diagnostics_accept_synthetic_stage_without_market_read(self):
        from test_peer_review_diagnostics import fixture
        analyze = controls()['peer_review_tables']
        args = fixture()
        expected = analyze('validation', *args)
        args[4][0]['stage'] = 'final'
        actual = analyze('final', *args)
        for name, rows in actual.items():
            self.assertEqual([{**row, 'stage':'validation'} for row in rows], expected[name])


if __name__ == '__main__':
    unittest.main()
