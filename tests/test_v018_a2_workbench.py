"""Headless regression checks for laptop workbench projections (no Tk needed)."""
import unittest
from types import SimpleNamespace

from app.workbench_snapshot_v018_a2 import clamp_geometry, elide_path, job_rows


class WorkbenchSnapshotA2Tests(unittest.TestCase):
    def test_job_rows_are_read_only_and_do_not_open_storage(self):
        class MissingShare:
            def __str__(self):
                return r"\\server\offline\uttrekk"
            def __fspath__(self):
                raise AssertionError("Must not access filesystem")

        job = SimpleNamespace(
            job_id="JOB-002", name="2016-09-27", status=SimpleNamespace(value="Ferdig"),
            progress=1.0, source_extraction=MissingShare(), source_root=None,
            work_operations=r"E:\repository_operations", active_extraction_root=None,
        )
        row, = job_rows([job], "JOB-002")
        self.assertEqual(row.percentage, 100)
        self.assertTrue(row.active)
        self.assertEqual(row.source, r"\\server\offline\uttrekk")
        self.assertEqual(job.progress, 1.0)

    def test_empty_and_unnamed_job(self):
        job = SimpleNamespace(job_id="JOB-001", status="Klar", progress=-1,
                              source_root=None, work_operations=None)
        row, = job_rows([job], None)
        self.assertEqual((row.name, row.percentage, row.source, row.active),
                         ("JOB-001", 0, "Ikke valgt", False))

    def test_progress_is_bounded(self):
        j = SimpleNamespace(job_id="J", progress=900, status="Kjører")
        row, = job_rows([j], "J")
        self.assertEqual(row.percentage, 100)

    def test_elide_long_network_path(self):
        p = "\\\\host\\share\\" + "longfolder\\" * 20 + "uttrekk"
        short = elide_path(p, 54)
        self.assertEqual(len(short), 54)
        self.assertTrue(short.startswith("\\\\host\\"))
        self.assertTrue(short.endswith("uttrekk"))
        self.assertEqual(elide_path("C:\\work"), "C:\\work")

    def test_geometry_on_laptop(self):
        x, y, w, h = clamp_geometry(-100, -50, 1500, 900,
                                  monitor_x=0, monitor_y=0,
                                  monitor_width=1366, monitor_height=728)
        self.assertEqual((x, y, w, h), (12, 12, 1342, 704))

    def test_geometry_on_negative_secondary(self):
        x, y, w, h = clamp_geometry(-2100, 100, 1850, 1000,
                                  monitor_x=-1920, monitor_y=0,
                                  monitor_width=1920, monitor_height=1040)
        self.assertEqual((x, y, w, h), (-1908, 28, 1850, 1000))


if __name__ == "__main__":
    unittest.main()
