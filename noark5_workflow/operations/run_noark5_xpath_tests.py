from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from noark5_workflow.analysis.master_results import (
    MasterResultError,
    build_master_result_set,
    load_master_result_set,
)
from noark5_workflow.analysis.xpath_test_engine import run_catalog
from noark5_workflow.core.context import OperationContext
from noark5_workflow.core.operation import BaseOperation, ExecutionTarget, OperationDefinition
from noark5_workflow.core.result import OperationResult

CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "noark5" / "tests" / "xpath_catalog_2026_05_26.json"


class _BaseNoark5XpathTestsOperation(BaseOperation):
    execution_profile = "normal"
    output_subdir = "xpath"

    raw_result_record = True

    def raw_result_identity(self, result, ctx):
        return {
            "test_id": f"noark5-kdrs-query-2026-05-26-{self.execution_profile}",
            "definition_version": "5",
        }

    def can_run(self, ctx: OperationContext) -> tuple[bool, str]:
        if ctx.work_operations is None:
            return False, "Jobben mangler Arbeid – operasjoner."
        if not CATALOG_PATH.is_file():
            return False, f"Testkatalogen mangler: {CATALOG_PATH}"
        return True, ""

    def _run_profile(self, ctx: OperationContext) -> OperationResult:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = Path(ctx.work_operations) / "noark5_tests" / self.output_subdir / stamp

        ctx.progress(0.02, f"Starter {self.definition.name}")

        def on_test_progress(phase, current, total, test, status, duration):
            job_id = test["legacy"]["job_id"]
            point = test["legacy"].get("test_point") or test.get("normalized_test_point") or "–"
            label = f"Test {current}/{total} – {job_id} / {point} – {test['name']}"
            if phase == "started":
                fraction = 0.02 + (0.94 * (current - 1) / max(total, 1))
                ctx.progress(fraction, label)
                ctx.log(
                    f"TEST START {current}/{total} | {test['test_id']} | "
                    f"{job_id} | {point} | {test['source_xml']} | {test['name']}"
                )
            else:
                fraction = 0.02 + (0.94 * current / max(total, 1))
                suffix = f" | {duration:.3f}s" if duration is not None else ""
                ctx.progress(fraction, f"{label} – {status}{suffix}")
                ctx.log(
                    f"TEST SLUTT {current}/{total} | {test['test_id']} | "
                    f"{job_id} | {point} | {status}{suffix}"
                )

        index = run_catalog(
            CATALOG_PATH,
            ctx.extraction_root,
            out,
            include_disabled=True,
            execution_profile=self.execution_profile,
            progress_callback=on_test_progress,
        )

        master_path = None
        master_summary = None
        if self.execution_profile == "normal":
            try:
                master_path = build_master_result_set(out)
                master_document = load_master_result_set(master_path)
                master_summary = master_document.get("summary") or {}
                index["master_result_set"] = {
                    "file": master_path.name,
                    "model_id": master_document.get("model_id"),
                    "role": master_document.get("role"),
                    "summary": master_summary,
                }
                (out / "index.json").write_text(
                    json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except MasterResultError as exc:
                return OperationResult(
                    False,
                    f"Noark 5-testene ble kjørt, men masterresultatsettet kunne ikke materialiseres: {exc}",
                    data={
                        "result_index": index,
                        "output_dir": str(out),
                        "catalog": str(CATALOG_PATH),
                        "execution_profile": self.execution_profile,
                    },
                )

        ctx.progress(1.0, f"{self.definition.name} fullført")
        s = index.get("summary", {})
        regression = index.get("legacy_regression_comparison")
        regression_text = ""
        if regression:
            rs = regression.get("summary", {})
            regression_text = (
                f" Legacy-regresjon: {rs.get('matches', 0)} match, "
                f"{rs.get('mismatches', 0)} mismatch, "
                f"{rs.get('not_comparable', 0)} ikke sammenlignbare."
            )

        master_text = ""
        if master_path is not None and master_summary is not None:
            master_text = (
                " Masterresultater: "
                f"{master_summary.get('available_master_results', 0)} tilgjengelige, "
                f"{master_summary.get('unavailable_master_results', 0)} utilgjengelige."
            )

        return OperationResult(
            True,
            f"Noark 5-testkatalog kjørt ({self.execution_profile}): "
            f"{s.get('ok', 0)} OK, {s.get('source_missing', 0)} mangler kildefil, "
            f"{s.get('disabled_by_legacy_source', 0)} legacy-deaktivert, "
            f"{s.get('error', 0)} feil.{master_text}{regression_text} Resultat: {out}",
            data={
                "result_index": index,
                "output_dir": str(out),
                "catalog": str(CATALOG_PATH),
                "execution_profile": self.execution_profile,
                "master_result_set": str(master_path) if master_path is not None else None,
            },
        )


class RunNoark5XpathTestsOperation(_BaseNoark5XpathTestsOperation):
    definition = OperationDefinition(
        operation_id="run_noark5_xpath_tests_2026",
        name="Noark 5 XPath-tester 2026",
        description=(
            "Kjører ordinær Noark 5-testprofil. Historiske regresjonsreferanser "
            "er ikke med i normal depotvalidering."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Innhold",
    )
    execution_profile = "normal"
    output_subdir = "xpath"

    def run(self, ctx: OperationContext) -> OperationResult:
        return self._run_profile(ctx)


class RunNoark5XpathRegressionOperation(_BaseNoark5XpathTestsOperation):
    # QA/regresjonskjøringen skal aldri stoppe workflow ved et kontrollpunkt.
    allow_checkpoint = False

    definition = OperationDefinition(
        operation_id="run_noark5_xpath_regression_2026",
        name="Noark 5 XPath-regresjon 2026",
        description=(
            "Utviklings-/QA-kjøring som inkluderer historiske U01/U02-regresjonsreferanser "
            "og lager maskinell sammenligning mot kanoniske individuelle analyser. "
            "Skal ikke brukes som ordinær depotvalidering."
        ),
        execution_target=ExecutionTarget.EITHER,
        category="Systemspesifikt",
    )
    execution_profile = "regression"
    output_subdir = "xpath_regression"

    def run(self, ctx: OperationContext) -> OperationResult:
        return self._run_profile(ctx)
