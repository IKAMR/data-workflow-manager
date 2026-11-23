from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from noark5_workflow.analysis.definition_engine import (
    AnalysisDefinitionError,
    write_analysis_result,
)
from noark5_workflow.analysis.legacy_a170_stream import run_legacy_a170_stream
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.sources.noark5_extraction import Noark5Extraction


DEFINITION_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "noark5"
    / "analysis"
    / "u1_u2_core_arkiv_arkivdel.json"
)


class AnalyseNoark5CoreOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="analyse_noark5_core",
        name="Noark 5-analyse: arkiv og arkivdel (Legacy)",
        description=(
            "Kjører eksternt definerte XPath-analyser basert på U1/U2-grunnlaget "
            "og lagrer et strukturert grunnresultat uavhengig av senere rapportformat."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Innhold",
    )

    # a17: preserve each execution as immutable raw evidence. This is not a
    # PREMIS declaration and does not make the analysis authoritative by itself.
    raw_result_record = True

    def raw_result_identity(self, result: OperationResult, ctx: OperationContext) -> dict[str, str]:
        try:
            definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
        except Exception:
            definition = {}
        return {
            "test_id": str(definition.get("definition_id") or self.definition.operation_id),
            "definition_version": str(definition.get("format_version") or ""),
        }

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        if not extraction.metadata_files.get("arkivstruktur"):
            return False, "arkivstruktur.xml er påkrevd."
        if ctx.work_operations is None:
            return (
                False,
                "Jobben mangler Arbeid – operasjoner. Åpne Mapper for aktiv jobb "
                "og velg området for analyseresultatet.",
            )
        if not DEFINITION_PATH.is_file():
            return False, f"Analysedefinisjonen mangler: {DEFINITION_PATH}"
        return True, ""

    def run(self, ctx: OperationContext) -> OperationResult:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        arkivstruktur = extraction.metadata_files.get("arkivstruktur")
        if arkivstruktur is None:
            return OperationResult(False, "arkivstruktur.xml ble ikke funnet.")

        try:
            definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
            output_cfg = definition["output"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return OperationResult(False, f"Kunne ikke lese analysedefinisjonen: {exc}")

        ctx.progress(0.10, "Leser U1/U2-basert analysedefinisjon")
        try:
            result = run_legacy_a170_stream(arkivstruktur, DEFINITION_PATH)
        except (OSError, etree.XMLSyntaxError, etree.XPathError, AnalysisDefinitionError, ValueError) as exc:
            return OperationResult(False, f"Noark 5-analysen feilet: {exc}")

        output_path = (
            Path(ctx.work_operations)
            / str(output_cfg["relative_dir"])
            / str(output_cfg["filename"])
        )
        write_analysis_result(result, output_path)
        ctx.progress(1.0, "Noark 5-analyse av arkiv og arkivdel fullført")

        counts = result["summary"]["entity_counts"]
        message = (
            "Noark 5-analyse fullført: "
            f"{counts.get('archive', 0)} arkiv og "
            f"{counts.get('archive_part', 0)} arkivdeler. "
            f"Resultat: {output_path}"
        )
        return OperationResult(
            True,
            message,
            data={
                "analysis": result,
                "report": str(output_path),
                "definition": str(DEFINITION_PATH),
                "definition_id": str(definition.get("definition_id", "")),
                "definition_version": str(definition.get("format_version", "")),
            },
        )
