"""A18 fix11 fix1: selected scoped KDRS count survives compact HTML export."""
import unittest

from noark5_workflow.reporting.archive_u2_a18 import render_u2_archive_parts


def part(title, count, *, verified=False):
    return {
        'job_id': 'JOB-001', 'title': title,
        'u2_count': 1, 'u2_status': 'Koblet via entydig arkivdeltittel',
        'metrics': {
            'registration_count': {
                'dwm': 15 if title == 'Saksarkiv' else None,
                'report': count,
                'source': 'KDRS Query (verifisert)' if verified else 'DWM',
            },
        },
        'kdrs_u2_observations': {
            'registration_count': {'value': 99 if verified else 77,
                                   'status': 'kildedokumentert'},
        },
    }


class CompactScopedReportTests(unittest.TestCase):
    def test_chosen_kdrs_is_visible_without_promoting_observation(self):
        data = {'archive_parts': [part('Saksarkiv', 20, verified=True),
                                  part('Elevarkiv', None)], 'unmatched_u2': []}
        output = render_u2_archive_parts(data)
        self.assertIn('Verifiserte rapportvalg', output)
        self.assertIn('Registreringer: 20 (KDRS)', output)
        self.assertNotIn('Registreringer: 99 (KDRS)', output)
        self.assertIn('>99</td>', output)
        self.assertIn('>77</td>', output)
        self.assertEqual(output.count('(KDRS)'), 1)

    def test_unselected_observation_is_not_labelled_verified(self):
        data = {'archive_parts': [part('Saksarkiv', 15)], 'unmatched_u2': []}
        output = render_u2_archive_parts(data)
        self.assertNotIn('(KDRS)', output)
        self.assertIn('>77</td>', output)
        self.assertIn('Verifiserte rapportvalg', output)


if __name__ == '__main__':
    unittest.main()
