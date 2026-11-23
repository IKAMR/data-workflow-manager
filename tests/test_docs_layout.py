"""Regression tests for conservative DWM docs migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("docs_layout", ROOT / "tools" / "docs_layout.py")
assert SPEC is not None and SPEC.loader is not None
import sys
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DocsLayoutTests(unittest.TestCase):
    def test_stable_release_and_development_paths_do_not_move(self):
        for name in ("DEVELOPMENT.md", "ARCHITECTURE.md", "RELEASES.md",
                     "RELEASE-v0.2.5.md", "NOARK-SOURCE-LIBRARY.md"):
            self.assertIsNone(MODULE.destination_category(name), name)

    def test_histories_and_references_are_separated(self):
        cases = {
            "v0.1.5-a20.md": "history/alpha/v0.1.5",
            "V025-A3-FORTSETT-RESTERENDE.md": "history/alpha/v0.2.5",
            "NOARK5-CANONICAL-A14.md": "history/alpha/canonical",
            "A12-DELTA-MANIFEST.json": "history/deltas",
            "TESTRESULTAT-V022-A3.md": "history/test-notes",
            "ARKADE5-CLI.md": "integrations/arkade5",
            "SIEGFRIED-TESTREGRESJON-V022-A4-1.md": "history/test-notes",
            "NOARK5-STANDARD-VALUES.md": "reference/noark5",
            "JOBS-AND-BATCHES.md": "workflow",
            "DWM-BACKLOG-CONSOLIDATED.md": "plans",
        }
        for name, want in cases.items():
            with self.subTest(file=name):
                self.assertEqual(MODULE.destination_category(name), want)

    def test_rebased_link_from_moved_file(self):
        old = "docs/ARKADE5-CLI.md"
        new = "docs/integrations/arkade5/ARKADE5-CLI.md"
        text = "[Guide](NOARK5-ANALYSIS-MODEL.md#details) [Local](ARKADE5-COMBINED-COVERAGE.md) [External](https://example.org)"
        moves = {
            old: new,
            "docs/NOARK5-ANALYSIS-MODEL.md": "docs/reference/noark5/NOARK5-ANALYSIS-MODEL.md",
            "docs/ARKADE5-COMBINED-COVERAGE.md": "docs/integrations/arkade5/ARKADE5-COMBINED-COVERAGE.md",
        }
        result = MODULE.rewrite_document(text, old, new, moves, set(moves))
        self.assertIn("../../reference/noark5/NOARK5-ANALYSIS-MODEL.md#details", result)
        self.assertIn("(ARKADE5-COMBINED-COVERAGE.md)", result)
        self.assertIn("https://example.org", result)

    def test_repo_root_path_in_text_is_updated(self):
        new = MODULE.rewrite_document("See `docs/ARKADE5-CLI.md`.", "README.md", "README.md",
                                      {"docs/ARKADE5-CLI.md": "docs/integrations/arkade5/ARKADE5-CLI.md"},
                                      {"docs/ARKADE5-CLI.md"})
        self.assertEqual(new, "See `docs/integrations/arkade5/ARKADE5-CLI.md`.")

    def test_current_repository_does_not_gain_root_clutter(self):
        # Permanent safeguard: new alpha/delta notes cannot silently build up.
        self.assertEqual(MODULE.root_layout_issues(ROOT), [])

    def test_docs_root_rejects_new_files_even_if_a_test_references_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            (root / "version.py").write_text(
                'APP_NAME = "Data Workflow Manager"\nVERSION = "0.2.6-a1"\n',
                encoding="utf-8",
            )
            (docs / "RELEASES.md").write_text("# Versions\n", encoding="utf-8")
            (docs / "V026-A2-NEW-FEATURE.md").write_text("# Disposable note\n", encoding="utf-8")
            (docs / "UNCLASSIFIED.md").write_text("# New note\n", encoding="utf-8")
            (docs / "ARKADE5-CLI.md").write_text("# New pinned document\n", encoding="utf-8")
            issues = MODULE.root_layout_issues(root)
            self.assertTrue(any("UNCLASSIFIED.md" in issue for issue in issues), issues)
            self.assertTrue(any("ARKADE5-CLI.md" in issue for issue in issues), issues)
            self.assertTrue(any("Alpha-notat" in issue for issue in issues), issues)

    def test_old_history_is_allowed_but_current_alpha_history_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "history" / "alpha" / "v0.2.5").mkdir(parents=True)
            (root / "version.py").write_text('VERSION = "0.2.6-a1"\n', encoding="utf-8")
            old = root / "docs" / "history" / "alpha" / "v0.2.5" / "V025-A3-DONE.md"
            old.write_text("# Archived\n", encoding="utf-8")
            self.assertEqual(MODULE.root_layout_issues(root), [])
            current = old.parent / "NOARK5-CONTROL-V026-A2-NEW.md"
            current.write_text("# New\n", encoding="utf-8")
            self.assertTrue(MODULE.root_layout_issues(root))

    def test_reorganization_is_idempotent_and_pins_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "docs").mkdir()
            (repo / "tests").mkdir()
            (repo / "tools").mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "docs" / "RELEASES.md").write_text("# Releases\n", encoding="utf-8")
            (repo / "docs" / "NOARK5-STANDARD-VALUES.md").write_text(
                "# Model\n[Version](v0.1.5-a1.md)\n", encoding="utf-8")
            (repo / "docs" / "v0.1.5-a1.md").write_text("# Alpha\n", encoding="utf-8")
            (repo / "docs" / "RELEASE-v0.2.5.md").write_text("# v0.2.5\n", encoding="utf-8")
            (repo / "docs" / "ARKADE5-CLI.md").write_text("# Arkade\n", encoding="utf-8")
            (repo / "docs" / "README.md").write_text("[Model](NOARK5-STANDARD-VALUES.md)\n", encoding="utf-8")
            (repo / "tests" / "test_contract.py").write_text(
                "DOC_NAME = 'ARKADE5-CLI.md'\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=QA",
                            "-c", "user.email=qa@example.invalid",
                            "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True)
            moves, pins = MODULE.planned_moves(repo)
            self.assertEqual(len(moves), 2)
            self.assertEqual(pins, {"ARKADE5-CLI.md": "tests/test_contract.py"})
            changed = MODULE.apply_moves(repo, moves)
            self.assertGreaterEqual(changed, 2)
            self.assertTrue((repo / "docs" / "history" / "alpha" / "v0.1.5" / "v0.1.5-a1.md").is_file())
            self.assertTrue((repo / "docs" / "reference" / "noark5" / "NOARK5-STANDARD-VALUES.md").is_file())
            contents = (repo / "docs" / "README.md").read_text(encoding="utf-8")
            self.assertIn("reference/noark5/NOARK5-STANDARD-VALUES.md", contents)
            contents = (repo / "docs" / "reference" / "noark5" / "NOARK5-STANDARD-VALUES.md").read_text(encoding="utf-8")
            self.assertIn("../../history/alpha/v0.1.5/v0.1.5-a1.md", contents)
            again, _ = MODULE.planned_moves(repo)
            self.assertEqual(again, [])


if __name__ == "__main__":
    unittest.main()
