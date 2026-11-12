"""Run the notebook's publish cell on copies of the recorded M7 validation exports."""
import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from path_robust.paths import NOTEBOOK, RUN

RECORDED = RUN['M7_VALIDATION']
NOT_EXPORTS = {'.gitattributes', 'README.md', 'SHA256SUMS.txt', 'runtime-requirements.txt', 'verification.json'}
RUN_ID = '20261111T081528Z-fzxevfhy'


def publish_cell():
    book = json.loads(NOTEBOOK['M7'].read_text(encoding='utf-8'))
    return next(''.join(c['source']) for c in book['cells'] if c.get('id') == 'm7-publish')


class PublishCellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / 'repo'
        (self.repo / 'results').mkdir(parents=True)
        self.save = base / 'm7_runs'
        self.run = self.save / RUN_ID
        self.run.mkdir(parents=True)
        for path in RECORDED.iterdir():
            if path.name not in NOT_EXPORTS:
                shutil.copy2(path, self.run / path.name)

    def tearDown(self):
        self.tmp.cleanup()

    def execute(self, publish=True, run_id='', repo=True):
        source = publish_cell()
        source = re.sub(r'(?m)^PUBLISH_RUN = .*$', f'PUBLISH_RUN = {publish}', source)
        source = re.sub(r'(?m)^PUBLISH_RUN_ID = .*$', f'PUBLISH_RUN_ID = {run_id!r}', source)
        shown = []
        scope = dict(Path=Path, json=json, csv=csv, io=io, hashlib=hashlib, shutil=shutil, datetime=datetime,
                     pd=pd, SAVE_BASE=self.save, RUN_ID='20261112T000000Z-session',
                     REPO_ROOT=self.repo if repo else None,
                     display=shown.append, Markdown=lambda text: text)
        exec(compile(source, 'm7-publish', 'exec'), scope)
        return scope, shown

    def manifest(self, **changes):
        path = self.run / 'run_manifest.json'
        path.write_text(json.dumps({**json.loads(path.read_text()), **changes}))

    def test_default_lists_runs_and_publishes_nothing(self):
        scope, shown = self.execute(publish=False)
        self.assertEqual([r['run_id'] for r in scope['SAVED_RUNS']], [RUN_ID])
        self.assertEqual(list((self.repo / 'results').iterdir()), [])

    def test_publishes_recorded_validation_byte_for_byte(self):
        self.execute(run_id=RUN_ID)
        target = self.repo / 'results' / 'm7_validation_20261111'
        for path in self.run.iterdir():
            self.assertEqual((target / path.name).read_bytes(), path.read_bytes(), path.name)
        # Same conventions as the folder published by hand on 11 November.
        self.assertEqual((target / '.gitattributes').read_bytes(), (RECORDED / '.gitattributes').read_bytes())
        self.assertEqual((target / 'runtime-requirements.txt').read_text().splitlines()[2:],
                         (RECORDED / 'runtime-requirements.txt').read_text().splitlines()[2:])
        listed = [line.split('  ', 1)[1] for line in (target / 'SHA256SUMS.txt').read_text().splitlines()]
        self.assertEqual(listed, sorted((p.name for p in target.iterdir() if p.name != 'SHA256SUMS.txt'), key=str.lower))
        for line in (target / 'SHA256SUMS.txt').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), digest)
        self.assertIn(RUN_ID, (target / 'README.md').read_text())

    def test_never_overwrites_and_never_publishes_twice(self):
        self.execute(run_id=RUN_ID)
        with self.assertRaisesRegex(RuntimeError, 'already published'):
            self.execute(run_id=RUN_ID)
        other = self.save / '20261111T120000Z-second'
        shutil.copytree(self.run, other)
        manifest = json.loads((other / 'run_manifest.json').read_text())
        (other / 'run_manifest.json').write_text(json.dumps({**manifest, 'run_id': other.name}))
        self.execute(run_id=other.name)
        self.assertTrue((self.repo / 'results' / 'm7_validation_20261111b').is_dir())

    def test_refuses_private_incomplete_or_inconsistent_runs(self):
        (self.run / 'bars.csv').write_text('symbol,open,high,low,close\nA,1,2,0.5,1.5\n')
        (self.run / 'prices.sqlite').write_bytes(b'x')
        (self.run / 'intervals.csv').unlink()
        self.manifest(final_test_evaluated=True)
        with self.assertRaises(RuntimeError) as caught:
            self.execute(run_id=RUN_ID)
        message = str(caught.exception)
        for expected in ('price or trade-level columns', '.sqlite', 'missing export intervals.csv',
                         'final_test_evaluated false'):
            self.assertIn(expected, message)
        self.assertEqual(list((self.repo / 'results').iterdir()), [])

    def test_final_run_needs_its_freeze_and_access_record(self):
        self.manifest(stage='final', final_test_evaluated=True, final_access_record={'approved': True},
                      completed_utc='2026-11-20T10:00:00+00:00')
        with self.assertRaisesRegex(RuntimeError, 'protocol_freeze.json'):
            self.execute(run_id=RUN_ID)
        (self.run / 'protocol_freeze.json').write_text('{}')
        (self.run / 'final_access.json').write_text('{}')
        self.execute(run_id=RUN_ID)
        readme = (self.repo / 'results' / 'm7_final_20261120' / 'README.md').read_text()
        self.assertIn('26 May 2023 to 29 December 2023', readme)

    def test_colab_without_repository_prepares_zip_in_save_folder(self):
        self.execute(run_id=RUN_ID, repo=False)
        prepared = self.save / 'ready_to_publish' / 'm7_validation_20261111'
        self.assertTrue((prepared / 'SHA256SUMS.txt').is_file())
        self.assertTrue(prepared.with_suffix('.zip').is_file())
        scope, _ = self.execute(publish=False)
        self.assertEqual(len(scope['SAVED_RUNS']), 1)  # the prepared folder is not listed as a run

    def test_unknown_run_id(self):
        with self.assertRaisesRegex(FileNotFoundError, 'No completed run'):
            self.execute(run_id='not-a-run')


if __name__ == '__main__':
    unittest.main()
