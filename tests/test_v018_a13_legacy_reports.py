"""a13 legacy multi-overview adapter: explicit Work selection, no joblist scan."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from app.result_evidence_v018_a13 import open_work_job
from app.legacy_multi_report_v018_a13 import (
    LegacyExportStopped, render_legacy_multi, write_legacy_multi_report,
)


class LegacyA6Stub(types.ModuleType):
    METRICS = (("folder_count", "Mapper"), ("registration_count", "Registreringer"))

    @staticmethod
    def selected_report_sections(profile, sections=None):
        return set(sections if sections is not None else ("archive_parts",))

    @staticmethod
    def extract(path):
        model = json.loads(path.read_text(encoding="utf-8"))
        return {"job": "JOB-001", "extraction": str(path.parent),
                "name": path.parent.name,
                "metrics": {"folder_count": model["summary"]["folder_count"],
                            "registration_count": model["summary"]["registration_count"]},
                "technical_status": "ok", "deviation_count": 1, "assessment_status": "requires_clarification"}

    @staticmethod
    def build_report_metrics(item):
        return {key: {"value": item["metrics"][key], "source": "DWM"}
                for key in ("folder_count", "registration_count")}

    @staticmethod
    def coverage_rows(items):
        return [["Mapper", sum(i["metrics"]["folder_count"] for i in items), True, len(items), len(items), len(items), len(items)]]

    @staticmethod
    def render(items, generated):
        return "<html><body><h1>Samlet Noark 5</h1><p>" + "|".join(
            i["job_uid"] for i in items) + "</p></body></html>"

    @staticmethod
    def filter_report_html(html, profile, sections):
        return html

    @staticmethod
    def render_extraction_attachment(item, generated, profile, sections):
        return "<html><body><p>" + item["job_uid"] + "</p></body></html>"


class LegacyOverviewBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.output = self.base / "output"
        self.output.mkdir()
        tools = types.ModuleType("tools")
        tools.__path__ = []
        self.stub = LegacyA6Stub("tools.noark5_batch_overview_a6")
        outputs = types.ModuleType("tools.report_outputs")
        def fake_pdf(html, pdf):
            pdf.write_bytes(b"test pdf file")
        outputs.html_to_pdf = fake_pdf
        self._old = {name: sys.modules.get(name) for name in (
            "tools", "tools.noark5_batch_overview_a6", "tools.report_outputs")}
        sys.modules.update({"tools": tools, "tools.noark5_batch_overview_a6": self.stub,
                            "tools.report_outputs": outputs})
        self.addCleanup(self._restore)

    def _restore(self):
        for name, previous in self._old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def make(self, name, uid, count=1, job_id="JOB-001"):
        root = self.base / name
        work = root / "dwm"
        report = work / "noark5_reports" / "depot_validation" / "run" / "depot_validation_report.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({"report_type": "noark5_depot_validation",
                                      "summary": {"folder_count": count, "registration_count": count+2}}), encoding="utf-8")
        (work / "job.json").write_text(json.dumps({"job_uid": uid, "job": {
            "job_id": job_id, "source_root": str(self.base / name / "source"),
            "archive_root": str(self.base / name / "AIP")}}),encoding="utf-8")
        return open_work_job(job_id, name, work)

    def test_old_renderer_receives_individual_report_facts_not_joblist(self):
        a=self.make('one','uid-1',4)
        b=self.make('two','uid-2',9)
        html,payload,attachments=render_legacy_multi([a,b])
        self.assertEqual(len(payload['items']),2)
        self.assertEqual({i['job_uid'] for i in payload['items']},{'uid-1','uid-2'})
        self.assertTrue(all(i['job']=='JOB-001' for i in payload['items']))
        self.assertIn('uid-1|uid-2',html)
        self.assertEqual(attachments,())
        self.assertEqual(payload['items'][1]['report_metrics']['folder_count']['value'],9)

    def test_export_three_formats_and_optional_pdf_uses_old_motor(self):
        a=self.make('one','uid-1',2)
        final,warnings=write_legacy_multi_report(self.output,[a])
        self.assertEqual(warnings,())
        self.assertTrue(final.is_file())
        self.assertTrue((self.output/'noark5-uttrekksoversikt.json').is_file())
        self.assertTrue((self.output/'noark5-uttrekksoversikt.csv').is_file())
        self.assertTrue((self.output/'noark5-uttrekksoversikt.pdf').is_file())
        records=json.loads((self.output/'noark5-uttrekksoversikt.json').read_text(encoding='utf-8'))
        self.assertEqual(records['items'][0]['job_uid'],'uid-1')
        self.assertIn('Varig Work-jobb-ID',(self.output/'noark5-uttrekksoversikt.csv').read_text(encoding='utf-8-sig'))

    def test_attachments_use_profile_sections_and_prefix(self):
        a=self.make('one','uid-1')
        b=self.make('two','uid-2')
        final,warnings=write_legacy_multi_report(self.output,[a,b],prefix='municipality',layout='attachments')
        self.assertFalse(warnings)
        self.assertIn('municipality_noark5-uttrekksoversikt-vedlegg/',final.read_text(encoding='utf-8'))
        folder=self.output/'municipality_noark5-uttrekksoversikt-vedlegg'
        self.assertTrue((folder/'vedlegg-001-JOB-001.html').is_file())
        self.assertTrue((folder/'vedlegg-002-JOB-001.html').is_file())

    def test_overview_attachments_keep_mandatory_content_without_optional_sections(self):
        """a13: Oversikt + hovedrapport/vedlegg must not yield a blank appendix.

        The real a6 engine drops the whole extraction section if the original
        'oversikt' profile is passed to its attachment renderer with no sections.
        """
        a = self.make('one', 'uid-1', 1)
        calls = []

        def legacy_attachment(item, timestamp, profile, sections):
            calls.append((profile, set(sections)))
            if profile == 'oversikt' and not sections:
                return '<html><body><h1>Vedlegg</h1></body></html>'
            if profile == 'standard' and sections == {'coverage'}:
                return ('<html><body><h1>Vedlegg</h1><h2>JOB-001</h2>'
                        '<p>Teknisk status: ok</p><h3>Datadekning</h3>'
                        '<table><tr><td>Mapper</td><td>1</td></tr></table>'
                        '</body></html>')
            raise AssertionError(f'Unexpected profile/sections: {profile}, {sections}')

        with patch.object(self.stub, 'selected_report_sections', return_value=set()), \
                patch.object(self.stub, 'render_extraction_attachment', legacy_attachment):
            html, payload, attachments = render_legacy_multi(
                [a], profile='oversikt', layout='attachments', sections=[]
            )
            self.assertEqual(calls, [('standard', {'coverage'})])
            self.assertIn('Mapper', attachments[0]['html'])
            self.assertIn('Datadekning', attachments[0]['html'])
            self.assertEqual(payload['report_presentation']['profile'], 'oversikt')
            self.assertEqual(payload['report_presentation']['sections'], [])
            self.assertIn('Vedlegg per uttrekk', html)
            output_html, warnings = write_legacy_multi_report(
                self.output, [a], prefix='1599_001_a02', profile='oversikt',
                layout='attachments', sections=[]
            )
            self.assertEqual(warnings, ())
            self.assertTrue(output_html.is_file())
            attachment = (self.output / '1599_001_a02_noark5-uttrekksoversikt-vedlegg'
                          / 'vedlegg-001-JOB-001.html')
            self.assertTrue(attachment.is_file())
            self.assertIn('Datadekning', attachment.read_text(encoding='utf-8'))
            self.assertIn('Mapper', attachment.read_text(encoding='utf-8'))

    def test_detail_attachment_profile_not_changed(self):
        a = self.make('one', 'uid-1', 1)
        calls = []

        def record_attachment(item, timestamp, profile, sections):
            calls.append((profile, set(sections)))
            return '<html><body><h1>Detaljert vedlegg</h1></body></html>'

        with patch.object(self.stub, 'selected_report_sections', return_value={'arkade_tests'}), \
                patch.object(self.stub, 'render_extraction_attachment', record_attachment):
            render_legacy_multi([a], profile='detaljert', layout='attachments')
        self.assertEqual(calls, [('detaljert', {'arkade_tests'})])

    def test_no_implicit_overwrites_or_source_writes(self):
        a=self.make('one','uid-1')
        write_legacy_multi_report(self.output,[a])
        with self.assertRaises(FileExistsError):
            write_legacy_multi_report(self.output,[a])
        source=self.base/'one'/'source'
        source.mkdir()
        with self.assertRaises(ValueError):
            write_legacy_multi_report(source,[a])
        aip=self.base/'one'/'AIP'
        aip.mkdir()
        with self.assertRaises(ValueError):
            write_legacy_multi_report(aip,[a])

    def test_cancel_before_export_no_files(self):
        a=self.make('one','uid-1')
        stop=Event()
        stop.set()
        with self.assertRaises(LegacyExportStopped):
            write_legacy_multi_report(self.output,[a],cancelled=stop)
        self.assertEqual(list(self.output.iterdir()),[])

    def test_duplicate_same_work_uid_is_rejected(self):
        a=self.make('one','uid-1')
        b=self.make('two','uid-1')
        with self.assertRaises(ValueError):
            render_legacy_multi([a,b])

if __name__=='__main__':
    unittest.main()
