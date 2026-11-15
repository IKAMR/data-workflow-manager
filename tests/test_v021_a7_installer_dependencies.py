"""a7: PDF source analysis must work after the repository installer runs.

The default PDF backend is pure-Python pypdf. PyMuPDF is optional; no
unreviewed reciprocal/commercial licence dependency is forced by install.bat.
"""
from __future__ import annotations

import builtins
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
from unittest.mock import patch

from app.noark5_source_document_reader_v021_a7 import read_source_document

REPO = Path(__file__).resolve().parents[1]


class TestA7InstallerDependencies(TestCase):
    def test_pdf_backend_is_declared_in_installed_core_requirements(self):
        lines = (REPO / 'requirements-core.txt').read_text(encoding='utf-8').splitlines()
        packages = [line.split('#', 1)[0].strip().lower() for line in lines]
        self.assertTrue(any(line.startswith(('pypdf>', 'pypdf=', 'pypdf '))
                            for line in packages),
                        'pypdf must be installed by install.bat through requirements-core.txt')

    def test_pdf_backend_is_in_both_install_profiles(self):
        # The original installer already uses the same core requirements in both
        # the default `py` runtime and the non-free-threaded GUI runtime.
        if not (REPO / 'install.bat').is_file():
            self.skipTest('installer not present in partial delta build tree')
        installer = (REPO / 'install.bat').read_text(encoding='utf-8-sig').lower()
        self.assertIn('py -m pip install', installer)
        self.assertIn('py %qt_py_flag% -m pip install', installer)
        self.assertGreaterEqual(installer.count('-r requirements-core.txt'), 2)
        self.assertIn('if errorlevel 1 goto install_error', installer)

    @skipUnless(find_spec('pypdf') is not None, 'pypdf installed via install.bat')
    def test_pdf_text_reader_uses_pypdf_when_pymupdf_unavailable(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

        with TemporaryDirectory() as directory:
            filename = Path(directory) / 'source.pdf'
            writer = PdfWriter()
            page = writer.add_blank_page(width=612, height=792)
            font = DictionaryObject({
                NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'),
                NameObject('/BaseFont'): NameObject('/Helvetica'),
            })
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): font}),
            })
            content = DecodedStreamObject()
            content.set_data(b'BT /F1 12 Tf 72 700 Td (M619 Besvart pa telefon) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(content)
            with filename.open('wb') as out:
                writer.write(out)

            original_import = builtins.__import__

            def without_mupdf(name, *args, **kwargs):
                if name == 'fitz':
                    raise ImportError('simulated optional PyMuPDF absence')
                return original_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=without_mupdf):
                sections, backend = read_source_document(filename)
            self.assertEqual(backend, 'pypdf')
            self.assertEqual(sections[0][0], 'page1')
            self.assertIn('M619 Besvart pa telefon', sections[0][1])
