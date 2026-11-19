"""Apply the a6 delta onto the merged A220+a4 development branch.

The connector-backed repository is not redistributed.  This installer makes
small, audited in-place changes to the user's *existing* source modules,
without replacing either colleague's A220 code or the a4 GUI files.

Usage (after unpacking the delta ZIP into the repository root):
    py tools/apply_v023_a6.py --check
    py tools/apply_v023_a6.py
"""
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = Path('noark5_workflow/operations/canonical_evidence_v022_a7.py')
VERSION = Path('version.py')
PROJECT = Path('pyproject.toml')
VERSION_TEST = Path('tests/test_v023_a4_guided_review.py')
A6_MARKER = 'noark5_workflow.reporting.qa_a260_v023_a6'


def _patch_operation(text: str) -> str:
    tree = ast.parse(text)
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'build_qa_basis']
    if len(definitions) != 1:
        raise RuntimeError('Forventet nøyaktig én A260 build_qa_basis-funksjon')
    node = definitions[0]
    if A6_MARKER in ast.get_source_segment(text, node):
        return text  # idempotent
    body = ast.get_source_segment(text, node)
    if 'build_review_snapshot_v022_a3' not in body or 'qa-basis-draft' not in body:
        raise RuntimeError('Uklar A260-implementasjon; avbryter i stedet for å overskrive fremmed kode')
    lines = text.splitlines(keepends=True)
    original = list(lines[node.lineno-1:node.end_lineno])
    original[0] = original[0].replace('def build_qa_basis(',
                                      'def _build_qa_basis_legacy_v022_a7(', 1)
    new = (
        "\n\ndef build_qa_basis(work: str | Path, *, job_id: str = '') -> dict:\n"
        '    """A260: stream complete source-bound findings; no 300-row ceiling."""\n'
        '    from noark5_workflow.reporting.qa_a260_v023_a6 import build_qa_basis_a6\n'
        '    return build_qa_basis_a6(work, job_id=job_id)\n'
    )
    result = ''.join(lines[:node.lineno-1]) + ''.join(original) + new + ''.join(lines[node.end_lineno:])
    compile(result, str(OPERATIONS), 'exec')
    return result


def _only_one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError('Forventet ikke gjeldende kildekode i ' + label)
    if text.count(old) != 1:
        raise RuntimeError('Flertydig endring i ' + label)
    return text.replace(old, new, 1)


def changes(root: Path) -> dict[Path, str]:
    src = (root/OPERATIONS).read_text(encoding='utf-8')
    version = (root/VERSION).read_text(encoding='utf-8')
    project = (root/PROJECT).read_text(encoding='utf-8')
    tests = (root/VERSION_TEST).read_text(encoding='utf-8')
    # Check both new source and the current merged baseline before editing.
    module = root/'noark5_workflow/reporting/qa_a260_v023_a6.py'
    if not module.is_file():
        raise RuntimeError('Pakk først ut a6-deltaen i rotmappen til repoet')
    compile(module.read_text(encoding='utf-8'), str(module), 'exec')
    patched = {
        OPERATIONS: _patch_operation(src),
        VERSION: _only_one(version, 'VERSION = "0.2.3-a4"',
                           'VERSION = "0.2.3-a6"', 'version.py'),
        PROJECT: _only_one(project, 'version = "0.2.3a4"',
                           'version = "0.2.3a6"', 'pyproject.toml'),
    }
    tests = _only_one(tests, "self.assertEqual(VERSION, '0.2.3-a4')",
                      "self.assertGreaterEqual(int(VERSION.rsplit('-a', 1)[1]), 4)",
                      str(VERSION_TEST))
    tests = _only_one(tests, "self.assertEqual(tomllib.load(f)['project']['version'], '0.2.3a4')",
                      "self.assertEqual(tomllib.load(f)['project']['version'], VERSION.replace('-a', 'a'))",
                      str(VERSION_TEST))
    patched[VERSION_TEST] = tests
    for path, code in patched.items():
        if path.suffix == '.py':
            compile(code, str(path), 'exec')
    return {rel: text for rel,text in patched.items()
            if (root/rel).read_text(encoding='utf-8') != text}


def _ensure_branch(root: Path, *, override: bool):
    if override:
        return
    r = subprocess.run(['git','branch','--show-current'],cwd=root,encoding='utf-8',
                       capture_output=True,check=True)
    if r.stdout.strip() != 'a220-a260-taa':
        raise RuntimeError('A6 skal bare brukes på a220-a260-taa, ikke main eller kollegaens branch')
    r = subprocess.run(['git','diff','--name-only','--diff-filter=U'],cwd=root,
                       encoding='utf-8',capture_output=True,check=True)
    if r.stdout.strip():
        raise RuntimeError('Repoet har uløste Git-merge-konflikter')


def apply(root: Path, *, dry_run: bool, override_branch: bool = False) -> list[str]:
    _ensure_branch(root, override=override_branch)
    updates = changes(root)
    if dry_run:
        return [str(x) for x in updates]
    originals = {rel:(root/rel).read_bytes() for rel in updates}
    written = []
    try:
        for rel, text in updates.items():
            target = root/rel
            if target.is_symlink():
                raise RuntimeError('Symbolsk lenke: ' + str(rel))
            fd, name = tempfile.mkstemp(prefix='.a6-',dir=target.parent)
            try:
                with os.fdopen(fd,'w',encoding='utf-8',newline='') as stream:
                    stream.write(text)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name,target)
                written.append(rel)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
    except Exception:
        for rel in reversed(written):
            (root/rel).write_bytes(originals[rel])
        raise
    return [str(x) for x in updates]


def main() -> int:
    parser = argparse.ArgumentParser(description='DWM v0.2.3-a6 apply/check')
    parser.add_argument('--check',action='store_true',help='Kontroll uten kildeendringer')
    parser.add_argument('--root',type=Path,default=ROOT)
    args = parser.parse_args()
    try:
        result=apply(args.root.resolve(),dry_run=args.check)
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
        print('[FEIL] A6 ble ikke lagt inn: '+str(exc))
        return 1
    print('[OK] '+('Mulige endringer: ' if args.check else 'Utførte endringer: ')+str(len(result)))
    for path in result:print(' - '+path)
    if not args.check:print('Kjør nå: cmd.exe /c test.bat')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
