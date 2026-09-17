from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]

class A114OperationCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"config"/"operations.json").read_text(encoding="utf-8"))
        cls.ops=cls.data["operations"]

    def test_category_order_is_explicit(self):
        self.assertEqual(list(self.data["display_categories"]), ["Kontroll","Analyse","Resultat","Pakking","Referanse","Avansert"])

    def test_master_path_categories_are_clean(self):
        self.assertEqual((self.ops["validate_xml_schema"]["display_category"],self.ops["validate_xml_schema"]["display_order"]),("Kontroll",1))
        self.assertEqual((self.ops["run_noark5_xpath_tests_2026"]["display_category"],self.ops["run_noark5_xpath_tests_2026"]["display_order"]),("Kontroll",2))
        self.assertEqual((self.ops["metadata_inventory"]["display_category"],self.ops["metadata_inventory"]["display_order"]),("Analyse",1))
        self.assertEqual((self.ops["analyse_arkivstruktur"]["display_category"],self.ops["analyse_arkivstruktur"]["display_order"]),("Analyse",2))

    def test_old_core_analysis_is_not_in_catalogue(self):
        self.assertFalse(self.ops["analyse_noark5_core"]["catalog_visible"])

    def test_u1_is_reference(self):
        self.assertEqual(self.ops["analyse_noark5_u1"]["display_category"],"Referanse")
        self.assertEqual(self.ops["analyse_noark5_u1"]["display_order"],1)

    def test_regression_remains_advanced(self):
        self.assertEqual(self.ops["run_noark5_xpath_regression_2026"]["display_category"],"Avansert")

    def test_gui_numbers_and_sorts_cards(self):
        text=(ROOT/"gui"/"operations_panel.py").read_text(encoding="utf-8")
        self.assertIn("display_order",text)
        self.assertIn("operations.sort(",text)
        self.assertIn('f"{index + 1}. {short_name',text)

if __name__=="__main__": unittest.main()
