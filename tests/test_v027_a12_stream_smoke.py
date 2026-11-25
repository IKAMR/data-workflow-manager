"""Additional deterministic tests for large U1 streaming behavior."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from noark5_workflow.analysis.u1_stream_v027_a12 import run_u1_stream


class U1StreamingSmoke(unittest.TestCase):
    def test_counts_many_files_without_materializing_xml_nodesets(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'arkivstruktur.xml'
            with path.open('w', encoding='utf-8') as w:
                w.write('<arkiv><arkivdel><mappe><registrering>')
                for i in range(2000):
                    w.write('<dokumentbeskrivelse><dokumentobjekt>'
                            '<filstoerrelse>120</filstoerrelse><format>PDF</format>'
                            '</dokumentobjekt></dokumentbeskrivelse>')
                w.write('</registrering></mappe></arkivdel></arkiv>')
            r = run_u1_stream(path)
            self.assertEqual(r['documents']['object_count'], 2000)
            self.assertEqual(r['files']['size_count'], 2000)
            self.assertEqual(r['files']['size_sum'], 240000)
            self.assertEqual(r['files']['format_counts'], {'PDF': 2000})
            self.assertEqual(r['structure']['archive_parts'][0]['dokumentbeskrivelse_count'], 2000)

    def test_empty_source_is_not_reported_as_complete(self):
        with TemporaryDirectory() as d:
            path = Path(d) / 'arkivstruktur.xml'
            path.write_text('', encoding='utf-8')
            with self.assertRaises(Exception):
                run_u1_stream(path)
