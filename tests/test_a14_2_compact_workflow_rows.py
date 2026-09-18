from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = (ROOT / "gui" / "workflow_panel.py").read_text(encoding="utf-8")


class A142CompactWorkflowRowsTests(unittest.TestCase):
    def test_status_is_compact_icon_not_second_text_row(self):
        self.assertIn("status_icon = ctk.CTkLabel", PANEL)
        self.assertIn("corner_radius=12", PANEL)
        self.assertNotIn('text="[FORELDET]"', PANEL)
        self.assertNotIn('actions.grid(row=1', PANEL)

    def test_operation_and_actions_share_single_row(self):
        self.assertIn('item.grid_columnconfigure(1, weight=1)', PANEL)
        self.assertIn('status_icon.grid(row=0', PANEL)
        self.assertIn('up.grid(row=0', PANEL)
        self.assertIn('down.grid(row=0', PANEL)

    def test_regenerate_action_has_own_full_width_row(self):
        self.assertIn('self.regenerate_stale_button.grid(row=3, column=0', PANEL)
        self.assertIn('sticky="ew"', PANEL)

    def test_existing_stale_provider_and_action_contract_remain(self):
        self.assertIn('stale_ids_provider', PANEL)
        self.assertIn('on_regenerate_stale', PANEL)
        self.assertIn('Regenerer foreldede', PANEL)

    def test_existing_tooltip_cleanup_contract_remains(self):
        self.assertIn('for tooltip in self._tooltips: tooltip._hide()', PANEL)


if __name__ == "__main__":
    unittest.main()
