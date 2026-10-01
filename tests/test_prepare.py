"""Archive staging uses identical bytes on Windows and mounted Google Drive."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare_pilot.py'
SPEC = importlib.util.spec_from_file_location('pilot_preparation', SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class ArchiveStagingTest(unittest.TestCase):
    def test_direct_and_zip_match_and_ambiguous_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            direct, delivery, cache, other = [root/name for name in ('direct', 'delivery', 'cache', 'other')]
            for folder in (direct, delivery, cache, other):
                folder.mkdir()
            name = 'Cash Data January 2021.rar'
            payload = b'synthetic archive bytes; no instructor data'
            (direct/name).write_bytes(payload)
            with zipfile.ZipFile(delivery/'NSE Cash Data.zip', 'w') as archive:
                archive.writestr('cash/'+name, payload)
            staged, zipped = prepare.stage_outer(delivery, '*.zip', name, cache)
            self.assertEqual(staged.read_bytes(), payload)
            self.assertTrue(zipped['outer_crc_checked'])
            staged, plain = prepare.stage_outer([direct, other], '*.zip', name, cache)
            self.assertEqual(staged.read_bytes(), payload)
            self.assertEqual(plain['nested_archive_sha256'], zipped['nested_archive_sha256'])
            self.assertNotIn('outer_crc_checked', plain)
            with self.assertRaisesRegex(ValueError, 'found 2'):
                prepare.stage_outer([direct, delivery], '*.zip', name, cache)
            (other/name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError, 'found 2'):
                prepare.stage_outer([direct, other], '*.zip', name, cache)


if __name__ == '__main__':
    unittest.main()
