from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from noark5_workflow.analysis.u1_total import run_u1_total
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.sources.noark5_extraction import Noark5Extraction


DEFINITION_PATH = (
    Path(__file__).resolve().parents[2]
    / "config" / "noark5" / "analysis" / "u1_total.json"
)


class AnalyseNoark5U1Operation(BaseOperation):
    definition = OperationDefinition(
        operation_id="analyse_noark5_u1",
        name="Noark 5 U1 – samlet opptelling (Legacy)",
        description=(
            "Kjører U1/N5.101 som samlet opptelling for hele Noark 5-uttrekket. "
            "Grunnlaget er den bevarte KDRS Query U01-filen fra 2022-09-21."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Innhold",
    )

    raw_result_record = True

    def raw_result_identity(self, result: OperationResult, ctx: OperationContext) -> dict[str, str]:
        return {"test_id": "noark5.u1.total.v1", "definition_version": "1"}

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        if not extraction.metadata_files.get("arkivstruktur"):
            return False, "arkivstruktur.xml er påkrevd for U1."
        if ctx.work_operations is None:
            return False, "Jobben mangler Arbeid – operasjoner."
        if not DEFINITION_PATH.is_file():
            return False, f"U1-definisjonen mangler: {DEFINITION_PATH}"
        return True, ""

    def run(self, ctx: OperationContext) -> OperationResult:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        source = extraction.metadata_files.get("arkivstruktur")
        if source is None:
            return OperationResult(False, "arkivstruktur.xml ble ikke funnet.")

        try:
            definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
            output_cfg = definition["output"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            return OperationResult(False, f"Kunne ikke lese U1-definisjonen: {exc}")

        ctx.progress(0.05, "Starter U1 – samlet opptelling")
        try:
            result = run_u1_total(source)
        except (OSError, etree.XMLSyntaxError, ValueError) as exc:
            return OperationResult(False, f"U1-analysen feilet: {exc}")

        result["definition_path"] = str(DEFINITION_PATH)
        result["basis"] = definition.get("basis", {})

        output_path = (
            Path(ctx.work_operations)
            / str(output_cfg["relative_dir"])
            / str(output_cfg["filename"])
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        ctx.progress(1.0, "U1 – samlet opptelling fullført")

        return OperationResult(
            True,
            (
                "U1 samlet opptelling fullført: "
                f"{result['archive']['count']} arkiv, "
                f"{result['structure']['archive_part_count']} arkivdeler, "
                f"{result['folders']['count']} mapper, "
                f"{result['registrations']['count']} registreringer, "
                f"{result['documents']['description_count']} dokumentbeskrivelser og "
                f"{result['documents']['object_count']} dokumentobjekter. "
                f"Resultat: {output_path}"
            ),
            data={
                "analysis": result,
                "report": str(output_path),
                "definition": str(DEFINITION_PATH),
                "definition_id": definition.get("definition_id", ""),
                "definition_version": str(definition.get("format_version", "")),
            },
        )
