from __future__ import annotations

import xml.etree.ElementTree as ET

from lxml import etree

from noark5_workflow.analysis.arkivstruktur import analyse_arkivstruktur
from noark5_workflow.analysis.defined_fields import (
    DefinedFieldExtractionError,
    extract_defined_fields,
)
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult
from noark5_workflow.sources.noark5_extraction import Noark5Extraction


class AnalyseArkivstrukturOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="analyse_arkivstruktur",
        name="Analyse arkivstruktur.xml",
        description=(
            "Strømmet strukturanalyse av arkivstruktur.xml med gjenbrukbare "
            "elementtellere som grunnlag for Noark-kontroller og rapporter."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Metadata",
    )

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        return extraction.is_noark5_candidate, "arkivstruktur.xml er påkrevd."

    def run(self, ctx: OperationContext) -> OperationResult:
        extraction = ctx.source or Noark5Extraction.detect(ctx.extraction_root)
        arkivstruktur = extraction.metadata_files["arkivstruktur"]
        if arkivstruktur is None:
            return OperationResult(False, "arkivstruktur.xml ble ikke funnet.")

        ctx.progress(0.05, "Starter strømmet analyse av arkivstruktur.xml")
        try:
            analysis = analyse_arkivstruktur(arkivstruktur)
        except (ET.ParseError, OSError, ValueError) as exc:
            return OperationResult(
                False,
                f"Analyse av arkivstruktur.xml feilet: {exc}",
                data={"arkivstruktur": str(arkivstruktur)},
            )

        ctx.progress(0.75, "Henter definerte Noark 5-felt")

        defined_fields = {}
        defined_fields_error = None
        warnings = []

        try:
            defined_fields = extract_defined_fields(arkivstruktur)
        except DefinedFieldExtractionError as exc:
            # The streamed structural analysis above is still valid. Defined
            # field extraction is enrichment and must not prevent the remaining
            # validation workflow from running. Keep the failure explicit.
            defined_fields_error = exc.as_dict()
            warning = (
                "Definert feltuttrekk kunne ikke fullføres. "
                f"{exc}. Workflow fortsetter med strukturanalysen."
            )
            warnings.append(warning)
            ctx.log(f"ADVARSEL: {warning}")
        except (etree.XMLSyntaxError, OSError) as exc:
            defined_fields_error = {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "phase": "defined_fields",
            }
            warning = (
                "Definert feltuttrekk kunne ikke fullføres: "
                f"{type(exc).__name__}: {exc}. "
                "Workflow fortsetter med strukturanalysen."
            )
            warnings.append(warning)
            ctx.log(f"ADVARSEL: {warning}")

        ctx.progress(1.0, "Analyse av arkivstruktur.xml fullført")
        key = analysis.key_counts
        message = (
            "Analyse arkivstruktur.xml fullført: "
            f"{analysis.total_elements} XML-elementer; "
            f"{key['arkiv']} arkiv, "
            f"{key['arkivdel']} arkivdel, "
            f"{key['mappe']} mapper, "
            f"{key['registrering']} registreringer, "
            f"{key['dokumentbeskrivelse']} dokumentbeskrivelser og "
            f"{key['dokumentobjekt']} dokumentobjekter."
        )
        if defined_fields_error is not None:
            message += " Definert feltuttrekk ga advarsel; se diagnosedata."

        data = {
            **analysis.as_dict(),
            "defined_fields": defined_fields,
        }
        if defined_fields_error is not None:
            data["defined_fields_error"] = defined_fields_error

        return OperationResult(
            True,
            message,
            data=data,
            warnings=warnings,
        )
