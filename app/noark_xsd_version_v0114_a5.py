"""Read-only Noark 5 version evidence from XSD declarations and known hashes.

The XSD schema/@version and a consistent set of accompanying schemas are
primary evidence. SHA-256 identifies known byte variants, not standard version
by itself; XSD comment changelogs describe maintenance, not new Noark versions.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

SIGNATURES = Path(__file__).resolve().parents[1] / 'config/noark5/standards/noark5_xsd_signatures_v0114_a5.json'
MAX_SCHEMA_SIZE = 5_000_000
MAX_ADDML_SIZE = 8_000_000
SCHEMA_NAMES = frozenset(('arkivstruktur.xsd', 'metadatakatalog.xsd', 'endringslogg.xsd',
                          'loependeJournal.xsd', 'offentligJournal.xsd'))
XML_NAMES = frozenset(('arkivuttrekk.xml',))
VERSIONS = frozenset(('3.0', '3.1', '4.0', '5.0'))
XSD_NS = 'http://www.w3.org/2001/XMLSchema'
NOARK_NAMESPACE_FRAGMENT = '/noark5/'
MAX_HEADER_READ = 128_000


@dataclass(frozen=True)
class SchemaEvidence:
    path: Path
    digest: str
    version: str | None
    reference: str | None
    status: str
    declared_version: str | None = None
    maintenance_note: str | None = None


@dataclass(frozen=True)
class VersionEvidence:
    version: str | None
    status: str
    schemas: tuple[SchemaEvidence, ...]
    addml_version: str | None
    addml_path: Path | None
    warnings: tuple[str, ...]
    source: Path | None

    @property
    def display(self) -> str:
        if self.status == 'confirmed':
            return f'Noark 5 v{self.version} – identifisert fra XSD'
        if self.status == 'partial':
            return f'Noark 5 v{self.version} – XSD indikerer versjonen, men ikke alle skjemaene er verifisert'
        if self.status == 'conflict':
            return 'Uavklart – motstridende XSD-versjoner'
        return 'Uavklart – ingen sikker XSD-identifikasjon'


@lru_cache(maxsize=1)
def _signatures() -> dict[str, dict]:
    obj = json.loads(SIGNATURES.read_text(encoding='utf-8'))
    matches: dict[str, dict] = {}
    for item in obj.get('signatures', []):
        digest = str(item.get('sha256') or '').lower()
        if (re.fullmatch('[a-f0-9]{64}', digest)
                and item.get('version') in VERSIONS and item.get('filename') in SCHEMA_NAMES):
            if digest in matches and matches[digest]['version'] != item['version']:
                # Ambiguous byte identity across versions cannot establish version.
                matches[digest] = {'version': None, 'repository_path': None}
            else:
                matches[digest] = item
    return matches


def _candidate_dirs(source: Path) -> tuple[Path, ...]:
    """The selected Source and its near ancestors; never scan a drive recursively."""
    p = Path(source)
    candidates = (p, *list(p.parents)[:4])
    return tuple(x for x in candidates if x.is_dir())


def _schema_files(source: Path) -> tuple[Path, ...]:
    # Schemas may be in extraction root or the selected content/sip/content.
    found: dict[str, Path] = {}
    for directory in _candidate_dirs(source):
        for name in sorted(SCHEMA_NAMES):
            candidate = directory / name
            if candidate.is_file():
                found.setdefault(name, candidate)
    return tuple(found.values())


def _hash_schema(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_SCHEMA_SIZE:
        raise ValueError('XSD mangler eller er større enn kontrollgrensen')
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(65536), b''):
            hasher.update(block)
    return hasher.hexdigest()


def _read_schema_declaration(path: Path) -> tuple[str | None, str | None]:
    """Read schema root safely and report its actual standard version.

    Only a real XSD root in a Noark namespace qualifies. A 5.5.0 maintenance
    comment never creates a distinct Noark version. No external entities used.
    """
    if path.stat().st_size > MAX_SCHEMA_SIZE:
        raise ValueError('XSD overskrider størrelsesgrensen')
    try:
        with path.open('rb') as handle:
            for event, element in ET.iterparse(handle, events=('start',)):
                if element.tag != '{' + XSD_NS + '}schema':
                    return None, None
                namespace = element.get('targetNamespace') or ''
                if NOARK_NAMESPACE_FRAGMENT not in namespace.lower():
                    return None, None
                raw = (element.get('version') or '').strip()
                version = raw if raw in VERSIONS else None
                break
            else:
                return None, None
        # Read a bounded header solely for a human-visible maintenance note.
        with path.open('rb') as handle:
            head = handle.read(MAX_HEADER_READ).decode('utf-8-sig', errors='replace')
        comments = re.findall(r'<!--(.*?)-->', head, flags=re.S)
        note = None
        for comment in comments:
            # Historical schemas mention old versions. Only a *maintenance*
            # statement about 5.5.0 is displayed as a maintenance note.
            if re.search(r'5\.5\.0', comment) and re.search(r'vedlikehold', comment, re.I):
                note = 'XSD-endringslogg omtaler 5.5.0 (vedlikehold); standardversjonen er fortsatt 5.0'
                break
        return version, note
    except ET.ParseError:
        return None, None


def _addml_version(source: Path) -> tuple[str | None, Path | None]:
    """A hint only; never infer Noark version from generic ADDML version tags."""
    for directory in _candidate_dirs(source):
        candidate = directory / 'arkivuttrekk.xml'
        if not candidate.is_file():
            continue
        if candidate.stat().st_size > MAX_ADDML_SIZE:
            return None, candidate
        try:
            with candidate.open('rb') as handle:
                for _event, element in ET.iterparse(handle, events=('end',)):
                    tag = str(element.tag).split('}')[-1].casefold()
                    if tag in {'noarkversjon', 'noarkversion', 'noark5versjon', 'noark5version'}:
                        value = (element.text or '').strip()
                        found = re.search(r'(?<!\d)(3\.0|3\.1|4\.0|5\.0)(?!\d)', value)
                        if found:
                            return found.group(1), candidate
                    element.clear()
        except (OSError, ET.ParseError, ValueError):
            return None, candidate
        return None, candidate
    return None, None


def inspect_source_version(source: str | Path | None) -> VersionEvidence:
    if not source:
        return VersionEvidence(None, 'unknown', (), None, None, ('Source er ikke valgt.',), None)
    root = Path(source)
    if not root.is_dir():
        return VersionEvidence(None, 'unknown', (), None, None, ('Source-mappen finnes ikke.',), root)
    lookups = _signatures()
    schemas = []
    notes = []
    for path in _schema_files(root):
        try:
            digest = _hash_schema(path)
            declared, maintenance = _read_schema_declaration(path)
        except (OSError, ValueError) as exc:
            schemas.append(SchemaEvidence(path, '', None, None, f'Kunne ikke lese: {exc}'))
            continue
        item = lookups.get(digest)
        name_matches = bool(item and item.get('filename') == path.name)
        hash_version = item.get('version') if name_matches else None
        reference = item.get('repository_path') if name_matches else None
        # A known digest can identify an XSD even when a legacy test fixture
        # or schema has no version attribute. A conflicting declaration is NOT
        # silently replaced with the catalog version.
        if declared and hash_version and declared != hash_version:
            version = None
            status_text = f'KONFLIKT: XSD oppgir v{declared}, SHA-256-registeret v{hash_version}'
            notes.append(f'{path.name}: uenighet mellom skjemadeklarasjon og kjent SHA-256.')
        else:
            version = declared or hash_version
            if declared:
                status_text = ('XSD version-attributt + kjent SHA-256' if hash_version else
                               'XSD version-attributt; ukjent SHA-256-filvariant')
            elif hash_version:
                status_text = 'Kjent SHA-256; ingen bekreftet version-attributt'
            else:
                status_text = 'Ukjent versjon i XSD og SHA-256-register'
        schemas.append(SchemaEvidence(path, digest, version, reference, status_text,
                                      declared, maintenance))
    versions = {record.version for record in schemas if record.version}
    contradictory = any(rec.status.startswith('KONFLIKT:') for rec in schemas)
    if len(versions) > 1 or contradictory:
        status, version = 'conflict', None
        notes.append('XSD-filene gir motstridende versjonsbelegg. Ingen regelversjon velges automatisk.')
    elif len(versions) == 1:
        version = next(iter(versions))
        # Versioned root XSD is sufficient for identification, but any unknown
        # accompanying XSD is a completeness warning rather than assumed OK.
        status = 'confirmed' if all(rec.version is not None for rec in schemas) else 'partial'
    else:
        status, version = 'unknown', None
        notes.append('XSD-versjonen kunne ikke identifiseres fra skjemadeklarasjon eller kjente SHA-256.')
    if any(record.version is None for record in schemas):
        notes.append('Én eller flere XSD-filer kan ikke versjonsbestemmes og må undersøkes.')
    for record in schemas:
        if record.maintenance_note:
            notes.append(f'{record.path.name}: {record.maintenance_note}')
    addml_version, addml_path = _addml_version(root)
    if addml_version and version and version != addml_version:
        notes.append(f'arkivuttrekk.xml oppgir v{addml_version}, mens XSD er v{version}. Metadata er ikke automatisk fasit.')
    return VersionEvidence(version, status, tuple(schemas), addml_version, addml_path, tuple(notes), root)


def source_from_report(report_path: str | Path | None) -> Path | None:
    """Recover the previously selected Source from Work's authoritative job.json."""
    if report_path is None:
        return None
    report = Path(report_path)
    for parent in report.parents:
        marker = parent / 'job.json'
        if marker.is_file():
            try:
                if marker.stat().st_size > 2_000_000:
                    return None
                obj = json.loads(marker.read_text(encoding='utf-8-sig'))
                if not isinstance(obj, dict):
                    return None
                for record in (obj, obj.get('job') if isinstance(obj.get('job'), dict) else {}):
                    for key in ('source_extraction', 'source_unzipped', 'source_root'):
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            path = Path(value)
                            if path.is_dir():
                                return path
            except (OSError, ValueError, TypeError):
                return None
            return None
    return None


def inspect_report_version(report_path: str | Path | None) -> VersionEvidence:
    return inspect_source_version(source_from_report(report_path))


def comparison_label(evidence: VersionEvidence, rule_version: str | None) -> str:
    if evidence.status != 'confirmed' or not evidence.version:
        return 'Versjon uavklart eller ikke fullt verifisert: sammenligning alene dokumenterer ikke regelbrudd'
    if str(rule_version) != evidence.version:
        return f'Historisk sammenligning: regel v{rule_version} gjelder ikke bekreftet XSD v{evidence.version}'
    return f'Regelversjon v{rule_version} samsvarer med XSD; verdilistefunn må fortsatt vurderes faglig'
