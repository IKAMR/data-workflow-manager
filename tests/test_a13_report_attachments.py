import unittest
from tools.noark5_batch_overview_a6 import attachment_filename


class AttachmentTests(unittest.TestCase):
    def test_unique_names_for_same_job_ids(self):
        self.assertNotEqual(attachment_filename(1,'.html'), attachment_filename(2,'.html'))
        self.assertEqual(attachment_filename(28,'.pdf'), 'vedlegg-028.pdf')

    def test_rejects_invalid_names(self):
        for num, ext in [(0,'.html'),(-1,'.pdf'),(1,'../file')]:
            with self.assertRaises(ValueError): attachment_filename(num,ext)


if __name__ == '__main__': unittest.main()
