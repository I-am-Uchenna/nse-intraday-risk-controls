"""Exercise the delivered M6 code with synthetic records only."""
import ast
from collections import defaultdict
import contextlib
from copy import deepcopy
import csv
from datetime import date
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from path_robust.paths import NOTEBOOK as NOTEBOOKS
NOTEBOOK = NOTEBOOKS['M6']
SCENARIOS = tuple((policy, path) for path in ('O-L-H-C', 'O-H-L-C')
                  for policy in ('time_only', 'stop_only', 'stop_and_target'))


def notebook_cells():
    return {c['id']: ''.join(c['source']) for c in
            json.loads(NOTEBOOK.read_text(encoding='utf-8'))['cells']}


def reconciler():
    function = next(node for node in ast.parse(notebook_cells()['research-031']).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'reconcile_ledgers')
    namespace = dict(Path=Path, csv=csv, math=math, defaultdict=defaultdict, SCENARIOS=SCENARIOS)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<M6 reconciliation>', 'exec'), namespace)
    return namespace['reconcile_ledgers']


def write_records(folder, tables):
    for name, rows in tables.items():
        with (folder / (name + '.csv')).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


class M6NotebookTests(unittest.TestCase):
    def test_visible_core_and_validation_boundary(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        namespace = {'__name__': '__main__'}
        with contextlib.redirect_stdout(io.StringIO()):
            for cell in notebook['cells']:
                if cell['cell_type'] != 'code':
                    continue
                source = ''.join(cell['source'])
                ast.parse(source)
                if 'research-core' in cell['metadata'].get('tags', []):
                    exec(compile(source, str(NOTEBOOK), 'exec'), namespace)
        self.assertEqual(namespace['METHOD_CHECKS']['synthetic_scenarios'], 19)
        self.assertEqual(namespace['METHOD_CHECKS']['status'], 'passed')

    def test_final_and_freeze_are_disabled_before_replay(self):
        cells = notebook_cells()
        self.assertIn('RUN_STAGE = "validation"', cells['research-002'])
        early = next(node for node in ast.parse(cells['research-002']).body
                     if isinstance(node, ast.If) and 'RUN_STAGE not in' in ast.unparse(node.test))
        guard = compile(ast.Module(body=[early], type_ignores=[]), '<M6 early stage guard>', 'exec')
        with self.assertRaisesRegex(RuntimeError, 'final-test execution is disabled'):
            exec(guard, {'RUN_STAGE': 'final'})
        gates = [node for node in ast.parse(cells['research-033']).body if isinstance(node, ast.If)]
        code = compile(ast.Module(body=gates, type_ignores=[]), '<M6 replay boundaries>', 'exec')
        validation = [date(2023, 5, 24), date(2023, 5, 25)]
        final = [date(2023, 5, 26)]
        scope = dict(RUN_STAGE='validation', EVALUATION_DATES=validation,
                     PARTITIONS={'validation': validation, 'final': final})
        exec(code, deepcopy(scope))
        for altered in [dict(RUN_STAGE='final', EVALUATION_DATES=final),
                        dict(EVALUATION_DATES=validation[:1]),
                        dict(RUN_STAGE='pilot', EVALUATION_DATES=final)]:
            with self.subTest(altered=altered), self.assertRaises(RuntimeError):
                exec(code, {**deepcopy(scope), **altered})
        freeze_guard = ast.parse(cells['research-047']).body[0]
        with self.assertRaisesRegex(RuntimeError, 'protocol freezing is disabled'):
            exec(compile(ast.Module(body=[freeze_guard], type_ignores=[]), '<M6 freeze guard>', 'exec'),
                 {'READY_TO_FREEZE': True})
        self.assertNotIn('NOTEBOOK_BUNDLE_SHA256', cells['research-033'])
        self.assertNotIn('protocol_freeze_v2.json', '\n'.join(cells.values()))

    def test_independent_export_reconciliation_detects_corruption(self):
        reconcile = reconciler()
        trades, daily, cash = [], [], []
        for policy, path in SCENARIOS:
            common = dict(date='2023-01-02', accounting='independent', segment=0, policy=policy, path=path)
            # Effective exit 99.95 already includes 5 bp slippage: net P&L is -0.125.
            trades.append(dict(**common, status='RESOLVED', episode_id='synthetic',
                               notional=100, entry_price=100, exit_price=99.95,
                               entry_fee=.0375, exit_fee=.0375, net_pnl=-.125))
            daily.append(dict(**common, status='EVALUABLE', net_pnl=-.125,
                              opening_cash=1000, closing_cash=999.875))
            cash.extend([dict(**common, event='ENTRY', cash_delta=-100.0375),
                         dict(**common, event='EXIT', cash_delta=99.9125)])
        baseline = dict(trades=trades, daily=daily, cash_events=cash)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            def check(tables):
                write_records(folder, tables)
                return reconcile(folder)
            passed = check(baseline)
            self.assertEqual(passed['status'], 'PASS')
            self.assertEqual(passed['matched_six_account_days'], 1)
            self.assertEqual(passed['resolved_trade_rows'], 6)
            bad = deepcopy(baseline)
            bad['trades'][0]['net_pnl'] -= .05
            with self.assertRaisesRegex(AssertionError, 'does not reconcile'):
                check(bad)
            bad = deepcopy(baseline)
            bad['cash_events'][0]['cash_delta'] += 1
            with self.assertRaisesRegex(AssertionError, 'does not reconcile'):
                check(bad)
            bad = deepcopy(baseline)
            bad['trades'][0]['episode_id'] = 'different_episode'
            with self.assertRaisesRegex(AssertionError, 'same episodes'):
                check(bad)
            bad = deepcopy(baseline)
            bad['trades'].append(deepcopy(bad['trades'][0]))
            with self.assertRaisesRegex(AssertionError, 'Duplicate resolved episode'):
                check(bad)
            # A genuine no-trade evaluable day still has six matched empty episode sets.
            for row in daily:
                row.update(net_pnl=0, closing_cash=1000)
            for name in ('trades', 'cash_events'):
                (folder / (name + '.csv')).write_text('\n', encoding='utf-8')
            with (folder / 'daily.csv').open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(daily[0]))
                writer.writeheader(); writer.writerows(daily)
            empty = reconcile(folder)
            self.assertEqual(empty['resolved_trade_rows'], 0)
            self.assertEqual(empty['matched_six_account_days'], 1)

    def test_funded_days_segments_and_session_reset_accounts_stay_separate(self):
        trades, daily, cash = [], [], []
        # Synthetic funded carry, then a separately identified new segment; no paths are pooled.
        accounts = [('2023-01-02', 'funded', 1, 1000., 101.),
                    ('2023-01-03', 'funded', 1, 1000.8, 99.),
                    ('2023-01-04', 'funded', 2, 1000., 102.),
                    ('2023-01-02', 'independent', 0, 1000., 101.)]
        for day, accounting, segment, opening, exit_price in accounts:
            pnl = exit_price - 100 - .2
            for policy, path in SCENARIOS:
                key = dict(date=day, accounting=accounting, segment=segment, policy=policy, path=path)
                trades.append(dict(**key, status='RESOLVED', episode_id='synthetic', notional=100,
                    entry_price=100, exit_price=exit_price, entry_fee=.1, exit_fee=.1, net_pnl=pnl))
                daily.append(dict(**key, status='EVALUABLE', net_pnl=pnl,
                    opening_cash=opening, closing_cash=opening + pnl))
                cash.extend([dict(**key, cash_delta=-100.1), dict(**key, cash_delta=exit_price - .1)])
        tables = dict(trades=trades, daily=daily, cash_events=cash)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            write_records(folder, tables)
            result = reconciler()(folder)
            self.assertEqual(result['evaluated_account_days'], 24)
            self.assertEqual(result['matched_six_account_days'], 4)
            # Offsetting daily errors must not cancel across days or segments.
            daily[6]['net_pnl'] += 1
            daily[12]['net_pnl'] -= 1
            write_records(folder, tables)
            with self.assertRaisesRegex(AssertionError, 'does not reconcile'):
                reconciler()(folder)

    def test_incomplete_days_remain_unknown_but_resolved_trades_are_checked(self):
        trades, daily, cash = [], [], []
        for accounting, status in [('funded', 'UNKNOWN_EQUITY'),
                                   ('independent', 'INCOMPLETE_CANDIDATE_COVERAGE')]:
            for policy, path in SCENARIOS:
                key = dict(date='2023-01-02', accounting=accounting, segment=0, policy=policy, path=path)
                trades.append(dict(**key, status='RESOLVED', episode_id='closed', notional=100,
                    entry_price=100, exit_price=101, entry_fee=.1, exit_fee=.1, net_pnl=.8))
                daily.append(dict(**key, status=status, net_pnl=None, opening_cash=1000, closing_cash=None))
                cash.extend([dict(**key, cash_delta=-100.1), dict(**key, cash_delta=100.9)])
                if accounting == 'funded':
                    trades.append(dict(**key, status='UNRESOLVED', episode_id='open', notional=100,
                        entry_price=100, exit_price=None, entry_fee=.1, exit_fee=None, net_pnl=None))
                    cash.append(dict(**key, cash_delta=-100.1))
        tables = dict(trades=trades, daily=daily, cash_events=cash)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            write_records(folder, tables)
            before = (folder / 'daily.csv').read_bytes()
            result = reconciler()(folder)
            self.assertEqual(result['resolved_trade_rows'], 12)
            self.assertEqual(result['evaluated_account_days'], 0)
            self.assertEqual(result['matched_six_account_days'], 0)
            self.assertEqual((folder / 'daily.csv').read_bytes(), before)
            trades[0]['net_pnl'] += 1
            write_records(folder, tables)
            with self.assertRaisesRegex(AssertionError, 'does not reconcile'):
                reconciler()(folder)


if __name__ == '__main__':
    unittest.main()
