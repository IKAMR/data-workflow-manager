"""a6: canonical backtracking, exact XSD facets and local-only variant observations."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from app.noark_xsd_rules_v0114_a6 import historical_constraints, comparison_rows, describe_constraint
from app.noark_xsd_local_evidence_v0114_a6 import save_xsd_evidence, evidence_path, work_from_report
from app.noark_xsd_version_v0114_a5 import inspect_source_version

XSD_NS='http://www.w3.org/2001/XMLSchema'
N5_NS='http://www.arkivverket.no/standarder/noark5/arkivstruktur'

class A6ContractTests(unittest.TestCase):
    def test_v5_backwards_5_4_31(self):
        r=historical_constraints('M300','5.0')
        self.assertEqual([x['version'] for x in r], ['5.0','4.0','3.1'])
        self.assertTrue(r[0]['current'])
        self.assertFalse(r[1]['current'])

    def test_v4_never_looks_forward_to_v5(self):
        self.assertEqual([x['version'] for x in historical_constraints('M082','4.0')],['4.0','3.1'])
        self.assertEqual(historical_constraints('M082',None),())
        self.assertEqual(historical_constraints('missing','5.0'),())

    def test_m300_v5_is_min_length_not_enum_or_max_length(self):
        rows=comparison_rows('M300','5.0',{'Elektroniskarkiv':678})
        self.assertEqual(rows[0]['min_length'],1)
        self.assertEqual(rows[0]['restriction'],'minLength')
        self.assertIn('Oppfyller minLength',rows[0]['observations'][0]['explanation'])
        self.assertIn('Ikke opplistet',rows[1]['observations'][0]['explanation'])
        self.assertEqual(rows[1]['values'][0],'Fysisk medium')

    def test_no_misleading_enumeration_for_m500_m502(self):
        for name in ('M500','M502'):
            a=historical_constraints(name,'5.0')
            self.assertEqual(a[0]['restriction'],'minLength')
            self.assertEqual(a[1]['restriction'],'string')
            self.assertNotIn('tillatte',describe_constraint(a[1]).lower())

    def test_save_local_variants_is_atomic_reusable_and_source_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';work=root/'work';source.mkdir();work.mkdir()
            data=(f'<xs:schema xmlns:xs="{XSD_NS}" targetNamespace="{N5_NS}" version="5.0" />').encode()
            xsd=source/'arkivstruktur.xsd';xsd.write_bytes(data)
            ev=inspect_source_version(source)
            self.assertEqual(ev.version,'5.0')
            dest=save_xsd_evidence(ev,work,timestamp='2026-11-13T12:00:00+00:00')
            self.assertEqual(dest,evidence_path(work))
            obj=json.loads(dest.read_text(encoding='utf8'))
            self.assertEqual(obj['variants'][0]['sha256'],hashlib.sha256(data).hexdigest())
            self.assertEqual(obj['variants'][0]['observation_count'],1)
            self.assertEqual(len(obj['observations']),1)
            first_id=obj['variants'][0]['variant_id']
            save_xsd_evidence(ev,work,timestamp='2026-11-13T13:00:00+00:00')
            again=json.loads(dest.read_text(encoding='utf8'))
            self.assertEqual(len(again['variants']),1)
            self.assertEqual(len(again['observations']),2)
            self.assertEqual(again['variants'][0]['variant_id'],first_id)
            self.assertEqual(again['variants'][0]['observation_count'],2)
            self.assertEqual(xsd.read_bytes(),data)
            with self.assertRaises(ValueError):save_xsd_evidence(ev,source)

    def test_reject_changed_source_after_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';work=root/'work';source.mkdir();work.mkdir()
            xsd=source/'arkivstruktur.xsd';xsd.write_text(f'<xs:schema xmlns:xs="{XSD_NS}" targetNamespace="{N5_NS}" version="5.0"/>')
            ev=inspect_source_version(source)
            xsd.write_text(f'<xs:schema xmlns:xs="{XSD_NS}" targetNamespace="{N5_NS}" version="4.0"/>')
            with self.assertRaisesRegex(ValueError,'endret'):save_xsd_evidence(ev,work)
            self.assertFalse(evidence_path(work).exists())

    def test_reject_unknown_ledger_version_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';work=root/'work';source.mkdir();work.mkdir()
            (source/'arkivstruktur.xsd').write_text(f'<xs:schema xmlns:xs="{XSD_NS}" targetNamespace="{N5_NS}" version="5.0"/>')
            ev=inspect_source_version(source)
            target=evidence_path(work);target.parent.mkdir(parents=True)
            target.write_text('{"schema_version":"99", "variants": []}')
            with self.assertRaisesRegex(ValueError,'Ukjent lokal'):save_xsd_evidence(ev,work)
            self.assertIn('"99"',target.read_text())

    def test_work_from_report_is_job_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'job.json').write_text('{}')
            r=p/'noark5_reports'/'x'/'depot_validation_report.json';r.parent.mkdir(parents=True)
            self.assertEqual(work_from_report(r),p)
            self.assertIsNone(work_from_report(None))

if __name__=='__main__':unittest.main()
