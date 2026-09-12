from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from noark5_workflow.analysis.view_composer import write_composed_views
from noark5_workflow.analysis.presentation_materializer import write_materialized_profiles
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult

DEFINITION_PATH = (
    Path(__file__).resolve().parents[2]
    / "config" / "noark5" / "views" / "canonical_views.json"
)
PRESENTATION_DEFINITION_PATH = (
    Path(__file__).resolve().parents[2]
    / "config" / "noark5" / "views" / "presentation_profiles.json"
)


def _latest_normal_result_set(work_operations: Path) -> Path | None:
    root = work_operations / "noark5_tests" / "xpath"
    if not root.is_dir():
        return None

    candidates = []
    for path in root.iterdir():
        if not path.is_dir() or not (path / "index.json").is_file():
            continue
        try:
            index = json.loads((path / "index.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if index.get("execution_profile") == "normal":
            candidates.append(path)

    return max(candidates, key=lambda p: p.name) if candidates else None


class ComposeNoark5ViewsOperation(BaseOperation):
    definition = OperationDefinition(
        operation_id="compose_noark5_views",
        name="Noark 5 views/compositions",
        description=(
            "Bygger definisjonsdrevne og gjenbrukbare visninger fra siste ordinære "
            "Noark 5-resultatsett. Ingen XML/XPath beregnes på nytt."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Rapport",
    )
    raw_result_record = True

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Jobben mangler Arbeid – operasjoner."
        if not DEFINITION_PATH.is_file():
            return False, f"View-definisjonen mangler: {DEFINITION_PATH}"
        if not PRESENTATION_DEFINITION_PATH.is_file():
            return False, f"Presentasjonsdefinisjonen mangler: {PRESENTATION_DEFINITION_PATH}"
        result_set = _latest_normal_result_set(Path(ctx.work_operations))
        if result_set is None:
            return False, (
                "Ingen ordinær Noark 5 XPath-kjøring finnes. "
                "Kjør Noark 5 XPath-tester 2026 først."
            )
        return True, ""

    def run(self, ctx: OperationContext) -> OperationResult:
        result_set = _latest_normal_result_set(Path(ctx.work_operations))
        if result_set is None:
            return OperationResult(
                False,
                "Ingen ordinær Noark 5 XPath-kjøring finnes.",
            )

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path(ctx.work_operations) / "noark5_views" / stamp
        ctx.progress(0.10, "Leser kanoniske Noark 5-resultater")
        index = write_composed_views(result_set, DEFINITION_PATH, out)

        composed_files = {
            row["id"]: out / row["file"]
            for row in index.get("views", [])
        }
        presentation_definition = json.loads(
            PRESENTATION_DEFINITION_PATH.read_text(encoding="utf-8")
        )
        presentation_out = out / "presentations"
        presentation_index = write_materialized_profiles(
            composed_files,
            presentation_definition,
            presentation_out,
        )

        ctx.progress(1.0, "Noark 5 views/compositions fullført")
        return OperationResult(
            True,
            f"Noark 5 views/compositions bygget: {len(index['views'])} views og "
            f"{len(presentation_index['profiles'])} presentasjonsprofiler. Resultat: {out}",
            data={
                "output_dir": str(out),
                "source_result_set": str(result_set),
                "view_index": index,
                "presentation_index": presentation_index,
                "definition": str(DEFINITION_PATH),
                "presentation_definition": str(PRESENTATION_DEFINITION_PATH),
            },
        )
