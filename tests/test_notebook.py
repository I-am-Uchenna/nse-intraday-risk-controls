"""Check the deliverable's actual visible core, without scientific plotting packages."""
import ast
import contextlib
import io
import json
from pathlib import Path
import unittest

NOTEBOOK = Path(__file__).resolve().parents[1] / 'NSE_Intraday_Research.ipynb'


class ResearchNotebookTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
