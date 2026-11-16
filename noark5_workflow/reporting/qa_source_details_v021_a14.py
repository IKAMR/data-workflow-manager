"""Read-only, source-faithful formatting for the a14 technical evidence viewer.

These strings describe the *recorded* finding. They neither parse or edit
arkivstruktur.xml, nor add a Noark validation rule or a professional verdict.
"""
from __future__ import annotations

from collections.abc import Mapping


def _value(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    return text or "Ikke dokumentert"


def format_source_details(finding: Mapping[str, object]) -> str:
    """Readable full evidence details, including all available XML line refs.

    No truncation: the Qt viewer handles scrolling, rather than squeezing a
    long technical record into a 118-pixel text field in the review form.
    """
    if not isinstance(finding, Mapping):
        raise TypeError("Funn må være et oppslagsobjekt")

    raw_lines = finding.get("lines")
    if isinstance(raw_lines, (list, tuple)):
        lines = [_value(item) for item in raw_lines]
    elif raw_lines is None or raw_lines == "":
        lines = []
    else:
        # Do not split a source-provided string speculatively.
        lines = [_value(raw_lines)]
    line_chunks = ["  " + ", ".join(lines[i:i + 8]) for i in range(0, len(lines), 8)]

    content = [
        "KONTROLL OG UTFALL",
        "Test-ID: " + _value(finding.get("test_id")),
        "Kilde: " + _value(finding.get("source")),
        "Rapportert nivå: " + _value(finding.get("severity")),
        "",
        "OBSERVERT FUNN",
        _value(finding.get("message")),
        "",
        "ARKIVDEL / KONTEKST",
        _value(finding.get("context")),
        "",
        "XML-KILDEHENVISNING",
        "Fil: " + _value(finding.get("file")),
        "Antall linjereferanser: " + (str(len(lines)) if lines else "Ikke dokumentert"),
        "Linjenumre:",
        *(line_chunks or ["  Ikke dokumentert"]),
        "",
        "EVIDENSKILDE",
        _value(finding.get("source_ref")),
        "",
        "OBS: Dette viser rapporterte linjenumre og kildehenvisninger, "
        "ikke XML-innhold fra kildefilen.",
        "Arkades tekniske resultat og original evidens er uendret.",
    ]
    return "\n".join(content) + "\n"
