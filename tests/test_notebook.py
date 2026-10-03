"""Check the deliverable's actual visible core, without scientific plotting packages."""
import ast
import contextlib
from copy import deepcopy
from datetime import date
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

NOTEBOOK = Path(__file__).resolve().parents[1] / 'NSE_Intraday_Research.ipynb'


class ResearchNotebookTests(unittest.TestCase):
    def test_interval_direction_never_becomes_confirmatory_evidence(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        source = next(c['source'] for c in notebook['cells'] if c['id'] == 'research-045')
        tree = ast.parse(''.join(source))
        loop = next(n for n in tree.body if isinstance(n, ast.For))
        index = next(i for i, n in enumerate(loop.body)
                     if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                     and n.targets[0].id == 'line')
        # Execute the delivered introduction and interval-interpretation branch, without market data or pandas.
        wording = compile(ast.Module(body=[tree.body[0], *loop.body[index:]], type_ignores=[]),
                          '<notebook interval interpretation>', 'exec')
        for stage in ['development', 'final']:
            for lower, upper, direction in [(1., 2., 'above zero'), (-2., -1., 'below zero'),
                                            (-1., 1., 'contains zero'), (0., 1., 'contains zero'),
                                            (-1., 0., 'contains zero'),
                                            (float('nan'), float('nan'), 'unavailable')]:
                with self.subTest(stage=stage, interval=(lower, upper)):
                    scope = dict(RUN_STAGE=stage, CFG={'start_date': '2021-01-01', 'end_date': '2023-12-29'},
                                 label='start', pd=SimpleNamespace(isna=lambda x: x != x),
                                 row=SimpleNamespace(mean_difference_bp=.1, n_days=100,
                                                     lower_bp=lower, upper_bp=upper))
                    exec(wording, scope)
                    text = '\n'.join(scope['conclusion_lines'])
                    self.assertIn(direction, text)
                    self.assertIn('All nominal bootstrap intervals are exploratory', text)
                    self.assertIn('They do not establish a confirmatory effect or superiority.', text)
                    self.assertIn('before final-test outcomes are accessed', text)
                    if direction != 'unavailable':
                        self.assertIn('exploratory nominal 95% interval', text)

    def test_freeze_rejects_rebound_settings_and_calendar(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        source = next(c['source'] for c in notebook['cells'] if 'export' in c['metadata'].get('tags', []))
        freeze = next(n for n in ast.parse(''.join(source)).body
                      if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == 'READY_TO_FREEZE')
        index = next(i for i, n in enumerate(freeze.body)
                     if isinstance(n, ast.Assign) and n.targets[0].id == 'current_settings')
        guard = compile(ast.Module(body=freeze.body[index:index+2], type_ignores=[]), '<freeze guard>', 'exec')
        days = [date(2021, 1, 4), date(2021, 1, 5)]
        scope = dict(CFG={'threshold': -2}, SETTINGS=[{'cost': 15}], INFERENCE={'seed': 17838},
                     DIAGNOSTIC_SPEC={'replications': 200}, CALENDAR=days,
                     PARTITIONS={'validation': days}, EVALUATION_DATES=days)
        scope['SCIENCE_PAYLOAD'] = dict(configuration=deepcopy(scope['CFG']), settings=deepcopy(scope['SETTINGS']),
            inference=deepcopy(scope['INFERENCE']), bootstrap_diagnostic=deepcopy(scope['DIAGNOSTIC_SPEC']),
            calendar=[d.isoformat() for d in days],
            splits=[dict(stage='validation',start=str(days[0]),end=str(days[-1]),scheduled_sessions='2')])
        exec(guard, deepcopy(scope))
        for key, value in [('CFG', {'threshold': -1}), ('SETTINGS', [{'cost': 5}]),
                           ('INFERENCE', {'seed': 1}), ('DIAGNOSTIC_SPEC', {'replications': 10}),
                           ('CALENDAR', days[:1]), ('PARTITIONS', {'validation': days[:1]}),
                           ('EVALUATION_DATES', days[:1])]:
            altered = deepcopy(scope)
            altered[key] = value
            with self.subTest(rebound=key), self.assertRaisesRegex(RuntimeError, 'differ from the executed protocol'):
                exec(guard, altered)

    def test_visible_core_and_synthetic_failure_cases(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        namespace = {'__name__': '__main__'}
        core_count = 0
        with contextlib.redirect_stdout(io.StringIO()):
            for cell in notebook['cells']:
                if cell['cell_type'] != 'code':
                    continue
                source = ''.join(cell['source'])
                ast.parse(source)
                self.assertNotIn('from path_robust', source)
                self.assertNotIn("'git', 'clone'", source)
                self.assertNotIn('scripts/run_pilot.py', source)
                if 'research-core' in cell['metadata'].get('tags', []):
                    exec(compile(source, str(NOTEBOOK), 'exec'), namespace)
                    core_count += 1
        self.assertEqual(core_count, 5)
        self.assertTrue(callable(namespace['run_research']))
        self.assertTrue(callable(namespace['run_notebook_method_checks']))

    def test_vendor_date_formats_and_preserved_failed_ingestion_retry(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
        namespace = {'__name__': '__main__'}
        for cell in notebook['cells']:
            source = ''.join(cell.get('source', []))
            if cell['cell_type'] == 'code' and ('def vendor_rows(' in source or 'def build_database(' in source):
                exec(compile(source, str(NOTEBOOK), 'exec'), namespace)
        parse, build = namespace['vendor_rows'], namespace['build_database']
        header = '<ticker>,<date>,<time>,<open>,<high>,<low>,<close>,<volume>\n'

        def row(day, clock='09:15:00'):
            return f'SYNTHETIC,{day},{clock},100,101,99,100.5,250\n'

        for day, expected in [('08/09/2023', '2023-08-09'), ('09-08-2023', '2023-08-09'),
                              ('08-09-2023', '2023-09-08')]:
            with self.subTest(date=day):
                self.assertEqual(list(parse(io.StringIO(header + row(day)), 'SYNTHETIC'))[0][0],
                                 expected + 'T09:15:00')
        for day, clock in [('31-02-2023', '09:15:00'), ('2023-08-09', '09:15:00'),
                           ('09-08-2023', '24:00:00'), ('09-08-2023', '09:15:01')]:
            with self.subTest(date=day, time=clock), self.assertRaises(ValueError):
                list(parse(io.StringIO(header + row(day, clock)), 'SYNTHETIC'))
        with self.assertRaises(ValueError):
            list(parse(io.StringIO(header + row('08/09/2023') + row('09-08-2023')), 'SYNTHETIC'))

        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            july, august = root / 'july.csv', root / 'august.csv'
            july.write_text(header + row('07/31/2023'), encoding='utf-8')
            august.write_text(header + row('09-08-2023') + row('09-08-2023', '09:16:01'), encoding='utf-8')
            plan = [dict(kind='csv', path=path, month=month, symbols=['SYNTHETIC'])
                    for path, month in [(july, '2023-07'), (august, '2023-08')]]
            cfg = dict(start_date='2023-07-01', end_date='2023-08-31')
            work = root / 'work'
            with self.assertRaises(ValueError):
                build(plan, cfg, work)
            failed_databases = list(work.rglob('bars.sqlite'))
            self.assertEqual(len(failed_databases), 1)
            partial = failed_databases[0]
            original_bytes = partial.read_bytes()
            with contextlib.closing(sqlite3.connect(partial.resolve().as_uri() + '?mode=ro', uri=True)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM bars').fetchone()[0], 1)
            august.write_text(header + row('09-08-2023') + row('09-08-2023', '09:16:00'), encoding='utf-8')
            database, audit = build(plan, cfg, work)
            self.assertNotEqual(database, partial)
            self.assertEqual(partial.read_bytes(), original_bytes)
            self.assertEqual(len(list(work.rglob('bars.sqlite'))), 2)
            self.assertEqual(len(audit['input_files']), 2)
            with contextlib.closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as con:
                self.assertEqual(con.execute('SELECT stamp FROM bars ORDER BY stamp').fetchall(),
                                 [('2023-07-31T09:15:00',), ('2023-08-09T09:15:00',), ('2023-08-09T09:16:00',)])

            # A copied August row inside September is verified, never relabelled as September 22.
            september = root / 'september.csv'
            august.write_text(header + row('22-08-2023'), encoding='utf-8')
            september.write_text(header + row('21-09-2023') + row('22-08-2023') + row('25-09-2023'),
                                 encoding='utf-8')
            plan = [dict(kind='csv', path=path, month=month, symbols=['SYNTHETIC'])
                    for path, month in [(august, '2023-08'), (september, '2023-09')]]
            cfg = dict(start_date='2023-08-01', end_date='2023-09-30')
            database, audit = build(plan, cfg, work)
            september_audit = audit['input_files'][1]
            self.assertEqual((september_audit['rows'], september_audit['retained_rows'],
                              september_audit['excluded_exact_out_of_month_duplicates'],
                              september_audit['outside_requested_dates']), (3, 2, 1, 0))
            self.assertEqual((september_audit['first_label'], september_audit['last_label']),
                             ('2023-09-21T09:15:00', '2023-09-25T09:15:00'))
            with contextlib.closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as con:
                self.assertEqual(con.execute('SELECT stamp FROM bars ORDER BY stamp').fetchall(),
                                 [('2023-08-22T09:15:00',), ('2023-09-21T09:15:00',),
                                  ('2023-09-25T09:15:00',)])
                self.assertEqual(con.execute("SELECT COUNT(*) FROM bars WHERE stamp LIKE '2023-09-22%'")
                                 .fetchone()[0], 0)
            for copied_row in [row('22-08-2023').replace(',250\n', ',251\n'), row('23-08-2023')]:
                with self.subTest(out_of_month_row=copied_row):
                    september.write_text(header + row('21-09-2023') + copied_row, encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, 'Unmatched/conflicting out-of-month row'):
                        build(plan, cfg, work)
            september.write_text(header + row('25-09-2023') + row('22-08-2023') + row('21-09-2023'),
                                 encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate or out-of-order timestamp'):
                build(plan, cfg, work)


if __name__ == '__main__':
    unittest.main()
