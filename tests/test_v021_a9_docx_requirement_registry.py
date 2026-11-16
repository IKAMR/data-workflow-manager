"""A9 full Word table cell, Strict OOXML, PDF identity and review QA contracts."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

from app.noark5_requirement_review_v021_a8 import REPORT_TYPE as A8_REPORT_TYPE
from app.noark5_requirement_registry_v021_a9 import (
    REPORT_TYPE, build_register, extract_docx_clauses, filter_register_rows,
    write_reports, _csv, _compare_text, _git_blob_sha1, _mark_duplicates,
)
from app.noark5_source_document_reader_v021_a7 import (
    diagnose_docx, read_source_document, read_docx_structured,
)

WORD_T = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
WORD_S = 'http://purl.oclc.org/ooxml/wordprocessingml/main'


def document_xml(ns: str, *, number: str='5.12.4', grade: str='B',
                 text: str='Tegnsettet til alle XML-filer skal være UTF-8, også ved avlevering.',
                 extra: str='', duplicate: str='') -> str:
    return f'''<w:document xmlns:w="{ns}"><w:body>
        <w:p><w:r><w:t>5.12 Krav til arkivuttrekk</w:t></w:r></w:p>
        <w:tbl>
            <w:tr><w:tc><w:p><w:r><w:t>Krav nr.</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>Kravtekst</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>Type</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>Merknad</w:t></w:r></w:p></w:tc></w:tr>
            <w:tr><w:tc><w:p><w:r><w:t>{number}</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>{grade}</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>Obligatorisk ved avlevering</w:t></w:r></w:p></w:tc></w:tr>
            {duplicate}
        </w:tbl>
        <w:p><w:r><w:t>9.9.9 Systemet skal kunne kjøre en eksempeltest uten kilde-QA.</w:t></w:r></w:p>
        {extra}
        </w:body></w:document>'''


def docx_bytes(data: str) -> bytes:
    from io import BytesIO
    buf=BytesIO()
    with ZipFile(buf,'w') as z:
        z.writestr('word/document.xml',data.encode('utf-8'))
    return buf.getvalue()


class A9RequirementRegistry(TestCase):
    def setUp(self):
        folder=TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp=Path(folder.name)
        self.source=self.tmp/'digital-archive-workflow'
        self.src=self.source/'docs/kilder/noark'
        self.src.mkdir(parents=True)
        self.manifest=[]
        self.a8={'report_type':A8_REPORT_TYPE,'normative_requirements_approved':False,
                 'source_checkout_commit':'82bd59f23aafdc2386e317e5492941862c2bab9a',
                 'versions':{v:{'source_candidates':4} for v in ('3.1','4.0','5.0')}}
        self.files={}
        spec={
            '3.1':'Noark5_v3.1_standarden',
            '4.0':'Noark5v4 Standard for elektronisk arkiv (01.12.2016)',
            '5.0':'Noark 5 v 5',
        }
        for ver,stem in spec.items():
            rel=f'noark5/v{ver}/spesifikasjoner/{stem}'
            ns=WORD_S if ver=='5.0' else WORD_T
            self.add_file(rel+'.docx',docx_bytes(document_xml(ns)),manifest=False)
            self.add_file(rel+'.pdf',b'%PDF fake reference '+ver.encode(),manifest=True)
        self.add_file('noark5/v3.1/spesifikasjoner/Noark5_v3.1_tabelloversikt_krav.xlsx',
                      self.make_xlsx(),manifest=True)
        self.write_manifest()
        self.signature_path=self.tmp/'docx_signatures.json'
        self.make_signatures()

    def make_signatures(self):
        self.signature_path.write_text(json.dumps({
            'source_repository':'IKAMR/digital-archive-workflow',
            'documents':[{'path':rel,'git_blob_sha1':_git_blob_sha1(p)}
                for rel,p in self.files.items() if p.suffix=='.docx']}),encoding='utf-8')

    def build(self, *args, **kwargs):
        return build_register(*args, signatures_path=self.signature_path, **kwargs)

    def add_file(self,rel: str,content: bytes,*,manifest: bool) -> Path:
        p=self.src/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(content)
        if manifest:
            self.manifest.append({'path':rel,'sha256':sha256(content).hexdigest()})
        self.files[rel]=p
        return p

    def write_manifest(self):
        self.add_file('SOURCE-MANIFEST.json',json.dumps({'files':self.manifest}).encode(),manifest=False)

    def make_xlsx(self):
        from io import BytesIO
        b=BytesIO()
        with ZipFile(b,'w') as z:
            z.writestr('xl/worksheets/sheet1.xml',
                '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
                  <row r="2"><c t="inlineStr"><is><t>5.12.4</t></is></c>
                  <c t="inlineStr"><is><t>Tegnsettet til alle XML-filer skal være UTF-8, også ved avlevering.</t></is></c>
                  <c t="inlineStr"><is><t>B</t></is></c>
                  <c t="inlineStr"><is><t>Obligatorisk ved avlevering</t></is></c></row>
                  </sheetData></worksheet>''')
        return b.getvalue()

    def test_strict_and_transitional_docx_with_full_table_cells(self):
        for ver, expected_ns in (('3.1','transitional'),('4.0','transitional'),('5.0','strict')):
            doc=next(p for rel,p in self.files.items() if rel.startswith('noark5/v'+ver+'/') and p.suffix=='.docx')
            result=read_docx_structured(doc)
            self.assertEqual(result['namespace'],expected_ns)
            self.assertEqual(result['tables'],1)
            self.assertGreater(result['text_characters'],100)
            rows,paragraphs=extract_docx_clauses(result,version=ver,source=doc.name,source_sha256='abc')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['number'],'5.12.4')
            self.assertEqual(rows[0]['requirement_class'],'B')
            self.assertEqual(rows[0]['text'],
                'Tegnsettet til alle XML-filer skal være UTF-8, også ved avlevering.')
            self.assertIn('Obligatorisk',rows[0]['remarks_or_conditions'])
            self.assertEqual(rows[0]['location'],'word/document.xml:tbl1:row2')
            self.assertFalse(rows[0]['printed_pdf_page_verified'])
            self.assertFalse(rows[0]['normative_requirement_approved'])
            self.assertEqual(len(paragraphs),1)
            d=diagnose_docx(doc)
            self.assertTrue(d['text_readable'])
            self.assertEqual(d['ooxml_variant'],expected_ns)
            self.assertGreater(d['word_text_nodes'],2)
            raw,backend=read_source_document(doc)
            self.assertEqual(backend,'docx_xml')
            self.assertTrue(any('UTF-8' in t for _,t in raw))

    def test_automatic_word_numbering_and_krav_prefix_are_recovered(self):
        # Unlike our PDF->DOCX conversion, original Word standards often store
        # list numbers in numbering.xml instead of in w:t text runs.
        from io import BytesIO
        for ns in (WORD_T, WORD_S):
            def ppr(level: int) -> str:
                return f'<w:pPr><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="7"/></w:numPr></w:pPr>'
            style_xml=f'''<w:styles xmlns:w="{ns}">
              <w:style w:type="paragraph" w:styleId="Requirement">
                <w:pPr><w:numPr><w:ilvl w:val="2"/><w:numId w:val="7"/></w:numPr></w:pPr>
              </w:style></w:styles>'''
            numbering_xml=f'''<w:numbering xmlns:w="{ns}">
                <w:abstractNum w:abstractNumId="3">
                  <w:lvl w:ilvl="0"><w:start w:val="5"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1"/></w:lvl>
                  <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl>
                  <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2.%3"/></w:lvl>
                </w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="3"/></w:num>
            </w:numbering>'''
            doc_xml=f'''<w:document xmlns:w="{ns}"><w:body>
              <w:p>{ppr(0)}<w:r><w:t>Arkivstrukturen</w:t></w:r></w:p>
              <w:p>{ppr(1)}<w:r><w:t>Arkiv og arkivdel</w:t></w:r></w:p>
              <w:tbl><w:tr>
                <w:tc><w:p>{ppr(2)}</w:p></w:tc>
                <w:tc><w:p><w:r><w:t>En arkivdel skal tilhøre ett arkiv og ikke to.</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>O</w:t></w:r></w:p></w:tc>
              </w:tr><w:tr>
                <w:tc><w:p><w:pPr><w:pStyle w:val="Requirement"/></w:pPr>
                  <w:r><w:t>Systemet bør kunne opprette en ny arkivdel.</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>V</w:t></w:r></w:p></w:tc>
              </w:tr></w:tbl>
              <w:p><w:r><w:t>Krav 5.1.3: En avsluttet arkivdel skal ikke opprette nye mapper.</w:t></w:r></w:p>
              <w:p><w:r><w:t>Se krav 5.1.3 for nærmere informasjon.</w:t></w:r></w:p>
              <w:p><w:r><w:t>5.1.4 Noark-standardens oversikt over innhold.</w:t></w:r></w:p>
            </w:body></w:document>'''
            b=BytesIO()
            with ZipFile(b,'w') as z:
                z.writestr('word/document.xml',doc_xml)
                z.writestr('word/numbering.xml',numbering_xml)
                z.writestr('word/styles.xml',style_xml)
            path=self.tmp/('auto_'+('strict' if ns==WORD_S else 'transitional')+'.docx')
            path.write_bytes(b.getvalue())
            data=read_docx_structured(path)
            self.assertEqual(data['word_numbering_paragraphs'],4)
            self.assertEqual(data['word_numbering_unresolved'],0)
            rows,unstructured=extract_docx_clauses(data,version='4.0',source=path.name,
                                                    source_sha256='abc')
            self.assertEqual([r['number'] for r in rows],['5.1.1','5.1.2','5.1.3'])
            self.assertEqual([r['requirement_class'] for r in rows],['O','V',''])
            self.assertEqual(rows[0]['text'],'En arkivdel skal tilhøre ett arkiv og ikke to.')
            self.assertFalse(any('5.1.4'==r['number'] for r in rows))
            self.assertEqual(len(unstructured),0)

    def test_explicit_krav_prefix_or_number_with_class_in_table(self):
        ns=WORD_T
        raw=f'''<w:document xmlns:w="{ns}"><w:body><w:tbl>
           <w:tr><w:tc><w:p><w:r><w:t>Krav 6.11.1</w:t></w:r></w:p></w:tc>
           <w:tc><w:p><w:r><w:t>Alle mapper skal være registrert i en arkivdel.</w:t></w:r></w:p></w:tc>
           <w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>
           <w:tr><w:tc><w:p><w:r><w:t>6.11.2</w:t></w:r></w:p></w:tc>
           <w:tc><w:p><w:r><w:t>Arkivdelen bør kunne inneholde flere mapper.</w:t></w:r></w:p></w:tc>
           <w:tc><w:p><w:r><w:t>V</w:t></w:r></w:p></w:tc></w:tr>
        </w:tbl></w:body></w:document>'''
        p=self.tmp/'literal.docx'
        p.write_bytes(docx_bytes(raw))
        data=read_docx_structured(p)
        rows,_=extract_docx_clauses(data,version='4.0',source=p.name,source_sha256='abc')
        self.assertEqual([x['number'] for x in rows],['6.11.1','6.11.2'])
        self.assertEqual([x['requirement_class'] for x in rows],['B','V'])

    def test_linked_word_numbering_style_without_explicit_numpr(self):
        from io import BytesIO
        ns=WORD_T
        def list_p(level,text):
            return (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{level}"/>'
                    f'<w:numId w:val="3"/></w:numPr></w:pPr>'
                    f'<w:r><w:t>{text}</w:t></w:r></w:p>')
        numbers=f'''<w:numbering xmlns:w="{ns}"><w:abstractNum w:abstractNumId="1">
         <w:lvl w:ilvl="0"><w:start w:val="2"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1"/></w:lvl>
         <w:lvl w:ilvl="1"><w:start w:val="4"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1.%2"/></w:lvl>
         <w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="decimal"/>
           <w:lvlText w:val="%1.%2.%3"/><w:pStyle w:val="ReqLinked"/></w:lvl>
         </w:abstractNum><w:num w:numId="3"><w:abstractNumId w:val="1"/></w:num>
         </w:numbering>'''
        styles=f'''<w:styles xmlns:w="{ns}"><w:style w:styleId="ReqLinked" w:type="paragraph"/></w:styles>'''
        doc=f'''<w:document xmlns:w="{ns}"><w:body>
          {list_p(0,'Hovedkapittel')}{list_p(1,'Underkapittel')}
          <w:tbl><w:tr><w:tc><w:p><w:pPr><w:pStyle w:val="ReqLinked"/></w:pPr>
           <w:r><w:t>En journalpost skal ha en gyldig dokumenttilknytning.</w:t></w:r></w:p></w:tc>
           <w:tc><w:p><w:r><w:t>O</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
        </w:body></w:document>'''
        buf=BytesIO()
        with ZipFile(buf,'w') as z:
            z.writestr('word/document.xml',doc)
            z.writestr('word/numbering.xml',numbers)
            z.writestr('word/styles.xml',styles)
        path=self.tmp/'linked.docx'
        path.write_bytes(buf.getvalue())
        data=read_docx_structured(path)
        rows,_=extract_docx_clauses(data,version='5.0',source=path.name,source_sha256='aaa')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['number'],'2.4.1')
        self.assertEqual(rows[0]['requirement_class'],'O')
        self.assertEqual(data['word_numbering_unresolved'],0)

    def test_requirement_prose_is_not_mistaken_for_table_header(self):
        # 'krav' and 'type' can appear within genuine requirement prose.
        raw=document_xml(WORD_T,number='13.2.3',grade='B',text=(
            'For alle hendelser som skal registreres skal følgende opplysninger '
            'lagres, jf. kravets type og metadataene i registeret.'))
        p=self.tmp/'prose.docx'
        p.write_bytes(docx_bytes(raw))
        rows,_=extract_docx_clauses(read_docx_structured(p),version='3.1',
                                    source=p.name,source_sha256='aaa')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['number'],'13.2.3')
        self.assertEqual(rows[0]['requirement_class'],'B')

    def test_compile_three_version_register_with_source_hash_evidence(self):
        before={name:sha256(path.read_bytes()).hexdigest() for name,path in self.files.items()}
        progress=[]
        r=self.build(self.a8,source_root=self.source,progress=progress.append)
        self.assertEqual(r['report_type'],REPORT_TYPE)
        self.assertEqual({k:v['requirements_indexed'] for k,v in r['versions'].items()},
                         {'3.1':1,'4.0':1,'5.0':1})
        self.assertEqual(len(r['candidate_rows']),3)
        self.assertTrue(r['source_inventory'])
        self.assertEqual(r['source_inventory'][2]['docx_manifest_status'],
                         'not_registered_derived_working_copy')
        self.assertTrue(all(x['pdf_sha256_verified'] for x in r['source_inventory']))
        self.assertTrue(any('Noark 5 v 5.docx' in s for s in progress))
        self.assertFalse(r['normative_requirements_approved'])
        self.assertFalse(r['original_pdf_wording_equivalence_verified'])
        self.assertFalse(r['dwm_implementation_coverage_verified'])
        self.assertFalse(r['saxon_lxml_semantic_parity_verified'])
        self.assertEqual(before,{name:sha256(path.read_bytes()).hexdigest() for name,path in self.files.items()})
        self.assertEqual(len(filter_register_rows(r,version='5.0',severity='WARNING')),1)
        self.assertEqual(len(filter_register_rows(r,origin='xlsx_requirement_row')),1)
        self.assertEqual(len(filter_register_rows(r,query='UTF-8')),3)

    def test_modified_original_pdf_blocks_docx_requirement_import(self):
        rel='noark5/v5.0/spesifikasjoner/Noark 5 v 5.pdf'
        self.files[rel].write_bytes(b'FALSIFIED ORIGINAL PDF')
        r=self.build(self.a8,source_root=self.source)
        self.assertEqual(r['versions']['5.0']['requirements_indexed'],0)
        self.assertTrue(any(x['kind']=='pdf_original_sha256_mismatch' and x['severity']=='FEIL'
                            for x in r['qa_issues']))
        self.assertTrue(any(x['kind']=='no_requirement_rows_indexed' for x in r['qa_issues']))

    def test_missing_main_docx_is_explicit_error(self):
        self.files['noark5/v4.0/spesifikasjoner/Noark5v4 Standard for elektronisk arkiv (01.12.2016).docx'].unlink()
        r=self.build(self.a8,source_root=self.source)
        self.assertEqual(r['versions']['4.0']['requirements_indexed'],0)
        self.assertTrue(any(x['kind']=='main_specification_docx_missing' for x in r['qa_issues']))

    def test_duplicate_conflicting_text_not_normalized(self):
        rel='noark5/v5.0/spesifikasjoner/Noark 5 v 5.docx'
        dupe='''<w:tr><w:tc><w:p><w:r><w:t>5.12.4</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>En motstridende tekst for det samme kravet.</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr>'''
        self.files[rel].write_bytes(docx_bytes(document_xml(WORD_S,duplicate=dupe)))
        self.make_signatures()
        r=self.build(self.a8,source_root=self.source)
        self.assertIn('5.0:5.12.4',r['duplicate_number_groups'])
        self.assertEqual(len(filter_register_rows(r,version='5.0',severity='FEIL')),2)
        self.assertIn('duplicate_conflicting_clause_text',
                      [x['kind'] for x in r['qa_issues']])

    def test_readonly_output_no_overwrite_and_csv_formula_escape(self):
        r=self.build(self.a8,source_root=self.source)
        dest=self.tmp/'output'
        paths=write_reports(r,dest,source_root=self.source)
        self.assertEqual(len(paths),5)
        self.assertEqual(json.loads(paths[0].read_text())['report_type'],REPORT_TYPE)
        self.assertIn('5.12.4',paths[1].read_text())
        self.assertIn('SHA-256',paths[4].read_text())
        with self.assertRaises(FileExistsError):
            write_reports(r,dest,source_root=self.source)
        with self.assertRaises(ValueError):
            write_reports(r,self.source/'docs',source_root=self.source)
        self.assertIn("'=SUM",_csv([{'text':'=SUM(1+2)'}],('text',)))

    def test_no_silent_quality_upgrade_and_source_variant_difference(self):
        r=self.build(self.a8,source_root=self.source)
        self.assertTrue(all(x['review_state']=='PENDING_MANUAL_QA' for x in r['candidate_rows']))
        self.assertTrue(all(x['source_wording_independently_reviewed'] is False
                            for x in r['candidate_rows']))
        self.assertEqual(r['versions']['3.1']['xlsx_is_primary'],True)
        self.assertEqual(r['versions']['5.0']['xlsx_is_primary'],False)
        self.assertEqual(_compare_text('A B C','A  B C'),1.0)
        self.assertLess(_compare_text('hello world','goodbye world'),0.85)

    def test_existing_qt_workspace_a9_tab_and_version(self):
        root=Path(__file__).resolve().parents[1]
        gui=(root/'gui_qt/noark5_xpath_audit_v021_a1.py').read_text(encoding='utf-8')
        for item in ('Kravregister DOCX a9','_choose_a9_report','_render_a9',
                     'a9_issue_table','filter_register_rows','_choose_a8_report'):
            self.assertIn(item,gui)
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', "0.2.1", 9)
        self.assertIn(f'version = "{VERSION.replace("-", "")}"',
                      (root/'pyproject.toml').read_text(encoding='utf-8'))



class A92SourceReferenceRegressions(TestCase):
    @staticmethod
    def table(number: str, text: str, index: int) -> dict:
        return {'kind':'table','anchor':f'word/document.xml:tbl{index}',
                'rows':[{'anchor':f'word/document.xml:tbl{index}:row1',
                         'cells':[{'text':number,'paragraphs':[]},
                                  {'text':text,'paragraphs':[]},
                                  {'text':'O','paragraphs':[]}]}]}

    def test_toc_page_number_must_not_become_requirement_heading(self):
        doc={'blocks':[
            {'kind':'paragraph','anchor':'word/document.xml:p1',
             'text':'15\tOrdforklaringer\t266','style':'TOC1','numbering_label':''},
            self.table('5.1.1','Arkivet skal ha en entydig identifikator.',1),
            {'kind':'paragraph','anchor':'word/document.xml:p2',
             'text':'Nøkkelord','style':'Heading2','numbering_label':'2.9'},
            self.table('2.9.1','Et nøkkelord skal registreres korrekt.',2),
            {'kind':'paragraph','anchor':'word/document.xml:p3',
             'text':'2.8.3 Systemet skal kunne opprette et objekt.',
             'style':'Normal','numbering_label':''},
            self.table('2.9.2','Systemet skal bevare registrerte nøkkelord.',3),
        ]}
        rows,unknown=extract_docx_clauses(doc,version='5.0',source='word.docx',
                                         source_sha256='sha')
        self.assertEqual([r['number'] for r in rows],['5.1.1','2.9.1','2.9.2'])
        self.assertEqual([r['source_heading_context'] for r in rows],
                         ['', '2.9 Nøkkelord', '2.9 Nøkkelord'])
        self.assertEqual([x['number'] for x in unknown],['2.8.3'])

    def test_literal_section_heading_but_not_toc_or_normative_prose(self):
        from app.noark5_requirement_registry_v021_a9 import _reliable_heading_context
        self.assertIsNone(_reliable_heading_context('15\tOrdforklaringer\t266', 'Normal', ''))
        self.assertIsNone(_reliable_heading_context('12.2.28 Regler skal kunne håndheves.', 'Normal', ''))
        self.assertEqual(_reliable_heading_context('2.9 Nøkkelord','Normal',''),'2.9 Nøkkelord')
        self.assertIsNone(_reliable_heading_context('15\tOrdforklaringer\t266','TOC1',''))

    def test_duplicate_qa_issue_has_both_anchors_and_wording(self):
        rows=[{'noark_version':'5.0','number':'2.8.3','text':'Første kravtekst',
               'location':'word/document.xml:tbl19:row4','source':'noark5/v5.0/main.docx',
               'qa_reasons':[],'qa_severity':'WARNING'},
              {'noark_version':'5.0','number':'2.8.3','text':'Andre kravtekst',
               'location':'word/document.xml:tbl20:row2','source':'noark5/v5.0/main.docx',
               'qa_reasons':[],'qa_severity':'WARNING'}]
        issues=[]
        groups=_mark_duplicates(rows,issues)
        self.assertEqual(groups['5.0:2.8.3'],[r['location'] for r in rows])
        self.assertEqual(len(issues),1)
        self.assertEqual(issues[0]['severity'],'FEIL')
        self.assertIn('tbl19:row4',issues[0]['location'])
        self.assertIn('tbl20:row2',issues[0]['detail'])
        self.assertIn('Andre kravtekst',issues[0]['detail'])


if __name__=='__main__':
    from unittest import main
    main()
