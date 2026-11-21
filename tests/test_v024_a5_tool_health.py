"""v0.2.4-a5: bounded local program discovery + durable cross-version Setup."""
from __future__ import annotations

import ast
import json
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from threading import RLock
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch
import sys

from app.tool_health_v024_a5 import (
    ToolHealth, check_both_tools, check_one_tool, discover_arkade5,
    discover_siegfried, file_fingerprint, persist_discovered_paths,
    probe_arkade5, probe_siegfried, read_health_cache, user_health_file,
    windows_roots, write_health_cache,
)

ROOT = Path(__file__).resolve().parents[1]


class DiscoveryTests(TestCase):
    def setUp(self):
        self.context = TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)

    def make(self, path):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'fake-CLI')
        return file.resolve()

    def test_windows_program_files_32_64_and_prog_are_considered(self):
        roots = windows_roots({'ProgramFiles': 'Q:/Program Files',
                              'ProgramFiles(x86)': 'Q:/Program Files (x86)',
                              'SystemDrive': 'Q:'}, platform='win32')
        # pathlib.Path on Windows renders Q:/... as Q:\...; these are
        # equivalent paths. Compare Windows-path semantics, not raw strings.
        values = {PureWindowsPath(str(root)) for root in roots}
        for expected in (
            'Q:/Program Files',
            'Q:/Program Files (x86)',
            'Q:/Prog',
            'Q:/Programfiler',
        ):
            with self.subTest(root=expected):
                self.assertIn(PureWindowsPath(expected), values)

    def test_arkade_v2131_under_program_files(self):
        exe = self.make('Program Files/Arkade5CLI-2.13.1/Arkivverket.Arkade.CLI.exe')
        items = discover_arkade5(roots=(self.root / 'Program Files',), env={'PATH': ''})
        self.assertIn(exe, items)

    def test_latest_version_first_if_multiple_distributions(self):
        old = self.make('Program Files/Arkade5CLI-2.12.5/arkade.bat')
        new = self.make('Program Files/Arkade5CLI-2.13.1/arkade.bat')
        found = discover_arkade5(roots=(self.root / 'Program Files',), env={'PATH': ''})
        self.assertEqual(found[:2], (new, old))

    def test_arkade_under_custom_c_prog(self):
        exe = self.make('Prog/Arkade5CLI-2.13.1/arkade.bat')
        items = discover_arkade5(roots=(self.root / 'Prog',), env={'PATH': ''})
        self.assertIn(exe, items)

    def test_arkade_nested_vendor_dir(self):
        exe = self.make('Program Files/Nasjonalarkivet/Arkade5CLI-2.13.1/arkade.bat')
        items = discover_arkade5(roots=(self.root / 'Program Files',), env={'PATH': ''})
        self.assertIn(exe, items)

    def test_siegfried_shared_siard(self):
        exe = self.make('AppData/SIARDManager/siegfried/v1.11.4/sf.exe')
        items = discover_siegfried(roots=(), env={'PATH':'', 'LOCALAPPDATA': str(self.root/'AppData')})
        self.assertIn(exe, items)

    def test_siegfried_under_programfiles(self):
        exe = self.make('Program Files/Siegfried/bin/sf.exe')
        items = discover_siegfried(roots=(self.root/'Program Files',), env={'PATH':''})
        self.assertIn(exe, items)

    def test_siegfried_from_path(self):
        exe = self.make('bin/sf.exe')
        exe.chmod(0o755)
        items = discover_siegfried(roots=(), env={'PATH':str(exe.parent)})
        self.assertIn(exe, items)

    def test_no_unbounded_recursive_scan(self):
        exe = self.make('Program Files/random/a/b/c/Arkivverket.Arkade.CLI.exe')
        found = discover_arkade5(roots=(self.root/'Program Files',), env={'PATH':''})
        self.assertNotIn(exe, found)

    def test_missing_roots_are_harmless(self):
        self.assertEqual(discover_arkade5(roots=(self.root/'missing',), env={'PATH':''}), ())


class HealthAndCacheTests(TestCase):
    def setUp(self):
        self.context = TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        self.exe = self.root / 'Arkivverket.Arkade.CLI.exe'
        self.exe.write_bytes(b'fake')
        self.sf = self.root / 'sf.exe'
        self.sf.write_bytes(b'fake')
        self.cache = self.root/'global/external-tools-v1.json'
        self.cache.parent.mkdir(parents=True, exist_ok=True)

    def fake_arkade_probe(self, path, *, origin=''):
        return ToolHealth('arkade5', 'ok', path, '2.13.1', '', origin,
                          'Arkade 5 svarer', file_fingerprint(path))

    def fake_sf_probe(self, path, *, origin=''):
        return ToolHealth('siegfried', 'ok', path, 'siegfried 1.11.4',
                          'PRONOM v122', origin, 'Siegfried svarer', file_fingerprint(path))

    def test_global_cache_is_outside_repo_and_version_folder(self):
        path = user_health_file({'LOCALAPPDATA':str(self.root/'Local')})
        self.assertEqual(path, self.root/'Local/IKAMR/DataWorkflowManager/external-tools-v1.json')

    def test_global_cache_roundtrip(self):
        original = {'arkade5': self.fake_arkade_probe(str(self.exe)),
                    'siegfried': self.fake_sf_probe(str(self.sf))}
        self.assertTrue(write_health_cache(original, self.cache))
        result = read_health_cache(self.cache)
        self.assertEqual(result['arkade5'].version, '2.13.1')
        self.assertEqual(result['siegfried'].signature, 'PRONOM v122')
        self.assertEqual(result['siegfried'].path, str(self.sf))
        self.assertEqual(json.loads(self.cache.read_text())['schema_version'], 1)

    def test_corrupted_cache_does_not_block_app(self):
        self.cache.write_text('{corrupt', encoding='utf-8')
        self.assertEqual(read_health_cache(self.cache), {})

    def test_wrong_cache_version_is_ignored(self):
        self.cache.write_text(json.dumps({'schema_version':3}), encoding='utf-8')
        self.assertEqual(read_health_cache(self.cache), {})

    def test_saved_configured_path_is_never_overridden(self):
        wrong = str(self.root/'missing'/self.exe.name)
        calls = []
        def probe(path, *, origin=''):
            calls.append((path, origin))
            return ToolHealth('arkade5', 'error', path, message='Filen finnes ikke')
        result = check_one_tool('arkade5', wrong,
                                cached=self.fake_arkade_probe(str(self.exe)),
                                discover=lambda: (self.exe,), probe=probe)
        self.assertEqual(result.path, wrong)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 'lagret Setup-sti')

    def test_valid_global_cache_is_rechecked_before_reuse(self):
        count = []
        def probe(path, *, origin=''):
            count.append(origin)
            return self.fake_arkade_probe(path, origin=origin)
        result = check_one_tool('arkade5', '',
                                cached=self.fake_arkade_probe(str(self.exe)),
                                discover=lambda: (), probe=probe)
        self.assertTrue(result.usable)
        self.assertEqual(count, ['tidligere installasjon'])

    def test_healthy_run_populates_file_and_maintains_identity(self):
        result = check_both_tools({'arkade5_cli_path':'', 'sf_executable':''},
                                  cache_file=self.cache,
                                  arkade_discovery=lambda: (self.exe,),
                                  siegfried_discovery=lambda: (self.sf,),
                                  arkade_probe=self.fake_arkade_probe,
                                  siegfried_probe=self.fake_sf_probe)
        self.assertTrue(result['arkade5'].usable)
        self.assertTrue(result['siegfried'].usable)
        self.assertEqual(read_health_cache(self.cache)['arkade5'].path, str(self.exe))

    def test_missing_tools_remains_error_not_fake_success(self):
        result = check_both_tools({}, cache_file=self.cache,
                                  arkade_discovery=lambda: (),
                                  siegfried_discovery=lambda: ())
        self.assertEqual(result['arkade5'].state, 'error')
        self.assertEqual(result['siegfried'].state, 'error')

    def test_arkade_adapter_result_is_used(self):
        checker = SimpleNamespace(check=lambda *a,**kw: SimpleNamespace(
            severity='ok', version='2.13.1', message='Arkade funnet'))
        res = probe_arkade5(str(self.exe), checker=checker)
        self.assertEqual(res.version, '2.13.1')
        self.assertTrue(res.usable)

    def test_siegfried_version_and_signature_are_used(self):
        inspector = lambda *a, **kw: SimpleNamespace(ok=True,version='siegfried 1.11.4',
                                            signature='PRONOM 122',message='OK')
        result = probe_siegfried(str(self.sf), inspector=inspector)
        self.assertTrue(result.usable)
        self.assertEqual(result.signature, 'PRONOM 122')

    def test_file_change_alters_fingerprint(self):
        first = file_fingerprint(self.exe)
        self.exe.write_bytes(b'another version')
        self.assertNotEqual(first, file_fingerprint(self.exe))

    def test_paths_are_saved_only_if_unset(self):
        cfg = []
        settings_mod = ModuleType('settings')
        settings_mod.save_config = lambda changes: cfg.append(dict(changes))
        checker = SimpleNamespace(invalidate=lambda: None)
        api = SimpleNamespace(settings={'arkade5_cli_path':'', 'sf_executable':'manual'},
                              _guard=RLock(), _assert_idle=lambda: None,
                              _arkade_checker=checker)
        states = {'arkade5': self.fake_arkade_probe(str(self.exe)),
                  'siegfried': self.fake_sf_probe(str(self.sf))}
        with patch.dict(sys.modules, {'settings':settings_mod}):
            saved = persist_discovered_paths(api, states)
        self.assertEqual(saved, {'arkade5_cli_path':str(self.exe)})
        self.assertEqual(cfg, [saved])
        self.assertEqual(api.settings['sf_executable'], 'manual')

    def test_no_changes_to_config_when_already_configured(self):
        cfg = []
        settings_mod = ModuleType('settings')
        settings_mod.save_config = lambda changes: cfg.append(changes)
        api = SimpleNamespace(settings={'arkade5_cli_path':'user', 'sf_executable':'user'},
                              _guard=RLock(), _assert_idle=lambda: None,
                              _arkade_checker=SimpleNamespace(invalidate=lambda:None))
        with patch.dict(sys.modules, {'settings':settings_mod}):
            self.assertEqual(persist_discovered_paths(api, {
                'arkade5':self.fake_arkade_probe(str(self.exe))}), {})
        self.assertEqual(cfg, [])

    def test_running_job_blocks_config_write_without_failure(self):
        cfg = []
        settings_mod = ModuleType('settings')
        settings_mod.save_config = lambda changes: cfg.append(changes)
        def busy():
            raise RuntimeError('busy')
        api = SimpleNamespace(settings={'arkade5_cli_path':'', 'sf_executable':''},
                              _guard=RLock(), _assert_idle=busy,
                              _arkade_checker=SimpleNamespace(invalidate=lambda:None))
        with patch.dict(sys.modules, {'settings':settings_mod}):
            self.assertEqual(persist_discovered_paths(api, {
                'arkade5':self.fake_arkade_probe(str(self.exe))}), {})
        self.assertEqual(cfg, [])


class IntegrationStaticTests(TestCase):
    def test_application_version_consistency(self):
        version = (ROOT/'version.py').read_text(encoding='utf-8')
        metadata = (ROOT/'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn('VERSION = "0.2.4-a5"', version)
        self.assertIn('version = "0.2.4a5"', metadata)

    def test_entrypoint_keeps_a4_and_safe_mode(self):
        source = (ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        self.assertIn('DwmMainWindow = _A4Window', source)
        self.assertIn('install_tool_health_setup()', source)
        self.assertIn('schedule_tool_check(window, api)', source)
        self.assertIn("os.environ.get('DWM_SAFE_MODE') != '1'", source)
        self.assertLess(source.index('window.show()'), source.index('schedule_tool_check(window, api)'))
        ast.parse(source)

    def test_module_never_installs_or_scans_source(self):
        src = (ROOT/'app/tool_health_v024_a5.py').read_text(encoding='utf-8')
        self.assertNotIn('pip install', src)
        self.assertNotIn('download(', src)
        self.assertNotIn('os.walk(', src)
        self.assertNotIn('rglob(', src)
        self.assertNotIn('job.json', src)
        ast.parse(src)

    def test_setup_uses_existing_dialog(self):
        src = (ROOT/'gui_qt/setup_tool_health_v024_a5.py').read_text(encoding='utf-8')
        self.assertIn('previous = module.DwmSetupDialog', src)
        self.assertIn('class SetupWithToolHealth(previous):', src)
        self.assertIn('self._external_sections.insertWidget', src)
        ast.parse(src)


if __name__ == '__main__':
    main()
