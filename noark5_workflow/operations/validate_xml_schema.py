from __future__ import annotations

import json
from pathlib import Path

from noark5_workflow.analysis.xml_schema_validation import resolve_local_schema, validate_xml_against_xsd, write_validation_report
from noark5_workflow.core.artifact_identity import artifact_run_dir, write_artifact_manifest
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.sources.noark5_extraction import Noark5Extraction

DEFINITION_PATH = Path(__file__).resolve().parents[2] / "config" / "noark5" / "xml_schema_validation.json"

class ValidateXmlSchemaOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="validate_xml_schema", name="Valider XML mot XSD",
        description="Validerer arkivstruktur.xml mot lokal XSD med lxml og skriver et strukturert JSON-resultat til jobbens Noark 5-testområde.",
        execution_target=ExecutionTarget.EITHER, category="Integritet",
    )

    raw_result_record = True

    def raw_result_identity(self, result: OperationResult, ctx: OperationContext) -> dict[str, str]:
        try:
            definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
            validation = (definition.get("validations") or [{}])[0]
        except Exception:
            definition, validation = {}, {}
        definition_id = str(definition.get("definition_id") or self.definition.operation_id)
        validation_id = str(validation.get("id") or "")
        return {
            "test_id": f"{definition_id}/{validation_id}" if validation_id else definition_id,
            "definition_version": str(definition.get("format_version") or ""),
        }

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        extraction=ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        if not extraction.metadata_files.get("arkivstruktur"): return False,"arkivstruktur.xml er påkrevd."
        if not extraction.xsd_files: return False,"Ingen lokal XSD-fil ble funnet i uttrekket."
        if ctx.work_operations is None: return False,"Jobben mangler Arbeid – operasjoner. Åpne Mapper for aktiv jobb og velg området for valideringsrapporten."
        return True,""

    def run(self, ctx: OperationContext) -> OperationResult:
        extraction=ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        definition=json.loads(DEFINITION_PATH.read_text(encoding="utf-8")); item=definition["validations"][0]
        xml_path=extraction.metadata_files[item["source_key"]]
        if xml_path is None: return OperationResult(False,f"{item['source']} ble ikke funnet.")
        schema_path=resolve_local_schema(xml_path,extraction.xsd_files,item.get("schema",{}).get("preferred_names",[]))
        if schema_path is None:
            return OperationResult(False,"Kunne ikke avgjøre hvilken lokal XSD som hører til arkivstruktur.xml.",data={"available_xsds":[str(p) for p in extraction.xsd_files]})
        out = artifact_run_dir(
            ctx,
            "noark5_tests",
            "schema",
            operation_id=self.definition.operation_id,
        )
        write_artifact_manifest(
            ctx,
            out,
            operation_id=self.definition.operation_id,
            definition_id=str(definition.get("definition_id", "")),
            definition_version=str(definition.get("format_version", "")),
        )
        ctx.progress(0.25,f"XSD: {schema_path.name}"); result=validate_xml_against_xsd(xml_path,schema_path)
        report_path=out / item["output"]
        write_validation_report(result,report_path,validation_id=item["id"]); ctx.progress(1.0,"XML/XSD-validering fullført")
        data={
            **result.as_dict(),
            "report":str(report_path),
            "artifact_manifest":str(out / "artifact_manifest.json"),
            "definition_id": str(definition.get("definition_id", "")),
            "definition_version": str(definition.get("format_version", "")),
            "validation_id": str(item.get("id", "")),
        }
        if result.valid: return OperationResult(True,f"XML/XSD-validering OK. Rapport: {report_path}",data=data)
        return OperationResult(False,f"XML/XSD-validering feilet med {len(result.errors)} avvik. Rapport: {report_path}",data=data)
