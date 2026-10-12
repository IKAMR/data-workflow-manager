import unittest
from app.analysis_resources_a15 import resource_plan, validate_resource_settings


class A15ResourceTests(unittest.TestCase):
    def test_automatic_small_laptop_safe(self):
        plan = resource_plan({}, cpu_count=4, memory_gib=8)
        self.assertEqual((plan.xpath_workers, plan.document_workers, plan.parallel_jobs), (1, 1, 1))

    def test_automatic_large_laptop_safe(self):
        plan = resource_plan({}, cpu_count=16, memory_gib=64)
        self.assertEqual((plan.xpath_workers, plan.document_workers), (1, 1))

    def test_explicit_workers(self):
        plan = resource_plan({'noark5_xpath_workers': 4, 'document_analysis_workers': 2}, cpu_count=8, memory_gib=64)
        self.assertEqual((plan.xpath_workers, plan.document_workers), (4, 2))

    def test_cap_by_cpu(self):
        plan = resource_plan({'noark5_xpath_workers': 8}, cpu_count=2, memory_gib=8)
        self.assertEqual(plan.xpath_workers, 2)

    def test_bad_values_rejected(self):
        for bad in ('hey', '-1', '100'):
            with self.assertRaises(ValueError):
                validate_resource_settings({'noark5_xpath_workers': bad, 'document_analysis_workers': 0, 'xpath_timeout_minutes': 0, 'document_timeout_minutes': 0})

    def test_unlimited_time_default(self):
        plan = resource_plan({}, cpu_count=4, memory_gib=8)
        self.assertEqual((plan.xpath_timeout_minutes, plan.document_timeout_minutes), (0, 0))


if __name__ == '__main__':
    unittest.main()
