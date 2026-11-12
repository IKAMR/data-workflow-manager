"""a3.5: file counts reported from completed Siegfried batches only."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest

from app.siegfried_tool_v0111_a3 import identify_siegfried_files, SiegfriedCheck


class RealBatchProgress(unittest.TestCase):
    def test_reports_actual_completed_file_counts_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)
            paths = []
            for k in range(205):
                p = source / f'file-{k:03}.bin'
                p.write_bytes(b'example file')
                paths.append(p)
            total_calls = []
            files_calls = []
            runner_calls = []

            def runner(args, **_kwargs):
                runner_calls.append(list(args))
                input_files = args[4:]
                model = {'files': [{'filename': f, 'matches': [{
                    'id': 'fmt/354', 'format': 'PDF/A', 'version': '1b',
                }]} for f in input_files]}
                return SimpleNamespace(returncode=0, stdout=json.dumps(model), stderr='')

            with patch('app.siegfried_tool_v0111_a3.inspect_siegfried',
                       return_value=SiegfriedCheck(True, 'sf', 'siegfried 1.11.9')):
                result = identify_siegfried_files(
                    'sf', source, paths, runner=runner,
                    progress_cb=lambda done, n: total_calls.append((done, n)),
                    file_progress_cb=lambda done, n: files_calls.append((done, n)),
                )
            self.assertEqual(files_calls, [(100,205), (200,205), (205,205)])
            self.assertEqual(total_calls, [(1,3), (2,3), (3,3)])
            self.assertEqual(result['files_total'], 205)
            self.assertEqual(result['identified'], 205)
            self.assertEqual(len(runner_calls), 3)
            self.assertEqual(paths[0].read_bytes(), b'example file')


if __name__ == '__main__':
    unittest.main()
