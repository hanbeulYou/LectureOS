import unittest

from lectureos.edit_export_cli_acceptance import run_edit_export_cli_acceptance


class EditExportCliAcceptanceTests(unittest.TestCase):
    def test_first_runnable_edit_export_slice_all_true(self) -> None:
        summary = run_edit_export_cli_acceptance()
        for key, value in summary.items():
            with self.subTest(check=key):
                self.assertTrue(value, f"acceptance check failed: {key}")


if __name__ == "__main__":
    unittest.main()
