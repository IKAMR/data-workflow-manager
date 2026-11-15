"""a11.4: conservative U1/U2 extraction and per-archive-part parity guards."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.noark5_kdrs_u1u2_v021_a11 import (
    U1_COUNTS, U2_COUNTS, _split_u2, _witness, map_u1, map_u2,
)
from app.noark5_kdrs_text_import_v021_a11 import (
    _parse_count, build_import, write_import,
)
from app.noark5_kdrs_parity_v021_a11 import compare, digest


U1_SOURCE = '''[XML_QUERY]
job_id=U01
source=arkivstruktur.xml
#START#
"U1. N5.101 Konsentrert opptelling", " ",
concat("N5.04 Arkiv: ", count(//arkiv)),
concat("N5.05/06 Arkivdeler: ", count(//arkivdel)),
concat("N5.07 Klassifikasjonssystemer: ", count(//klassifikasjonssystem)),
concat("N5.10/12/14 Mapper: ", count(//mappe)),
concat("N5.16 Registreringer: ", count(//registrering)),
concat("N5.23 Dokumentbeskrivelse: ", count(//dokumentbeskrivelse)),
concat("N5.26.01 Dokumentobjekt: ", count(//dokumentobjekt)),
concat("N5.42 Skjerminger: ", count(//skjerming))
#STOP#
'''

U2_SOURCE = '''[XML_QUERY]
job_id=U02
source=arkivstruktur.xml
#START#
//arkivdel/(concat("Arkivdel ", position(), ": " , tittel),
concat("[.1] ", dokumentmedium/text(), ", Klassifikasjonssystemer: ", count(descendant::klassifikasjonssystem), ", Klasser: ", count(descendant::klasse)),
concat("[.2] Mappe typer: @@", ", Alle: ", count(descendant::mappe), " @@"),
concat("[.3] Registreringer; Alle: ", count(descendant::registrering)),
concat("[.4] Dokumentbeskrivelse; Alle: ", count(descendant::dokumentbeskrivelse)),
concat("Dokumentobjekt; Alle: ", count(descendant::dokumentobjekt)),
concat("[.5] Korrespondansepart: ", count(descendant::korrespondansepart)),
concat("Avskrivning: ", count(descendant::avskrivningsmaate),
", Skjerming: ", count(descendant::skjerming),
", Kassasjonsvedtak: ", count(descendant::kassasjon),
", Utført kassasjon: ", count(descendant::utfoertKassasjon),
", Sletting: ", count(descendant::sletting)))
#STOP#
'''

U1_RAW = 'U1. N5.101, N5.04 Arkiv: 1, N5.05/06 Arkivdeler: 2, N5.07 Klassifikasjonssystemer: 2, N5.10/12/14 Mapper: 5, N5.16 Registreringer: 3, N5.23 Dokumentbeskrivelse: 7, N5.26.01 Dokumentobjekt: 9, N5.42 Skjerminger: 0'
U2_RAW = '''U2. N5.102, Arkivdel 1: Alfa, Beskrivelse: A,
[.1] Elektronisk, Klassifikasjonssystemer: 1, Klasser: 2,
[.2] Mappe typer: @@, Alle: 3 @@, [.3] Registreringer; Alle: 2,
[.4] Dokumentbeskrivelse; Alle: 4, Dokumentobjekt; Alle: 6,
[.5] Korrespondansepart: 7, Avskrivning: 1, Skjerming: 1, Kassasjonsvedtak: 1, Utført kassasjon: 0, Sletting: 0,
Arkivdel 2: Beta, Beskrivelse: B,
[.1] Papir, Klassifikasjonssystemer: 1, Klasser: 1,
[.2] Mappe typer: @@, Alle: 2 @@, [.3] Registreringer; Alle: 1,
[.4] Dokumentbeskrivelse; Alle: 3, Dokumentobjekt; Alle: 3,
[.5] Korrespondansepart: 1, Avskrivning: 0, Skjerming: 0, Kassasjonsvedtak: 0, Utført kassasjon: 0, Sletting: 0'''


def clean_report(source_basename: str, job_id: str, raw: str) -> str:
    return (f'Query file: C:\\KDRS\\doc\\{source_basename}\n\n'
            f'=================================\n{job_id}\n\n{raw}\n'
            f'=================================\n')


class A11U1U2Tests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.dwm=self.root/'dwm'
        ref=self.dwm/'docs/reference/kdrs-query'
        ref.mkdir(parents=True)
        (ref/'xml-queries_noark5_2026-05-26.txt').write_text(U1_SOURCE+U2_SOURCE,encoding='utf-8')
        (ref/'xml-queries_noark5_2026-05-26_U1.txt').write_text(U1_SOURCE,encoding='utf-8')
        (ref/'xml-queries_noark5_2026-05-26_U2.txt').write_text(U2_SOURCE,encoding='utf-8')
        cat={"tests":[
            {"test_id":"kdrs.u01","legacy":{"job_id":"U01"},"source_xml":"arkivstruktur.xml","execution":{"kind":"u1_total"}},
            {"test_id":"kdrs.u02","legacy":{"job_id":"U02"},"source_xml":"arkivstruktur.xml","execution":{"kind":"u2_archive_parts"}}
        ]}
        d=self.dwm/'config/noark5/tests'
        d.mkdir(parents=True)
        (d/'xpath_catalog_2026_05_26.json').write_text(json.dumps(cat),encoding='utf-8')
        self.xml=self.root/'source'
        self.xml.mkdir()
        (self.xml/'arkivstruktur.xml').write_text('<arkiv><arkivdel><tittel>Alfa</tittel></arkivdel><arkivdel><tittel>Beta</tittel></arkivdel></arkiv>',encoding='utf-8')
        self.run=self.root/'run'
        (self.run/'results').mkdir(parents=True)
        self.u1_result={
            'test_id':'kdrs.u01','status':'ok','source_xml':'arkivstruktur.xml',
            'source_path':str(self.xml/'arkivstruktur.xml'),
            'values':{'archive':{'count':1},'structure':{'archive_part_count':2,'classification_system_count':2},
                      'folders':{'count':5},'registrations':{'count':3},
                      'documents':{'description_count':7,'object_count':9},
                      'preservation':{'screening':{'count':0}}},
        }
        self.u2_result={
            'test_id':'kdrs.u02','status':'ok','source_xml':'arkivstruktur.xml',
            'source_path':str(self.xml/'arkivstruktur.xml'),
            'values':{'archive_parts':[
                {'archive_part':{'index':1,'title':'Alfa','system_id':'A'},
                 'values':{'classification_system_count':1,'class_count':2,'folder_count':3,
                           'registration_count':2,'document_description_count':4,'document_object_count':6,
                           'correspondence_party_count':7,'writeoff_count':1,'screening_count':1,
                           'disposal_count':1,'performed_disposal_count':0,'deletion_count':0}},
                {'archive_part':{'index':2,'title':'Beta','system_id':'B'},
                 'values':{'classification_system_count':1,'class_count':1,'folder_count':2,
                           'registration_count':1,'document_description_count':3,'document_object_count':3,
                           'correspondence_party_count':1,'writeoff_count':0,'screening_count':0,
                           'disposal_count':0,'performed_disposal_count':0,'deletion_count':0}}
            ]},
        }
        self._put(self.u1_result)
        self._put(self.u2_result)
        self.index=self.run/'index.json'
        self.index.write_text(json.dumps({'result_set_format_version':2,'tests':[
            {'test_id':'kdrs.u01','status':'ok','file':'results/kdrs_u01.json'},
            {'test_id':'kdrs.u02','status':'ok','file':'results/kdrs_u02.json'}]}),encoding='utf-8')
        self.u1=self.root/'u1.txt'
        self.u2=self.root/'u2.txt'
        self.u1.write_text(clean_report('xml-queries_noark5_2026-05-26_U1.txt','U01',U1_RAW),encoding='utf-8')
        self.u2.write_text(clean_report('xml-queries_noark5_2026-05-26_U2.txt','U02',U2_RAW),encoding='utf-8')

    def _put(self, r):
        (self.run/'results'/(r['test_id'].replace('.','_')+'.json')).write_text(json.dumps(r),encoding='utf-8')

    def build(self, reports=None, index=True):
        return build_import(dwm_root=self.dwm,xml_root=self.xml,
                            reports=reports if reports is not None else {'U1':self.u1,'U2':self.u2},
                            noark_version='5.0',dwm_index_path=self.index if index else None)

    def test_u1_source_checked_mapping_and_partial_results(self):
        values, rows, issues=map_u1(U1_RAW, U1_SOURCE, {'test_id':'kdrs.u01','execution':{'kind':'u1_total'}},_parse_count)
        self.assertEqual(values['archive_count'],1)
        self.assertEqual(values['archive_part_count'],2)
        self.assertEqual(values['screening_count'],0)
        self.assertGreaterEqual(len(rows),7)
        self.assertTrue(all(row['profile']=='U1' for row in rows))
        self.assertEqual(len({row['kdrs_path'] for row in rows}),len(rows))
        self.assertTrue(any(s.metric=='without_object_count' for s in U1_COUNTS))

    def test_u1_changed_source_expression_is_not_mapped(self):
        bad=U1_SOURCE.replace('count(//arkiv)', 'count(//foo)')
        values, rows, issues=map_u1(U1_RAW,bad, {'test_id':'kdrs.u01','execution':{'kind':'u1_total'}},_parse_count)
        self.assertNotIn('archive_count',values)
        self.assertTrue(any(q['kind']=='u1_xpath_label_witness_missing' and q['metric_id']=='archive_count' for q in issues))

    def test_u1_wrong_special_handler_is_rejected(self):
        values, rows, issues=map_u1(U1_RAW,U1_SOURCE, {'test_id':'kdrs.u01','execution':{'kind':'metrics'}},_parse_count)
        self.assertFalse(rows)
        self.assertEqual(issues[0]['kind'],'u1_engine_definition_not_recognized')

    def test_u2_two_parts_and_own_identity_checked(self):
        values, rows, issues=map_u2(U2_RAW,U2_SOURCE,{'test_id':'kdrs.u02','execution':{'kind':'u2_archive_parts'}},self.index,_parse_count)
        self.assertEqual(len(values['archive_parts']),2)
        self.assertEqual(values['archive_parts'][0]['values']['folder_count'],3)
        self.assertEqual(values['archive_parts'][1]['values']['folder_count'],2)
        self.assertEqual(values['archive_parts'][1]['archive_part']['system_id'],'B')
        self.assertGreaterEqual(len(rows),20)
        self.assertEqual({r['archive_part']['index'] for r in rows},{1,2})
        self.assertTrue(all(r['profile']=='U2' for r in rows))

    def test_u2_part_title_or_order_conflict_never_maps(self):
        for value in ('Arkivdel 2: Wrong,','Arkivdel 3: Beta,', 'Arkivdel 1: Alfa, Beskrivelse: Arkivdel 3: surprise,'):
            raw=U2_RAW.replace('Arkivdel 2: Beta,',value) if 'Beskrivelse:' not in value else U2_RAW.replace('Arkivdel 1: Alfa,',value)
            v, rows, qa=map_u2(raw,U2_SOURCE,{'test_id':'kdrs.u02','execution':{'kind':'u2_archive_parts'}},self.index,_parse_count)
            self.assertEqual(rows,[])
            self.assertTrue(qa)

    def test_u2_absent_index_or_nonexistent_reference_is_opaque(self):
        test={'test_id':'kdrs.u02','execution':{'kind':'u2_archive_parts'}}
        self.assertEqual(map_u2(U2_RAW,U2_SOURCE,test,None,_parse_count),({},[],[]))
        _,rows,qa=map_u2(U2_RAW,U2_SOURCE,test,self.root/'does_not_exist',_parse_count)
        self.assertFalse(rows)
        self.assertTrue(qa)

    def test_u2_missing_xml_values_is_not_silently_zero(self):
        raw=U2_RAW.replace('[.2] Mappe typer: @@, Alle: 3 @@,','[.2] Mappe typer: @@, Alle: unknown @@,')
        values,rows,qa=map_u2(raw,U2_SOURCE,{'test_id':'kdrs.u02','execution':{'kind':'u2_archive_parts'}},self.index,_parse_count)
        self.assertNotIn('folder_count',values['archive_parts'][0]['values'])
        self.assertIn('folder_count',values['archive_parts'][1]['values'])
        self.assertNotIn('metrics.archive_parts.0.values.folder_count',{r['kdrs_path'] for r in rows})

    def test_import_and_compare_realistic_u1_u2_text(self):
        legacy,mapping,inventory=self.build()
        self.assertTrue(legacy['jobs']['U01']['metrics']['archive_count']==1)
        self.assertEqual(len(legacy['jobs']['U02']['metrics']['archive_parts']),2)
        self.assertGreaterEqual(len(mapping['comparisons']),25)
        self.assertEqual({v['mapping_status'] for v in inventory},
                         {'U1_METRICS_PROVISIONAL','U2_ARCHIVE_PART_METRICS_PROVISIONAL'})
        out=self.root/'output'
        a,b,*_=write_import(legacy,mapping,inventory,out)
        report=compare(self.index,a,b,self.xml)
        self.assertGreater(report['summary']['provisional_matches'],25)
        self.assertEqual(report['summary']['provisional_mismatches'],0)
        self.assertEqual(report['summary']['not_comparable'],0)
        self.assertFalse(report['summary']['whole_standard_saxon_lxml_parity_verified'])
        self.assertFalse(report['summary']['execution_time_source_identity_attested'])
        self.assertEqual(set(report['summary']['by_profile']),{'U1','U2'})

    def test_import_without_index_leaves_u2_unmapped(self):
        legacy,mapping,inventory=self.build(index=False)
        self.assertTrue(any(x['profile']=='U1' for x in mapping['comparisons']))
        self.assertFalse(any(x['profile']=='U2' for x in mapping['comparisons']))
        self.assertEqual(legacy['jobs']['U02']['metrics'],{})
        self.assertEqual(next(row for row in inventory if row['profile']=='U2')['mapping_status'],'OPAQUE_NOT_MAPPED')

    def test_forged_archive_part_title_refused_by_parity(self):
        legacy,mapping,_=self.build()
        row=next(x for x in mapping['comparisons'] if x['profile']=='U2')
        row['archive_part']['title']='Swapped'
        out=self.root/'forge'
        a,b,*_=write_import(legacy,mapping,[],out)
        r=compare(self.index,a,b,self.xml)
        self.assertEqual(next(x for x in r['comparisons'] if x['profile']=='U2')['reason'],
                         'archive_part_identity_mismatch')

    def test_unguarded_archive_part_mapping_rejected(self):
        legacy,mapping,_=self.build()
        next(x for x in mapping['comparisons'] if x['profile']=='U2').pop('archive_part')
        out=self.root/'forged_guard'
        a,b,*_=write_import(legacy,mapping,[],out)
        r=compare(self.index,a,b,self.xml)
        self.assertEqual(next(x for x in r['comparisons'] if x['profile']=='U2')['reason'],
                         'archive_part_identity_mismatch')

    def test_hash_of_same_xml_is_streamed_once_for_many_u2_rows(self):
        legacy,mapping,_=self.build()
        out=self.root/'output'
        a,b,*_=write_import(legacy,mapping,[],out)
        import app.noark5_kdrs_parity_v021_a11 as parity
        calls=[]
        original=parity.digest
        def tracked(path):
            calls.append(Path(path).resolve())
            return original(path)
        with patch.object(parity,'digest',side_effect=tracked):
            report=parity.compare(self.index,a,b,self.xml)
        self.assertEqual(calls.count((self.xml/'arkivstruktur.xml').resolve()),1)
        self.assertGreater(report['summary']['rows'],25)

    def test_same_index_wrong_dwm_id_rejected(self):
        legacy,mapping,_=self.build()
        self.u2_result['values']['archive_parts'][0]['archive_part']['system_id']='replaced'
        self._put(self.u2_result)
        out=self.root/'idchange'
        a,b,*_=write_import(legacy,mapping,[],out)
        r=compare(self.index,a,b,self.xml)
        row=next(x for x in r['comparisons'] if x['profile']=='U2')
        self.assertEqual(row['reason'],'archive_part_identity_mismatch')

    def test_extreme_count_text_rejected_without_integer_overflow(self):
        from app.noark5_kdrs_text_import_v021_a11 import _parse_count
        count, reason = _parse_count('N5.04 Arkiv: ' + '9' * 6000, 'N5.04 Arkiv:')
        self.assertIsNone(count)
        self.assertEqual(reason, 'count_out_of_range')

    def test_duplicate_dwm_result_id_fails_closed(self):
        legacy,mapping,_=self.build()
        out=self.root/'dup-index'
        a,b,*_=write_import(legacy,mapping,[],out)
        index=json.loads(self.index.read_text())
        index['tests'].append(dict(index['tests'][0]))
        self.index.write_text(json.dumps(index),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplisert DWM test-ID'):
            compare(self.index,a,b,self.xml)

    def test_u2_count_label_requires_source_xpath_witness(self):
        bogus=U2_SOURCE.replace('count(descendant::mappe)', 'count(descendant::other)')
        values,rows,problems=map_u2(U2_RAW,bogus,{'test_id':'kdrs.u02','execution':{'kind':'u2_archive_parts'}},self.index,_parse_count)
        self.assertNotIn('folder_count',values['archive_parts'][0]['values'])
        self.assertTrue(any(x['kind']=='u2_xpath_label_witness_missing' for x in problems))

if __name__=='__main__':
    unittest.main()
