"""v0.2.4-a5 – bounded startup discovery, read-only CLI checks and durable cache.

This is *not* an installer. Searches configured program files, SIARD's shared
Siegfried, Windows PATH and shallow known local installation directories only.
Cache is per user (independent of a DWM clone), never inside Source/Work.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

_CACHE_VERSION = 1
_ARKADE_NAMES = (
    'Arkivverket.Arkade.CLI.exe', 'Nasjonalarkivet.Arkade.CLI.exe',
    'Arkade5CLI.exe', 'Arkade5.CLI.exe', 'Arkade5.exe',
    'arkade5.exe', 'arkade5-cli.exe', 'arkade.exe',
    'arkade.bat', 'arkade.cmd', 'arkade5.bat', 'arkade5.cmd',
    'arkade5', 'arkade',
)
_SF_NAMES = ('sf.exe',) if sys.platform == 'win32' else ('sf', 'sf.exe')
_ROOT_FOLDERS = ('bin', 'publish', 'win-x64', 'cli', 'siegfried', 'tools')
_FOLDER_PATTERN = re.compile(r'arkade|siegfried|siard|nasjonalarkivet|arkivverket', re.I)
_ALLOWED_STATES = {'ok', 'warning', 'error'}


@dataclass(frozen=True)
class ToolHealth:
    tool: str
    state: str
    path: str = ''
    version: str = ''
    signature: str = ''
    origin: str = ''
    message: str = ''
    fingerprint: str = ''
    checked_at: str = ''

    @property
    def usable(self) -> bool:
        return self.state == 'ok' and bool(self.path)


def user_health_file(env: Mapping[str, str] | None = None, *, home: Path | None = None) -> Path:
    """A stable per-user file survives separate DWM source/version folders."""
    environ = os.environ if env is None else env
    if environ.get('LOCALAPPDATA'):
        root = Path(environ['LOCALAPPDATA'])
    elif sys.platform == 'win32' and environ.get('APPDATA'):
        root = Path(environ['APPDATA'])
    elif environ.get('XDG_CONFIG_HOME'):
        root = Path(environ['XDG_CONFIG_HOME'])
    else:
        root = (home or Path.home()) / '.config'
    return root / 'IKAMR' / 'DataWorkflowManager' / 'external-tools-v1.json'


def file_fingerprint(path: str | Path) -> str:
    try:
        p = Path(path)
        stat = p.stat()
        if not p.is_file():
            return ''
        return f'{stat.st_size}:{stat.st_mtime_ns}'
    except (OSError, ValueError):
        return ''


def read_health_cache(path: Path | None = None) -> dict[str, ToolHealth]:
    file = Path(path) if path is not None else user_health_file()
    try:
        data = json.loads(file.read_text(encoding='utf-8'))
        if data.get('schema_version') != _CACHE_VERSION:
            return {}
        result: dict[str, ToolHealth] = {}
        for name in ('arkade5', 'siegfried'):
            raw = data.get('tools', {}).get(name)
            if not isinstance(raw, dict):
                continue
            fields = {key: str(raw.get(key, '') or '') for key in ToolHealth.__dataclass_fields__}
            fields['tool'] = name
            if fields['state'] not in _ALLOWED_STATES:
                continue
            result[name] = ToolHealth(**fields)
        return result
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def write_health_cache(results: Mapping[str, ToolHealth], path: Path | None = None) -> bool:
    file = Path(path) if path is not None else user_health_file()
    data = {
        'schema_version': _CACHE_VERSION,
        'note': 'Kun lokale verktøykontroller; ingen Source/Work eller arkivdata',
        'tools': {name: asdict(value) for name, value in results.items()
                  if name in ('arkade5', 'siegfried') and isinstance(value, ToolHealth)},
    }
    temporary = file.with_name(file.name + '.tmp')
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, file)
        return True
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _is_arkade_name(name: str) -> bool:
    return name.casefold() in {x.casefold() for x in _ARKADE_NAMES}


def windows_roots(env: Mapping[str, str] | None = None, *,
                  platform: str | None = None) -> tuple[Path, ...]:
    """Known local install roots; no recursive filesystem walk or network root."""
    environ = os.environ if env is None else env
    os_platform = sys.platform if platform is None else platform
    roots: list[Path] = []
    for key in ('PROGRAMFILES', 'ProgramFiles', 'ProgramFiles(x86)',
                'PROGRAMFILES(X86)', 'ProgramW6432', 'LOCALAPPDATA'):
        value = environ.get(key)
        if value:
            roots.append(Path(value))
    if os_platform == 'win32':
        drive = environ.get('SystemDrive', environ.get('SYSTEMDRIVE', 'C:')).rstrip('\\/')
        if not re.match(r'^[A-Za-z]:$', drive):
            drive = 'C:'
        roots += [Path(drive + '\\' + tail) for tail in (
            'Prog', 'Program Files', 'Program Files (x86)', 'Programfiler')]
    seen: set[str] = set()
    answer: list[Path] = []
    for item in roots:
        key = os.path.normcase(str(item)).casefold()
        if key not in seen:
            seen.add(key)
            answer.append(item)
    return tuple(answer)


def _find_in_root(root: Path, filenames: tuple[str, ...], *,
                  max_children: int = 100) -> list[Path]:
    """Root, direct matching subdirectories and one known bin/CLI level only."""
    candidates: list[Path] = []
    try:
        if not root.is_dir():
            return []
        folders = [root]
        for child in sorted(root.iterdir(), key=lambda p: p.name.casefold())[:max_children]:
            if child.is_dir() and not child.is_symlink() and _FOLDER_PATTERN.search(child.name):
                folders.append(child)
        for folder in folders:
            for prefix in ('', *_ROOT_FOLDERS):
                base = folder / prefix if prefix else folder
                # A file check is cheap; avoid enumerating all children of folders.
                for name in filenames:
                    p = base / name
                    if p.is_file():
                        candidates.append(p)
            # Common distribution layout: <vendor>/Arkade5CLI-2.x/arkade.bat
            if folder != root:
                for child in sorted(folder.iterdir(), key=lambda p: p.name.casefold())[:40]:
                    if child.is_dir() and not child.is_symlink() and _FOLDER_PATTERN.search(child.name):
                        for name in filenames:
                            for prefix in ('', 'bin'):
                                p = child / prefix / name if prefix else child / name
                                if p.is_file():
                                    candidates.append(p)
    except (OSError, ValueError):
        return candidates
    return candidates


def _deduplicate(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    answer: list[Path] = []
    for path in paths:
        try:
            p = path.resolve(strict=True)
            if not p.is_file():
                continue
            key = str(p).casefold()
            if key not in seen:
                seen.add(key)
                answer.append(p)
        except (OSError, ValueError, RuntimeError):
            continue
    return tuple(answer)


def _path_candidates(names: tuple[str, ...], env: Mapping[str, str]) -> list[Path]:
    paths = []
    path_value = str(env.get('PATH', '') or '')
    for name in names:
        item = shutil.which(name, path=path_value)
        if item:
            paths.append(Path(item))
    return paths


def discover_arkade5(*, roots: tuple[Path, ...] | None = None,
                     env: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    environ = os.environ if env is None else env
    search_roots = windows_roots(environ) if roots is None else tuple(roots)
    found = _path_candidates(_ARKADE_NAMES, environ)
    for root in search_roots:
        found.extend(_find_in_root(root, _ARKADE_NAMES))
    items = _deduplicate(found)
    # Prefer newer, version-named distributions (e.g. 2.13.1 over 2.12.5),
    # but do not override an explicit user choice or previously checked path.
    def version_key(path: Path):
        parts = re.findall(r'(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?', str(path))
        if not parts:
            return (-1, -1, -1)
        major, minor, patch = parts[-1]
        return (int(major), int(minor), int(patch or 0))
    return tuple(sorted(items, key=version_key, reverse=True))


def discover_siegfried(*, roots: tuple[Path, ...] | None = None,
                       env: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    environ = os.environ if env is None else env
    found: list[Path] = []
    local = environ.get('LOCALAPPDATA')
    if local:
        shared = Path(local) / 'SIARDManager' / 'siegfried'
        found += _find_in_root(shared, _SF_NAMES)
        # Siegfried can be extracted into a version-named folder without
        # having Siegfried in that child name; SIARD's resolver handles it.
        try:
            for sub in sorted(shared.iterdir())[:40] if shared.is_dir() else ():
                if sub.is_dir() and not sub.is_symlink():
                    for name in _SF_NAMES:
                        found.append(sub / name)
        except OSError:
            pass
    found.extend(_path_candidates(_SF_NAMES, environ))
    search_roots = windows_roots(environ) if roots is None else tuple(roots)
    for root in search_roots:
        found.extend(_find_in_root(root, _SF_NAMES))
    return _deduplicate(found)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _build_health(tool: str, path: str, *, state: str, origin: str,
                  version: str = '', signature: str = '', message: str = '') -> ToolHealth:
    return ToolHealth(tool=tool, state=state, path=path, version=version,
                      signature=signature, origin=origin, message=message,
                      fingerprint=file_fingerprint(path) if path else '', checked_at=_now())


def probe_arkade5(path: str, *, origin: str = '', checker=None) -> ToolHealth:
    """Actual read-only Arkade version probe using the existing DWM adapter."""
    if not Path(path).is_file():
        return _build_health('arkade5', path, state='error', origin=origin,
                             message='Arkade 5-programfilen finnes ikke. Velg fil i Setup.')
    try:
        if checker is None:
            from app.arkade5_setup_v018_a7 import Arkade5DependencyChecker
            from noark5_workflow.external_tools.arkade5 import inspect_arkade5_cli
            # A cold .NET 10 CLI launch on Windows can exceed the older
            # preflight's 2.5 s limit. Startup probing is async, so allow 5 s.
            checker = Arkade5DependencyChecker(
                inspector=lambda config, timeout_seconds: inspect_arkade5_cli(
                    config, timeout_seconds=max(5.0, timeout_seconds)),
                ttl_seconds=0,
            )
        result = checker.check({'arkade5_cli_path': path}, refresh=True)
        severity = str(result.severity or 'error')
        return _build_health('arkade5', path, state=severity, origin=origin,
                             version=str(result.version or ''), message=str(result.message or ''))
    except (OSError, ValueError, RuntimeError) as exc:
        return _build_health('arkade5', path, state='error', origin=origin,
                             message='Arkade 5-test feilet: ' + str(exc))


def probe_siegfried(path: str, *, origin: str = '', inspector=None) -> ToolHealth:
    if not Path(path).is_file():
        return _build_health('siegfried', path, state='error', origin=origin,
                             message='sf.exe finnes ikke. Velg fil i Setup.')
    try:
        if inspector is None:
            from app.siegfried_tool_v0111_a3 import inspect_siegfried
            inspector = inspect_siegfried
        result = inspector(path, auto_discover=False)
        return _build_health('siegfried', path, state='ok' if result.ok else 'error',
                             origin=origin, version=str(result.version or ''),
                             signature=str(result.signature or ''), message=str(result.message or ''))
    except (OSError, ValueError, RuntimeError) as exc:
        return _build_health('siegfried', path, state='error', origin=origin,
                             message='Siegfried-test feilet: ' + str(exc))


def check_one_tool(tool: str, configured: str = '', *, cached: ToolHealth | None = None,
                   discover: Callable[[], tuple[Path, ...]] | None = None,
                   probe: Callable[..., ToolHealth] | None = None) -> ToolHealth:
    """Do not silently replace a user-configured path, even if it is broken."""
    if tool not in ('arkade5', 'siegfried'):
        raise ValueError(tool)
    probe_fn = probe or (probe_arkade5 if tool == 'arkade5' else probe_siegfried)
    explicit = str(configured or '').strip().strip('"')
    if explicit:
        return probe_fn(explicit, origin='lagret Setup-sti')
    if cached and cached.path and file_fingerprint(cached.path):
        status = probe_fn(cached.path, origin='tidligere installasjon')
        if status.usable:
            return status
    finder = discover or (discover_arkade5 if tool == 'arkade5' else discover_siegfried)
    found = finder()
    for path in found[:8]:
        if cached and str(path).casefold() == cached.path.casefold():
            continue
        status = probe_fn(str(path), origin='automatisk funnet')
        if status.usable:
            return status
    return _build_health(tool, '', state='error', origin='automatisk søk',
                         message=('Arkade 5 CLI ikke funnet eller ikke kjørbar. '
                                  'Last ned manuelt og velg fil i Setup.' if tool == 'arkade5'
                                  else 'Siegfried ikke funnet eller ikke kjørbar. '
                                       'Installer via SIARD Workflow Manager eller velg sf.exe.'))


def check_both_tools(settings: Mapping, *, cache_file: Path | None = None,
                     arkade_discovery=None, siegfried_discovery=None,
                     arkade_probe=None, siegfried_probe=None) -> dict[str, ToolHealth]:
    """Run asynchronously from GUI; this call itself performs bounded probes."""
    existing = read_health_cache(cache_file)
    arkade = check_one_tool('arkade5', str(settings.get('arkade5_cli_path', '') or ''),
                            cached=existing.get('arkade5'), discover=arkade_discovery,
                            probe=arkade_probe)
    siegfried = check_one_tool('siegfried', str(settings.get('sf_executable', '') or ''),
                               cached=existing.get('siegfried'), discover=siegfried_discovery,
                               probe=siegfried_probe)
    result = {'arkade5': arkade, 'siegfried': siegfried}
    write_health_cache(result, cache_file)
    return result


def persist_discovered_paths(api, checks: Mapping[str, ToolHealth]) -> dict[str, str]:
    """Update Setup paths only if absent; keep user's explicit choices intact.

    The core run preflight remains authoritative and rechecks tools on use.
    A valid historical cache NEVER means the executable is assumed installed.
    """
    proposals: dict[str, str] = {}
    for tool, key in (('arkade5', 'arkade5_cli_path'), ('siegfried', 'sf_executable')):
        state = checks.get(tool)
        if state and state.usable and file_fingerprint(state.path):
            proposals[key] = state.path
    if not proposals:
        return {}
    try:
        from settings import save_config
        with api._guard:
            api._assert_idle()
            new_values = {key: path for key, path in proposals.items()
                          if not str(api.settings.get(key, '') or '').strip()}
            if not new_values:
                return {}
            save_config(new_values)
            api.settings.update(new_values)
            if 'arkade5_cli_path' in new_values:
                api._arkade_checker.invalidate()
            return new_values
    except (AttributeError, OSError, RuntimeError, ValueError):
        return {}  # cache still survives an application update; retry next start
