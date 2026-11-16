"""Depot organization identity and document presentation profiles (v0.2.2-a1).

Independent from Noark control profiles, login identities, and archive METS.
Only explicit operator saves write to a per-user location outside Source/Work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import zlib
from typing import Any
from uuid import uuid4

from app.user_profile import user_data_dir

FILE_TYPE = "dwm-depot-organization-profiles"
FORMAT_VERSION = 1
TEST_ID = "test-depot"
SIZES = ("Small", "Medium", "Full")
DOCUMENT_KINDS = ("checklist", "quality_report", "depot_report", "approval_letter")
DOCUMENT_LABELS = {
    "checklist": "Depotets sjekkliste",
    "quality_report": "Kvalitetssikringsrapport",
    "depot_report": "Depotrapport",
    "approval_letter": "Godkjenningsbrev",
}
DEFAULT_SIZES = {
    "checklist": "Medium", "quality_report": "Medium",
    "depot_report": "Full", "approval_letter": "Full",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_LOGO_DIMENSION = 4096
_MAX_PROFILE_BYTES = 256 * 1024
_ASSET_RE = re.compile(r"^assets/([a-f0-9]{64})\.(png|jpg)$")
_PROFILE_ID_RE = re.compile(r"^(?:test-depot|depot-[0-9a-f]{32})$")
_ORG_RE = re.compile(r"^(?:[0-9]{9})?$")


class DepotProfileError(ValueError):
    """Invalid or unavailable depot-organization profile; no silent reset."""


@dataclass(frozen=True)
class DepotProfile:
    profile_id: str
    profile_name: str
    organization_name: str
    organization_number: str = ""
    department: str = ""
    sender_name: str = ""
    address: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = "Norge"
    telephone: str = ""
    email: str = ""
    website: str = ""
    signature_name: str = ""
    signature_title: str = ""
    reference_prefix: str = ""
    footer_text: str = ""
    logo_ref: str = ""
    header_sizes: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SIZES))

    @property
    def is_template(self) -> bool:
        return self.profile_id == TEST_ID


@dataclass(frozen=True)
class DepotProfileSet:
    active_profile_id: str = TEST_ID
    custom_profiles: tuple[DepotProfile, ...] = ()

    @property
    def profiles(self) -> tuple[DepotProfile, ...]:
        return (TEST_DEPOT,) + self.custom_profiles

    def get(self, profile_id: str) -> DepotProfile:
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise DepotProfileError("Ukjent depotprofil: " + str(profile_id))

    @property
    def active(self) -> DepotProfile:
        return self.get(self.active_profile_id)


# Always available and immutable; reserved domains prevent accidental real-world identity.
TEST_DEPOT = DepotProfile(
    profile_id=TEST_ID,
    profile_name="Test Depot (demoprofil)",
    organization_name="Test Depot",
    department="Fiktivt digitalt arkivdepot",
    sender_name="Test Depot",
    address="Eksempelgata 1",
    postal_code="0000",
    city="Eksempelby",
    email="post@testdepot.invalid",
    footer_text="DEMO – Test Depot. Ikke en virkelig depotidentitet.",
)


def depot_profiles_path() -> Path:
    """Separate from app.user_profile, settings.json and each archive's Work."""
    return user_data_dir() / "depot-profiles.json"


def _single_line(value: str, label: str, maximum: int = 220) -> str:
    if not isinstance(value, str):
        raise DepotProfileError(label + " må være tekst.")
    value = value.strip()
    if len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise DepotProfileError(label + " har ugyldige tegn eller er for lang.")
    return value


def validate_profile(profile: DepotProfile) -> DepotProfile:
    if not isinstance(profile, DepotProfile):
        raise DepotProfileError("Ugyldig depotprofilobjekt.")
    if not _PROFILE_ID_RE.fullmatch(profile.profile_id):
        raise DepotProfileError("Ugyldig profil-ID.")
    if profile.is_template and profile != TEST_DEPOT:
        raise DepotProfileError("Den innebygde Test Depot-profilen kan ikke endres; opprett en kopi.")
    for key in (
        "profile_name", "organization_name", "department", "sender_name", "address",
        "postal_code", "city", "country", "telephone", "email", "website",
        "signature_name", "signature_title", "reference_prefix", "footer_text",
    ):
        _single_line(getattr(profile, key), key, maximum=400 if key == "footer_text" else 220)
    if not profile.profile_name.strip() or not profile.organization_name.strip():
        raise DepotProfileError("Profilnavn og depotets organisasjonsnavn er obligatoriske.")
    if not isinstance(profile.organization_number, str) or not _ORG_RE.fullmatch(profile.organization_number):
        raise DepotProfileError("Organisasjonsnummer må være tomt eller ni sifre.")
    if profile.email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", profile.email):
        raise DepotProfileError("Ugyldig e-postadresse.")
    if profile.website and not re.fullmatch(r"https?://[^\s<>\"']+", profile.website, flags=re.I):
        raise DepotProfileError("Nettadresse må starte med http:// eller https://.")
    if profile.logo_ref and not _ASSET_RE.fullmatch(profile.logo_ref):
        raise DepotProfileError("Logoreferansen må peke til en kontrollert lokal bildekopi.")
    if not isinstance(profile.header_sizes, dict) or set(profile.header_sizes) != set(DOCUMENT_KINDS):
        raise DepotProfileError("Headeroppsett må dekke alle fire dokumenttyper.")
    if any(size not in SIZES for size in profile.header_sizes.values()):
        raise DepotProfileError("Headerstørrelse må være Small, Medium eller Full.")
    return profile


def _parse_profile(payload: Any) -> DepotProfile:
    if not isinstance(payload, dict):
        raise DepotProfileError("Profilen har ugyldig JSON-struktur.")
    permitted = {f.name for f in DepotProfile.__dataclass_fields__.values()}
    if set(payload) - permitted:
        raise DepotProfileError("Profilen har ukjente felt: " + ", ".join(sorted(set(payload)-permitted)))
    try:
        profile = DepotProfile(**payload)
    except (TypeError, KeyError) as exc:
        raise DepotProfileError("Manglende eller ugyldige depotprofilfelt.") from exc
    return validate_profile(profile)


def _check_set(profiles: DepotProfileSet) -> None:
    if not isinstance(profiles, DepotProfileSet) or len(profiles.custom_profiles) > 100:
        raise DepotProfileError("Ugyldig eller for stort depotprofilregister.")
    seen = {TEST_ID}
    for profile in profiles.custom_profiles:
        validate_profile(profile)
        if profile.is_template or profile.profile_id in seen:
            raise DepotProfileError("Duplisert eller låst depotprofil-ID.")
        seen.add(profile.profile_id)
    if profiles.active_profile_id not in seen:
        raise DepotProfileError("Aktiv depotprofil finnes ikke i registeret.")


def load_depot_profiles(*, path: Path | None = None) -> DepotProfileSet:
    path = Path(path) if path is not None else depot_profiles_path()
    if path.is_symlink():
        raise DepotProfileError("Profilfilen kan ikke være en symbolsk lenke.")
    if not path.exists():
        return DepotProfileSet()
    if not path.is_file() or path.stat().st_size > _MAX_PROFILE_BYTES:
        raise DepotProfileError("Profilfilen er ikke en normal fil innenfor sikkerhetsgrensen.")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DepotProfileError("Kan ikke lese depotprofiler. Eksisterende fil er ikke endret.") from exc
    if not isinstance(raw, dict) or raw.get("file_type") != FILE_TYPE or raw.get("format_version") != FORMAT_VERSION:
        raise DepotProfileError("Ukjent eller ugyldig depotprofilformat. Eksisterende fil er ikke endret.")
    if not isinstance(raw.get("profiles"), list):
        raise DepotProfileError("Depotprofilregisteret mangler profilliste.")
    result = DepotProfileSet(
        active_profile_id=str(raw.get("active_profile_id", "")),
        custom_profiles=tuple(_parse_profile(p) for p in raw["profiles"]),
    )
    _check_set(result)
    return result


def save_depot_profiles(profiles: DepotProfileSet, *, path: Path | None = None) -> Path:
    _check_set(profiles)
    path = Path(path) if path is not None else depot_profiles_path()
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise DepotProfileError("Depotprofilfilen kan ikke være en symbolsk lenke eller mappe.")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({
        "file_type": FILE_TYPE,
        "format_version": FORMAT_VERSION,
        "active_profile_id": profiles.active_profile_id,
        "profiles": [asdict(profile) for profile in profiles.custom_profiles],
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(content.encode("utf-8")) > _MAX_PROFILE_BYTES:
        raise DepotProfileError("Depotprofilregisteret er for stort.")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".depot-profile-", suffix=".tmp", delete=False) as handle:
            temp_name = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.is_symlink():
            raise DepotProfileError("Depotprofilfilen ble endret til en symbolsk lenke.")
        os.replace(temp_name, path)
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)
    return path


def new_profile(*, name: str, source: DepotProfile = TEST_DEPOT) -> DepotProfile:
    validate_profile(source)
    new_name = _single_line(name, "Profilnavn")
    if not new_name:
        raise DepotProfileError("Profilnavn kan ikke være tomt.")
    if source.is_template:
        # Do not pass on fictional contact details into a real depot profile.
        return DepotProfile(
            profile_id="depot-" + uuid4().hex,
            profile_name=new_name,
            organization_name=new_name,
            header_sizes=dict(source.header_sizes),
        )
    return replace(source, profile_id="depot-" + uuid4().hex,
                   profile_name=new_name, header_sizes=dict(source.header_sizes))


def upsert_profile(store: DepotProfileSet, profile: DepotProfile, *, activate: bool = True) -> DepotProfileSet:
    _check_set(store)
    validate_profile(profile)
    if profile.is_template:
        raise DepotProfileError("Opprett en kopi av Test Depot i stedet for å endre malen.")
    remaining = tuple(p for p in store.custom_profiles if p.profile_id != profile.profile_id)
    updated = DepotProfileSet(
        active_profile_id=profile.profile_id if activate else store.active_profile_id,
        custom_profiles=remaining + (profile,),
    )
    _check_set(updated)
    return updated


def activate_profile(store: DepotProfileSet, profile_id: str) -> DepotProfileSet:
    store.get(profile_id)
    return replace(store, active_profile_id=profile_id)


def delete_profile(store: DepotProfileSet, profile_id: str) -> DepotProfileSet:
    if profile_id == TEST_ID:
        raise DepotProfileError("Den innebygde demoprofilen kan ikke slettes.")
    store.get(profile_id)
    remaining = tuple(p for p in store.custom_profiles if p.profile_id != profile_id)
    result = DepotProfileSet(
        active_profile_id=TEST_ID if store.active_profile_id == profile_id else store.active_profile_id,
        custom_profiles=remaining,
    )
    _check_set(result)
    return result


def _png_size(data: bytes) -> tuple[int, int] | None:
    """Require complete bounded PNG chunks and valid checksums, not a header spoof."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos = 8
    dims = None
    seen_data = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        end = pos + 12 + length
        if length > MAX_LOGO_BYTES or end > len(data):
            return None
        kind = data[pos+4:pos+8]
        contents = data[pos+8:pos+8+length]
        checksum = struct.unpack(">I", data[end-4:end])[0]
        if zlib.crc32(kind + contents) != checksum:
            return None
        if pos == 8:
            if kind != b"IHDR" or length != 13:
                return None
            dims = struct.unpack(">II", contents[:8])
        elif kind == b"IHDR":
            return None
        if kind == b"IDAT":
            seen_data = True
        if kind == b"IEND":
            return dims if length == 0 and seen_data and end == len(data) else None
        pos = end
    return None

def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        return None
    cursor = 2
    while cursor + 9 < len(data):
        if data[cursor] != 0xff:
            return None
        while cursor < len(data) and data[cursor] == 0xff:
            cursor += 1
        if cursor >= len(data):
            return None
        marker = data[cursor]
        cursor += 1
        if marker in (0xD8, 0xD9):
            continue
        if marker == 0xDA:
            return None
        if cursor + 2 > len(data):
            return None
        length = struct.unpack(">H", data[cursor:cursor+2])[0]
        if length < 2 or cursor + length > len(data):
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            if length < 7:
                return None
            height, width = struct.unpack(">HH", data[cursor+3:cursor+7])
            return width, height
        cursor += length
    return None


def _image_kind(data: bytes) -> str:
    for kind, probe in (("png", _png_size), ("jpg", _jpeg_size)):
        size = probe(data)
        if size is not None and all(0 < value <= MAX_LOGO_DIMENSION for value in size):
            return kind
    raise DepotProfileError("Logo må være et gyldig PNG- eller JPEG-bilde, maksimalt 4096 × 4096 piksler.")


def import_logo(source: Path, *, path: Path | None = None) -> str:
    """Copy a validated logo to content-addressed local assets; never edit input."""
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise DepotProfileError("Logokilden må være en vanlig bildefil, ikke en lenke.")
    if not 0 < source.stat().st_size <= MAX_LOGO_BYTES:
        raise DepotProfileError("Logo må være større enn 0 og høyst 2 MiB.")
    content = source.read_bytes()
    kind = _image_kind(content)
    target_root = (Path(path) if path is not None else depot_profiles_path()).parent / "depot-profile-assets"
    if target_root.is_symlink():
        raise DepotProfileError("Logo-katalogen kan ikke være en symbolsk lenke.")
    target_root.mkdir(parents=True, exist_ok=True)
    digest = sha256(content).hexdigest()
    target = target_root / (digest + "." + kind)
    if target.is_symlink():
        raise DepotProfileError("Logomålet kan ikke være en symbolsk lenke.")
    if target.exists():
        if not target.is_file() or sha256(target.read_bytes()).hexdigest() != digest:
            raise DepotProfileError("Eksisterende logo er endret eller uleselig.")
    else:
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(dir=target_root, prefix=".logo-",
                                             suffix=".tmp", delete=False) as handle:
                temp_name = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if temp_name is not None:
                temp_name.unlink(missing_ok=True)
    return "assets/" + target.name


def resolve_logo(profile: DepotProfile, *, path: Path | None = None) -> Path | None:
    if not profile.logo_ref:
        return None
    match = _ASSET_RE.fullmatch(profile.logo_ref)
    if not match:
        raise DepotProfileError("Ugyldig logoreferanse.")
    root = (Path(path) if path is not None else depot_profiles_path()).parent
    file = root / "depot-profile-assets" / (match.group(1) + "." + match.group(2))
    if file.is_symlink() or not file.is_file():
        raise DepotProfileError("Logobildet mangler eller er erstattet med en lenke.")
    if not 0 < file.stat().st_size <= MAX_LOGO_BYTES or sha256(file.read_bytes()).hexdigest() != match.group(1):
        raise DepotProfileError("Logobildets SHA-256 stemmer ikke med profilreferansen.")
    return file


def document_header_context(profile: DepotProfile, kind: str, *, path: Path | None = None) -> dict[str, Any]:
    """Immutable value snapshot for a future checklist/report/letter renderer.

    Returning context does not change current reports or imply approval.
    Callers must save this context with the generated document to avoid a
    later profile edit silently changing an old report's identity.
    """
    validate_profile(profile)
    if kind not in DOCUMENT_KINDS:
        raise DepotProfileError("Ukjent dokumenttype: " + str(kind))
    logo = resolve_logo(profile, path=path)
    record = asdict(profile)
    snapshot_sha = sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "model": "dwm-depot-document-header.v1",
        "profile_id": profile.profile_id,
        "profile_name": profile.profile_name,
        "profile_sha256": snapshot_sha,
        "demo": profile.is_template,
        "document_kind": kind,
        "document_name": DOCUMENT_LABELS[kind],
        "header_size": profile.header_sizes[kind],
        "organization_name": profile.organization_name,
        "organization_number": profile.organization_number,
        "department": profile.department,
        "sender_name": profile.sender_name or profile.organization_name,
        "address": profile.address,
        "postal_code": profile.postal_code,
        "city": profile.city,
        "country": profile.country,
        "telephone": profile.telephone,
        "email": profile.email,
        "website": profile.website,
        "signature_name": profile.signature_name,
        "signature_title": profile.signature_title,
        "reference_prefix": profile.reference_prefix,
        "footer_text": profile.footer_text,
        "logo_ref": profile.logo_ref,
        "logo_sha256": logo.stem if logo else "",
        "source_type": "local_depot_organization_profile_not_archive_metadata",
        "automatic_approval": False,
    }


def header_preview_html(context: dict[str, Any]) -> str:
    """Escape all user text; paper preview only, not a generated report."""
    size = context["header_size"]
    text = lambda value: escape(str(value or ""), quote=True)
    organization = text(context["organization_name"])
    heading = text(context["document_name"])
    demo = "<div class='demo'>DEMO – fiktiv depotidentitet</div>" if context.get("demo") else ""
    if size == "Small":
        block = f"<div class='small'><span class='mark'>D</span> {organization}</div>"
    elif size == "Medium":
        detail = text(context["department"])
        block = f"<div class='medium'><span class='mark'>D</span> <b>{organization}</b><div>{detail}</div></div>"
    else:
        parts = [context["address"], " ".join(filter(None, (context["postal_code"], context["city"]))),
                 context["email"], context["telephone"], context["website"]]
        rows = " · ".join(text(p) for p in parts if p)
        block = f"<div class='full'><span class='mark'>D</span> <b>{organization}</b><div>{text(context['department'])}</div><div>{rows}</div></div>"
    return ("<html><head><style>body{font-family:Arial;color:#22313d;background:#fff;padding:20px;}"
            ".mark{display:inline-block;background:#2e536e;color:#fff;border-radius:6px;padding:6px 12px;font-weight:bold;}"
            ".demo{color:#8d3f22;font-weight:bold;padding-bottom:10px;}"
            "h2{border-top:1px solid #b9c4cb;padding-top:12px;font-size:21px;}"
            ".small{font-size:13px}.medium{font-size:16px}.full{font-size:17px}"
            ".full div,.medium div{font-size:12px;color:#53616c;margin:6px 0;}"
            "</style></head><body>" + demo + block + f"<h2>{heading}</h2>"
            "<p style='color:#52626d'>Forhåndsvisning av header, ikke et depotvedtak eller en ferdig rapport.</p>"
            "</body></html>")
