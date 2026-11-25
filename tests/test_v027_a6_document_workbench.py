"""a6: source-bound file-level Siegfried, professional status and safe copying."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import ast
import json
import sys
import unittest

from app.noark5_document_workbench_v027_a6 import (
    DocumentWorkbenchError, _normalized_ref, _raw_record, _safe_file,
    _run, arkade_raf_by_puid, build_document_index, copy_selected_files,
    file_page, find_document_index, format_groups, format_policy_label,
    latest_assessment, format_annotations, save_format_annotation,
)

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


class DocumentTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.output = self.root / 'output'
        self.output.mkdir()
        self.uid = 'actual-work-job-uid'
        self.xml = self.source / 'arkivstruktur.xml'
        self.xml.write_text('''<?xml version="1.0" encoding="utf-8"?>
<arkiv xmlns="http://www.arkivverket.no/standarder/noark5/arkivstruktur">
<systemID>ark-1</systemID>
<arkivdel><systemID>part-A</systemID>
<mappe><systemID>sak-1</systemID><registrering><systemID>reg-1</systemID>
<dokumentbeskrivelse><systemID>desc-1</systemID>
<dokumentobjekt><systemID>obj-1</systemID><referanseDokumentfil>DOKUMENT/sub/a.pdf</referanseDokumentfil></dokumentobjekt>
</dokumentbeskrivelse></registrering></mappe></arkivdel>
<arkivdel><systemID>part-B</systemID><mappe><registrering>
<dokumentbeskrivelse><systemID>desc-2</systemID><dokumentobjekt>
<systemID>obj-2</systemID><referanseDokumentfil>DOKUMENT/other/b.doc</referanseDokumentfil>
</dokumentobjekt></dokumentbeskrivelse></registrering></mappe></arkivdel>
</arkiv>\n''', encoding='utf-8')
        definition = {'file_type':'dwm-work-job', 'job_uid':self.uid,
                      'job':{'job_id':'JOB-001','source_extraction':str(self.source)}}
        (self.work/'job.json').write_text(json.dumps(definition), encoding='utf-8')
        self.report_dir = self.work / 'noark5_reports' / 'depot_validation' / 'JOB-001__run'
        self.report_dir.mkdir(parents=True)
        self.report = self.report_dir / 'depot_validation_report.json'
        self.report.write_text(json.dumps({'report_type':'noark5_depot_validation'}), encoding='utf-8')
        (self.report_dir/'artifact_manifest.json').write_text(json.dumps({
            'job_uid':self.uid,'job_id':'JOB-001'}), encoding='utf-8')
        self.snapshot = SimpleNamespace(
            work=self.work, report_path=self.report, job_uid=self.uid, job_id='JOB-001',
            report={'delivery_validation':{'complete': True, 'source_sha256':digest(self.xml)}},
            parts=[{'archive_part': {'system_id':'part-A'}},
                   {'archive_part': {'system_id':'part-B'}}],
        )
        self.run_dir = self.work / 'external_evidence' / 'siegfried' / '20261125T000000Z-1234567890'
        self.run_dir.mkdir(parents=True)
        self.rows = [
            ('DOKUMENT/sub/a.pdf', b'First PDF', [{'id':'fmt/14','format':'PDF','version':'1.0'}], ''),
            ('DOKUMENT/other/b.doc', b'DOC', [{'id':'x-fmt/263','format':'Word'}], ''),
            ('DOKUMENT/sub/other.pdf', b'Second PDF', [{'id':'fmt/14','format':'PDF'}], ''),
            ('DOKUMENT/sub/none.bin', b'???', [], ''),
            ('DOKUMENT/sub/multi.dat', b'???', [{'id':'fmt/14'}, {'id':'fmt/18'}], ''),
            ('DOKUMENT/sub/fail.txt', b'???', [], 'sf_error'),
        ]
        self.write_run()
        external = ModuleType('app.ks_xml_evidence_v023_a19')
        external._job_sources = lambda _w: [self.source]
        external.resolve_source_xml = lambda _w, filename: self.source/filename
        self.patch_sources = patch.dict(sys.modules, {'app.ks_xml_evidence_v023_a19':external})
        self.patch_sources.start()
        self.addCleanup(self.patch_sources.stop)

    def write_run(self):
        inventory, results = [], []
        for rel, data, matches, errors in self.rows:
            file = self.source/rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
            st = file.stat()
            inventory.append(json.dumps({'path':rel,'size':st.st_size,'mtime_ns':st.st_mtime_ns},
                                        ensure_ascii=False,separators=(',', ':'))+'\n')
            results.append(json.dumps({'filename':str(file),'matches':matches,'errors':errors},
                                      ensure_ascii=False)+'\n')
        raw = self.run_dir / 'siegfried_files.jsonl'
        inv = self.run_dir / 'file_inventory.jsonl'
        raw.write_text(''.join(results), encoding='utf-8', newline='\n')
        inv.write_text(''.join(inventory), encoding='utf-8', newline='\n')
        self.run_manifest = {'file_type':'dwm-siegfried-run',
                             'run_id':self.run_dir.name,'job_id':'JOB-001','job_uid':self.uid,
                             'source_root':str(self.source),'raw_file':'siegfried_files.jsonl',
                             'raw_sha256':digest(raw), 'inventory_sha256':digest(inv),
                             'files_total':len(self.rows)}
        (self.run_dir/'manifest.json').write_text(json.dumps(self.run_manifest), encoding='utf-8')

    def build(self):
        return build_document_index(self.snapshot)

    def test_completed_siegfried_and_six_per_file_entries(self):
        meta = self.build()
        self.assertEqual(meta['files_total'],6)
        self.assertEqual(meta['formats_total'],5)
        self.assertEqual(meta['xml_mapping']['state'],'work_sha256_verified')
        self.assertEqual(meta['by_puid']['fmt/14'],2)
        self.assertEqual(meta['by_puid']['__ambiguous__'],1)
        self.assertEqual(meta['by_puid']['__unidentified__'],1)
        self.assertEqual(meta['by_puid']['__error__'],1)
        self.assertEqual(len(file_page(self.snapshot,meta)['rows']),6)

    def test_archive_part_only_exact_document_references(self):
        meta = self.build()
        group_a = format_groups(self.snapshot,meta,'part-A')
        self.assertEqual([(g['puid'],g['count']) for g in group_a],[('fmt/14',1)])
        part_b = file_page(self.snapshot, meta, part_id='part-B')
        self.assertEqual(part_b['total'],1)
        row = part_b['rows'][0]
        self.assertEqual(row['doc_id'],'obj-2')
        self.assertEqual(row['description_id'],'desc-2')
        self.assertGreater(row['xml_line'],0)
        self.assertEqual(file_page(self.snapshot,meta,part_id='part-A')['total'],1)
        self.assertEqual(file_page(self.snapshot,meta)['total'],6)

    def test_selected_formats_and_page_search(self):
        meta = self.build()
        result = file_page(self.snapshot,meta,puids=['fmt/14'],page_size=1)
        self.assertEqual(result['total'],2)
        self.assertEqual(result['pages'],2)
        self.assertEqual(file_page(self.snapshot,meta,puids=['fmt/14'],page=1,page_size=1)['total'],2)
        self.assertEqual(file_page(self.snapshot,meta,search='a.pdf')['total'],1)
        self.assertEqual(file_page(self.snapshot,meta,status='ambiguous')['total'],1)
        with self.assertRaises(DocumentWorkbenchError):
            file_page(self.snapshot,meta,page_size=10000)

    def test_cache_is_used_after_success_and_no_extra_reports(self):
        meta=self.build()
        cached=find_document_index(self.snapshot)
        self.assertEqual(cached['index_sha256'],meta['index_sha256'])
        self.assertEqual(self.build()['index_sha256'],meta['index_sha256'])
        self.assertEqual(len(list((self.work/'noark5_evidence'/'document_formats_v027_a6').glob('*.sqlite'))),1)

    def test_cache_rejects_changed_report_and_index(self):
        meta=self.build()
        self.report.write_text('{}',encoding='utf-8')
        self.assertIsNone(find_document_index(self.snapshot))
        with self.assertRaises(DocumentWorkbenchError):
            file_page(self.snapshot,meta)

    def test_cache_rejects_modified_index(self):
        meta=self.build()
        path=self.work/meta['index_relative_path']
        with path.open('ab') as f: f.write(b'tampered')
        self.assertIsNone(find_document_index(self.snapshot))

    def test_siegfried_source_is_checked_against_work_job_definition(self):
        # No separate XML reader or test stub may authorize a foreign Source.
        foreign = self.root / 'other_source'
        foreign.mkdir()
        self.run_manifest['source_root'] = str(foreign)
        (self.run_dir / 'manifest.json').write_text(
            json.dumps(self.run_manifest), encoding='utf-8')
        with self.assertRaisesRegex(DocumentWorkbenchError, 'tilhører ikke valgt Work-jobb'):
            self.build()

    def test_document_source_checks_work_identity_not_xml_reader_stub(self):
        # In the complete Windows test suite a module stub may be stale.
        # The job.json Source and Siegfried run identity are authoritative.
        import app.ks_xml_evidence_v023_a19 as evidence
        previous = evidence._job_sources
        try:
            evidence._job_sources = lambda _work: []
            self.assertEqual(self.build()['files_total'], 6)
        finally:
            evidence._job_sources = previous

    def test_source_path_alias_is_normalized_against_work_job(self):
        # A syntactically different path to the *same* directory is safe.
        # Windows may normalize temporary directory paths on resolve().
        self.run_manifest['source_root'] = str(self.source / 'DOKUMENT' / '..')
        (self.run_dir / 'manifest.json').write_text(
            json.dumps(self.run_manifest), encoding='utf-8')
        self.assertEqual(self.build()['files_total'], 6)

    def test_wrong_work_uid_rejected(self):
        self.snapshot.job_uid='another'
        with self.assertRaises(ValueError):
            self.build()

    def test_wrong_siegfried_uid_rejected(self):
        self.run_manifest['job_uid']='another'
        (self.run_dir/'manifest.json').write_text(json.dumps(self.run_manifest),encoding='utf-8')
        with self.assertRaises(DocumentWorkbenchError):
            self.build()

    def test_raw_and_inventory_hashes_must_match(self):
        with (self.run_dir/'siegfried_files.jsonl').open('a') as out: out.write('{}\n')
        with self.assertRaises(DocumentWorkbenchError):
            self.build()

    def test_raw_path_alias_resolves_to_exact_inventoried_file(self):
        # Windows Source roots can have a different lexical name from their
        # resolved path.  A physical alias is valid when it is the SAME file.
        alias = self.root / 'source_alias'
        try:
            alias.symlink_to(self.source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks not available on this Windows test account')
        raw = self.run_dir / 'siegfried_files.jsonl'
        records = raw.read_text(encoding='utf-8').splitlines()
        first = json.loads(records[0])
        first['filename'] = str(alias / 'DOKUMENT' / 'sub' / 'a.pdf')
        records[0] = json.dumps(first)
        raw.write_text('\n'.join(records) + '\n', encoding='utf-8', newline='\n')
        self.run_manifest['raw_sha256'] = digest(raw)
        (self.run_dir / 'manifest.json').write_text(
            json.dumps(self.run_manifest), encoding='utf-8')
        self.assertEqual(self.build()['files_total'], 6)

    def test_raw_hardlink_alias_is_not_a_different_inventory_entry(self):
        # Same inode, different Source path must NOT authorize a wrong PUID.
        alias = self.source / 'DOKUMENT' / 'sub' / 'alias.pdf'
        try:
            import os
            os.link(self.source / 'DOKUMENT' / 'sub' / 'a.pdf', alias)
        except (OSError, NotImplementedError):
            self.skipTest('Hard links not available on this filesystem')
        raw = self.run_dir / 'siegfried_files.jsonl'
        records = raw.read_text(encoding='utf-8').splitlines()
        first = json.loads(records[0])
        first['filename'] = str(alias)
        records[0] = json.dumps(first)
        raw.write_text('\n'.join(records) + '\n', encoding='utf-8', newline='\n')
        self.run_manifest['raw_sha256'] = digest(raw)
        (self.run_dir / 'manifest.json').write_text(
            json.dumps(self.run_manifest), encoding='utf-8')
        with self.assertRaisesRegex(DocumentWorkbenchError, 'ulike filer'):
            self.build()

    def test_raw_filename_must_correspond_to_inventory(self):
        raw=self.run_dir/'siegfried_files.jsonl'
        records=raw.read_text().splitlines()
        obj=json.loads(records[0]);obj['filename']=str(self.source/'DOKUMENT/other/b.doc')
        records[0]=json.dumps(obj)
        raw.write_text('\n'.join(records)+'\n',encoding='utf-8')
        self.run_manifest['raw_sha256']=digest(raw)
        (self.run_dir/'manifest.json').write_text(json.dumps(self.run_manifest),encoding='utf-8')
        with self.assertRaisesRegex(DocumentWorkbenchError,'ulike filer'):
            self.build()

    def test_cancelled_index_leaves_no_manifest(self):
        with self.assertRaisesRegex(DocumentWorkbenchError,'Avbrutt|avbrutt'):
            build_document_index(self.snapshot,cancelled=lambda:True)
        folder=self.work/'noark5_evidence'/'document_formats_v027_a6'
        self.assertEqual(list(folder.glob('*.json')) if folder.exists() else [],[])

    def test_copy_puid_subfolders_and_manifest_with_verified_hashes(self):
        meta=self.build()
        original=(self.source/'DOKUMENT/sub/a.pdf').read_bytes()
        output=copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                   destination=self.output)
        target=Path(output['path'])
        self.assertEqual(output['files_copied'],2)
        self.assertTrue((target/'fmt_14'/'a.pdf').is_file())
        self.assertEqual((target/'fmt_14'/'a.pdf').read_bytes(),original)
        rows=[json.loads(x) for x in (target/'kopimanifest.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['sha256'],sha256(original).hexdigest())
        self.assertTrue((target/'sammendrag.json').is_file())
        self.assertEqual((self.source/'DOKUMENT/sub/a.pdf').read_bytes(),original)

    def test_copy_flat_handles_equal_filename_collision(self):
        self.rows.append(('DOKUMENT/other/a.pdf',b'Second same basename',
                          [{'id':'fmt/14','format':'PDF'}],''))
        self.write_run()
        meta=self.build()
        output=copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                   destination=self.output,structure='flat')
        files=list(Path(output['path']).glob('*.pdf'))
        self.assertEqual(len(files),3)
        self.assertEqual(len({p.name.casefold() for p in files}),3)

    def test_copy_specific_part_only_one_document(self):
        meta=self.build()
        output=copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                   destination=self.output,part_id='part-A')
        self.assertEqual(output['files_copied'],1)

    def test_changed_xml_blocks_part_scoped_copy(self):
        meta = self.build()
        self.xml.write_text(self.xml.read_text().replace('part-A','part-Z'),encoding='utf-8')
        with self.assertRaisesRegex(DocumentWorkbenchError,'XML-kilden er endret'):
            copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                destination=self.output,part_id='part-A')
        self.assertFalse(list(self.output.iterdir()))

    def test_bad_newer_same_job_run_cannot_fall_back_to_older_one(self):
        newer = self.run_dir.parent/'20261126T000000Z-1234567890'
        newer.mkdir()
        data = {**self.run_manifest,'run_id':newer.name}
        (newer/'manifest.json').write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(DocumentWorkbenchError,'mangler komplett råinventar'):
            self.build()

    def test_copy_reports_real_hash_without_changing_work_report(self):
        meta = self.build()
        original = self.report.read_bytes()
        output = copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                     destination=self.output)
        root = Path(output['path'])
        summary = json.loads((root/'sammendrag.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['work_job_uid'],self.uid)
        self.assertEqual(summary['source_run_id'],meta['run_id'])
        self.assertEqual(summary['file_manifest_sha256'],digest(root/'kopimanifest.jsonl'))
        self.assertEqual(original,self.report.read_bytes())

    def test_output_inside_source_or_work_rejected(self):
        meta=self.build()
        for dest in (self.source,self.work):
            with self.assertRaises(DocumentWorkbenchError):
                copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                    destination=dest)

    def test_changed_source_prevents_copying_any_final_output(self):
        meta=self.build()
        (self.source/'DOKUMENT/sub/a.pdf').write_bytes(b'file changed')
        with self.assertRaises(DocumentWorkbenchError):
            copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                destination=self.output)
        self.assertFalse(list(self.output.iterdir()))

    def test_copy_cancellation_cleans_staging(self):
        meta=self.build()
        with self.assertRaisesRegex(DocumentWorkbenchError,'avbrutt'):
            copy_selected_files(self.snapshot,meta,selected_puids=['fmt/14'],
                                destination=self.output,cancelled=lambda:True)
        self.assertFalse(list(self.output.iterdir()))

    def test_same_work_annotation_store_for_format_assessment(self):
        meta=self.build()
        memory=[]
        ledger=ModuleType('noark5_workflow.analysis.depot_annotations')
        def save(path,**kwargs):
            memory.append({'target':{'view_id':kwargs['view_id'],
                                     'target_id':kwargs['target_id'],
                                     'target_type':kwargs['target_type']},
                           'text':kwargs['text'],'annotation_type':kwargs['annotation_type']})
            return memory[-1]
        def read(path,**filters):
            return [x for x in memory if all(x['target'].get(k)==v for k,v in filters.items())]
        ledger.record_depot_annotation=save
        ledger.list_depot_annotations=read
        with patch.dict(sys.modules,{'noark5_workflow':ModuleType('noark5_workflow'),
                                     'noark5_workflow.analysis':ModuleType('noark5_workflow.analysis'),
                                     'noark5_workflow.analysis.depot_annotations':ledger}):
            save_format_annotation(self.snapshot,meta,'fmt/14',assessment='deviation',
                                   kind='note',text='Krever begrunnelse',user=object())
            self.assertEqual(latest_assessment(self.snapshot,meta,'fmt/14'),'deviation')
            self.assertEqual(len(format_annotations(self.snapshot,meta,'fmt/14')),1)
            self.assertEqual(memory[0]['annotation_type'],'deviation')
            self.assertEqual(memory[0]['target']['view_id'],'analysis')
            self.assertEqual(self.report.read_text(),'{"report_type": "noark5_depot_validation"}')

    def test_format_types_and_unknown_format_not_approved(self):
        self.assertEqual(_raw_record({'matches':[]})[0],'__unidentified__')
        self.assertEqual(_raw_record({'matches':[{'id':'fmt/14'},{'id':'fmt/18'}]})[0],
                         '__ambiguous__')
        self.assertEqual(_raw_record({'matches':[],'errors':'failure'})[0],'__error__')
        module = ModuleType('app.format_assessment_v0111_a2')
        module.FORMAT_SOURCE_NASJONALARKIVET = 'nasjonalarkivet_2026_11_10'
        module.FORMAT_SOURCE_ARKADE_RAF = 'arkade_raf220301'
        module.historical_arkade_status = lambda raw: SimpleNamespace(label='Ukjent')
        with patch.dict(sys.modules, {'app.format_assessment_v0111_a2': module}):
            self.assertIn('ikke',format_policy_label('__unidentified__','nasjonalarkivet_2026_11_10')[1].lower())

    def test_path_traversal_and_absolute_paths_rejected(self):
        for path in ('../escape','DOKUMENT/../../escape','C:/untrusted','/etc/passwd',
                     'DOKUMENT\\thing','DOKUMENT//file.pdf'):
            with self.subTest(path=path):
                with self.assertRaises(DocumentWorkbenchError):
                    _safe_file(self.source,path)
        self.assertEqual(_normalized_ref('DOKUMENT/sub/a.pdf'),'dokument/sub/a.pdf')
        self.assertEqual(_normalized_ref('a.pdf'),'')
        self.assertEqual(_normalized_ref('../DOKUMENT/a.pdf'),'')

    def test_xml_ambiguous_reference_is_not_attached_to_part(self):
        text=self.xml.read_text()
        # Two document objects refer to the same physical file in different parts.
        text=text.replace('DOKUMENT/other/b.doc','DOKUMENT/sub/a.pdf')
        self.xml.write_text(text)
        self.snapshot.report['delivery_validation']['source_sha256']=digest(self.xml)
        meta=self.build()
        self.assertEqual(file_page(self.snapshot,meta,part_id='part-A')['total'],0)
        self.assertEqual(file_page(self.snapshot,meta,part_id='part-B')['total'],0)
        self.assertEqual(file_page(self.snapshot,meta)['total'],6)

    def test_without_attested_xml_scope_remains_unavailable(self):
        self.snapshot.report['delivery_validation']['complete']=False
        meta=self.build()
        self.assertEqual(meta['xml_mapping']['state'],'not_attested')
        with self.assertRaises(DocumentWorkbenchError):
            file_page(self.snapshot,meta,part_id='part-A')
        self.assertEqual(file_page(self.snapshot,meta)['total'],6)

    def test_same_source_verification_does_not_modify_xml(self):
        orig=self.xml.read_bytes()
        self.build()
        self.assertEqual(self.xml.read_bytes(),orig)


class WiringTests(unittest.TestCase):
    def test_a6_after_a5_and_original_qt_pipeline(self):
        main=(ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(main)
        self.assertLess(main.index('install_analysis_workspace_v4(window)'),
                        main.index('install_analysis_workspace_v5(window)'))
        self.assertLess(main.index('install_analysis_workspace_v5(window)'),
                        main.index('install_analysis_workspace_v6(window)'))
        self.assertIn("if hasattr(window, '_toolbar'):",main)
        self.assertIn('install_integrated_home(window)',main)
        source=(ROOT/'gui_qt/noark5_document_workbench_v027_a6.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('class AnalysisWorkspaceDialogV6(AnalysisWorkspaceDialogV5)',source)
        self.assertIn('QThread',source)
        self.assertIn('QFileDialog',source)
        self.assertIn('QListWidget',source)
        self.assertIn('Kopier filtrerte filtyper',source)

    def test_version_and_distribution_match_without_alpha_lock(self):
        import tomllib
        from version import VERSION
        with (ROOT/'pyproject.toml').open('rb') as inp:
            self.assertEqual(tomllib.load(inp)['project']['version'],VERSION.replace('-a','a'))


if __name__ == '__main__':
    unittest.main()
