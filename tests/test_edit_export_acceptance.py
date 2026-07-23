import unittest

from lectureos.edit_export_acceptance import run_edit_export_acceptance


class EditExportAcceptanceTests(unittest.TestCase):
    def test_edit_export_foundation_acceptance_all_true(self) -> None:
        summary = run_edit_export_acceptance()
        for key, value in summary.items():
            with self.subTest(check=key):
                self.assertTrue(value, f"acceptance check failed: {key}")


if __name__ == "__main__":
    unittest.main()
