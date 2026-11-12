"""a3.4: exercise a real subprocess-like Siegfried CLI against a small Source."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.siegfried_results_v0111_a3 import list_siegfried_runs
from noark5_workflow.core.context import OperationContext
from noark5_workflow.operations.run_siegfried_pronom import (
    SiegfriedPronomOperation, document_files,
)


class SiegfriedEvidenceTests(unittest.TestCase):
    def _fake_sf(self, folder):
        path=folder/'sf'
        path.write_text('#!'+sys.executable+'\n'
                        'import json,sys\n'
                        'if "-version" in sys.argv:\n'
                        ' print("siegfried 1.11.9 PRONOM signature V125")\n'
                        'else:\n'
                        ' paths=sys.argv[4:]\n'
                        ' print(json.dumps({"files":[{"filename":p, "matches":[{"id":"fmt/354",'
                        ' "format":"PDF/A", "version":"1b", "basis":"signature"}]} for p in paths]}))\n',
                        encoding='utf-8')
        path.chmod(0o755)
        return path

    def test_scan_output_remains_outside_source_and_visible_in_work(self):
        if os.name == 'nt':
            self.skipTest('Windows .exe integration is tested separately; this fake binary is POSIX')
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); src=base/'Source'; src.mkdir(); work=base/'Work'; work.mkdir()
            content=src/'DOKUMENT'; content.mkdir()
            document=content/'PDF test.pdf'; document.write_bytes(b'%PDF-1.4\n')
            meta=src/'arkivstruktur.xml';meta.write_bytes(b'<arkiv/>')
            sf=self._fake_sf(base)
            before={str(p):p.read_bytes() for p in (document,meta)}
            ctx=OperationContext(src,work_operations=work,settings={'sf_executable':str(sf)},
                                 metadata={'job_id':'JOB-001'})
            result=SiegfriedPronomOperation().run(ctx)
            self.assertTrue(result.ok,result.message)
            self.assertEqual({str(p):p.read_bytes() for p in (document,meta)},before)
            self.assertFalse((work/'dwm').exists())
            runs=list_siegfried_runs(work)
            self.assertEqual(len(runs),1)
            model=runs[0]['model']
            self.assertEqual(model['files_total'],1)
            self.assertEqual(model['identified'],1)
            self.assertEqual(model['format_groups'][0]['puid'],'fmt/354')
            self.assertEqual(model['source_scope'],'DOKUMENT')
            self.assertNotIn('RAF',json.dumps(model))
            raw=runs[0]['folder']/'siegfried_files.jsonl'
            self.assertIn('basis',raw.read_text('utf-8'))
            self.assertEqual(runs[0]['manifest']['raw_sha256'], hashlib.sha256(raw.read_bytes()).hexdigest())

    def test_cancelled_never_exposes_partial_run_as_success(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'Source';src.mkdir();work=Path(td)/'Work';work.mkdir()
            (src/'test.bin').write_bytes(b'hello')
            files,scope=document_files(src,cancelled_cb=lambda:False)
            self.assertEqual(len(files),1)
            self.assertIn('Hele uttrekksmappen',scope)
            with self.assertRaises(InterruptedError):
                document_files(src,cancelled_cb=lambda:True)
            self.assertFalse(list_siegfried_runs(work))

    def test_manifest_guard_rejects_partial_or_malformed_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td)
            root=work/'external_evidence'/'siegfried';root.mkdir(parents=True)
            partial=root/'.partial-123';partial.mkdir()
            (partial/'manifest.json').write_text('{}')
            complete=root/'20260101T000000Z-abc';complete.mkdir()
            (complete/'manifest.json').write_text('{"file_type":"dwm-siegfried-run", "run_id":"wrong"}')
            (complete/'pronom_statistics.json').write_text('{"evidence_type":"dwm_siegfried_pronom_identification","run_id":"wrong", "format_groups":[], "files_total":0}')
            self.assertEqual(list_siegfried_runs(work),[])


if __name__=='__main__':unittest.main()
