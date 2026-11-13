"""a7: local experience matching and assessments; no source modification."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.noark_experience_v0114_a7 import (find_known_cases, save_assessment,
    assessment_path, save_local_practice, known_cases)


class A7ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.work=self.root/'work';self.work.mkdir();(self.work/'job.json').write_text('{}')
        self.xsd=self.source/'arkivstruktur.xsd';self.xsd.write_text('untouched')
        self.environment=patch.dict(os.environ, {'LOCALAPPDATA':str(self.root/'profile')})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def match(self,version='5.0',field='document_medium',value='Elektroniskarkiv'):
        return find_known_cases(metadata_id='M300',field=field,noark_version=version,observed_values={value:678})

    def test_seed_exists_and_is_not_approved_conclusion(self):
        self.assertEqual(len(known_cases()),1)
        self.assertEqual(known_cases()[0]['review_status'],'draft')
        self.assertIn('ikke i seg selv', known_cases()[0]['suggested_note'])

    def test_exact_version_and_value_not_historical_comparison(self):
        self.assertEqual(len(self.match()),1)
        self.assertFalse(self.match(version=None))
        self.assertFalse(self.match(version='4.0'))
        self.assertFalse(self.match(value='Elektronisk arkiv'))
        self.assertFalse(self.match(field='other'))

    def test_assessment_is_event_history_not_test_mutation(self):
        kwargs=dict(case_id='NOARK5-M300-001',noark_version='5.0',observed_value='Elektroniskarkiv',
                    observed_count=678,status='needs_follow_up',note='Må vurderes',
                    test_id='kdrs.c02',source=self.source)
        path=save_assessment(self.work,**kwargs,timestamp='2026-11-13T12:00:00Z')
        # Windows may resolve the same directory to a long or 8.3 short path.
        # Compare filesystem identity, not the textual path spelling.
        self.assertTrue(path.samefile(assessment_path(self.work)))
        save_assessment(self.work,**{**kwargs,'status':'reviewed_equivalent','note':'Kontrollert semantikk'})
        events=json.loads(path.read_text())['events']
        self.assertEqual(len(events),2)
        self.assertNotEqual(events[0]['event_id'],events[1]['event_id'])
        self.assertEqual(events[0]['decision'],'needs_follow_up')
        self.assertEqual(events[1]['decision'],'reviewed_equivalent')
        self.assertFalse(events[0]['automatic_test_status_modified'])
        self.assertEqual(self.xsd.read_text(),'untouched')
        self.assertNotIn(str(self.source),path.read_text())

    def test_refuse_wrong_version_status_and_missing_work(self):
        common=dict(case_id='NOARK5-M300-001',noark_version='5.0',observed_value='Elektroniskarkiv',
                    observed_count=678,status='needs_follow_up',note='OK',test_id='kdrs.c02',source=self.source)
        for key,value in [('noark_version','3.1'),('status','approved_extract'),('observed_value','X'),('observed_count',0),('note','')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                save_assessment(self.work,**{**common,key:value})
        with self.assertRaises(ValueError):save_assessment(self.source,**common)
        with self.assertRaises(ValueError):save_assessment(self.root/'nojob',**common)
        self.assertFalse(assessment_path(self.work).exists())

    def test_local_override_is_separate_and_optional(self):
        self.assertFalse(self.match()[0].get('local_practice'))
        dest=save_local_practice(case_id='NOARK5-M300-001',note='Lokal praksis valgt')
        self.assertTrue(dest.is_file())
        self.assertIn(str(self.root/'profile'),str(dest))
        match=self.match()[0]
        self.assertEqual(match['suggested_note'],'Lokal praksis valgt')
        self.assertTrue(match['local_practice'])
        self.assertFalse(assessment_path(self.work).exists())
        self.assertEqual(self.xsd.read_text(),'untouched')

    def test_unknown_format_not_overwritten(self):
        dest=self.root/'profile'/'DataWorkflowManager'/'noark5'/'experience'/'local_practice.json'
        dest.parent.mkdir(parents=True)
        dest.write_text('{"schema_version":"99","catalog_type":"dwm_noark5_local_practice","overrides":[]}')
        with self.assertRaisesRegex(ValueError,'Ukjent erfaringsfilformat'):
            save_local_practice(case_id='NOARK5-M300-001',note='text')
        self.assertIn('"99"',dest.read_text())

if __name__=='__main__':unittest.main()
