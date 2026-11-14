"""Readable, read-only projection of an existing depot-review row.

Do not derive approvals, merge whole-extraction deviations into archive parts,
or replace the underlying version-bound decision evidence. The full raw
payload remains accessible in the Qt reviewer.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_GROUPS = (
    ("Arkiver", "archive_count"),
    ("Arkivdeler", "archive_part_count"),
    ("Mapper", "folder_count"),
    ("Registreringer", "registration_count"),
    ("Dokumentbeskrivelser", "document_description_count"),
    ("Dokumentobjekter", "document_object_count"),
)


def _simple(value: Any, *, width: int = 180) -> str:
    if value is None:
        return "Ikke oppgitt"
    if isinstance(value, bool):
        return "Ja" if value else "Nei"
    if isinstance(value, (str, int, float)):
        result = str(value).strip()
        return result[:width] + "…" if len(result) > width else (result or "Ikke oppgitt")
    if isinstance(value, (list, tuple)):
        if not value:
            return "Ingen registrerte elementer"
        text = ", ".join(_simple(item, width=70) for item in value[:5])
        return text + (f" … (+{len(value) - 5})" if len(value) > 5 else "")
    if isinstance(value, Mapping):
        for key in ("title", "name", "status", "message", "description", "reason", "value"):
            if key in value and value[key] not in (None, ""):
                return _simple(value[key], width=width)
        return "; ".join(f"{key}: {_simple(val, width=80)}" for key, val in list(value.items())[:3]) or "Ingen registrerte felt"
    return _simple(str(value), width=width)


def _add_section(lines: list[str], heading: str, entries: list[tuple[str, Any]]) -> None:
    lines.extend(("", heading, "-" * len(heading)))
    lines.extend(f"{label}: {_simple(value)}" for label, value in entries)


def readable_depot_review(row: Any, *, max_findings: int = 8, max_sources: int = 8) -> str:
    """Render values from an existing DepotReviewRow without any filesystem reads.

    Unknown/missing fields stay unknown. Counts and statuses are copied from
    recorded evidence, never inferred from the job's successful workflow.
    """
    if row is None:
        return "Velg et uttrekk eller en arkivdel for å se vurderingsgrunnlaget."
    details = getattr(row, "details", {}) or {}
    if not isinstance(details, Mapping):
        details = {}
    scope = str(getattr(row, "scope", "") or "")
    title = str(getattr(row, "title", "") or "Ukjent omfang")
    lines = ["FAGLIG VURDERINGSGRUNNLAG", "=" * 27]
    _add_section(lines, "Omfang og status", [
        ("Omfang", "Hele uttrekket" if scope == "uttrekk" else "Arkivdel" if scope == "arkivdel" else scope),
        ("Uttrekk", getattr(row, "job_name", None)),
        ("Valgt", title),
        ("Jobb-ID", getattr(row, "job_id", None)),
        *([("Arkivdelens system-ID", getattr(row, "native_id", None))] if scope == "arkivdel" else []),
        ("Teknisk status", getattr(row, "technical_status", None)),
        ("Faglig depotstatus", getattr(row, "professional_status", None)),
        ("Periodevurdering", getattr(row, "period_status", None)),
        ("Vurderingspunkter", getattr(row, "deviation_count", None)),
        ("Historiske faglige beslutninger", getattr(row, "history_count", None)),
        ("Sist vurdert", getattr(row, "updated_at", None)),
    ])

    if getattr(row, "warning", ""):
        _add_section(lines, "Merknad / manglende grunnlag", [("Merknad", row.warning)])

    decision = details.get("faglig_beslutning")
    if isinstance(decision, Mapping) and decision:
        user = decision.get("user") or {}
        user_text = (user.get("name") or user.get("username") or user.get("user_id")) if isinstance(user, Mapping) else None
        _add_section(lines, "Registrert faglig beslutning", [
            ("Registrert status", decision.get("status")),
            ("Begrunnelse", decision.get("reason")),
            ("Vurdert", decision.get("assessed_at")),
            ("Registrert av", user_text),
        ])
    else:
        lines.extend(("", "Ingen faglig beslutning er registrert for valgt omfang."))

    overview = details.get("rapportert_oversikt")
    if isinstance(overview, Mapping) and overview:
        counts = [(label, overview[key]) for label, key in _GROUPS if key in overview]
        if counts:
            _add_section(lines, "Rapportert uttrekksoversikt", counts)

    automatic = details.get("opprinnelig_automatisk_vurdering")
    if isinstance(automatic, Mapping) and automatic:
        _add_section(lines, "Rapportens opprinnelige oppfølging (ikke faglig vedtak)", [
            ("Rapportstatus", automatic.get("status")),
            ("Rapportens begrunnelse", automatic.get("reason")),
        ])

    _add_section(lines, "Periodegrunnlag", [
        ("Oppgitt periode", details.get("periode_oppgitt")),
        ("Observert periode", details.get("periode_observert_arkivdel") if scope == "arkivdel"
         else details.get("periode_observert")),
    ])

    if scope == "arkivdel":
        findings = details.get("avvik_per_arkivdel")
    else:
        findings = details.get("vurderingspunkter")
    if isinstance(findings, (tuple, list)):
        lines.extend(("", "Vurderingspunkter", "-----------------"))
        if findings:
            for index, finding in enumerate(findings[:max(0, max_findings)], 1):
                lines.append(f"{index}. {_simple(finding, width=240)}")
            if len(findings) > max_findings:
                lines.append(f"Ytterligere {len(findings) - max_findings} punkter er tilgjengelige i rådata.")
        else:
            lines.append("Ingen punkter registrert i den aktuelle rapportseksjonen.")
    else:
        lines.extend(("", "Vurderingspunkter: Ikke dokumentert for valgt omfang."))

    sources = details.get("evidenskilder")
    if isinstance(sources, (tuple, list)):
        lines.extend(("", "Registrerte evidenskilder", "-------------------------"))
        if scope == "arkivdel":
            lines.append("Kildene nedenfor er opptalt på uttrekksnivå, ikke verifisert for arkivdelen.")
        if not sources:
            lines.append("Ingen eksterne evidenskilder oppført i oversikten.")
        for source in sources[:max(0, max_sources)]:
            if isinstance(source, Mapping):
                label = source.get("kilde") or "Ukjent kilde"
                number = _simple(source.get("antall"))
                identifier = _simple(source.get("import_id"))
                lines.append(f"• {_simple(label)} | import: {identifier} | antall: {number} | "
                             f"status: {_simple(source.get('status'))}")
            else:
                lines.append("• " + _simple(source))
        if len(sources) > max_sources:
            lines.append(f"Ytterligere {len(sources) - max_sources} kilder finnes i rådata.")

    _add_section(lines, "Sporbarhet", [
        ("Rapport", details.get("rapport")),
        ("Rapport SHA-256", details.get("rapport_sha256")),
    ])
    lines.extend(("", "Teknisk fullføring er ikke faglig godkjenning.",
                  "Visningen er et sammendrag. Velg «Rå JSON» for samtlige lagrede detaljer."))
    return "\n".join(lines)
