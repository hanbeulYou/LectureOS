import unittest

from lectureos.repository_validation_acceptance import (
    run_repository_validation_acceptance,
)


class RepositoryValidationAcceptanceTests(unittest.TestCase):
    def test_repository_validation_acceptance_all_true(self) -> None:
        summary = run_repository_validation_acceptance()
        for key, value in summary.items():
            with self.subTest(check=key):
                self.assertTrue(value, f"acceptance check failed: {key}")


if __name__ == "__main__":
    unittest.main()
