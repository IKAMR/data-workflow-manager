"""v0.2.4-a1 regression: Siegfried invalid JSON must not discard good files."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import ast
import unittest

from noark5_workflow.operations import siegfried_resilient_v024_a1 as rescue


class FakeProcess:
    def __init__(self, stdout: bytes, *, stderr: bytes = b'', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.stdout, self.stderr

    def poll(self):
        return self.returncode


class SiegfriedJsonRecoveryTests(unittest.TestCase):
    def test_invalid_windows_escape_is_not_silently_repaired(self):
        # Backslash followed by 'q' is invalid in JSON. The exact bytes must
        # survive for Work diagnostics; never strip slash characters.
        raw = b'{"files":[{"filename":"C:\\q\\test.pdf","matches":[]}]}'
        with patch.object(rescue.subprocess, 'Popen', return_value=FakeProcess(raw)):
            with self.assertRaises(rescue.BadSiegfriedResponse) as caught:
                rescue._parse_sf('sf.exe', [r'C:\q\test.pdf'])
        self.assertEqual(caught.exception.stdout, raw)
        self.assertIn('JSON', str(caught.exception))

    def test_valid_windows_escaped_path_roundtrips(self):
        path = r'C:\data\folder\my file.pdf'
        raw = json.dumps({'files': [{'filename': path, 'matches': []}]},
                         ensure_ascii=False).encode('utf-8')
        with patch.object(rescue.subprocess, 'Popen', return_value=FakeProcess(raw)):
            actual = rescue._parse_sf('sf.exe', [path])
        self.assertEqual(actual[0]['filename'], path)

    def test_corrupt_file_isolated_and_all_source_paths_counted(self):
        with TemporaryDirectory() as folder:
            paths = [Path(folder) / f'{i:03d}.pdf' for i in range(7)]
            bad = paths[4]
            calls = []
            def fake_sf(_exe, selected, **kwargs):
                calls.append(tuple(selected))
                if str(bad) in selected:
                    raise rescue.BadSiegfriedResponse('Invalid \\escape', b'{bad \\q json}', b'')
                return [{'filename': name, 'matches': [{'id':'fmt/18','format':'PDF'}]}
                        for name in reversed(selected)]
            with patch.object(rescue.base, '_validate_batch_files',
                              side_effect=lambda batch, _root: [str(path) for path, _ in batch]), \
                 patch.object(rescue, '_parse_sf', side_effect=fake_sf):
                rows, diagnostics = rescue._recover_batch([(p, {}) for p in paths], Path(folder), 'sf')
            self.assertEqual([x['filename'] for x in rows], [str(p) for p in paths])
            self.assertEqual(len(rows), len(paths))
            self.assertEqual(sum(x.get('dwm_identification_status') == 'error' for x in rows), 1)
            self.assertEqual(rows[4]['filename'], str(bad))
            self.assertEqual(rows[4]['matches'], [])
            self.assertIn(rescue.ERROR_CODE, rows[4]['errors'])
            self.assertTrue(any(entry.stdout == b'{bad \\q json}' for entry in diagnostics))
            self.assertGreater(len(calls), 2)

    def test_unrecoverable_program_error_must_not_be_marked_as_a_file_error(self):
        paths = [(Path('a.pdf'), {})]
        with patch.object(rescue.base, '_validate_batch_files', return_value=['a.pdf']), \
             patch.object(rescue, '_parse_sf', side_effect=RuntimeError('sf.exe could not start')):
            with self.assertRaisesRegex(RuntimeError, 'could not start'):
                rescue._recover_batch(paths, Path('.'), 'sf')

    def test_abort_does_not_become_fake_json_failure(self):
        with self.assertRaises(InterruptedError):
            rescue._recover_batch([(Path('a.pdf'), {})], Path('.'), 'sf', cancelled_cb=lambda: True)

    def test_raw_response_diagnostics_and_sha_are_preserved(self):
        with TemporaryDirectory() as folder:
            stage = Path(folder)
            raw = b'{"files": ["C:\\bad\\foo"]} \x00'
            problems = [rescue.RawProblem(('C:\\source\\x',), 'Invalid escape', raw, b'warning', 1)]
            rescue._persist_diagnostics(stage, problems, start_index=37900)
            entries = [json.loads(s) for s in (stage/'diagnostics'/'index.jsonl').read_text().splitlines()]
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry['batch_offset'], 37900)
            self.assertEqual(entry['stdout_sha256'], sha256(raw).hexdigest())
            self.assertEqual((stage/'diagnostics'/entry['stdout_file']).read_bytes(), raw)

    def test_failure_count_is_distinct_from_unidentified_count(self):
        with TemporaryDirectory() as folder:
            p = Path(folder) / 'raw.jsonl'
            p.write_text('\n'.join([
                json.dumps({'filename': 'a', 'matches': []}),
                json.dumps({'filename': 'b', 'matches': [], 'dwm_identification_status': 'error'}),
                json.dumps({'filename': 'c', 'matches': [{'id': 'fmt/18'}]})
            ])+'\n', encoding='utf-8')
            self.assertEqual(rescue._failure_count(p), 1)

    def test_parallel_invalid_json_keeps_inventory_order_without_duplicates(self):
        # Reproduce the reporter's two-process mode with a corrupt response
        # in the second of three batches (100 + 100 + 5).
        with TemporaryDirectory() as root:
            source = Path(root) / 'source'
            docs = source / 'dokument'
            docs.mkdir(parents=True)
            work = Path(root) / 'work'
            work.mkdir()
            for i in range(205):
                (docs / f'{i:03d}.pdf').write_bytes(b'PDF')
            exe = Path(root) / 'sf.exe'
            exe.write_bytes(b'test')
            def fake_sf(_exe, files, **kwargs):
                if any(Path(f).name == '105.pdf' for f in files):
                    raise rescue.BadSiegfriedResponse('invalid escape', b'\\bad', b'')
                return [{'filename': p, 'matches': [{'id': 'fmt/18'}]}
                        for p in reversed(files)]
            with patch.object(rescue, '_parse_sf', side_effect=fake_sf):
                result = rescue.scan_document_tree(
                    source=source, work=work, executable=str(exe),
                    version='test', signature='sig', job_id='JOB-002', workers=2)
            records = [json.loads(row) for row in
                       (result['target']/'siegfried_files.jsonl').read_text().splitlines()]
            # Windows can spell the Temp path as an 8.3 alias (TORBJO~1.AAS)
            # while the scanner records resolved long paths. Resolve both
            # identities; still demand exact inventory order and uniqueness.
            expected = [str((docs / f'{i:03d}.pdf').resolve(strict=True))
                        for i in range(205)]
            observed = [str(Path(row['filename']).resolve(strict=True))
                        for row in records]
            self.assertEqual(observed, expected)
            self.assertEqual(len(set(observed)), len(expected))
            self.assertEqual(result['model']['files_total'], 205)
            self.assertEqual(result['model']['identified'], 204)
            self.assertEqual(result['model']['files_failed'], 1)
            self.assertGreater(result['model']['json_response_errors'], 0)
            self.assertEqual(records[105]['dwm_identification_status'], 'error')

    def test_checkpoint_resume_after_unrelated_fatal_failure(self):
        # One healthy batch is durable before the next sf call fails with a
        # genuine tool error. A later invocation must resume, not duplicate.
        with TemporaryDirectory() as root:
            work = Path(root) / 'work'
            source = Path(root) / 'source'
            documents = source / 'DOKUMENT'
            documents.mkdir(parents=True)
            work.mkdir()
            for i in range(105):
                (documents / f'{i:03d}.pdf').write_bytes(b'%PDF')
            executable = Path(root) / 'sf.exe'
            executable.write_bytes(b'fake executable')
            first_calls = []
            def first(_program, files, **kwargs):
                first_calls.extend(files)
                if any(Path(f).name == '104.pdf' for f in files):
                    raise RuntimeError('test: sf crash after durable checkpoint')
                return [{'filename': f, 'matches': [{'id': 'fmt/18'}]} for f in files]
            with patch.object(rescue, '_parse_sf', side_effect=first):
                with self.assertRaisesRegex(RuntimeError, 'sf crash'):
                    rescue.scan_document_tree(source=source, work=work, executable=str(executable),
                        version='test', signature='sig', job_id='JOB-001', workers=1)
            partials = list((work / 'external_evidence' / 'siegfried').glob('.partial-*'))
            self.assertEqual(len(partials), 1)
            checkpoint = json.loads((partials[0]/'checkpoint.json').read_text())
            self.assertGreater(checkpoint['files_processed'], 0)
            later_calls = []
            def second(_program, files, **kwargs):
                later_calls.extend(files)
                return [{'filename': f, 'matches': [{'id':'fmt/18'}]} for f in files]
            with patch.object(rescue, '_parse_sf', side_effect=second):
                result = rescue.scan_document_tree(source=source, work=work, executable=str(executable),
                    version='test', signature='sig', job_id='JOB-001', workers=1)
            self.assertTrue(result['resumed'])
            self.assertEqual(result['model']['files_total'], 105)
            self.assertEqual(result['model']['identified'], 105)
            self.assertEqual(len(later_calls), 105 - checkpoint['files_processed'])
            all_rows = [json.loads(line) for line in
                        (result['target']/'siegfried_files.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len({row['filename'] for row in all_rows}), 105)

    def test_scanner_is_a_separate_adapter_not_a_monkeypatch(self):
        p = Path(__file__).resolve().parents[1] / 'noark5_workflow' / 'operations' / 'siegfried_resilient_v024_a1.py'
        doc = ast.parse(p.read_text(encoding='utf-8'))
        self.assertIn('scan_document_tree', [n.name for n in doc.body if isinstance(n, ast.FunctionDef)])
        self.assertNotIn('base._run_sf_batch =', p.read_text(encoding='utf-8'))

    def test_scan_keeps_complete_evidence_when_one_file_fails(self):
        with TemporaryDirectory() as root:
            work = Path(root) / 'work'
            source = Path(root) / 'source'
            documents = source / 'dokument'
            documents.mkdir(parents=True)
            work.mkdir()
            for name in ('ok1.pdf', 'bad.pdf', 'ok2.pdf'):
                (documents / name).write_bytes(b'x')
            executable = Path(root) / 'sf.exe'
            executable.write_bytes(b'fake executable')
            def fake_sf(_executable, paths, **kwargs):
                if any(Path(p).name == 'bad.pdf' for p in paths):
                    raise rescue.BadSiegfriedResponse('Invalid \\escape', b'{"files": ["\\q"]}', b'')
                return [{'filename': p, 'matches': [{'id': 'fmt/18', 'format': 'PDF'}]}
                        for p in reversed(paths)]
            with patch.object(rescue, '_parse_sf', side_effect=fake_sf):
                result = rescue.scan_document_tree(
                    source=source, work=work, executable=str(executable),
                    version='test-1', signature='test-signature',
                    job_id='JOB-001', workers=2)
            model = result['model']
            self.assertEqual(model['files_total'], 3)
            self.assertEqual(model['identified'], 2)
            self.assertEqual(model['files_failed'], 1)
            self.assertGreater(model['json_response_errors'], 0)
            self.assertEqual(model['unidentified'], 0)
            self.assertEqual(model['identification_status'], 'complete_with_file_errors')
            destination = result['target']
            manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['files_failed'], 1)
            self.assertEqual(manifest['json_response_errors'], model['json_response_errors'])
            self.assertIn('diagnostics_index', manifest)
            raw = (destination / 'siegfried_files.jsonl').read_bytes()
            self.assertEqual(manifest['raw_sha256'], sha256(raw).hexdigest())
            lines = [json.loads(v) for v in raw.splitlines()]
            self.assertEqual(len(lines), 3)
            self.assertEqual(sum('error' == row.get('dwm_identification_status') for row in lines), 1)
            self.assertFalse(any(p.name.startswith('.partial-') for p in destination.parent.iterdir()))


if __name__ == '__main__':
    unittest.main()
