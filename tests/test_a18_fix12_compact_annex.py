"""Fix12: compact per-part evidence and conservative Arkade source hints."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from noark5_workflow.reporting.archive_part_annex_a18 import render_archive_part_annex
from noark5_workflow.reporting.source_identity_a18 import source_identity_warnings
from noark5_workflow.reporting import report_package_a16 as report
from noark5_workflow.reporting import job_summary_a16 as summary


def job(id='JOB-002'):
    return SimpleNamespace(job_id=id,name='arkiv', source_extraction='G:/arkiv/1502_024_ephorte-mk_2TB_2023_noark5',
                           work_operations='G:/arkiv/1502_024_ephorte-mk_2TB_2023_noark5/repository_operations/dwm',
                           progress=1.0,status=SimpleNamespace(value='Ferdig'))


def native():
    return {'summary':{'archive_part_count':2},'archive_parts':[
        {'archive_part':{'system_id':'a1','title':'Saksarkiv','status':'Avsluttet periode',
                          'description':'Historisk dokumentasjon','archive_period_start_date':'2005-01-01'},
         'folder_count':None,'registration_count':None,'journalpost_count':None,
         'document_description_count':None,'document_object_count':None,'yearly_volume':{}},
        {'archive_part':{'system_id':'a2','title':'Voksenopplæring','description':''},
         'folder_count':0,'registration_count':0,'journalpost_count':0,
         'document_description_count':0,'document_object_count':0,'yearly_volume':{}},
    ]}


def comparison():
    def part(sid,title,values):
        return {'job_id':'JOB-002','title':title,'system_id':sid,
            'u2_status':'Koblet via entydig arkivdeltittel','u2':[{'source_file':'legacy_U02.txt','source_import_id':'import1'}],
            'metrics':{k:{'dwm': (0 if sid=='a2' else None), 'report':(0 if sid=='a2' else None), 'source':'DWM' if sid=='a2' else None}
                       for k in ('folder_count','registration_count','journalpost_count','document_description_count','document_object_count')},
            'kdrs_u2_observations':{k:{'value':v,'status':'kildedokumentert','sources':[]} for k,v in zip(
                ('folder_count','registration_count','journalpost_count','document_description_count','document_object_count'),values)}}
    return {'archive_parts':[part('a1','Saksarkiv',(6848,41467,41254,49926,121728)),
                             part('a2','Voksenopplæring',(0,0,0,0,0))], 'unmatched_u2':[], 'diagnostics':[]}


class TestCompactAnnex(unittest.TestCase):
    def test_exactly_one_part_section_with_dwm_and_u2(self):
        html=render_archive_part_annex([(job(),native(),None,'')],comparison())
        self.assertEqual(html.count('<section class="appendix">'),2)
        self.assertIn('121 728',html)
        self.assertIn('41 467',html)
        self.assertIn('Historisk dokumentasjon',html)
        self.assertIn('archive_period_start_date',html)
        self.assertIn('KDRS Query U2 (observert)',html)
        self.assertIn('Rapportverdi',html)
        self.assertNotIn('Omfang per år',html)
        self.assertNotIn('Ingen lagret årsfordeling',html)
        self.assertNotIn('<td>None</td>',html)
        self.assertIn('<td>0</td>',html)
        self.assertIn('legacy_U02.txt',html)

    def test_never_presents_observed_u2_as_dwm_report(self):
        html=render_archive_part_annex([(job(),native(),None,'')],comparison())
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(html,'html.parser')
        rows=soup.select('section.appendix')[0].select('table')[-1].select('tr')
        self.assertIn('6 848',rows[2].get_text(' ',strip=True))
        self.assertIn('Ukjent',rows[3].get_text(' ',strip=True))

    def test_verified_scope_is_only_one_part(self):
        model=comparison()
        model['archive_parts'][0]['metrics']['folder_count']={'dwm':None,'report':6848,'source':'KDRS Query (verifisert)'}
        html=render_archive_part_annex([(job(),native(),None,'')],model)
        self.assertEqual(html.count('(KDRS)'),1)
        self.assertIn('Verifisert, arkivdelavgrenset KDRS-valg',html)

    def test_unmatched_u2_stays_unassigned(self):
        model=comparison()
        model['unmatched_u2']=[{'job_id':'JOB-002','title':'Feil navn','reason':'Ingen entydig tittel','source_file':'U02.txt'}]
        self.assertIn('U2-kilder uten entydig arkivdelkobling',render_archive_part_annex([(job(),native(),None,'')],model))

    def test_no_cross_job_evidence(self):
        html=render_archive_part_annex([(job('JOB-999'),native(),None,'')],comparison())
        self.assertNotIn('6 848',html)
        self.assertIn('ikke tilordnet',html)

    def test_source_name_warns_only_strong_mismatch(self):
        runs=[{'import_id':'ark1','source_file':'1502_003_mei_2TB_testrapport.json'},
              {'import_id':'ark2','source_file':'1502_003_mk_2TB_testrapport.json'},
              {'import_id':'ark3','source_file':'arkade5_report.json'}]
        warnings=source_identity_warnings(job(),runs)
        self.assertEqual(len(warnings),1)
        self.assertEqual(warnings[0]['file_subseries'],'mei')
        self.assertEqual(warnings[0]['job_subseries'],'mk')
        self.assertEqual(warnings[0]['import_id'],'ark1')

    def test_source_name_no_heuristic_on_unrelated_job(self):
        j=SimpleNamespace(job_id='JOB-001',source_extraction='G:/extractions/ephorte-hist-lb',name='historisk')
        self.assertFalse(source_identity_warnings(j,[{'source_file':'arkade5.json'}]))

    def test_report_package_uses_compact_annex_instead_of_duplicates(self):
        from noark5_workflow.reporting import evidence_comparison_a18 as comparison_mod
        d=native(); j=job()
        e={'arkade5':{'imports':[{'import_id':'im1','source_file':'1502_003_mei_2TB_testrapport.json','source_version':'2.12.3',
                                 'number_of_errors':10,'tests':[]}]},'kdrs_query':{'resources':[]}}
        options=summary.ReportOptions('Full',('overview','totals','technical','external'),True,True)
        with TemporaryDirectory() as temp:
            with patch.object(summary,'_latest_report',return_value=(d,None,'')),\
                 patch.object(report,'_latest_report',return_value=(d,None,'')),\
                 patch.object(report,'collect_job_evidence',return_value=e),\
                 patch.object(report,'collect_u2_archive_parts',return_value=comparison()):
                report.write_report_package(temp,[j],options,formats=('html','json'))
            b=Path(temp,'vedlegg-b-arkivdeler.html').read_text('utf8')
            c=Path(temp,'vedlegg-c-teknisk-evidens.html').read_text('utf8')
            idx=Path(temp,'index.html').read_text('utf8')
            js=Path(temp,'index.json').read_text('utf8')
        self.assertEqual(b.count('<section class="appendix">'),2)
        self.assertEqual(b.count('Vedlegg – arkivdel:'),2)
        self.assertIn('121 728',b)
        self.assertNotIn('Ingen lagret årsfordeling',b)
        self.assertIn('Kildeidentitet',idx)
        self.assertIn('Mulig kildetilhørighetsavvik',c)
        self.assertIn('source_identity_warnings',js)

if __name__=='__main__':unittest.main()
