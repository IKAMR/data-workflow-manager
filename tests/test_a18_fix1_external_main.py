"""New report requirements from the 1502 and 1525 cross-client trials."""
import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from noark5_workflow.reporting import report_package_a16 as package
from noark5_workflow.reporting import job_summary_a16 as job_summary
from noark5_workflow.reporting import external_report_a18 as evidence


class Job:
    def __init__(self, ident, work):
        self.job_id = ident
        self.name = ident
        self.work_operations = str(work)
        self.status = types.SimpleNamespace(value='Ferdig')
        self.progress = 1.0


def native():
    return {
        'summary': {'archive_part_count': 2, 'folder_count': 10, 'registration_count': 50},
        'archive_parts': [
            {'archive_part': {'title': 'Saksarkiv', 'system_id': 'S'}},
            {'archive_part': {'title': 'Elevarkiv', 'system_id': 'E'}},
        ],
        'technical_validation': {'summary': {'ok': 2, 'error': 0}},
    }


class A18Fix1ReportTests(unittest.TestCase):
    def test_multiple_archive_parts_have_separate_html_lines_in_both_renderers(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job('JOB-001', td)
            data = native()
            with patch.object(job_summary, '_latest_report', return_value=(data, None, '')):
                result = job_summary.render_selected_jobs_report(
                    [job], job_summary.ReportOptions(level='Enkel'))
            self.assertIn('Saksarkiv<br>Elevarkiv', result)
            overview = package._main([job], [(job, data, None, '')], level='Enkel')
            self.assertIn('Saksarkiv<br>Elevarkiv', overview)
            self.assertNotIn('Saksarkiv, Elevarkiv', overview)

    def test_count_overview_never_presents_partial_sum_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            a = Job('JOB-001', td)
            b = Job('JOB-002', td)
            rows = [(a, native(), None, ''), (b, None, None, 'Mangler depotrapport')]
            result = evidence.report_count_overview(rows)
            folders = next(x for x in result['totals'] if x['metric'] == 'folder_count')
            self.assertEqual((folders['dwm_sum'], folders['dwm_coverage'], folders['effective_coverage']), (10, 1, 1))
            html = evidence.render_count_overview(result)
            self.assertIn('10 (1/2 uttrekk)', html)
            self.assertIn('Ukjent', html)

    def test_verified_kdrs_selected_value_is_replacement_not_additive(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            report = base / 'depot_validation_report.json'
            report.write_text(json.dumps(native()), encoding='utf8')
            source = b'imported KDRS data'
            (base / 'depot-external-evidence.json').write_bytes(source)
            projection = {
                'kind': 'noark5_effective_evidence_projection',
                'native_report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
                'evidence_companion_file': 'depot-external-evidence.json',
                'evidence_companion_sha256': hashlib.sha256(source).hexdigest(),
                'whole': {'folder_count': {
                    'dwm_value': 10, 'effective_value': 12,
                    'effective_source': 'KDRS Query',
                    'status': 'external_evidence_selected',
                    'evidence': {'source_sha256': 'abc', 'metric_id': 'folder_count'},
                }},
            }
            candidate = base / 'depot-effective-evidence.json'
            candidate.write_text(json.dumps(projection), encoding='utf8')
            values, warning = evidence.verified_main_counts(native(), report)
            self.assertEqual(warning, '')
            self.assertEqual(values['folder_count'], {'dwm_value': 10, 'effective_value': 12, 'source': 'KDRS Query'})
            count = evidence.report_count_overview([(Job('JOB-001', td), native(), report, '')])
            self.assertEqual(next(x for x in count['totals'] if x['metric']=='folder_count')['effective_sum'], 12)
            self.assertIn('Valgt KDRS', evidence.render_count_overview(count))
            # A native edit or tampered external companion must not be used.
            (base / 'depot-external-evidence.json').write_text('tampered', encoding='utf8')
            values, warning = evidence.verified_main_counts(native(), report)
            self.assertEqual(values['folder_count']['effective_value'], 10)
            self.assertIn('endret', warning)

    def test_kdrs_import_visible_even_when_native_report_missing(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            (work / 'external_evidence' / 'kdrs_query').mkdir(parents=True)
            job = Job('JOB-002', work)
            fake = {'schema':'ikamr.noark5.external_report.a18.v1', 'job_id':'JOB-002',
                    'arkade5':{'imports': []}, 'kdrs_query':{'resources':[
                        {'report_type':'u02','source_file':'u2.txt','test_id':'U2',
                         'observations':[{'line':1,'text':'6848 mapper'}]}
                    ],'selected_report_values':{'folder_count':{'value':6848}}}, 'diagnostics':[]}
            with patch.object(evidence, 'collect_job_evidence', return_value=fake):
                rows=evidence.external_status_rows([(job,None,None,'48 XPath-feil')])
            self.assertEqual(rows[0]['kdrs_u2'], 1)
            self.assertEqual(rows[0]['kdrs_selected'], 1)
            self.assertFalse(rows[0]['depot_report'])
            rendered=evidence.render_external_status(rows)
            self.assertIn('JOB-002', rendered)
            self.assertIn('U2: 1', rendered)
            self.assertIn('Mangler', rendered)

    def test_report_main_contains_external_status_and_covered_counts(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job('JOB-001', td)
            d=native()
            html = package._main([job], [(job,d,None,'')], level='Enkel')
            self.assertIn('Ekstern evidens – importstatus per uttrekk', html)
            self.assertIn('Samlet omfang – DWM og valgt KDRS Query',html)
            self.assertIn('PRONOM-filobservasjoner',html)
            self.assertIn('Saksarkiv<br>Elevarkiv',html)
            self.assertNotIn('48 XPath-feil',html)

    def test_missing_observation_is_cannot_assess_not_no_review(self):
        with tempfile.TemporaryDirectory() as td:
            job = Job('JOB-002', td)
            self.assertEqual(job_summary._review_status(job, {'period_reconciliation':{'observed_series':{}}}), 'Kan ikke vurderes')

if __name__ == '__main__':
    unittest.main()

class A18Fix1ChosenSourceTests(unittest.TestCase):
    def test_selected_whole_kdrs_fills_missing_native_but_not_conflicting_dwm(self):
        with tempfile.TemporaryDirectory() as td:
            a=Job('JOB-001',td)
            b=Job('JOB-002',td)
            native_report = native()
            selected_a = {'kdrs_query': {'selected_report_values': {
                'document_object_count': {'value':121728},
                'folder_count':{'value':11},
            }}}
            def collector(job,_):
                return selected_a if job.job_id == 'JOB-001' else {'kdrs_query': {'selected_report_values': {}}}
            with patch.object(evidence,'collect_job_evidence',side_effect=collector):
                overview=evidence.report_count_overview([(a,native_report,None,''),(b,None,None,'')])
            one=overview['jobs'][0]['values']
            self.assertEqual(one['document_object_count']['effective_value'],121728)
            self.assertEqual(one['document_object_count']['source'],'KDRS Query (valgt)')
            self.assertEqual(one['folder_count']['effective_value'],10)
            self.assertEqual(one['folder_count']['kdrs_selected_value'],11)
            self.assertIn('121 728 (1/2 uttrekk)',evidence.render_count_overview(overview))
            self.assertIn('Valgt KDRS',evidence.render_count_overview(overview))

class A18Fix1PDFTests(unittest.TestCase):
    def test_pdf_keeps_separate_archive_parts(self):
        try:
            import reportlab  # noqa: F401
            import bs4  # noqa: F401
        except ImportError:
            self.skipTest('PDF optional dependencies are unavailable')
        html=package._page('Test',package._table(('Uttrekk','Arkivdeler'),[
            ('Test', 'Saksarkiv\nElevarkiv')]),['index.html'])
        pdf=package._pdf_bytes(html)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf),1000)

class A18Fix1MachineReadableTests(unittest.TestCase):
    def test_json_reports_the_same_main_overview_sources(self):
        with tempfile.TemporaryDirectory() as td:
            job=Job('JOB-002',td)
            report=native()
            opts=job_summary.ReportOptions(level='Medium',sections=('overview','totals','external'))
            with patch.object(job_summary,'_latest_report',return_value=(report,None,'')),patch.object(package,'_latest_report',return_value=(report,None,'')):
                package.write_report_package(td,[job],opts,formats=('html','json'))
            j=json.loads((Path(td)/'index.json').read_text(encoding='utf8'))
            self.assertEqual(j['main_count_overview']['totals'][1]['effective_sum'],10)
            self.assertEqual(j['external_import_status'][0]['job_id'],'JOB-002')
            html=(Path(td)/'index.html').read_text(encoding='utf8')
            self.assertIn('10 (1/1 uttrekk)',html)
            self.assertIn('JOB-002',html)
