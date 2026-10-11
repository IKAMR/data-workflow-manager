import unittest
from tools.noark5_batch_overview_a6 import attachment_filename, render_extraction_attachment


class AttachmentA132Tests(unittest.TestCase):
    def test_unique_descriptive_file_names(self):
        first = attachment_filename(1, '.pdf', r'G:\\arkiv\\1502_029_ephorte', 'JOB-001')
        second = attachment_filename(2, '.pdf', r'G:\\arkiv\\1502_030_ephorte', 'JOB-001')
        self.assertNotEqual(first, second)
        self.assertIn('JOB-001', first)
        self.assertIn('1502_029', first)

    def test_no_directory_traversal(self):
        name = attachment_filename(5, '.html', '../../strange name', 'JOB-002')
        self.assertNotIn('/', name)
        self.assertNotIn('..', name)

    def test_detail_only_and_section_filter(self):
        # Test with a stub to avoid duplicating a full depot report fixture.
        import tools.noark5_batch_overview_a6 as mod
        old_render, old_filter = mod.render, mod.filter_report_html
        try:
            mod.render = lambda items, t: '<html><head></head><body><h2>Valgte uttrekk</h2><table><tr><td>FELLES</td></tr></table><section class="page"><h2>Uttrekksdetaljer</h2><p>EGET</p></section></body></html>'
            mod.filter_report_html = lambda doc, profile, sections: doc
            text = render_extraction_attachment({'extraction': '/x/1502_029'}, 'now', 'detaljert', set())
            self.assertIn('EGET', text)
            self.assertNotIn('FELLES', text)
            self.assertNotIn('Valgte uttrekk', text)
        finally:
            mod.render, mod.filter_report_html = old_render, old_filter

if __name__ == '__main__':
    unittest.main()
