from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from noark5_workflow.analysis import xpath_test_engine as engine
from noark5_workflow.analysis.xpath_diagnostics import run_catalog_profiled


class A162XpathDiagnosticsTests(unittest.TestCase):
    def _catalog(self, path: Path) -> None:
        payload = {
            "catalog_id": "a16.2-test",
            "source": {"role": "test"},
            "tests": [
                {
                    "test_id": "ok.metric",
                    "legacy": {"job_id": "OK", "test_point": "T1", "job_enabled": 1},
                    "name": "ok",
                    "source_xml": "arkivstruktur.xml",
                    "scope": "source_document",
                    "execution": {
                        "kind": "metrics",
                        "metrics": [
                            {
                                "id": "count",
                                "type": "xpath",
                                "expression": "count(//mappe)",
                            }
                        ],
                    },
                    "status": "active",
                    "tags": [],
                    "noark_versions": ["5.0"],
                },
                {
                    "test_id": "bad.metric",
                    "legacy": {"job_id": "BAD", "test_point": "T2", "job_enabled": 1},
                    "name": "bad",
                    "source_xml": "arkivstruktur.xml",
                    "scope": "source_document",
                    "execution": {
                        "kind": "metrics",
                        "metrics": [
                            {
                                "id": "broken",
                                "type": "xpath",
                                "expression": "count(//mappe[",
                            }
                        ],
                    },
                    "status": "active",
                    "tags": [],
                    "noark_versions": ["5.0"],
                },
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_profiled_catalog_writes_performance_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            out = root / "out"
            source.mkdir()
            (source / "arkivstruktur.xml").write_text(
                "<arkiv><mappe/><mappe/></arkiv>",
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            self._catalog(catalog)

            index = run_catalog_profiled(catalog, source, out)

            ref = index["performance_diagnostics"]
            perf = json.loads((out / ref["file"]).read_text(encoding="utf-8"))
            self.assertEqual(2, perf["summary"]["tests"])
            self.assertEqual(1, perf["summary"]["errors"])
            self.assertGreaterEqual(
                perf["summary"]["total_tree_preparation_seconds"],
                0,
            )
            self.assertIn("cpu_logical_count", perf["environment"])

    def test_error_diagnostics_identify_exact_metric_and_expression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            out = root / "out"
            source.mkdir()
            (source / "arkivstruktur.xml").write_text(
                "<arkiv><mappe/></arkiv>",
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            self._catalog(catalog)

            run_catalog_profiled(catalog, source, out)
            perf = json.loads(
                (out / "performance-diagnostics.json").read_text(encoding="utf-8")
            )
            error = perf["errors"][0]
            context = error["error_context"]
            self.assertEqual("bad.metric", error["test_id"])
            self.assertEqual("broken", context["metric_id"])
            self.assertEqual("xpath", context["metric_type"])
            self.assertEqual("count(//mappe[", context["expression"])

    def test_result_keeps_phase_timings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            out = root / "out"
            source.mkdir()
            (source / "arkivstruktur.xml").write_text(
                "<arkiv><mappe/></arkiv>",
                encoding="utf-8",
            )
            catalog = root / "catalog.json"
            self._catalog(catalog)

            run_catalog_profiled(catalog, source, out)
            result = json.loads(
                (out / "results" / "ok_metric.json").read_text(encoding="utf-8")
            )
            diagnostics = result["diagnostics"]
            self.assertEqual(1, diagnostics["tree_preparation"]["calls"])
            self.assertGreaterEqual(
                diagnostics["tree_preparation"]["duration_seconds"],
                0,
            )
            self.assertEqual("count", diagnostics["metrics"][0]["metric_id"])
            self.assertGreaterEqual(
                diagnostics["metric_evaluation_seconds"],
                0,
            )

    def test_instrumentation_is_restored_after_catalog_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            out = root / "out"
            source.mkdir()
            (source / "arkivstruktur.xml").write_text("<arkiv/>", encoding="utf-8")
            catalog = root / "catalog.json"
            self._catalog(catalog)

            old_run_test = engine.run_test
            old_normalise = engine._normalise_tree
            old_eval = engine._eval_metrics
            run_catalog_profiled(catalog, source, out)
            self.assertIs(old_run_test, engine.run_test)
            self.assertIs(old_normalise, engine._normalise_tree)
            self.assertIs(old_eval, engine._eval_metrics)


if __name__ == "__main__":
    unittest.main()
