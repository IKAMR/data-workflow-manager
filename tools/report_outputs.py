"""Shared DWM report outputs: an HTML report is accompanied by a searchable PDF.

Do not print via Microsoft Print to PDF: use the browser PDF renderer directly.
The browser is launched with an isolated temporary profile; report inputs are read only.
"""
from __future__ import annotations

import argparse
import uuid
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def _browsers() -> list[Path]:
    candidates = []
    override = os.environ.get('DWM_PDF_BROWSER')
    if override:
        candidates.append(Path(override))
    if os.name == 'nt':
        for base in (os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')):
            if base:
                candidates.extend((Path(base) / 'Microsoft/Edge/Application/msedge.exe',
                                   Path(base) / 'Google/Chrome/Application/chrome.exe'))
    for name in ('msedge', 'microsoft-edge', 'chromium', 'chromium-browser', 'google-chrome', 'chrome'):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return [p for p in candidates if p.is_file()]


def _text_check(pdf: Path) -> bool | None:
    """Return True for selectable text, False for a raster-only PDF, None if no parser."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import fitz
        except ImportError:
            return None
        with fitz.open(pdf) as doc:
            return any(len(page.get_text().strip()) >= 12 for page in doc)
    return any(len(page.extract_text().strip()) >= 12 for page in PdfReader(str(pdf)).pages)


def _publish_pdf(intermediate: Path, target: Path) -> None:
    """Publish across volumes safely; Windows os.replace cannot cross drives."""
    temporary = target.with_name(f'.{target.stem}-{uuid.uuid4().hex}.tmp.pdf')
    try:
        shutil.copyfile(intermediate, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def html_to_pdf(html_path: str | Path, pdf_path: str | Path | None = None) -> Path:
    """Create searchable PDF from existing HTML; fail without overwriting a good PDF."""
    source = Path(html_path).resolve(strict=True)
    if source.suffix.lower() not in ('.html', '.htm'):
        raise ValueError('Forventer en HTML-fil')
    target = Path(pdf_path).resolve() if pdf_path else source.with_suffix('.pdf')
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix='dwm-pdf-') as temporary:
        scratch = Path(temporary)
        intermediate = scratch / 'report.pdf'
        for executable in _browsers():
            cmd = [str(executable), '--headless', '--disable-gpu', '--no-first-run',
                   '--no-default-browser-check', '--disable-extensions',
                   '--disable-background-networking', '--disable-features=Translate',
                   '--no-pdf-header-footer', f'--user-data-dir={scratch / "profile"}',
                   f'--print-to-pdf={intermediate}', source.as_uri()]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=150, check=False)
                if intermediate.is_file() and intermediate.stat().st_size > 1000:
                    check = _text_check(intermediate)
                    if check is False:
                        raise RuntimeError('PDF inneholder ikke markerbar tekst')
                    _publish_pdf(intermediate, target)
                    return target
                errors.append(f'{executable.name}: {result.stderr[-250:]}')
            except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
                errors.append(f'{executable.name}: {exc}')
            finally:
                intermediate.unlink(missing_ok=True)
    # Optional fallback for machines with WeasyPrint installed.
    try:
        from weasyprint import HTML
        with tempfile.TemporaryDirectory(prefix='dwm-pdf-') as directory:
            interim = Path(directory) / 'report.pdf'
            HTML(filename=str(source), base_url=source.parent.as_uri() + '/').write_pdf(str(interim))
            if _text_check(interim) is False:
                raise RuntimeError('PDF inneholder ikke markerbar tekst')
            _publish_pdf(interim, target)
            return target
    except (ImportError, OSError, RuntimeError) as exc:
        errors.append(f'WeasyPrint: {exc}')
    raise RuntimeError('PDF kunne ikke genereres. Krever Edge/Chrome (eller WeasyPrint). ' + '; '.join(errors))


def write_html_and_pdf(html_path: str | Path, markup: str, *, encoding: str = 'utf-8') -> tuple[Path, Path]:
    """Reusable single entry point for every DWM HTML report producer."""
    html_file = Path(html_path)
    html_file.parent.mkdir(parents=True, exist_ok=True)
    html_file.write_text(markup, encoding=encoding)
    return html_file, html_to_pdf(html_file)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='DWM: konverter HTML-rapport til søkbar PDF')
    parser.add_argument('html', type=Path)
    parser.add_argument('pdf', type=Path, nargs='?')
    args = parser.parse_args(argv)
    try:
        path = html_to_pdf(args.html, args.pdf)
        print('PDF klar:', path)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print('PDF-feil:', exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
