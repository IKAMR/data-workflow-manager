from __future__ import annotations
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.noark5_batch_discovery_v027_a11 import (
    Candidate, component, discover, assign_work, resolve_info_xml,
)


class BatchDiscoveryTests(unittest.TestCase):
    def test_many_packages_and_skip_document_payload(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('1502_003', '1502_004', '1502_005'):
                docs = root / name / 'content' / 'sip' / 'content' / 'a' / 'avleveringspakke' / 'DOKUMENT'
                docs.mkdir(parents=True)
                (docs.parent / 'arkivstruktur.xml').write_text('<arkiv/>')
                (docs / 'arkivstruktur.xml').write_text('<not_candidate/>')
            (root / 'other').mkdir()
            (root / 'other' / 'arkivstruktur.xml').write_text('<not_candidate/>')
            found = discover(root)
            self.assertEqual(len(found), 3)
            self.assertEqual({c.package_root.name for c in found}, {'1502_003','1502_004','1502_005'})
            mapping = assign_work(found, dwm_folder='dwm', run_folder='a01')
            self.assertEqual(len(set(mapping.values())), 3)
            self.assertTrue(all(p.parts[-3:] == ('repository_operations', 'dwm', 'a01') for p in mapping.values()))

    def test_same_package_gets_distinct_work(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            a = Candidate(root / 'one', root / 'package')
            b = Candidate(root / 'two', root / 'package')
            mapping = assign_work((a,b))
            self.assertNotEqual(mapping[a.source], mapping[b.source])

    def test_external_info_only_exact_match(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'part' / 'extract'
            source.mkdir(parents=True)
            candidate = Candidate(source, root / 'part')
            info = root / 'infos' / 'part'
            info.mkdir(parents=True)
            (info / 'info.xml').write_text('<mets/>')
            self.assertTrue((resolve_info_xml(candidate, root / 'infos')).samefile(info / 'info.xml'))
            (source / 'info.xml').write_text('<mets/>')
            self.assertIsNone(resolve_info_xml(candidate, root / 'infos'))

    def test_reject_unsafe_work_components(self):
        for invalid in ('../a01', 'a01/other', '', 'CON\\x', '..'):
            with self.assertRaises(ValueError):
                component(invalid)

    def test_never_descend_old_work(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            hidden = root / 'repository_operations' / 'dwm' / 'old'
            (hidden / 'DOKUMENT').mkdir(parents=True)
            (hidden / 'arkivstruktur.xml').write_text('<arkiv/>')
            self.assertEqual(discover(root), ())


if __name__ == '__main__':
    unittest.main()
