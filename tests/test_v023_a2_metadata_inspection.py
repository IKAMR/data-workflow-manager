"""a2: registered metadata and values, never inferred Noark compliance."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import tomllib
import unittest

from app.ks_metadata_v023_a2 import (
    catalogue_ids, field_detail, field_rows, _value_relation, VERSIONS, inspection_note,
)
from app.ks_inspector_v023_a1 import inspect_xml_line

ROOT = Path(__file__).resolve().parents[1]


def sample_bundle():
    meta = []
    sets = {}
    for mid, field, values in (
        ('M001', 'systemID', None),
        ('M003', 'mappeID', None),
        ('M052', 'saksstatus', ['Under behandling', 'Avsluttet', 'Utgår']),
        ('M053', 'journalstatus', ['Journalført', 'Ekspedert', 'Arkivert', 'Utgår']),
        ('M054', 'dokumentstatus', ['Dokumentet er under redigering', 'Dokumentet er ferdigstilt']),
        ('M300', 'dokumentmedium', ['Fysisk arkiv', 'Elektronisk arkiv', 'Blandet fysisk og elektronisk arkiv']),
    ):
        entry = {'metadata_id': mid, 'name': field,
                 'verification_status': 'verified_for_registered_value_set' if values else 'verified',
                 'source_scope': 'verified_registered_value_set_only' if values else 'selected_properties_source_verified',
                 'source_id': 'noark5-5.0-metadata-catalog', 'source_location': 'vedlegg 1',
                 'registered_value_set_id': mid + '_' + field if values else None,
                 'mapping_state': 'xpath_candidate' if values else 'no_xpath_candidate',
                 'xpath_candidates': ([{'test_id':'kdrs.c13','kdrs_id':'c13',
                                        'metrics':[{'xpath':'//mappe/saksstatus'}]}]
                                      if field=='saksstatus' else []),
                 'explicit_value_set_references': []}
        meta.append(entry)
        if values:
            sets[mid+'_'+field] = {'values':values, 'metadata_id':mid, 'value_set_role':'obligatory_values'}
    return {'versions':{
        '5.0':{'state':'loaded','metadata_registry_status':'loaded',
               'metadata':meta, 'value_sets':sets},
        '4.0':{'state':'loaded','metadata_registry_status':'loaded',
               'metadata':meta[:1], 'value_sets':{}},
        '3.1':{'state':'unavailable','metadata_registry_status':'unavailable',
               'metadata':[], 'value_sets':{}}}}


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.bundle=sample_bundle()
        self.xml={'element':'saksstatus','xml_value':'Under behandling',
                  'object_type':'mappe','system_id':'fold1','fields':[
                     {'field':'systemID','value':'fold1','line':3,'xpath':'/a/mappe/systemID'},
                     {'field':'mappeID','value':'2011/1','line':4,'xpath':'/a/mappe/mappeID'},
                     {'field':'saksstatus','value':'Under behandling','line':8,'xpath':'/a/mappe/saksstatus'},
                  ]}

    def test_selected_saksstatus_maps_to_m052_not_m300(self):
        rows=field_rows(self.xml,self.bundle,'5.0')
        self.assertEqual([r['metadata_id'] for r in rows],['M001','M003','M052'])
        self.assertTrue(rows[-1]['is_selected'])
        self.assertNotIn('M300',[r['metadata_id'] for r in rows])

    def test_registered_value_is_not_automatically_valid_delivery(self):
        row=field_rows(self.xml,self.bundle,'5.0')[-1]
        self.assertEqual(row['value_relation'],'Finnes i registrert verdisett')
        self.assertNotIn('PASS',field_detail(self.xml,self.bundle,'5.0','M052'))
        self.assertIn('avleveringsuttrekk',field_detail(self.xml,self.bundle,'5.0','M052'))
        self.assertIn('Under behandling',field_detail(self.xml,self.bundle,'5.0','M052'))

    def test_xml_field_xpath_is_distinct_from_candidate_xpath(self):
        detail=field_detail(self.xml,self.bundle,'5.0','M052')
        self.assertIn('Faktisk XML-XPath: /a/mappe/saksstatus',detail)
        self.assertIn('Kandidat (ikke attestert semantisk identitet)',detail)
        self.assertIn('//mappe/saksstatus',detail)
        self.assertIn('kdrs.c13',detail)

    def test_m300_lookup_also_works_when_not_observed(self):
        options=catalogue_ids(self.bundle,'5.0')
        self.assertIn(('M300','dokumentmedium'),options)
        detail=field_detail(self.xml,self.bundle,'5.0','M300')
        self.assertIn('Ingen direkte forekomst',detail)
        self.assertIn('Elektronisk arkiv',detail)
        self.assertNotIn('Faktisk XML-XPath:',detail)

    def test_m053_on_journalstatus(self):
        x={'element':'journalstatus','fields':[{'field':'journalstatus','value':'Journalført',
                                                 'line':7,'xpath':'/arkiv/registrering/journalstatus'}]}
        row=field_rows(x,self.bundle,'5.0')[0]
        self.assertEqual(row['metadata_id'],'M053')
        self.assertIn('registrert verdisett',row['value_relation'])

    def test_m054_on_dokumentstatus(self):
        x={'element':'dokumentstatus','fields':[{'field':'dokumentstatus',
              'value':'Dokumentet er under redigering', 'line':5,'xpath':'/a/dokumentbeskrivelse/dokumentstatus'}]}
        row=field_rows(x,self.bundle,'5.0')[0]
        self.assertEqual(row['metadata_id'],'M054')
        self.assertIn('registrert verdisett',row['value_relation'])

    def test_unregistered_xml_field_is_not_assigned_m_id(self):
        xml={'element':'saksstatus','fields':[{'field':'strangeField','value':'x'}]}
        row=field_rows(xml,self.bundle,'5.0')[0]
        self.assertEqual(row['metadata_id'],'')
        self.assertIn('Ingen dokumentert',row['value_relation'])

    def test_disconnected_metadata_registry_is_not_assumed(self):
        row=field_rows(self.xml,self.bundle,'3.1')[-1]
        self.assertEqual(row['metadata_id'],'')
        self.assertIn('ikke entydig registrert',field_detail(self.xml,self.bundle,'3.1','M052'))

    def test_requested_version_changes_mapping(self):
        self.assertEqual(field_rows(self.xml,self.bundle,'5.0')[-1]['metadata_id'],'M052')
        self.assertEqual(field_rows(self.xml,self.bundle,'4.0')[-1]['metadata_id'],'')

    def test_duplicate_field_names_do_not_create_arbitrary_mapping(self):
        b=sample_bundle()
        b['versions']['5.0']['metadata'].append({'name':'saksstatus','metadata_id':'M999'})
        self.assertEqual(field_rows(self.xml,b,'5.0')[-1]['metadata_id'],'')

    def test_non_registered_value_requires_review_not_auto_failure(self):
        self.xml['fields'][-1]['value']='Lokal kode'
        row=field_rows(self.xml,self.bundle,'5.0')[-1]
        self.assertIn('faglig kontroll nødvendig',row['value_relation'])
        self.assertNotIn('FEIL',row['value_relation'])

    def test_optional_values_are_differentiated(self):
        self.assertEqual(_value_relation('Personalsaker',{'values':['Unntatt offentlighet','Personalsaker'],
             'optional_values':['Personalsaker']}),'Registrert valgfri kodeverdi')

    def test_large_field_collection_is_bounded(self):
        self.xml['fields']=[{'field':'saksstatus','value':'Under behandling'}]*500
        self.assertEqual(len(field_rows(self.xml,self.bundle,'5.0')),96)

    def test_noark_version_is_never_inferred_from_arkade_test(self):
        for version in VERSIONS:
            detail=field_detail(self.xml,self.bundle,version,'M052')
            if version=='5.0':
                self.assertIn('ikke automatisk påvist fra uttrekket',detail)
            else:
                self.assertIn('ikke entydig',detail)

    def test_invalid_requested_version_rejected(self):
        with self.assertRaisesRegex(ValueError,'Ukjent Noark'):
            field_rows(self.xml,self.bundle,'9.0')

    def test_m_id_is_never_created_from_an_unregistered_test_number(self):
        self.xml['element']='N5.15'
        self.xml['fields']=[{'field':'N5.15','value':'Under behandling'}]
        self.assertEqual(field_rows(self.xml,self.bundle,'5.0')[0]['metadata_id'],'')

    def test_real_xml_reader_collects_only_direct_child_values(self):
        context=TemporaryDirectory();self.addCleanup(context.cleanup)
        root=Path(context.name)
        source=root/'source';source.mkdir();work=root/'work';work.mkdir()
        (work/'job.json').write_text(json.dumps({'file_type':'dwm-work-job','job':
            {'source_extraction':str(source)}}),encoding='utf-8')
        xml='''<arkiv>
<arkivdel>
<mappe>
<systemID>M-1</systemID>
<mappeID>2012/4</mappeID>
<tittel>Sak</tittel>
<saksstatus>Under behandling</saksstatus>
<registrering><systemID>R-1</systemID><journalstatus>Journalført</journalstatus></registrering>
</mappe></arkivdel></arkiv>'''
        path=source/'arkivstruktur.xml';path.write_text(xml,encoding='utf-8')
        before=sha256(path.read_bytes()).hexdigest()
        data=inspect_xml_line(work,{'file':'arkivstruktur.xml','line':7,'test_id':'N5.15'})
        self.assertTrue(data['available'])
        fields=data['metadata']['fields']
        self.assertEqual([f['field'] for f in fields],['systemID','mappeID','tittel','saksstatus'])
        self.assertNotIn('journalstatus',[f['field'] for f in fields])
        self.assertEqual(data['metadata']['field_coverage'],'direkte XML-felt ferdig lest')
        self.assertEqual(sha256(path.read_bytes()).hexdigest(),before)

    def test_evidence_note_requires_real_xml_and_remains_only_observation(self):
        evidence={'test_id':'N5.15','message':'Under behandling','file':'arkivstruktur.xml',
                  'archive_part_id':'AR-1','archive_part_title':'STHA5','line':274533,
                  'source_ref':'external_evidence/arkade5/id/normalized/arkade5_results.json'}
        xml={'available':True,'metadata':self.xml}
        note=inspection_note(evidence,xml,self.bundle,'5.0')
        for token in ('M052 saksstatus', 'Arkade-test: N5.15', 'arkivstruktur.xml:274533',
                      'Objekt systemID: fold1', 'IKKE faglig konklusjon',
                      'Noark 5 v5.0: valgt referanseversjon'):
            self.assertIn(token,note)
        with self.assertRaisesRegex(ValueError,'ikke tilgjengelig'):
            inspection_note(evidence,{'available':False},self.bundle,'5.0')

    def test_metadata_reference_loading_is_deferred_to_user_inspection(self):
        module=(ROOT/'app/ks_metadata_v023_a2.py').read_text(encoding='utf-8')
        self.assertIn('from app.noark5_xpath_metadata_qa_v021_a4 import build_metadata_qa',module)
        self.assertIn('from app.noark5_xpath_version_qa_v021_a3 import _standard_registry',module)
        self.assertNotIn('record_review(',module)
        self.assertNotIn('write_text(',module)

    def test_gui_and_bootstrap_are_a2(self):
        entry=(ROOT/'gui_qt/__main__.py').read_text(encoding='utf-8')
        main=(ROOT/'gui_qt/main_v023_a2.py').read_text(encoding='utf-8')
        ui=(ROOT/'gui_qt/ks_metadata_v023_a2.py').read_text(encoding='utf-8')
        self.assertIn('from gui_qt.main_v023_a2 import DwmMainWindow',entry)
        self.assertIn('from gui_qt.main_v023_a1 import DwmMainWindow',main)
        for text in ('M-felt, verdier og XPath','M-feltoppslag','_MetadataReferenceWorker',
                     '_show_inspector','_reader_completed','_close_reader'):
            self.assertIn(text,ui)

    def test_version_and_distribution(self):
        from version import VERSION
        from tests.version_assertions import assert_release_at_least
        assert_release_at_least(self, f'VERSION = "{VERSION}"', '0.2.3', 2)
        with (ROOT/'pyproject.toml').open('rb') as file:
            self.assertEqual(tomllib.load(file)['project']['version'],'0.2.3a2')


if __name__=='__main__':
    unittest.main()
