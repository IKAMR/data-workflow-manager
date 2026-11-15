"""a7: source-first, read-only QA coverage matrix; never a Noark pass."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.sax.saxutils import quoteattr
from zipfile import ZipFile

from app.noark5_requirement_matrix_v021_a7 import (
    build_matrix, markdown_summary, write_reports, main, REPORT_FILES, REPORT_TYPE,
    filter_matrix_rows,
)
from app.noark_semantic_values_v021_a6 import load_registry


class TestA7Matrix(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src=Path(tmp.name)/'digital-archive-workflow'
        self.dwm=Path(tmp.name)/'data-workflow-manager'
        self.config=self.dwm/'config/noark5/standards'
        self.config.mkdir(parents=True)
        self.registry = load_registry()
        (self.config/'noark5_semantic_values_v021_a6.json').write_text(
            json.dumps(self.registry,ensure_ascii=False),encoding='utf-8')
        for version in ('3.1','4.0','5.0'):
            (self.config/'metadata').mkdir(exist_ok=True)
            (self.config/'requirements').mkdir(exist_ok=True)
            (self.config/'metadata'/f'{version}.json').write_text(json.dumps({
                'metadata':[{'metadata_id':'M619'}]}),encoding='utf-8')
            (self.config/'requirements'/f'{version}.json').write_text(json.dumps({
                'requirements':[{'requirement_id':'R1','xml_field_name':'avskrivningsmaate'}]
            }),encoding='utf-8')
        (self.dwm/'config/noark5/tests').mkdir(parents=True)
        (self.dwm/'config/noark5/tests/xpath_catalog_2026_05_26.json').write_text(
            json.dumps({'tests':[
                {'test_id':'kdrs.f06','legacy':{'job_id':'F06'},
                 'source_xml':'arkivstruktur.xml', 'noark_versions':['3.1','4.0','5.0'],
                 'execution':{'kind':'metrics','metrics':[{
                     'id':'method_count','type':'xpath',
                     'expression':'count(//avskrivningsmaate)'}]}},
                {'test_id':'kdrs.special','noark_versions':['3.1','4.0','5.0'],
                 'execution':{'kind':'special_handler'}}
            ]}),encoding='utf-8')
        (self.config/'noark5_standard_values.json').write_text(json.dumps({
            'versions':{v:{'value_sets':{'M300_dokumentmedium':{
                'metadata_id':'M300','values':['Fysisk arkiv','Elektronisk arkiv',
                                               'Blandet fysisk og elektronisk arkiv']}}}
                        for v in ('3.1','4.0','5.0')}
        },ensure_ascii=False),encoding='utf-8')
        for v in ('3.1','4.0','5.0'):
            folder=self.src/'docs/kilder/noark/noark5'/f'v{v}'/'schemas'
            folder.mkdir(parents=True)
            defs=[]
            for mid,name in self.registry['historical_xsd_type_names_3_1_4_0'].items():
                values=self.registry['xsd_enumerations_by_version'][v].get(mid,[])
                facets=(''.join(f'<xs:enumeration value={quoteattr(value)}/>'
                                for value in values)
                        if values else '<xs:minLength value="1"/>')
                defs.append(f'<xs:simpleType name="{name}"><xs:annotation>'
                            f'<xs:documentation>{mid}</xs:documentation></xs:annotation>'
                            f'<xs:restriction base="xs:string">{facets}</xs:restriction>'
                            f'</xs:simpleType>')
            defs.append('<xs:simpleType name="systemID"><xs:annotation>'
                        '<xs:documentation>M001</xs:documentation></xs:annotation>'
                        '<xs:restriction base="xs:string"/></xs:simpleType>')
            header=f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="{v}">'
            (folder/'metadatakatalog.xsd').write_text(header+''.join(defs)+'</xs:schema>',encoding='utf-8')
            for name in ('arkivstruktur','endringslogg','loependeJournal','offentligJournal'):
                element=('<xs:element name="avskrivningsmaate" type="md:avskrivningsmaate" '
                         'minOccurs="0"/>' if name=='arkivstruktur' else '')
                (folder/f'{name}.xsd').write_text(header+element+'</xs:schema>',encoding='utf-8')
        source = self.src/'docs/kilder/noark'
        source.mkdir(parents=True,exist_ok=True)
        (self.config/'noark5_xsd_signatures_v0114_a5.json').write_text(json.dumps({
            'signatures':[{'version':v,'filename':name,'sha256':self.digest(
                source/'noark5'/f'v{v}'/'schemas'/name)}
                for v in ('3.1','4.0','5.0') for name in (
                    'arkivstruktur.xsd','endringslogg.xsd','loependeJournal.xsd',
                    'metadatakatalog.xsd','offentligJournal.xsd')]
        }),encoding='utf-8')
        self.m619_doc=self.src/'docs/kilder/noark/noark5/v4.0/spesifikasjoner/Noark5v4 vedl1 Metadatakatalog (word).docx'
        self.m619_doc.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(self.m619_doc,'w') as z:
            body='''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
                <w:p><w:r><w:t>M619 avskrivningsmåte: eksempel Besvart på telefon.</w:t></w:r></w:p>
                <w:p><w:r><w:t>2.1.4 Dette er en syntetisk teststreng og ikke normativ godkjenning.</w:t></w:r></w:p>
                </w:body></w:document>'''
            z.writestr('word/document.xml',body.encode('utf-8'))
        self.v31_xlsx=self.src/'docs/kilder/noark/noark5/v3.1/spesifikasjoner/Noark5_v3.1_tabelloversikt_krav.xlsx'
        self.v31_xlsx.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(self.v31_xlsx,'w') as z:
            xml='''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
            <row r="3"><c r="A3" t="inlineStr"><is><t>M300 dokumentmedium, test</t></is></c></row>
            </sheetData></worksheet>'''
            z.writestr('xl/worksheets/sheet1.xml',xml)
        self.make_manifest()

    @staticmethod
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def make_manifest(self):
        root=self.src/'docs/kilder/noark'
        files=[{'path':p.relative_to(root).as_posix(), 'sha256':self.digest(p),
                'source_status':'not_documented'}
                for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SOURCE-MANIFEST.json']
        (root/'SOURCE-MANIFEST.json').write_text(json.dumps({'files':files},ensure_ascii=False),encoding='utf-8')

    def matrix(self, **kwargs):
        return build_matrix(self.src,self.dwm,**kwargs)

    def test_all_fifteen_xsds_identified_exact(self):
        r=self.matrix()
        self.assertEqual(r['report_type'],REPORT_TYPE)
        self.assertEqual(len(r['source_xsd']),15)
        self.assertTrue(all(x['identity']=='identical_bytes' for x in r['source_xsd']))
        self.assertFalse(r['normative_requirements_all_read'])
        self.assertFalse(r['noark_conformance_verified'])
        self.assertFalse(r['saxon_lxml_expression_parity_verified'])
        self.assertFalse(r['source_files_modified'])

    def test_all_versions_preserved_even_with_no_normative_register(self):
        r=self.matrix()
        self.assertEqual(set(r['versions']),{'3.1','4.0','5.0'})
        self.assertEqual([r['versions'][v]['registered_requirements'] for v in ('3.1','4.0','5.0')],[1,1,1])
        self.assertTrue(all(entry['normative_validation_verified'] is False for ver in r['versions'].values()
                            for entry in ver['metadata_rows']))
        self.assertEqual(len(r['versions']['4.0']['metadata_rows']),18)

    def test_m619_exact_source_line_and_document_anchor(self):
        r=self.matrix()
        row=next(x for x in r['versions']['4.0']['metadata_rows'] if x['metadata_id']=='M619')
        self.assertIn('Besvart på telefon',row['enumeration_literals'])
        self.assertIn('Besvart med notat',row['enumeration_literals'])
        self.assertIsInstance(row['xsd_type_definition_line'],int)
        self.assertEqual(row['xpath_lexical_test_ids'],['kdrs.f06'])
        self.assertIn('M619',row['document_references'][0]['excerpt'])
        self.assertTrue(row['document_references'][0]['location'].startswith('word/document.xml:p'))
        self.assertFalse(row['document_references'][0]['is_pdf_page_reference'])
        self.assertFalse(row['document_references_are_only_candidates'] is False)

    def test_xlsx_source_anchor_is_row_not_pdf_page(self):
        r=self.matrix()
        row=next(x for x in r['versions']['3.1']['metadata_rows'] if x['metadata_id']=='M300')
        self.assertEqual(row['document_references'][0]['location'],'xl/worksheets/sheet1.xml:row3')
        self.assertFalse(row['document_references'][0]['is_pdf_page_reference'])

    def test_m300_value_disagreement_requires_qa_not_auto_fix(self):
        r=self.matrix()
        for version in ('3.1','4.0'):
            row=next(x for x in r['versions'][version]['metadata_rows'] if x['metadata_id']=='M300')
            self.assertTrue(row['value_set_mismatch_from_xsd'])
            self.assertEqual(row['qa_severity'],'WARNING')
            self.assertEqual(row['qa_reason'],'dwm_value_list_differs_from_xsd_qa')
            self.assertFalse(row['normative_validation_verified'])
        self.assertFalse(next(x for x in r['versions']['5.0']['metadata_rows'] if x['metadata_id']=='M300')['value_set_mismatch_from_xsd'])

    def test_does_not_promote_lexical_number_to_requirement(self):
        r=self.matrix()
        self.assertIn('2.1.4',r['versions']['4.0']['documents'][0]['requirement_number_lexical_examples'])
        self.assertFalse(any(x.get('requirement_id')=='2.1.4'
                             for x in r['versions']['4.0']['requirement_rows']))
        self.assertFalse(r['versions']['4.0']['requirement_rows'][0]['normative_validation_verified'])

    def test_xsd_typed_reference_and_xpath_candidate_are_not_proofs(self):
        r=self.matrix()
        row=next(x for x in r['versions']['4.0']['metadata_rows'] if x['metadata_id']=='M619')
        self.assertEqual(row['xsd_structural_type_reference_candidates'][0]['file'],'arkivstruktur.xsd')
        self.assertEqual(row['qa_reason'],'lexical_xpath_candidate_not_implementation_proof')
        self.assertFalse(row['normative_validation_verified'])

    def test_version_diffs_are_source_declarations_not_normative(self):
        r=self.matrix()
        changed=[x for x in r['technical_xsd_version_differences'] if x['metadata_id']=='M619']
        self.assertEqual([(x['from'],x['to']) for x in changed],[('3.1','4.0'),('4.0','5.0')])
        self.assertTrue(all(x['technical_xsd_change_not_normative_interpretation'] for x in changed))

    def test_content_changed_schema_is_a_qa_conflict(self):
        p=self.src/'docs/kilder/noark/noark5/v4.0/schemas/metadatakatalog.xsd'
        raw=p.read_bytes()
        self.assertIn(b'Besvart p',raw)
        p.write_bytes(raw.replace('Besvart på telefon'.encode('utf-8'),
                                  'Besvart via telefon'.encode('utf-8')))
        r=self.matrix()
        row=next(x for x in r['source_xsd'] if x['noark_version']=='4.0' and x['file'].endswith('metadatakatalog.xsd'))
        self.assertEqual(row['identity'],'hash_mismatch_qa')  # raw changed relative to manifest: unexpected\n        self.assertIn('xsd_identity_conflict',[x['kind'] for x in r['qa_issues']])

    def test_lf_checkout_matches_manifest_original_crlf(self):
        # Manifest was recorded with CRLF original, checkout now LF only.
        p=self.src/'docs/kilder/noark/noark5/v3.1/schemas/arkivstruktur.xsd'
        original=p.read_bytes().replace(b'><',b'>\n<')
        p.write_bytes(original)
        crlf=original.replace(b'\n',b'\r\n')
        m=self.src/'docs/kilder/noark/SOURCE-MANIFEST.json'
        reg=json.loads(m.read_text(encoding='utf-8'))
        for item in reg['files']:
            if item['path']=='noark5/v3.1/schemas/arkivstruktur.xsd':
                item['sha256']=hashlib.sha256(crlf).hexdigest()
        m.write_text(json.dumps(reg),encoding='utf-8')
        signatures=self.config/'noark5_xsd_signatures_v0114_a5.json'
        known=json.loads(signatures.read_text(encoding='utf-8'))
        for entry in known['signatures']:
            if entry['version']=='3.1' and entry['filename']=='arkivstruktur.xsd':
                entry['sha256']=hashlib.sha256(crlf).hexdigest()
        signatures.write_text(json.dumps(known),encoding='utf-8')
        r=self.matrix()
        row=next(x for x in r['source_xsd'] if x['noark_version']=='3.1' and x['file'].endswith('arkivstruktur.xsd'))
        self.assertEqual(row['identity'],'matches_original_after_restoring_crlf')
        self.assertFalse(any(x['kind']=='xsd_identity_conflict' for x in r['qa_issues']))

    def test_manifest_signature_conflict_detected(self):
        sig=self.config/'noark5_xsd_signatures_v0114_a5.json'
        item=json.loads(sig.read_text(encoding='utf-8'))
        item['signatures'][0]['sha256']='0'*64
        sig.write_text(json.dumps(item),encoding='utf-8')
        r=self.matrix()
        self.assertIn('dwm_xsd_signature_manifest_conflict',[x['kind'] for x in r['qa_issues']])

    def test_missing_specification_document_is_issue(self):
        self.m619_doc.unlink()
        r=self.matrix()
        self.assertIn('specification_file_missing',[x['kind'] for x in r['qa_issues']])
        self.assertEqual(r['versions']['4.0']['documents_not_read_or_unavailable'],[
            'noark5/v4.0/spesifikasjoner/Noark5v4 vedl1 Metadatakatalog (word).docx'])

    def test_changed_specification_file_is_sha_qa(self):
        self.m619_doc.write_bytes(self.m619_doc.read_bytes()+b'altered')
        r=self.matrix()
        self.assertIn('specification_hash_conflict',[x['kind'] for x in r['qa_issues']])

    def test_missing_schema_is_not_reported_as_success(self):
        (self.src/'docs/kilder/noark/noark5/v3.1/schemas/arkivstruktur.xsd').unlink()
        with self.assertRaises(ValueError):
            self.matrix()

    def test_skip_document_text_is_explicit_and_no_anchors(self):
        r=self.matrix(scan_documents=False)
        self.assertFalse(r['document_text_scanned'])
        self.assertTrue(all(f['readable_sections']==0 for ver in r['versions'].values() for f in ver['documents']))
        self.assertTrue(all(not row['document_references'] for ver in r['versions'].values()
                            for row in ver['metadata_rows']))

    def test_cannot_write_into_source_or_dwm(self):
        r=self.matrix()
        with self.assertRaises(ValueError):
            write_reports(r,self.src,self.dwm,self.dwm/'reports')
        with self.assertRaises(ValueError):
            write_reports(r,self.src,self.dwm,self.src/'reports')

    def test_cli_report_files_and_no_overwrite(self):
        with TemporaryDirectory() as directory:
            ret=main(['--source-root',str(self.src),'--dwm-root',str(self.dwm),
                      '--output-dir',directory])
            self.assertEqual(ret,0)
            produced=sorted(p.name for p in Path(directory).iterdir())
            self.assertEqual(produced,sorted(REPORT_FILES))
            doc=json.loads((Path(directory)/REPORT_FILES[0]).read_text(encoding='utf-8'))
            self.assertFalse(doc['noark_conformance_verified'])
            self.assertIn('M619',(Path(directory)/'noark5-a7-metadata.csv').read_text(encoding='utf-8'))
            with self.assertRaises(SystemExit):
                main(['--source-root',str(self.src),'--dwm-root',str(self.dwm),
                      '--output-dir',directory])

    def test_report_does_not_change_source_or_xsd(self):
        paths=[self.m619_doc,self.v31_xlsx,
               self.src/'docs/kilder/noark/noark5/v4.0/schemas/metadatakatalog.xsd']
        before={str(p):self.digest(p) for p in paths}
        r=self.matrix()
        with TemporaryDirectory() as directory:
            write_reports(r,self.src,self.dwm,directory)
        self.assertEqual(before,{str(p):self.digest(p) for p in paths})

    def test_gui_tab_is_existing_dialog_and_filters(self):
        path=Path(__file__).resolve().parents[1]/'gui_qt/noark5_xpath_audit_v021_a1.py'
        source=path.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('Kravmatrise og XSD',source)
        self.assertIn('self._render_coverage()',source)
        self.assertIn('A7_MATRIX_REPORT_TYPE',source)
        self.assertIn("('FEIL - kildekonflikt', 'FEIL')",source)
        self.assertIn('self.coverage_table',source)

    def test_gui_filters_are_pure_and_severity_distinct(self):
        r=self.matrix()
        all_rows=filter_matrix_rows(r)
        warnings=filter_matrix_rows(r,severity='WARNING')
        notes=filter_matrix_rows(r,severity='NOTE')
        errors=filter_matrix_rows(r,severity='FEIL')
        self.assertGreater(len(all_rows),len(warnings))
        self.assertTrue(all(row['severity']=='WARNING' for row in warnings))
        self.assertTrue(all(row['severity']=='NOTE' for row in notes))
        self.assertEqual(errors,[])
        filtered=filter_matrix_rows(r,version='4.0',severity='WARNING',query='M300')
        self.assertEqual(len(filtered),2)  # metadata row + QA issue
        self.assertTrue(all(row['version']=='4.0' for row in filtered))
        with self.assertRaises(ValueError):
            filter_matrix_rows(r,version='6.0')
        with self.assertRaises(ValueError):
            filter_matrix_rows(r,severity='PASS')

    def test_numbered_text_candidates_are_not_requirements(self):
        r=self.matrix()
        self.assertIn('4.0:2.1.4',r['numbered_document_text_candidates'])
        candidates=r['numbered_document_text_candidates']['4.0:2.1.4']
        self.assertEqual(candidates[0]['kind'],'numbered_text_candidate_not_verified_requirement')
        self.assertTrue(r['numbered_document_text_candidates_are_not_normative_requirements'])
        self.assertFalse(r['normative_requirements_all_read'])

    def test_extract_testable_requirement_without_implementation_is_warning(self):
        path=self.config/'requirements/5.0.json'
        value=json.loads(path.read_text(encoding='utf-8'))
        value['requirements'].append({
            'requirement_id':'synthetic.m619.mandatory',
            'noark_version':'5.0', 'related_metadata_id':'M619',
            'xml_field_name':'avskrivningsmaate',
            'extract_validation':{'directly_testable_from_extract':True,
                                  'implemented_as_dwm_control':False}})
        path.write_text(json.dumps(value),encoding='utf-8')
        r=self.matrix()
        added=next(x for x in r['versions']['5.0']['requirement_rows']
                   if x['requirement_id']=='synthetic.m619.mandatory')
        self.assertEqual(added['qa_severity'],'WARNING')
        self.assertEqual(added['qa_reason'],
                         'extract_testable_requirement_without_verified_dwm_control')
        self.assertFalse(added['normative_validation_verified'])

    def test_pdf_document_evidence_uses_pdf_page_not_docx_coordinate(self):
        try:
            import fitz
        except ImportError:
            self.skipTest('PyMuPDF optional; PDF text extraction not installed')
        path=self.src/'docs/kilder/noark/noark5/v5.0/spesifikasjoner/Noark 5 v 5.pdf'
        path.parent.mkdir(parents=True,exist_ok=True)
        document=fitz.open()
        page=document.new_page()
        page.insert_text((45,52),'M619 example metadata from synthetic source text')
        document.save(str(path))
        document.close()
        self.make_manifest()
        result=self.matrix()
        entry=next(x for x in result['versions']['5.0']['metadata_rows'] if x['metadata_id']=='M619')
        self.assertEqual(entry['document_references'][0]['location'],'page1')
        self.assertTrue(entry['document_references'][0]['is_pdf_page_reference'])
        self.assertTrue(entry['document_references'][0]['source_hash_verified'])

    def test_version_guards(self):
        root=Path(__file__).resolve().parents[1]
        version=(root/'version.py').read_text(encoding='utf-8')
        self.assertIn('0.2.1-a7',version)
        self.assertIn('version = "0.2.1a7"',(root/'pyproject.toml').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
