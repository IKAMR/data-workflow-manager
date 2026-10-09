"""Norwegian presentation of numeric counts; never changes stored values."""
from __future__ import annotations

def format_count(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Count must be an integer")
    return f"{value:,}".replace(",", " ")



# Presentation only: target explicit counts, not IDs, dates, years or file names.
import re

_COUNT_LABELS = re.compile(
    r"(?P<label>\b(?:Mappe|Reg|Doc|Elektr|Alle|Journalpost|Hoveddok|Vedlegg|Dokumentobjekt|Dokumentbeskrivelse|Registreringer|Mapper|Saker|Klasser|Arkivdeler|Korrespondansepart|Arkivformat|Produksjonsformat)\s*[:=]\s*)(?P<number>\d{4,})(?![\d-])",
    re.IGNORECASE,
)

def format_result_text(value: str) -> str:
    """Display grouping for well-defined counts; retain source evidence unchanged."""
    return _COUNT_LABELS.sub(lambda m: m.group('label') + format_count(int(m.group('number'))), str(value))
