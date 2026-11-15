"""A8 five-XML technical XSD workflow; never changes source or claims normativity."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.noark5_xsd_full_xml_v021_a8 import validate_extraction, XML_TO_SCHEMA


class FiveXmlTechnicalXSD(TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name)
        self.src=root/'source'
        self.xsd=self.src/'docs/kilder/noark/noark5/v5.0/schemas'
        self.xsd.mkdir(parents=True)
        self.ex=root/'extraction'
        self.ex.mkdir()
        self.manifest_path=self.src/'docs/kilder/noark/SOURCE-MANIFEST.json'
        self.manifest=[]
        for xml,xsd in XML_TO_SCHEMA.items():
            if xsd is None:
                continue
            self.make_schema(xsd,xml[:-4])
        self.make_schema('metadatakatalog.xsd','metadata')
        self.make_manifest()
        self.signature_path=root/'dwm_xsd_signatures.json'
        self.make_signatures()

    def make_schema(self,filename,root):
        path=self.xsd/filename
        path.write_text('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
           <xs:element name="'''+root+'''" type="xs:string"/>
           </xs:schema>''',encoding='utf-8')
        rel=path.relative_to(self.src/'docs/kilder/noark').as_posix()
        self.manifest.append({'path':rel,'sha256':sha256(path.read_bytes()).hexdigest()})

    def make_manifest(self):
        self.manifest_path.write_text(json.dumps({'files':self.manifest}),encoding='utf-8')

    def make_signatures(self):
        entries=[]
        for item in self.manifest:
            entries.append({'version':'5.0',
                            'filename':Path(item['path']).name,
                            'sha256':item['sha256']})
        self.signature_path.write_text(json.dumps({'signatures':entries}),encoding='utf-8')

    def test_valid_and_invalid_missing_and_addml_without_mutation(self):
        (self.ex/'arkivstruktur.xml').write_text('<arkivstruktur>test</arkivstruktur>',encoding='utf-8')
        (self.ex/'endringslogg.xml').write_text('<bad>wrong root</bad>',encoding='utf-8')
        (self.ex/'arkivuttrekk.xml').write_text('<arkivuttrekk>package</arkivuttrekk>',encoding='utf-8')
        before={p.name:sha256(p.read_bytes()).hexdigest() for p in self.ex.iterdir()}
        report=validate_extraction(self.ex,self.src,noark_version='5.0',signature_registry=self.signature_path)
        results={r['xml_file']:r for r in report['xml_records']}
        self.assertEqual(len(results),5)
        self.assertEqual(results['arkivstruktur.xml']['technical_xsd_status'],'XSD_VALID')
        self.assertTrue(results['arkivstruktur.xml']['schema_original_sha256_verified'])
        self.assertEqual(results['endringslogg.xml']['technical_xsd_status'],'XSD_INVALID')
        self.assertEqual(results['endringslogg.xml']['qa_severity'],'FEIL')
        self.assertGreater(results['endringslogg.xml']['error_count'],0)
        self.assertEqual(results['loependeJournal.xml']['technical_xsd_status'],'XML_FILE_NOT_PRESENT')
        self.assertEqual(results['loependeJournal.xml']['qa_severity'],'NOTE')
        self.assertEqual(results['arkivuttrekk.xml']['technical_xsd_status'],'ADDML_SCHEMA_NOT_PRESENT')
        self.assertEqual(results['arkivuttrekk.xml']['qa_severity'],'WARNING')
        self.assertFalse(report['full_noark_conformance_verified'])
        self.assertFalse(report['source_files_modified'])
        self.assertEqual(before,{p.name:sha256(p.read_bytes()).hexdigest() for p in self.ex.iterdir()})

    def test_addml_is_separate_supplied_xsd_not_metadatakatalog(self):
        (self.ex/'arkivuttrekk.xml').write_text('<arkivuttrekk>package</arkivuttrekk>',encoding='utf-8')
        (self.ex/'addml.xsd').write_text(
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
            '<xs:element name="arkivuttrekk" type="xs:string"/></xs:schema>',encoding='utf-8')
        report=validate_extraction(self.ex,self.src,noark_version='5.0',signature_registry=self.signature_path)
        a=next(x for x in report['xml_records'] if x['xml_file']=='arkivuttrekk.xml')
        self.assertEqual(a['technical_xsd_status'],'XSD_VALID')
        self.assertIn('addml.xsd',a['schema_file'])
        self.assertFalse(a['schema_original_sha256_verified'])
        self.assertFalse(a['normative_conformance_verified'])

    def test_xsd_source_hash_conflict_never_validates_with_modified_schema(self):
        (self.ex/'arkivstruktur.xml').write_text('<arkivstruktur>ok</arkivstruktur>',encoding='utf-8')
        with (self.xsd/'arkivstruktur.xsd').open('a',encoding='utf-8') as f:
            f.write('<!-- modified -->')
        report=validate_extraction(self.ex,self.src,noark_version='5.0',signature_registry=self.signature_path)
        a=next(x for x in report['xml_records'] if x['xml_file']=='arkivstruktur.xml')
        self.assertEqual(a['technical_xsd_status'],'SCHEMA_SOURCE_UNAVAILABLE')
        self.assertFalse(a['schema_original_sha256_verified'])
        self.assertEqual(a['qa_severity'],'FEIL')

    def test_unknown_schema_dependency_is_not_automatically_trusted(self):
        (self.ex/'arkivstruktur.xml').write_text('<arkivstruktur>ok</arkivstruktur>',encoding='utf-8')
        (self.xsd/'other.xsd').write_text(
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"/>',encoding='utf-8')
        p=self.xsd/'arkivstruktur.xsd'
        p.write_text('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
        <xs:include schemaLocation="other.xsd"/>
        <xs:element name="arkivstruktur" type="xs:string"/>
        </xs:schema>''',encoding='utf-8')
        for entry in self.manifest:
            if entry['path'].endswith('arkivstruktur.xsd'):
                entry['sha256']=sha256(p.read_bytes()).hexdigest()
        self.make_manifest()
        self.make_signatures()
        report=validate_extraction(self.ex,self.src,noark_version='5.0',signature_registry=self.signature_path)
        a=next(x for x in report['xml_records'] if x['xml_file']=='arkivstruktur.xml')
        self.assertEqual(a['technical_xsd_status'],'SCHEMA_DEPENDENCY_UNVERIFIED')
        self.assertEqual(a['qa_severity'],'FEIL')

    def test_mutable_manifest_cannot_replace_pinned_original(self):
        xml=self.ex/'arkivstruktur.xml'
        xml.write_text('<arkivstruktur>value</arkivstruktur>',encoding='utf-8')
        p=self.xsd/'arkivstruktur.xsd'
        p.write_text(p.read_text(encoding='utf-8')+'<!-- vendor variant -->',encoding='utf-8')
        for entry in self.manifest:
            if entry['path'].endswith('arkivstruktur.xsd'):
                entry['sha256']=sha256(p.read_bytes()).hexdigest()
        self.make_manifest()
        # DWM signature registry is deliberately NOT updated.
        report=validate_extraction(self.ex,self.src,noark_version='5.0',
                                  signature_registry=self.signature_path)
        record=next(x for x in report['xml_records'] if x['xml_file']=='arkivstruktur.xml')
        self.assertEqual(record['technical_xsd_status'],'SCHEMA_SOURCE_UNAVAILABLE')
        self.assertEqual(report['original_xsd_inventory']['arkivstruktur.xsd']['status'],
                         'dwm_xsd_signature_mismatch')
        self.assertFalse(record['schema_original_sha256_verified'])

    def test_unknown_version_refused(self):
        with self.assertRaises(ValueError):
            validate_extraction(self.ex,self.src,noark_version='3.0',signature_registry=self.signature_path)

    def test_xml_exceeding_limit_is_note_or_warning_not_valid(self):
        (self.ex/'arkivstruktur.xml').write_text('<arkivstruktur>x</arkivstruktur>',encoding='utf-8')
        r=validate_extraction(self.ex,self.src,noark_version='5.0',max_xml_bytes=10,signature_registry=self.signature_path)
        a=next(x for x in r['xml_records'] if x['xml_file']=='arkivstruktur.xml')
        self.assertEqual(a['technical_xsd_status'],'SKIPPED_LARGE_XML')
        self.assertNotEqual(a['technical_xsd_status'],'XSD_VALID')


if __name__=='__main__':
    from unittest import main
    main()
