"""A7 regression: PUID-first view, durable copy history and bounded drill-down."""
from __future__ import annotations

import ast
from contextlib import closing
from hashlib import sha256
import importlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from app.noark5_document_workbench_v027_a6 import (
    DocumentWorkbenchError, build_document_index, copy_selected_files,
)
from app.noark5_format_overview_v027_a7 import (
    HISTORY_FILE, copied_page_counts, copy_totals, copy_with_history,
    export_history, file_page_seek, mime_category, puid_overview,
    record_copy_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


class PuidOverviewTests(unittest.TestCase):
    def setUp(self):
        # The live A6 fixture uses the full registered Work and Source layout.
        # Avoid a second, drift-prone imitation of the Siegfried raw manifest.
        prior = importlib.import_module('test_v027_a6_document_workbench')
        self.write_run = prior.DocumentTest.write_run.__get__(self)
        prior.DocumentTest.setUp(self)
        self.meta = build_document_index(self.snapshot)

    def test_grouped_summary_is_a_puid_overview_not_a_file_list(self):
        rows = puid_overview(self.snapshot, self.meta)
        self.assertEqual(sum(x['files'] for x in rows), 6)
        by_puid = {x['puid']: x for x in rows}
        self.assertEqual(by_puid['fmt/14']['files'], 2)
        self.assertEqual(by_puid['fmt/14']['mime'], 'application/pdf')
        self.assertEqual(by_puid['fmt/14']['group'], 'PDF')
        self.assertEqual(by_puid['__unidentified__']['mime'], 'ukjent')
        self.assertEqual(by_puid['fmt/14']['copy_events'], 0)
        self.assertEqual(len(rows), 5)

    def test_mime_is_clearly_heuristic_and_never_an_approval(self):
        self.assertEqual(mime_category('fmt/14', 'Portable Document Format'),
                         ('PDF', 'application/pdf'))
        self.assertEqual(mime_category('x-fmt/280', 'XML Schema Definition'),
                         ('XML', 'application/xml'))
        self.assertEqual(mime_category('fmt/44', 'JPEG File Interchange Format'),
                         ('Bilde', 'image/*'))
        self.assertEqual(mime_category('__ambiguous__', 'PDF'), ('Ukjent', 'ukjent'))
        self.assertEqual(mime_category('fmt/77777', 'Completely Unknown'),
                         ('Annet / ukjent', 'ukjent'))

    def test_verified_part_filter_only_counts_mapped_files(self):
        part = puid_overview(self.snapshot, self.meta, part_id='part-A')
        self.assertEqual([(r['puid'],r['files']) for r in part], [('fmt/14',1)])
        other = puid_overview(self.snapshot, self.meta, part_id='part-B')
        self.assertEqual([(r['puid'],r['files']) for r in other], [('x-fmt/263',1)])
        no_xml = {**self.meta, 'xml_mapping': {'state':'not_available'}}
        # A modified manifest must fail before allowing a fake part filter.
        with self.assertRaises(DocumentWorkbenchError):
            puid_overview(self.snapshot, no_xml, part_id='part-A')

    def test_seek_pagination_has_no_offset_and_only_one_puid(self):
        first = file_page_seek(self.snapshot, self.meta, puid='fmt/14',limit=1)
        self.assertTrue(first['has_next'])
        self.assertEqual(len(first['rows']), 1)
        self.assertEqual(first['rows'][0]['copies_recorded'], 0)
        second = file_page_seek(self.snapshot, self.meta, puid='fmt/14',
                                after_id=first['next_cursor'],limit=1)
        self.assertFalse(second['has_next'])
        self.assertNotEqual(first['rows'][0]['rel'],second['rows'][0]['rel'])
        self.assertEqual(len(second['rows']),1)
        self.assertEqual(file_page_seek(self.snapshot,self.meta,puid='fmt/14',
                                       search='a.pdf')['rows'][0]['rel'],
                         'DOKUMENT/sub/a.pdf')
        with self.assertRaises(DocumentWorkbenchError):
            file_page_seek(self.snapshot, self.meta, puid='fmt/14',limit=1000)
        with self.assertRaises(DocumentWorkbenchError):
            file_page_seek(self.snapshot, self.meta, puid='fake/type')

    def test_absent_history_is_not_a_claim_about_older_a6_copies(self):
        self.assertFalse((self.work / HISTORY_FILE).exists())
        self.assertEqual(copy_totals(self.snapshot,self.meta), {})
        self.assertEqual(export_history(self.snapshot,self.meta), ())
        self.assertEqual(copied_page_counts(self.snapshot,self.meta,
                         ['DOKUMENT/sub/a.pdf']), {})

    def test_successful_copy_creates_work_only_receipts(self):
        before = (self.source / 'DOKUMENT/sub/a.pdf').read_bytes()
        out = copy_with_history(self.snapshot,self.meta,selected_puids=('fmt/14',),
                                destination=self.output)
        self.assertEqual(out['history_state'], 'recorded')
        self.assertEqual(out['files_copied'], 2)
        self.assertTrue((self.work / HISTORY_FILE).is_file())
        totals = copy_totals(self.snapshot,self.meta)
        self.assertEqual(totals['fmt/14']['copies'], 2)
        self.assertEqual(totals['fmt/14']['exports'], 1)
        self.assertEqual(len(export_history(self.snapshot,self.meta)), 1)
        record = file_page_seek(self.snapshot,self.meta,puid='fmt/14')['rows']
        self.assertEqual([x['copies_recorded'] for x in record], [1,1])
        self.assertEqual((self.source / 'DOKUMENT/sub/a.pdf').read_bytes(), before)
        self.assertEqual(self.report.read_bytes(),
                         json.dumps({'report_type':'noark5_depot_validation'}).encode())

    def test_part_copy_counts_are_only_for_that_archivdel(self):
        out = copy_with_history(self.snapshot,self.meta,selected_puids=('fmt/14',),
                                destination=self.output)
        self.assertEqual(out['history_state'],'recorded')
        self.assertEqual(copy_totals(self.snapshot,self.meta)['fmt/14']['copies'],2)
        self.assertEqual(copy_totals(self.snapshot,self.meta,part_id='part-A')
                         ['fmt/14']['copies'],1)
        self.assertNotIn('fmt/14',copy_totals(self.snapshot,self.meta,part_id='part-B'))
        a = puid_overview(self.snapshot,self.meta,part_id='part-A')
        self.assertEqual(a[0]['copy_events'],1)

    def test_receipt_replay_is_idempotent_and_does_not_duplicate_counts(self):
        original = copy_selected_files(self.snapshot,self.meta,
                                       selected_puids=['fmt/14'],destination=self.output)
        first = record_copy_receipt(self.snapshot,self.meta,original)
        second = record_copy_receipt(self.snapshot,self.meta,original)
        self.assertFalse(first['already_recorded'])
        self.assertTrue(second['already_recorded'])
        self.assertEqual(copy_totals(self.snapshot,self.meta)['fmt/14']['copies'], 2)
        with closing(sqlite3.connect(self.work / HISTORY_FILE)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM exports').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM copied_files').fetchone()[0],2)

    def test_repeated_copies_show_history_but_not_invent_unique_file_count(self):
        for i in range(2):
            out = copy_with_history(self.snapshot,self.meta,
                                    selected_puids=('fmt/14',),destination=self.output)
            self.assertEqual(out['history_state'],'recorded')
        summary = copy_totals(self.snapshot,self.meta)['fmt/14']
        self.assertEqual(summary['copies'], 4)
        self.assertEqual(summary['exports'], 2)
        self.assertEqual(len(export_history(self.snapshot,self.meta)),2)
        self.assertEqual(copied_page_counts(self.snapshot,self.meta,
                         ['DOKUMENT/sub/a.pdf']),{'DOKUMENT/sub/a.pdf':2})

    def test_format_history_is_scoped_by_run_and_puid(self):
        out = copy_with_history(self.snapshot,self.meta,
                                selected_puids=('fmt/14',),destination=self.output)
        self.assertEqual(out['history_state'],'recorded')
        totals = copy_totals(self.snapshot,self.meta)
        self.assertEqual(set(totals),{'fmt/14'})
        self.assertEqual(file_page_seek(self.snapshot,self.meta,puid='x-fmt/263')
                         ['rows'][0]['copies_recorded'],0)

    def test_failed_copy_does_not_register_receipt(self):
        (self.source / 'DOKUMENT/sub/a.pdf').write_bytes(b'CHANGED FILE')
        with self.assertRaises(DocumentWorkbenchError):
            copy_with_history(self.snapshot,self.meta,selected_puids=['fmt/14'],
                              destination=self.output)
        self.assertFalse((self.work / HISTORY_FILE).exists())
        self.assertEqual(tuple(self.output.iterdir()),())

    def test_stopped_copy_does_not_register_receipt(self):
        with self.assertRaises(DocumentWorkbenchError):
            copy_with_history(self.snapshot,self.meta,selected_puids=['fmt/14'],
                              destination=self.output,cancelled=lambda: True)
        self.assertFalse((self.work / HISTORY_FILE).exists())

    def test_changed_copy_manifest_is_rejected_without_receipt(self):
        original = copy_selected_files(self.snapshot,self.meta,
                                       selected_puids=['fmt/14'],destination=self.output)
        manifest=Path(original['manifest'])
        manifest.write_bytes(manifest.read_bytes()+b'\n')
        with self.assertRaises(DocumentWorkbenchError):
            record_copy_receipt(self.snapshot,self.meta,original)
        self.assertFalse((self.work / HISTORY_FILE).exists())

    def test_unsafe_history_symlink_reports_copy_success_with_warning(self):
        history = self.work / HISTORY_FILE
        history.parent.mkdir(exist_ok=True)
        try:
            history.symlink_to(self.report)
        except (OSError, NotImplementedError):
            self.skipTest('Windows-konto mangler symlink-tillatelse')
        output = copy_with_history(self.snapshot,self.meta,selected_puids=['fmt/14'],
                                   destination=self.output)
        self.assertEqual(output['history_state'],'not_recorded')
        self.assertTrue(Path(output['path']).is_dir())
        self.assertIn('history_warning',output)

    def test_copy_receipt_rejects_wrong_job_and_manifest(self):
        original = copy_selected_files(self.snapshot,self.meta,
                                       selected_puids=['fmt/14'],destination=self.output)
        summary=Path(original['path'])/'sammendrag.json'
        data=json.loads(summary.read_text())
        data['work_job_uid']='another-job'
        summary.write_text(json.dumps(data))
        with self.assertRaises(DocumentWorkbenchError):
            record_copy_receipt(self.snapshot,self.meta,original)
        self.assertFalse((self.work / HISTORY_FILE).exists())

    def test_paged_search_remains_bounded_for_many_indexed_files(self):
        # Augment a *temporary* immutable fixture with 2k rows and resign its
        # own test manifest. This models deep navigation without 2k GUI cells.
        db = self.work / self.meta['index_relative_path']
        with closing(sqlite3.connect(db)) as conn:
            template = conn.execute('SELECT rel,puid,fmt,version,ident_state,size,mtime_ns,'
                                    'part_id,doc_id,description_id,xml_line,search '
                                    'FROM files WHERE puid=? LIMIT 1',('fmt/14',)).fetchone()
            newrows = []
            for n in range(2000):
                raw=list(template)
                raw[0] = f'DOKUMENT/sub/synthetic-{n:05d}.pdf'
                raw[-1]=raw[0].casefold()+' fmt/14 pdf'
                newrows.append(raw)
            conn.executemany('INSERT INTO files(rel,puid,fmt,version,ident_state,size,mtime_ns,'
                             'part_id,doc_id,description_id,xml_line,search) VALUES '
                             '(?,?,?,?,?,?,?,?,?,?,?,?)',newrows)
            conn.commit()
        st=db.stat()
        newmeta={**self.meta, 'index_size':st.st_size,'index_mtime_ns':st.st_mtime_ns,
                 'index_sha256':sha256(db.read_bytes()).hexdigest(),
                 'by_puid':{**self.meta['by_puid'],'fmt/14':2002},
                 'files_total':2006}
        db.with_suffix('.json').write_text(json.dumps(newmeta))
        first = file_page_seek(self.snapshot,newmeta,puid='fmt/14',limit=50)
        self.assertEqual(len(first['rows']),50)
        self.assertTrue(first['has_next'])
        nxt=file_page_seek(self.snapshot,newmeta,puid='fmt/14',
                           after_id=first['next_cursor'],limit=50)
        self.assertTrue(nxt['rows'][0]['id']>first['rows'][-1]['id'])
        self.assertEqual(len(nxt['rows']),50)
        groups=puid_overview(self.snapshot,newmeta)
        self.assertEqual(sum(x['files'] for x in groups),2006)

    def test_large_number_of_file_paths_not_materialized_in_overview(self):
        code=(ROOT/'app/noark5_format_overview_v027_a7.py').read_text(encoding='utf-8')
        self.assertIn('SELECT fmt,version FROM files WHERE puid=? LIMIT 1', code)
        self.assertIn('ORDER BY id LIMIT ?',code)
        self.assertNotIn('OFFSET ?',code)


class WiringTests(unittest.TestCase):
    def test_a7_follows_a6_without_removing_a5(self):
        main=(ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        ast.parse(main)
        self.assertLess(main.index('install_analysis_workspace_v5(window)'),
                        main.index('install_analysis_workspace_v6(window)'))
        self.assertLess(main.index('install_analysis_workspace_v6(window)'),
                        main.index('install_analysis_workspace_v7(window)'))
        a7=(ROOT/'gui_qt/noark5_format_overview_v027_a7.py').read_text(encoding='utf-8')
        ast.parse(a7)
        for token in ('QStackedWidget','group_table','copy_with_history',
                      '_drill_to_files','_back_to_groups','_step_level',
                      'Kopihistorikk', 'AnalysisWorkspaceDialogV6'):
            self.assertIn(token,a7)
        self.assertIn('window._analysis_dialog_class = AnalysisWorkspaceDialogV7',a7)

    def test_release_versions_agree_without_alpha_lock(self):
        from version import VERSION
        import tomllib
        with (ROOT/'pyproject.toml').open('rb') as stream:
            self.assertEqual(tomllib.load(stream)['project']['version'],
                             VERSION.replace('-a','a'))


if __name__=='__main__':
    unittest.main()
