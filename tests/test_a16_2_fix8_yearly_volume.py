"""unittest: year-volume aggregation and boundary candidates."""
import unittest
from noark5_workflow.reporting.yearly_volume_a16 import archive_part_volumes, combined_volumes, sparse_boundary_years


class YearlyVolumeTests(unittest.TestCase):
    def test_combines_part_counts_without_mutating_parts(self):
        report = {'archive_parts': [
            {'archive_part': {'system_id': '1', 'title': 'A'}, 'yearly_volume': {'folder': {'1997': 1, '1999': 100, '2000': 90}, 'journal': {'1999': 200}}},
            {'archive_part': {'system_id': '2', 'title': 'B'}, 'yearly_volume': {'folder': {'1999': 5}, 'journal': {'1999': 7}}},
        ]}
        parts = archive_part_volumes(report)
        self.assertEqual(2, len(parts))
        self.assertEqual(1, parts[0][2][1997]['folder'])
        summed = combined_volumes(parts)
        self.assertEqual(105, summed[1999]['folder'])
        self.assertEqual(207, summed[1999]['journal'])
        self.assertEqual(1, summed[1997]['folder'])
        self.assertEqual([(1997, 1)], sparse_boundary_years(summed))

    def test_2099_single_case_requires_review_not_auto_removed(self):
        report = {'archive_parts': [{'archive_part': {'system_id': 'M', 'title': 'Møteserie'},
                  'yearly_volume': {'folder': {'1999': 160, '2000': 200, '2099': 1},
                                    'document_description': {'1999': 3000, '2000': 4000}}}]}
        volumes = combined_volumes(archive_part_volumes(report))
        self.assertEqual(1, volumes[2099]['folder'])
        self.assertIn((2099, 1), sparse_boundary_years(volumes))

    def test_empty(self):
        self.assertEqual([], archive_part_volumes({}))
        self.assertEqual([], sparse_boundary_years({}))


if __name__ == '__main__':
    unittest.main()
