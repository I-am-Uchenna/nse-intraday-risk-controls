"""Synthetic checks of the declared 23 June 2023 source amendment.

Builds a small SQLite database and fake archive members in memory; never
opens instructor market data and never evaluates any strategy outcome.
"""
import ast
import csv
import hashlib
import io
import json
import math
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from path_robust.paths import NOTEBOOK

DAY = '2023-06-23'
STOCKS = ['RELIANCE', 'HDFCBANK', 'INFY', 'TCS', 'ITC']
CFG = dict(start_date='2021-01-01', end_date='2023-12-31', universe=STOCKS, index_symbol='.NSEI',
           normal_session_open='09:15', normal_session_close='15:30')
GAP = (datetime(2023, 6, 23, 14, 16), datetime(2023, 6, 23, 14, 57))


def amendment_scope():
    """Execute only the amendment definitions from the notebook cell research-011."""
    cells = {c['id']: ''.join(c['source']) for c in json.loads(NOTEBOOK['M7'].read_text(encoding='utf-8'))['cells']}
    tree = ast.parse(cells['research-011'])
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef)
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'SOURCE_AMENDMENTS')]
    import calendar
    scope = dict(calendar=calendar, csv=csv, re=re, math=math, hashlib=hashlib, shutil=shutil, sqlite3=sqlite3, tempfile=tempfile,
                 Path=Path, datetime=datetime, timedelta=timedelta, closing=closing)
    exec(compile(ast.Module(body=keep, type_ignores=[]), '<M7 source amendment>', 'exec'), scope)
    return scope


def minutes(start='09:15', end='15:30'):
    t = datetime.strptime(f'{DAY} {start}', '%Y-%m-%d %H:%M')
    stop = datetime.strptime(f'{DAY} {end}', '%Y-%m-%d %H:%M')
    while t < stop:
        yield t
        t += timedelta(minutes=1)


def supplement_text(price_shift=0.0, drop=None, other_date=False, preopen_rows=1):
    lines = []
    for k in range(preopen_rows):
        lines.append(f'20230623,09:0{7 + k},100.00,100.00,100.00,100.00,500,0')
    for t in minutes():
        if drop and t == drop:
            continue
        day = '20230624' if other_date and t.hour == 12 else '20230623'
        p = 100 + price_shift
        lines.append(f'{day},{t:%H:%M},{p:.2f},{p + 1:.2f},{p - 1:.2f},{p:.2f},1000,0')
    return '\n'.join(lines) + '\n'


class Harness:
    """Temporary database, fake archive file and in-memory archive members."""

    def __init__(self, members):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'cash').mkdir()
        (root / 'cash' / 'Cash - June 2023- Missing Data.7z').write_bytes(b'synthetic archive')
        self.roots, self.work = [root / 'cash'], root / 'work'
        self.work.mkdir()
        self.db = root / 'bars.sqlite'
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('CREATE TABLE bars(symbol TEXT, stamp TEXT, o REAL,h REAL,l REAL,c REAL,volume REAL,'
                        'source_id INTEGER,PRIMARY KEY(symbol,stamp)) WITHOUT ROWID')
            for s in STOCKS:
                for t in minutes():
                    if GAP[0] <= t <= GAP[1]:
                        continue
                    o, v = (100.0, 1500.0) if t.strftime('%H:%M') == '09:15' else (100.0, 1000.0)
                    if t.strftime('%H:%M') == '14:15':
                        v = 50.0  # partial bar cut off by the outage
                    con.execute('INSERT INTO bars VALUES(?,?,?,?,?,?,?,1)', (s, t.isoformat(), o, 101.0, 99.0, 100.0, v))
                con.execute('INSERT INTO bars VALUES(?,?,?,?,?,?,?,1)', (s, '2023-06-22T10:00:00', 1, 1, 1, 1, 1))
            for t in minutes():
                con.execute('INSERT INTO bars VALUES(?,?,?,?,?,?,?,2)', ('.NSEI', t.isoformat(), 1, 1, 1, 1, 0))
            con.commit()
        self.members = members
        self.scope = amendment_scope()
        self.scope['file_hash'] = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        self.scope['archive_members'] = lambda path: list(self.members)
        self.scope['member_named'] = lambda names, base: next(n for n in names if n.rsplit('/', 1)[-1] == base)

        @contextmanager
        def archive_lines(path, member=None):
            yield io.StringIO(self.members[member])
        self.scope['archive_lines'] = archive_lines

    def run(self, cfg=CFG):
        return self.scope['apply_source_amendments'](self.db, self.roots, cfg, self.work, self.scope['SOURCE_AMENDMENTS'])

    def rows(self, symbol, day=DAY):
        with closing(sqlite3.connect(self.db)) as con:
            return con.execute('SELECT stamp,o,h,l,c,volume,source_id FROM bars WHERE symbol=? AND substr(stamp,1,10)=? '
                               'ORDER BY stamp', (symbol, day)).fetchall()

    def close(self):
        self.tmp.cleanup()


def members(**overrides):
    base = {f'Cash - June 2023- Missing Data/{s}.csv': supplement_text() for s in STOCKS}
    for s, text in overrides.items():
        base[f'Cash - June 2023- Missing Data/{s}.csv'] = text
    return base


class SourceAmendmentTests(unittest.TestCase):
    def test_declaration_is_single_dated_and_bounded(self):
        (a,) = amendment_scope()['SOURCE_AMENDMENTS']
        self.assertEqual((a['amendment_id'], a['trade_date']), ('M7-A1-2023-06-23', DAY))
        self.assertEqual((a['min_identical_share'], a['max_shared_price_gap_bp']), (0.95, 50.0))

    def test_merge_prune_and_audit(self):
        h = Harness(members())
        try:
            (audit,) = h.run()
            self.assertEqual(audit['status'], 'applied')
            self.assertEqual(audit['index_session_minutes_missing'], 0)
            for record in audit['symbols']:
                self.assertEqual(record['session_minutes_missing_before'], 42)
                self.assertEqual(record['session_minutes_filled'], 42)
                self.assertEqual(record['supplement_rows_inserted'], 375)
                self.assertEqual(record['shared_session_minutes'], 333)
                self.assertGreaterEqual(record['identical_shared_minutes'], 331)
            day = h.rows('RELIANCE')
            self.assertEqual(len(day), 375)
            self.assertTrue(all(r[6] == 3 for r in day))  # every bar now from the amendment source
            first = day[0]
            self.assertEqual(first[0], '2023-06-23T09:15:00')
            self.assertEqual(first[1:6], (100.0, 101.0, 99.0, 100.0, 1500.0))  # pre-open folded in
            self.assertEqual(len(h.rows('RELIANCE', '2023-06-22')), 1)         # other dates untouched
            self.assertEqual(len(h.rows('.NSEI')), 375)                        # index untouched
        finally:
            h.close()

    def test_outside_requested_dates_changes_nothing(self):
        h = Harness(members())
        try:
            (audit,) = h.run(dict(CFG, end_date='2023-05-25'))
            self.assertEqual(audit['status'], 'outside requested dates')
            self.assertEqual(len(h.rows('RELIANCE')), 333)
        finally:
            h.close()

    def test_refusals(self):
        cases = [
            (members(TCS=supplement_text(drop=datetime(2023, 6, 23, 11, 0))), 'full session'),
            (members(INFY=supplement_text(other_date=True)), 'Unexpected date'),
            (members(ITC=supplement_text(price_shift=1.0)), 'too few shared minutes'),
            (members(HDFCBANK=supplement_text(preopen_rows=2)), 'pre-open'),
        ]
        for case, message in cases:
            h = Harness(case)
            try:
                with self.assertRaisesRegex(ValueError, message):
                    h.run()
            finally:
                h.close()

    def test_price_gap_limit(self):
        text = supplement_text().replace('20230623,10:00,100.00,101.00,99.00,100.00',
                                         '20230623,10:00,100.00,101.00,99.00,100.60')
        h = Harness(members(RELIANCE=text))
        try:
            with self.assertRaisesRegex(ValueError, 'price gap'):
                h.run()
        finally:
            h.close()

    def test_missing_archive_and_bad_rows(self):
        h = Harness(members())
        try:
            (h.roots[0] / 'Cash - June 2023- Missing Data.7z').unlink()
            with self.assertRaises(FileNotFoundError):
                h.run()
        finally:
            h.close()
        parse = amendment_scope()['supplement_rows']
        for bad in ('20230623,09:15,100,99,101,100,1,0\n',                 # high below low
                    '20230623,09:16,100,101,99,100,1,0\n20230623,09:15,100,101,99,100,1,0\n',  # out of order
                    '20230623,09:15,100,101,99,100,1\n'):                  # wrong field count
            with self.assertRaises(ValueError):
                parse(io.StringIO(bad), 'TEST', DAY)


class SourceCheckDisplayTests(unittest.TestCase):
    def test_grid_marks_sources_missing_months_and_supplement_use(self):
        scope = amendment_scope()
        scope['month_keys'] = lambda a, b: [f'{y}-{m:02d}' for y in (2023,) for m in range(1, 13)]
        cfg = dict(CFG, start_date='2023-01-01')
        plan = [dict(kind='rar', month=f'2023-{m:02d}', symbols=STOCKS) for m in range(1, 13) if m != 3]
        plan += [dict(kind='year', month=f'2023-{m:02d}', symbols=['.NSEI']) for m in range(1, 13)]
        text = scope['source_status_markdown'](plan, ['Cash Data March 2023.rar or extracted CSVs'],
                                               ['/x/Cash - June 2023- Missing Data.7z'], cfg, scope['SOURCE_AMENDMENTS'])
        self.assertIn('| Stocks | 2023 | RAR | RAR | MISSING |', text)
        self.assertIn('| Index | 2023 | 7z |', text)
        self.assertIn('used by declared amendment M7-A1-2023-06-23', text)
        self.assertIn('1 month(s) MISSING', text)


if __name__ == '__main__':
    unittest.main()
