"""Versioned, read-only Siegfried interoperability with SIARD-managed tools."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.siegfried_shared_v0111_a2 import find_siegfried_executable
from app.siegfried_tool_v0111_a3 import (
    SiegfriedCheck, identify_siegfried_files, inspect_siegfried, parse_siegfried_json,
)

ROOT = Path(__file__).resolve().parents[1]
BIN = 'sf.exe' if sys.platform == 'win32' else 'sf'


class ProbeTests(unittest.TestCase):
    def fake_bin(self, root):
        f = Path(root) / BIN
        f.write_bytes(b'fake-sf')
        return f

    def test_successful_version_and_signatures_are_reported(self):
        with tempfile.TemporaryDirectory() as td:
            exe = self.fake_bin(td)
            cmd = []
            def fake_runner(args, **kwargs):
                cmd.append((args,kwargs))
                return SimpleNamespace(returncode=0, stdout='siegfried 1.11.4\nPRONOM signature 1234\n', stderr='')
            result = inspect_siegfried(str(exe), runner=fake_runner, auto_discover=False)
            self.assertTrue(result.ok)
            self.assertIn('1.11.4', result.version)
            self.assertIn('PRONOM signature', result.signature)
            self.assertEqual(cmd[0][0], [str(exe.resolve()), '-version'])
            self.assertTrue(cmd[0][1]['capture_output'])
            self.assertNotIn('shell', cmd[0][1])

    def test_missing_binary_is_not_executed(self):
        run = Mock(side_effect=AssertionError('No execution'))
        result = inspect_siegfried('/definitely/not-a/binary/sf', runner=run, auto_discover=False)
        self.assertFalse(result.ok)
        run.assert_not_called()

    def test_wrong_program_is_rejected_even_if_named_in_settings(self):
        with tempfile.TemporaryDirectory() as td:
            other = Path(td)/'not-sf.exe'
            other.write_text('fake')
            run = Mock()
            result = inspect_siegfried(str(other), runner=run)
            self.assertFalse(result.ok)
            run.assert_not_called()

    def test_success_without_siegfried_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            exe = self.fake_bin(td)
            run = Mock(return_value=SimpleNamespace(returncode=0, stdout='other binary 1.0', stderr=''))
            self.assertFalse(inspect_siegfried(str(exe), runner=run).ok)

    def test_nonzero_exit_remains_failure(self):
        with tempfile.TemporaryDirectory() as td:
            exe = self.fake_bin(td)
            run = Mock(return_value=SimpleNamespace(returncode=2, stdout='', stderr='signature unavailable'))
            status = inspect_siegfried(str(exe), runner=run)
            self.assertFalse(status.ok)
            self.assertIn('signature unavailable', status.message)

    def test_timeout_is_bounded_and_reported(self):
        with tempfile.TemporaryDirectory() as td:
            exe = self.fake_bin(td)
            run = Mock(side_effect=subprocess.TimeoutExpired(['sf','-version'], 2))
            result = inspect_siegfried(str(exe), runner=run)
            self.assertFalse(result.ok)
            self.assertIn('tidsgrensen', result.message)

    def test_explicit_missing_path_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fake_bin(root)
            with patch('app.siegfried_tool_v0111_a3.find_siegfried_executable', return_value=root/BIN) as finder:
                result = inspect_siegfried(str(root/'invalid'/BIN), runner=Mock())
            self.assertFalse(result.ok)
            finder.assert_not_called()

    def test_shared_siard_binary_can_be_detected_without_binary_copy(self):
        with tempfile.TemporaryDirectory() as td:
            shared = Path(td)/'SIARDManager'/'siegfried'
            shared.mkdir(parents=True)
            exe = self.fake_bin(shared)
            found = find_siegfried_executable(shared_root=shared, include_path=False)
            self.assertEqual(found, exe.resolve())
            self.assertEqual(list(shared.iterdir()), [exe])


class JsonFormatTests(unittest.TestCase):
    def test_parse_pronom_and_unknown_without_invented_approval(self):
        payload = {'files': [
            {'filename': 'A.pdf', 'matches': [{'id': 'fmt/354', 'format': 'PDF/A', 'version': '1b'}]},
            {'filename': 'B.pdf', 'matches': [{'id': 'fmt/354', 'format': 'PDF/A', 'version': '1b'}]},
            {'filename': 'C.bin', 'matches': []},
        ]}
        result = parse_siegfried_json(payload)
        self.assertEqual(result['files_total'], 3)
        self.assertEqual(result['identified'], 2)
        self.assertEqual(result['unidentified'], 1)
        self.assertEqual(result['format_groups'][0]['count'], 2)
        self.assertEqual(result['format_groups'][0]['puid'], 'fmt/354')
        self.assertNotIn('valid', json.dumps(result).lower())
        self.assertNotIn('accepted', json.dumps(result).lower())

    def test_multimatches_are_explicit_and_not_double_counted(self):
        result = parse_siegfried_json({'files':[{'filename':'file.bin','matches':[
            {'id':'fmt/101', 'format':'XML'}, {'id':'x-fmt/280', 'format':'XSD'}]}]})
        self.assertEqual(result['files_total'], 1)
        self.assertEqual(result['ambiguous'], 1)
        self.assertEqual(sum(g['count'] for g in result['format_groups']), 1)

    def test_bad_shape_is_rejected(self):
        for payload in ({}, [], {'files': {}}, {'files':[{'filename': 'a','matches':{}}]},
                        {'files':[{'matches':[]}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_siegfried_json(payload)

    def test_x_fmt_is_known_and_unknown_id_is_not(self):
        result = parse_siegfried_json({'files':[{'filename':'schema.xsd','matches':[{'id':'x-fmt/280','format':'XSD'}]},
                                                  {'filename':'blob','matches':[{'id':'UNKNOWN','format':'Unknown'}]}]})
        self.assertEqual(result['identified'], 1)
        self.assertEqual(result['unidentified'], 1)


class ScanTests(unittest.TestCase):
    def test_runs_in_batches_and_does_not_modify_source_or_work(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)/'Source'; root.mkdir()
            exe = self.exe = Path(td)/BIN; exe.write_bytes(b'fake')
            files = []
            for i in range(103):
                f=root/f'f{i:03}.pdf';f.write_bytes(b'%PDF-1.4\n');files.append(f)
            calls = []
            def run(args, **kwargs):
                calls.append(args)
                if args[-1] == '-version':
                    return SimpleNamespace(returncode=0, stdout='siegfried 1.11.4', stderr='')
                return SimpleNamespace(returncode=0, stdout=json.dumps({'files':[
                    {'filename':p,'matches':[{'id':'fmt/18','format':'PDF'}]} for p in args[4:]
                ]}), stderr='')
            report = identify_siegfried_files(exe,root,files,runner=run)
            self.assertEqual([len(c) - 4 for c in calls[1:]], [100,3])
            self.assertEqual(report['files_total'],103)
            self.assertEqual(report['format_groups'][0]['count'],103)
            self.assertTrue(all(f.stat().st_size==9 for f in files))
            self.assertEqual(sorted(x.name for x in Path(td).iterdir()), ['Source',BIN])

    def test_outside_source_rejected_before_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'source';root.mkdir()
            external=Path(td)/'external.pdf';external.write_bytes(b'a')
            exe=Path(td)/BIN;exe.write_bytes(b'fake')
            calls=[]
            def run(args, **kw):
                calls.append(args)
                return SimpleNamespace(returncode=0, stdout='siegfried 1.11', stderr='')
            with self.assertRaises(ValueError):
                identify_siegfried_files(exe,root,[external],runner=run)
            self.assertEqual(len(calls),0)  # Reject unsafe paths before any CLI execution

    def test_binary_failure_does_not_return_partial_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'source';root.mkdir()
            file=root/'a';file.write_bytes(b'a')
            exe=Path(td)/BIN;exe.write_bytes(b'fake')
            def run(args, **kw):
                if '-version' in args:
                    return SimpleNamespace(returncode=0,stdout='siegfried 1.11',stderr='')
                return SimpleNamespace(returncode=3,stdout='',stderr='bad signature')
            with self.assertRaisesRegex(RuntimeError,'bad signature'):
                identify_siegfried_files(exe,root,[file],runner=run)


class SetupContracts(unittest.TestCase):
    def test_setup_includes_shared_cli_without_duplicate_tab(self):
        p=ROOT/'gui_qt'/'setup_format_v0111_a2.py'
        tree=ast.parse(p.read_text('utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DwmSetupDialog')
        methods={n.name for n in cls.body if isinstance(n,ast.FunctionDef)}
        for fn in ('_build_siegfried_tools','_find_siegfried','_browse_siegfried',
                   '_test_siegfried','_read_siegfried_check','_updates'):
            self.assertIn(fn,methods)
        source=p.read_text('utf-8')
        self.assertIn("name == 'Eksterne verktøy'", source)
        self.assertNotIn("_tab('Siegfried')", source)
        self.assertIn("updates['sf_executable']", source)
        self.assertIn("updates['format_assessment_source']", source)
        self.assertNotIn('install_siegfried(', source)

    def test_default_setting_allows_automatic_discovery(self):
        from settings import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG['sf_executable'],'')


if __name__=='__main__':
    unittest.main()
