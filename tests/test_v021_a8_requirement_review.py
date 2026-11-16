"""A8 requirements QA: original evidence, not automatic Noark conformance."""
from __future__ import annotations

from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch
from zipfile import ZipFile

from app.noark5_requirement_review_v021_a8 import (
    REPORT_TYPE, A7_REPORT_TYPE, _csv_safe, _parse_pdf_requirements,
    _parse_xlsx_requirements, build_review, filter_review_rows, write_reports,
    markdown_summary,
)


class A8ReviewTest(TestCase):
    def setUp(self):
        self.dir = TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.dwm = self.root/'dwm'
        self.source = self.root/'digital-archive-workflow'
        self.dwm.mkdir()
        self.src = self.source/'docs/kilder/noark'
        self.src.mkdir(parents=True)
        self.a7 = {
            'report_type':A7_REPORT_TYPE,
            'source_repository':'IKAMR/digital-archive-workflow',
            'source_checkout_commit':'82bd59f23aafdc2386e317e5492941862c2bab9a',
            'source_checkout_commit_verified':True,
            'source_commit_matches_semantic_registry':True,
            'source_files_modified':False,
            'source_xsd':[],
            'numbered_document_text_candidates':{
                '3.1:5.12.4':[{'source':'s.xlsx','location':'row8',
                               'snippet':'5.12.4 originally UTF-8','source_sha256':'X'}],
                '4.0:01.01.18':[{'source':'s.pdf','location':'page1',
                                  'snippet':'date not a requirement','source_sha256':'Y'}],
                '5.0:9.9.9':[{'source':'s.pdf','location':'page3',
                               'snippet':'unverified number','source_sha256':'Z'}],
            },
            'versions':{v:{'documents':[], 'metadata_rows':[],
                           'requirement_rows':[], 'xsd_metadata_types':158,
                           'registered_metadata':0}
                        for v in ('3.1','4.0','5.0')},
        }
        self.make_structured_xlsx()
        self.make_pdf_placeholders()

    def add_source(self,version,name,content):
        relative=Path(f'noark5/v{version}/spesifikasjoner')/name
        path=self.src/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        self.a7['versions'][version]['documents'].append({
            'file':relative.as_posix(),
            'manifest_sha256':sha256(content).hexdigest(),
            'readable_sections':1,
        })
        return path

    def make_structured_xlsx(self):
        stream=io.BytesIO()
        with ZipFile(stream,'w') as z:
            z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
              <row r="4"><c t="inlineStr"><is><t>5.12.4</t></is></c><c t="inlineStr"><is><t>Tegnsettet til alle XML-filer skal være UTF-8.</t></is></c><c t="inlineStr"><is><t>B</t></is></c><c t="inlineStr"><is><t>Obligatorisk ved avlevering</t></is></c></row>
              <row r="5"><c t="inlineStr"><is><t>5.12.5</t></is></c><c t="inlineStr"><is><t>Utgår</t></is></c><c t="inlineStr"><is><t>O</t></is></c></row>
              <row r="6"><c t="inlineStr"><is><t>Not a requirement</t></is></c><c t="inlineStr"><is><t>blabla</t></is></c></row>
              </sheetData></worksheet>''')
        self.xlsx=self.add_source('3.1','Noark5_v3.1_tabelloversikt_krav.xlsx',stream.getvalue())

    def make_pdf_placeholders(self):
        self.pdf4=self.add_source('4.0','Noark5v4 Standard for elektronisk arkiv (01.12.2016).pdf',b'%PDF synthetic')
        self.pdf5=self.add_source('5.0','Noark 5 v 5.pdf',b'%PDF synthetic2')

    def fake_pdf(self,path):
        return ([('page3', '''Krav nr.  Type  Merknad
5.12.4 Tegnsettet til XML-filene skal være UTF-8.
01.01.18 dato som ikke er et krav
5.12.5 ...................................... 25
5.13.1 Systemet skal ha en funksjon for å opprette dokumenter.
''')], 'synthetic_pdf_text')

    def test_xlsx_has_full_cell_text_class_and_row_anchor(self):
        rows=_parse_xlsx_requirements(self.xlsx,'3.1',self.a7['versions']['3.1']['documents'][0])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['number'],'5.12.4')
        self.assertEqual(rows[0]['requirement_class'],'B')
        self.assertIn('ved avlevering',rows[0]['condition'])
        self.assertIn('UTF-8',rows[0]['text'])
        self.assertEqual(rows[0]['location'],'xl/worksheets/sheet1.xml:row4')
        self.assertFalse(rows[0]['normative_requirement_approved'])
        self.assertTrue(rows[1]['retired_text'])
        self.assertEqual(rows[1]['qa_severity'],'NOTE')

    def test_pdf_does_not_treat_date_and_toc_as_a_clause(self):
        with patch('app.noark5_requirement_review_v021_a8.read_source_document',side_effect=self.fake_pdf):
            rows,info=_parse_pdf_requirements(self.pdf4,'4.0',self.a7['versions']['4.0']['documents'][0])
        self.assertEqual([r['number'] for r in rows],['5.12.4','5.13.1'])
        self.assertEqual(rows[0]['location'],'page3:line2')
        self.assertTrue(rows[0]['pdf_columns_and_wrapped_lines_not_reconstructed'])
        self.assertTrue(rows[0]['pdf_table_header_on_page'])
        self.assertFalse(rows[0]['source_wording_independently_reviewed'])
        self.assertEqual(info['backend'],'synthetic_pdf_text')

    def test_build_full_matrix_keeps_source_kinds_separate(self):
        with patch('app.noark5_requirement_review_v021_a8.read_source_document',side_effect=self.fake_pdf):
            r=build_review(self.a7,source_root=self.source,dwm_root=self.dwm)
        self.assertEqual(r['report_type'],REPORT_TYPE)
        self.assertEqual(r['versions']['3.1']['source_candidates'],2)
        self.assertEqual(r['versions']['4.0']['source_candidates'],2)
        self.assertEqual(r['versions']['5.0']['source_candidates'],2)
        self.assertEqual(r['versions']['3.1']['a7_lexical_only'],0)
        self.assertEqual(r['versions']['4.0']['a7_lexical_only'],1)
        self.assertEqual(r['versions']['5.0']['a7_lexical_only'],1)
        self.assertFalse(r['normative_requirements_approved'])
        self.assertFalse(r['saxon_lxml_semantic_parity_verified'])
        self.assertTrue(all(x['normative_requirement_approved'] is False
                            for x in r['candidate_rows']))
        self.assertEqual(len(filter_review_rows(r,version='3.1',severity='NOTE')),1)
        self.assertEqual(len(filter_review_rows(r,origin='xlsx_numbered_row')),2)
        self.assertEqual(len(filter_review_rows(r,query='UTF-8')),3)

    def test_missing_pdf_original_is_qa_warning_not_approval(self):
        r=build_review(self.a7,source_root=None,dwm_root=self.dwm)
        self.assertEqual(r['versions']['3.1']['source_candidates'],0)
        self.assertEqual(r['versions']['3.1']['a7_lexical_only'],1)
        self.assertTrue(any(q['kind']=='source_checkout_not_supplied' for q in r['qa_issues']))
        self.assertFalse(r['original_source_checkout_supplied'])

    def test_hash_mismatch_does_not_read_modified_source(self):
        self.xlsx.write_bytes(b'WRONG')
        with patch('app.noark5_requirement_review_v021_a8.read_source_document',side_effect=self.fake_pdf):
            r=build_review(self.a7,source_root=self.source,dwm_root=self.dwm)
        self.assertEqual(r['source_tables']['3.1']['sha256_identity'],'source_sha256_mismatch')
        self.assertTrue(any(q['severity']=='FEIL' and q['kind']=='source_sha256_mismatch'
                            for q in r['qa_issues']))
        self.assertEqual(r['versions']['3.1']['source_candidates'],0)

    def test_duplicate_numbered_pdf_lines_are_not_silently_merged(self):
        def repeating(_path):
            return ([('page1','Krav nr. Type\n5.1.1 First possible requirement.'),
                     ('page2','Krav nr. Type\n5.1.1 Repeated possible requirement.')], 'pdf')
        with patch('app.noark5_requirement_review_v021_a8.read_source_document',side_effect=repeating):
            r=build_review(self.a7,source_root=self.source,dwm_root=self.dwm)
        self.assertEqual(len([x for x in r['candidate_rows']
                              if x['noark_version']=='4.0' and x['number']=='5.1.1']),2)
        self.assertIn('4.0:5.1.1',r['duplicate_number_groups'])

    def test_filter_guards_output_guard_and_existing_file(self):
        r=build_review(self.a7,dwm_root=self.dwm)
        with self.assertRaises(ValueError):
            filter_review_rows(r,version='7.0')
        with self.assertRaises(ValueError):
            filter_review_rows(r,severity='APPROVED')
        with self.assertRaises(ValueError):
            write_reports(r,self.dwm/'report',dwm_root=self.dwm)
        out=self.root/'out'
        paths=write_reports(r,out,dwm_root=self.dwm)
        self.assertEqual(len(paths),5)
        self.assertEqual(json.loads(paths[0].read_text(encoding='utf-8'))['report_type'],REPORT_TYPE)
        self.assertIn('a8',paths[1].name)
        with self.assertRaises(FileExistsError):
            write_reports(r,out,dwm_root=self.dwm)

    def test_csv_injection_protection_is_display_only(self):
        self.assertEqual(_csv_safe('=-evil'),"'=-evil")
        self.assertEqual(_csv_safe('+1'),"'+1")
        self.assertEqual(_csv_safe('Normal'),'Normal')

    def test_wrong_a7_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'a7'):
            build_review({'report_type':'wrong'})

    def test_gui_integration_is_in_existing_xpath_dialog(self):
        root=Path(__file__).resolve().parents[1]
        code=(root/'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf-8')
        for needle in ('Krav- og KDRS-review a8','_choose_a8_report','_render_a8',
                       'a8_kdrs_table','a8_origin','filter_review_rows'):
            self.assertIn(needle,code)

    def test_a8_version_matches_distribution(self):
        root=Path(__file__).resolve().parents[1]
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.1", 8)
        self.assertIn(f'version = "{VERSION.replace("-", "")}"',
                      (root/'pyproject.toml').read_text(encoding='utf-8'))


if __name__=='__main__':
    from unittest import main
    main()
