from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree

from app.resource_strategy import ResourceDecision, choose_resource_strategy


_SCHEMA_LOCATION_READ_CHUNK = 64 * 1024
_STREAM_PARSE_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class XmlSchemaValidationResult:
    valid: bool
    xml_path: Path
    schema_path: Path | None
    errors: list[dict]
    file_size_bytes: int | None = None
    validation_mode: str = "streaming-iterparse"
    resource_decision: dict | None = None

    def as_dict(self) -> dict:
        return {
            "valid": self.valid,
            "xml": str(self.xml_path),
            "schema": str(self.schema_path) if self.schema_path else None,
            "errors": self.errors,
            "file_size_bytes": self.file_size_bytes,
            "validation_mode": self.validation_mode,
            "resource_decision": self.resource_decision,
        }


def _error_rows(log) -> list[dict]:
    return [
        {
            "line": entry.line,
            "column": entry.column,
            "level": entry.level_name,
            "domain": entry.domain_name,
            "type": entry.type_name,
            "message": entry.message,
        }
        for entry in log
    ]


def _exception_row(exc: BaseException, *, domain: str) -> dict:
    position = getattr(exc, "position", None)
    return {
        "line": getattr(exc, "lineno", None),
        "column": position[1] if position else None,
        "level": "ERROR",
        "domain": domain,
        "type": exc.__class__.__name__,
        "message": str(exc),
    }


def schema_location_candidates(xml_path: Path) -> list[str]:
    """Read xsi schema locations from the root element only."""
    xml_path = Path(xml_path)
    parser = etree.XMLPullParser(
        events=("start",),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )

    root = None
    with xml_path.open("rb") as stream:
        while root is None:
            chunk = stream.read(_SCHEMA_LOCATION_READ_CHUNK)
            if not chunk:
                break
            parser.feed(chunk)
            for _event, element in parser.read_events():
                root = element
                break

    if root is None:
        return []

    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    values: list[str] = []

    schema_location = root.get(f"{{{xsi}}}schemaLocation", "")
    tokens = schema_location.split()
    values.extend(tokens[1::2])

    no_namespace = root.get(f"{{{xsi}}}noNamespaceSchemaLocation", "")
    if no_namespace:
        values.append(no_namespace)

    return values


def resolve_local_schema(
    xml_path: str | Path,
    available_xsds: list[Path],
    preferred_names: list[str] | None = None,
) -> Path | None:
    xml_path = Path(xml_path)
    available = [Path(p).resolve() for p in available_xsds]
    by_name = {p.name.lower(): p for p in available}

    for name in preferred_names or []:
        found = by_name.get(name.lower())
        if found:
            return found

    for location in schema_location_candidates(xml_path):
        candidate_name = Path(urlparse(location).path).name.lower()
        if candidate_name and candidate_name in by_name:
            return by_name[candidate_name]

        local_candidate = (xml_path.parent / location).resolve()
        if local_candidate.is_file() and local_candidate.suffix.lower() == ".xsd":
            return local_candidate

    same_stem = by_name.get(f"{xml_path.stem}.xsd".lower())
    if same_stem:
        return same_stem

    return available[0] if len(available) == 1 else None


def _load_schema(
    schema_path: Path,
) -> tuple[etree.XMLSchema | None, list[dict]]:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )
    try:
        schema_doc = etree.parse(str(schema_path), parser)
        return etree.XMLSchema(schema_doc), []
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError, OSError) as exc:
        log = getattr(exc, "error_log", None)
        rows = _error_rows(log) if log is not None and len(log) else []
        return None, rows or [_exception_row(exc, domain="SCHEMA")]


def _stream_validate_xml(
    xml_path: Path,
    schema: etree.XMLSchema,
) -> tuple[bool, list[dict]]:
    context = None
    try:
        with xml_path.open("rb") as stream:
            context = etree.iterparse(
                stream,
                events=("end",),
                schema=schema,
                resolve_entities=False,
                no_network=True,
                huge_tree=True,
                chunk_size=_STREAM_PARSE_CHUNK,
            )
            for _event, element in context:
                element.clear()
                parent = element.getparent()
                if parent is not None:
                    while element.getprevious() is not None:
                        del parent[0]

        errors = _error_rows(context.error_log) if context is not None else []
        return not errors, errors
    except etree.XMLSyntaxError as exc:
        errors: list[dict] = []
        if context is not None:
            errors = _error_rows(context.error_log)
        if not errors:
            log = getattr(exc, "error_log", None)
            errors = _error_rows(log) if log is not None and len(log) else []
        return False, errors or [_exception_row(exc, domain="XML")]
    except OSError as exc:
        return False, [_exception_row(exc, domain="IO")]


def _tree_validate_xml(
    xml_path: Path,
    schema: etree.XMLSchema,
    *,
    in_memory: bool,
) -> tuple[bool, list[dict]]:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )
    try:
        if in_memory:
            with xml_path.open("rb") as stream:
                payload = stream.read()
            root = etree.fromstring(payload, parser=parser)
            document = etree.ElementTree(root)
        else:
            # Python owns the file handle even for the direct/disk strategy.
            # This avoids libxml2 path-opening limitations on Windows.
            with xml_path.open("rb") as stream:
                document = etree.parse(stream, parser)

        valid = bool(schema.validate(document))
        return valid, _error_rows(schema.error_log)
    except etree.XMLSyntaxError as exc:
        log = getattr(exc, "error_log", None)
        errors = _error_rows(log) if log is not None and len(log) else []
        return False, errors or [_exception_row(exc, domain="XML")]
    except OSError as exc:
        return False, [_exception_row(exc, domain="IO")]


def validate_xml_against_xsd(
    xml_path: str | Path,
    schema_path: str | Path,
    *,
    resource_strategy: str = "auto",
    environment: dict | None = None,
    expected_reuse: int = 1,
) -> XmlSchemaValidationResult:
    xml_path = Path(xml_path).resolve()
    schema_path = Path(schema_path).resolve()

    try:
        file_size_bytes = xml_path.stat().st_size
    except OSError:
        file_size_bytes = None

    decision: ResourceDecision = choose_resource_strategy(
        xml_path,
        requested=resource_strategy,
        workload="xml_schema_tree",
        expected_reuse=expected_reuse,
        environment=environment,
    )

    schema, schema_errors = _load_schema(schema_path)
    if schema is None:
        return XmlSchemaValidationResult(
            False,
            xml_path,
            schema_path,
            schema_errors,
            file_size_bytes=file_size_bytes,
            validation_mode="schema-load",
            resource_decision=decision.as_dict(),
        )

    if decision.selected == "memory":
        valid, errors = _tree_validate_xml(xml_path, schema, in_memory=True)
        mode = "memory-tree"
    elif decision.selected == "disk":
        valid, errors = _tree_validate_xml(xml_path, schema, in_memory=False)
        mode = "disk-tree"
    else:
        valid, errors = _stream_validate_xml(xml_path, schema)
        mode = "streaming-iterparse"

    return XmlSchemaValidationResult(
        valid,
        xml_path,
        schema_path,
        errors,
        file_size_bytes=file_size_bytes,
        validation_mode=mode,
        resource_decision=decision.as_dict(),
    )


def write_validation_report(
    result: XmlSchemaValidationResult,
    output_path: str | Path,
    *,
    validation_id: str,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "validation_id": validation_id,
        **result.as_dict(),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
