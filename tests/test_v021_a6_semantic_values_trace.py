"""a6: source-backed literal inventories, stable meaning IDs, explicit semantic QA."""
from __future__ import annotations

import ast
import copy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import quoteattr

from app.noark_semantic_values_v021_a6 import (
    load_registry, load_decisions, resolve_value, analyze_observations, main as meaning_cli,
)
from app.noark5_spec_xsd_trace_v021_a6 import (build_trace, _xpath_field_mentioned, main as trace_cli)

REGISTRY = load_registry()


def sample_approval(mid, raw, meaning, *, decision='approve_semantic_link'):
    return {'metadata_id':mid, 'raw_value':raw, 'concept_id':meaning, 'decision':decision,
            'decision_id':'QA-VALUE-2026-11-15-01', 'approved_by':'Faglig QA',
            'approved_at':'2026-11-15', 'reason':'Gjennomgått samme betydning uten normativ XSD-aksept'}


class TestMeaningIDs(unittest.TestCase):
    def test_historical_literal_inventory_has_17_xsd_enumerations_each(self):
        self.assertEqual(len(REGISTRY['concepts']), 64)
        self.assertEqual(len(REGISTRY['xsd_enumerations_by_version']['3.1']), 17)
        self.assertEqual(len(REGISTRY['xsd_enumerations_by_version']['4.0']), 17)
        self.assertEqual(len(REGISTRY['xsd_enumerations_by_version']['5.0']), 0)
        self.assertEqual(REGISTRY['xsd_enumerations_by_version']['3.1']['M619'], [
            'Besvart med brev', 'Besvart med e-post', 'Besvart på telefon',
            'Tatt til etterretning','Tatt til orientering'])
        self.assertEqual(REGISTRY['xsd_enumerations_by_version']['4.0']['M619'][-2:],
                         ['Besvart med notat','Saken ble avsluttet'])
        self.assertIn('Fysisk medium', REGISTRY['xsd_enumerations_by_version']['3.1']['M300'])
        self.assertNotIn('Fysisk arkiv', REGISTRY['xsd_enumerations_by_version']['3.1']['M300'])

    def test_phone_preposition_same_meaning_distinct_raw_literals(self):
        a = resolve_value('M619','3.1','Besvart på telefon', registry=REGISTRY)
        b = resolve_value('M619','3.1','Besvart i telefon', registry=REGISTRY)
        self.assertEqual(a['meaning_id'],b['meaning_id'])
        self.assertEqual(a['meaning_id'],'N5.M619.003')
        self.assertNotEqual(a['observed_raw'],b['observed_raw'])
        self.assertEqual(a['xsd_listing_status'],'listed_in_xsd_enumeration')
        self.assertEqual(b['xsd_listing_status'],'not_listed_in_xsd_enumeration')
        self.assertEqual(b['semantic_state'],'owner_confirmed_semantic_example')
        self.assertEqual(b['normative_conformance'],'not_assessed')

    def test_historial_v4_literal_in_v3_keeps_meaning_but_not_enum(self):
        value = resolve_value('M619','3.1','Besvart med notat',registry=REGISTRY)
        self.assertIsNotNone(value['meaning_id'])
        self.assertEqual(value['xsd_listing_status'],'not_listed_in_xsd_enumeration')

    def test_v5_no_enumeration_does_not_establish_xsd_pass(self):
        value = resolve_value('M619','5.0','Besvart i telefon',registry=REGISTRY)
        self.assertEqual(value['xsd_listing_status'],'v5_min_length_1_nonempty_not_full_validation')
        self.assertEqual(value['full_xsd_validation'],'not_performed')
        self.assertEqual(resolve_value('M619','5.0','',registry=REGISTRY)['xsd_listing_status'],
                         'v5_min_length_1_empty')

    def test_suspected_typo_and_m300_conflict_only_proposed(self):
        for raw in ('Elektronkskarkiv','Fysisk arkiv'):
            value=resolve_value('M300','4.0',raw,registry=REGISTRY)
            self.assertIsNone(value['meaning_id'])
            self.assertIsNotNone(value['candidate_meaning_id'])
            self.assertEqual(value['semantic_state'],'candidate_requires_qa')
            self.assertEqual(value['xsd_listing_status'],'not_listed_in_xsd_enumeration')

    def test_unconfirmed_spelling_variant_not_silently_approved(self):
        record=resolve_value('M619','4.0','Besvart i Telefon',registry=REGISTRY)
        self.assertEqual(record['semantic_state'],'candidate_requires_qa')
        self.assertIsNone(record['meaning_id'])

    def test_raw_and_semantic_counts_are_separate_and_lossless(self):
        counts={'Besvart på telefon':8,'Besvart i telefon':7,'Besvart med brev':2,
                'Besvart i Telefon':3,'Ukjent, lokal':1}
        report=analyze_observations('M619','4.0',counts,registry=REGISTRY)
        self.assertEqual(report['total_occurrences'],21)
        self.assertEqual(report['distinct_raw_values'],5)
        self.assertEqual(report['distinct_assigned_meaning_ids'],2)
        self.assertEqual(report['qa_candidate_occurrences'],3)
        self.assertEqual(report['unassigned_occurrences'],1)
        phone=next(x for x in report['meanings'] if x['label']=='Besvart på telefon')
        self.assertEqual(phone['occurrences'],15)
        self.assertEqual(len(phone['raw_variants']),2)
        self.assertEqual({x['observed_raw'] for x in report['rows']},set(counts))

    def test_approved_qa_decision_maps_variant_not_normative_validity(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'decision.json'
            path.write_text(json.dumps({'format_version':1,'decisions':[
                sample_approval('M300','Elektronkskarkiv','N5.M300.002')]}),encoding='utf-8')
            decisions=load_decisions(path,REGISTRY)
            row=resolve_value('M300','3.1','Elektronkskarkiv',registry=REGISTRY,decisions=decisions)
            self.assertEqual(row['meaning_id'],'N5.M300.002')
            self.assertEqual(row['semantic_state'],'qa_approved_semantic_equivalence')
            self.assertEqual(row['xsd_listing_status'],'not_listed_in_xsd_enumeration')
            self.assertEqual(row['qa_decision_id'],'QA-VALUE-2026-11-15-01')
            self.assertEqual(row['normative_conformance'],'not_assessed')

    def test_explicit_rejection_overrides_example_not_xsd(self):
        row=sample_approval('M619','Besvart i telefon','N5.M619.003',decision='reject_semantic_link')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'qa.json'
            path.write_text(json.dumps({'format_version':1,'decisions':[row]}))
            mapped=load_decisions(path,REGISTRY)
            result=resolve_value('M619','3.1','Besvart i telefon',registry=REGISTRY,decisions=mapped)
            self.assertIsNone(result['meaning_id'])
            self.assertEqual(result['candidate_reason'],'rejected_by_explicit_qa')

    def test_qa_rejects_missing_provenance_conflict_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'qa.json'
            row=sample_approval('M619','Besvart i telefon','N5.M619.003')
            for decisions in ([{k:v for k,v in row.items() if k!='reason'}],
                              [row,row],
                              [sample_approval('M300','X','N5.M619.003')],
                              [sample_approval('M619','Besvart på telefon','N5.M619.002')]):
                path.write_text(json.dumps({'format_version':1,'decisions':decisions}))
                with self.assertRaises(ValueError):
                    load_decisions(path,REGISTRY)

    def test_registry_refuses_conflicting_xsd_literal_meaning(self):
        with tempfile.TemporaryDirectory() as directory:
            r=copy.deepcopy(REGISTRY)
            item=next(x for x in r['concepts'] if x['concept_id']=='N5.M619.001')
            item['exact_xsd_literals']['3.1'].append('Besvart på telefon')
            path=Path(directory)/'bad.json';path.write_text(json.dumps(r))
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_no_auto_approval_from_case_spacing(self):
        row=resolve_value('M300','4.0','elektronisk    ARKIV',registry=REGISTRY)
        self.assertIsNone(row['meaning_id'])
        self.assertEqual(row['semantic_state'],'candidate_requires_qa')

    def test_counts_reject_negative_and_bool(self):
        for n in (-1,True,1.5):
            with self.assertRaises(ValueError):
                analyze_observations('M619','4.0',{'Besvart på telefon':n},registry=REGISTRY)

    def test_fifteen_raw_values_can_have_nine_distinct_meanings_after_qa(self):
        registry=copy.deepcopy(REGISTRY)
        for i in (8,9):
            registry['concepts'].append({
                'concept_id': f'N5.M619.{i:03d}',
                'metadata_id':'M619', 'preferred_label':f'Lokal meningskategori {i}',
                'source_type':'qa_approved_custom_concept',
                'concept_scope':'qa_approved_semantics_only_no_normative_compliance',
                'exact_xsd_literals':{'3.1':[],'4.0':[]},
                'qa':{'decision_id':f'QA-M619-CUSTOM-{i}', 'approved_by':'Faglig QA',
                      'approved_at':'2026-11-15', 'reason':'Syntetisk test av nytt meningsbegrep'},
            })
        counts={x:1 for x in registry['xsd_enumerations_by_version']['4.0']['M619']}
        additions=['Besvart i telefon', 'Svar via telefon', 'Svar i telefon',
                   'Besvart per telefon','Besvart telefonisk','Telefonisk svar']
        counts.update({x:1 for x in additions})
        counts.update({'Lokal meningskategori 8':1,'Lokal meningskategori 9':1})
        self.assertEqual(len(counts),15)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'custom.json'
            path.write_text(json.dumps(registry,ensure_ascii=False),encoding='utf-8')
            loaded=load_registry(path)
            decisions={}
            for label in additions[1:]:
                row=sample_approval('M619',label,'N5.M619.003')
                decisions[('M619',label)]=row
            for i in (8,9):
                raw=f'Lokal meningskategori {i}'
                decisions[('M619',raw)]=sample_approval('M619',raw,f'N5.M619.{i:03d}')
            report=analyze_observations('M619','4.0',counts,registry=loaded,decisions=decisions)
        self.assertEqual(report['distinct_raw_values'],15)
        self.assertEqual(report['distinct_assigned_meaning_ids'],9)
        self.assertEqual(report['unassigned_occurrences'],0)
        self.assertEqual(report['qa_candidate_occurrences'],0)
        self.assertEqual(report['total_occurrences'],15)
        phone=next(x for x in report['meanings'] if x['meaning_id']=='N5.M619.003')
        self.assertEqual(phone['occurrences'],7)
        self.assertEqual(len(phone['raw_variants']),7)
        self.assertFalse(any(row['full_xsd_validation']=='passed' for row in report['rows']))

    def test_unreviewed_new_custom_concept_is_rejected(self):
        registry=copy.deepcopy(REGISTRY)
        registry['concepts'].append({
            'concept_id':'N5.M619.008','metadata_id':'M619', 'preferred_label':'Egendefinert',
            'source_type':'qa_approved_custom_concept','exact_xsd_literals':{},
        })
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.json'
            path.write_text(json.dumps(registry,ensure_ascii=False),encoding='utf-8')
            with self.assertRaises(ValueError):
                load_registry(path)

    def test_cli_prints_lossless_counts_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'counts.json'
            p.write_text(json.dumps({'Besvart på telefon':2,'Besvart i telefon':1},ensure_ascii=False), encoding='utf-8')
            capture=StringIO()
            with redirect_stdout(capture):
                ret=meaning_cli(['--metadata','M619','--noark-version','3.1',
                                  '--counts-json',str(p)])
            report=json.loads(capture.getvalue())
            self.assertEqual(ret,0)
            self.assertEqual(report['distinct_raw_values'],2)
            self.assertEqual(report['distinct_assigned_meaning_ids'],1)
            self.assertEqual(sorted(x.name for x in Path(directory).iterdir()),['counts.json'])

    def test_gui_has_same_window_meaning_tab_and_source_preserved(self):
        gui=Path(__file__).resolve().parents[1]/'gui_qt/noark5_xpath_audit_v021_a1.py'
        source=gui.read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn("'Verdier og menings-ID'",source)
        self.assertIn('self._render_semantics()',source)
        self.assertIn('load_registry()',source)
        self.assertIn('ikke xsd-validering eller normativ godkjenning',source.lower())
        self.assertIn('QTabWidget',source)

    def test_two_fields_never_share_meaning_id(self):
        a=resolve_value('M050','4.0','Avsluttet',registry=REGISTRY)
        b=resolve_value('M052','4.0','Avsluttet',registry=REGISTRY)
        self.assertNotEqual(a['meaning_id'],b['meaning_id'])


class TestFullXsdTrace(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.src=Path(self.temp.name)/'digital-archive-workflow'
        self.dwm=Path(self.temp.name)/'data-workflow-manager'
        self.config=self.dwm/'config/noark5/standards'
        self.config.mkdir(parents=True)
        (self.config/'noark5_semantic_values_v021_a6.json').write_text(
            json.dumps(REGISTRY,ensure_ascii=False),encoding='utf-8')
        (self.dwm/'config/noark5/tests').mkdir(parents=True)
        (self.dwm/'config/noark5/tests/xpath_catalog_2026_05_26.json').write_text(json.dumps({
            'tests':[
                {'test_id':'kdrs.f06','legacy':{'job_id':'F06'},'source_xml':'arkivstruktur.xml',
                 'noark_versions':['3.1','4.0','5.0'],
                 'execution':{'kind':'metrics','metrics':[{'id':'method_count','type':'xpath',
                   'expression':'count(//avskrivningsmaate)'}]}},
                {'test_id':'kdrs.special','noark_versions':['3.1','4.0','5.0'],
                 'execution':{'kind':'special_handler'}},
            ]},ensure_ascii=False),encoding='utf-8')
        for version in ('3.1','4.0','5.0'):
            (self.config/'metadata').mkdir(exist_ok=True)
            (self.config/'requirements').mkdir(exist_ok=True)
            (self.config/'metadata'/f'{version}.json').write_text(json.dumps({
                'metadata':[{'metadata_id':'M619'}]}))
            (self.config/'requirements'/f'{version}.json').write_text(json.dumps({
                'requirements':[{'requirement_id':'R1','xml_field_name':'avskrivningsmaate'}]}))
        (self.config/'noark5_standard_values.json').write_text(json.dumps({
            'versions':{v:{'value_sets':{'M300_dokumentmedium':{
                'metadata_id':'M300','values':['Fysisk arkiv','Elektronisk arkiv',
                                              'Blandet fysisk og elektronisk arkiv']}}}
                        for v in ('3.1','4.0','5.0')}}),encoding='utf-8')
        self.create_xsds()

    def create_xsds(self):
        meta=REGISTRY['historical_xsd_type_names_3_1_4_0']
        for version in ('3.1','4.0','5.0'):
            folder=(self.src/'docs/kilder/noark/noark5'/f'v{version}'/'schemas')
            folder.mkdir(parents=True)
            defs=[]
            for mid,name in meta.items():
                values=REGISTRY['xsd_enumerations_by_version'][version].get(mid,[])
                facets=(''.join(f'<xs:enumeration value={quoteattr(val)}/>' for val in values)
                        if values else '<xs:minLength value="1"/>')
                defs.append(f'<xs:simpleType name="{name}"><xs:annotation>'
                            f'<xs:documentation>{mid}</xs:documentation></xs:annotation>'
                            f'<xs:restriction base="xs:string">{facets}</xs:restriction>'
                            f'</xs:simpleType>')
            # Add unlisted field as evidence of incompleteness, not normative approval.
            defs.append('<xs:simpleType name="systemID"><xs:annotation>'
                        '<xs:documentation>M001</xs:documentation></xs:annotation>'
                        '<xs:restriction base="xs:string"/></xs:simpleType>')
            head=f'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" version="{version}">'
            (folder/'metadatakatalog.xsd').write_text(head+''.join(defs)+'</xs:schema>',encoding='utf-8')
            for name in ('arkivstruktur','endringslogg','loependeJournal','offentligJournal'):
                body=('<xs:element name="avskrivningsmaate" type="md:avskrivningsmaate" '
                      'minOccurs="0"/>' if name=='arkivstruktur' else '')
                (folder/f'{name}.xsd').write_text(head+body+'</xs:schema>',encoding='utf-8')

    def test_xsd_types_provenance_gaps_and_xpath_candidates(self):
        report=build_trace(self.src,self.dwm)
        self.assertFalse(report['normative_requirements_all_read'])
        self.assertTrue(report['read_only'])
        self.assertEqual(report['xpath_catalog_tests'],2)
        self.assertEqual(report['xpath_special_handlers_not_semantically_audited'],1)
        for v in ('3.1','4.0','5.0'):
            vrow=report['versions'][v]
            self.assertEqual(vrow['xsd_metadata_type_definitions'],18)
            self.assertEqual(vrow['xsd_metadata_with_enumerations'],17 if v!='5.0' else 0)
            self.assertEqual(vrow['semantic_xsd_reference_enumeration_diff'],{})
            method=next(x for x in vrow['rows'] if x['metadata_id']=='M619')
            self.assertEqual(method['xpath_lexical_candidates'][0]['test_id'],'kdrs.f06')
            self.assertEqual(method['xsd_structural_type_reference_candidates'][0]['file'],'arkivstruktur.xsd')
            self.assertFalse(method['normative_requirement_tested'])
            self.assertEqual(method['dwm_registered_requirement_references'][0]['requirement_id'],'R1')
            self.assertFalse(vrow['reference_metadatakatalog_xsd_raw_sha256_matches_pinned'])
        self.assertEqual(report['qa_required']['dwm_standard_values_need_review']['3.1']['missing_enumerations_count'],16)
        issues=report['qa_required']['dwm_standard_values_need_review']['4.0']['value_set_differences']
        self.assertEqual(issues[0]['metadata_id'],'M300')
        self.assertIn('Fysisk medium',issues[0]['xsd_only'])
        self.assertIn('Fysisk arkiv',issues[0]['dwm_only'])

    def test_trace_cli_refuses_in_repo_output_and_existing_report(self):
        with tempfile.TemporaryDirectory() as dest:
            output=Path(dest)/'audit.json'
            capture=StringIO()
            with redirect_stdout(capture):
                self.assertEqual(trace_cli(['--source-root',str(self.src),
                                            '--dwm-root',str(self.dwm),
                                            '--output',str(output)]),0)
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['report_type'],
                             'technical_xsd_metadata_to_xpath_lexical_trace_not_normative_requirements_audit')
            with self.assertRaises(SystemExit):
                trace_cli(['--source-root',str(self.src),'--dwm-root',str(self.dwm),
                           '--output',str(output)])
        with self.assertRaises(SystemExit):
            trace_cli(['--source-root',str(self.src),'--dwm-root',str(self.dwm),
                       '--output',str(self.dwm/'docs/unsafe.json')])

    def test_source_xsd_missing_no_silent_acceptance(self):
        path=self.src/'docs/kilder/noark/noark5/v4.0/schemas/offentligJournal.xsd'
        path.unlink()
        with self.assertRaises(ValueError):
            build_trace(self.src,self.dwm)

    def test_xpath_lexical_does_not_match_literal_only(self):
        self.assertFalse(_xpath_field_mentioned('count(//foo[@type="avskrivningsmaate"])',
                                               'avskrivningsmaate'))
        self.assertTrue(_xpath_field_mentioned('count(//avskrivningsmaate)',
                                              'avskrivningsmaate'))


if __name__=='__main__':
    unittest.main()
