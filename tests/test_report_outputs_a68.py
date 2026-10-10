from pathlib import Path
from tools.report_outputs import html_to_pdf, write_html_and_pdf, _text_check


def test_html_and_searchable_pdf(tmp_path):
    html_path, pdf_path = write_html_and_pdf(tmp_path / 'rapport.html', '<!doctype html><html lang="no"><meta charset="utf-8"><body><h1>Arkivrapport JOB-002</h1><p>Testbar norsk tekst: æøå</p></body></html>')
    assert html_path.is_file() and pdf_path.is_file()
    assert pdf_path.stat().st_size > 1000
    assert _text_check(pdf_path) is True
    assert pdf_path == html_path.with_suffix('.pdf')
