"""DOCX unreadable evidence is an explicit QA finding, not PDF equivalence."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zipfile import ZipFile

from app.noark5_source_document_reader_v021_a7 import diagnose_docx,read_source_document


class DOCXDiagnostics(TestCase):
    def test_word_with_text_counts_the_nodes(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'docs.docx'
            with ZipFile(p,'w') as z:
                z.writestr('word/document.xml',
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    '<w:body><w:p><w:r><w:t>M619 Besvart på telefon</w:t></w:r></w:p></w:body></w:document>')
            data=diagnose_docx(p)
            self.assertEqual(data['status'],'text_found')
            self.assertEqual(data['word_text_nodes'],1)
            sections,backend=read_source_document(p)
            self.assertEqual(backend,'docx_xml')
            self.assertIn('M619',sections[0][1])

    def test_image_only_docx_is_not_reported_as_text_read(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'no_text.docx'
            with ZipFile(p,'w') as z:
                z.writestr('word/document.xml',
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    '<w:body><w:p><w:r/></w:p></w:body></w:document>')
                z.writestr('word/media/image1.png',b'test')
            data=diagnose_docx(p)
            self.assertEqual(data['status'],'no_word_text_nodes')
            self.assertFalse(data['text_readable'])
            self.assertEqual(data['embedded_or_media_parts'],1)
            self.assertTrue(data['not_ocr_or_rendered_equivalence'])

    def test_docx_missing_document_xml(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'bad.docx'
            with ZipFile(p,'w') as z:
                z.writestr('word/media/a.png',b'a')
            data=diagnose_docx(p)
            self.assertEqual(data['status'],'docx_document_xml_missing')

    def test_a7_progress_callback_is_nonintrusive(self):
        from app.noark5_requirement_matrix_v021_a7 import _document_index
        with TemporaryDirectory() as folder:
            src=Path(folder)
            p=src/'docs/kilder/noark/noark5/v5.0/spesifikasjoner/a.docx'
            p.parent.mkdir(parents=True)
            with ZipFile(p,'w') as z:
                z.writestr('word/document.xml',
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    '<w:body><w:p><w:r><w:t>M619</w:t></w:r></w:p></w:body></w:document>')
            events=[]
            references,numbers,inventory,issues=_document_index(src,{
                'noark5/v5.0/spesifikasjoner/a.docx':{'sha256':__import__('hashlib').sha256(p.read_bytes()).hexdigest()}
            },scan_text=True,progress=lambda i,n,v,path:events.append((i,n,v,path)))
            self.assertEqual(events[0][:3],(1,1,'5.0'))
            self.assertEqual(inventory['5.0'][0]['readable_sections'],1)
            self.assertIn('5.0:M619',references)


if __name__=='__main__':
    from unittest import main
    main()
