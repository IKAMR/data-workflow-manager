"""A260 a6 guarded source integration and version migration."""
from pathlib import Path
import tempfile
import unittest

from tools.apply_v023_a6 import apply


class ApplyA6Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for rel in ('noark5_workflow/operations','noark5_workflow/reporting', 'tests'):
            (self.root/rel).mkdir(parents=True,exist_ok=True)
        (self.root/'version.py').write_text('APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.3-a4"\n')
        (self.root/'pyproject.toml').write_text('[project]\nversion = "0.2.3a4"\n')
        (self.root/'noark5_workflow/reporting/qa_a260_v023_a6.py').write_text('def build_qa_basis_a6(*args,**kwargs):\n    return {}\n')
        (self.root/'noark5_workflow/operations/canonical_evidence_v022_a7.py').write_text(
            'from pathlib import Path\n'
            "def build_qa_basis(work: str | Path, *, job_id: str = '') -> dict:\n"
            '    from noark5_workflow.reporting.qa_workflow_v022_a3 import build_review_snapshot_v022_a3\n'
            "    output = 'qa-basis-draft'\n"
            '    return {"output":output, "result":build_review_snapshot_v022_a3()}\n\n'
            'class BuildNoark5QaDraftOperation:\n'
            '    worker = staticmethod(build_qa_basis)\n')
        (self.root/'tests/test_v023_a4_guided_review.py').write_text(
            'from version import VERSION\nimport tomllib\nimport unittest\n'
            'class VersionTest(unittest.TestCase):\n'
            "    def test_version(self):\n        self.assertEqual(VERSION, '0.2.3-a4')\n"
            "        with open('pyproject.toml','rb') as f:\n"
            "            self.assertEqual(tomllib.load(f)['project']['version'], '0.2.3a4')\n")

    def test_patch_preserves_legacy_and_wires_new_a260(self):
        files = apply(self.root,dry_run=True,override_branch=True)
        self.assertEqual(len(files),4)
        applied=apply(self.root,dry_run=False,override_branch=True)
        self.assertEqual(set(files),set(applied))
        self.assertEqual(apply(self.root,dry_run=True,override_branch=True),[])
        self.assertEqual(apply(self.root,dry_run=False,override_branch=True),[])
        op=(self.root/'noark5_workflow/operations/canonical_evidence_v022_a7.py').read_text()
        self.assertIn('def _build_qa_basis_legacy_v022_a7(',op)
        self.assertIn('def build_qa_basis(',op)
        self.assertIn('from noark5_workflow.reporting.qa_a260_v023_a6 import',op)
        self.assertIn('worker = staticmethod(build_qa_basis)',op)
        self.assertIn('0.2.3-a6',(self.root/'version.py').read_text())
        self.assertIn('0.2.3a6',(self.root/'pyproject.toml').read_text())

    def test_unknown_operation_is_rejected_without_changes(self):
        module=self.root/'noark5_workflow/operations/canonical_evidence_v022_a7.py'
        module.write_text('def build_qa_basis(work):\n    return {}\n')
        version_before=(self.root/'version.py').read_bytes()
        with self.assertRaises(RuntimeError):
            apply(self.root,dry_run=False,override_branch=True)
        self.assertEqual(version_before,(self.root/'version.py').read_bytes())


if __name__=='__main__':unittest.main()
