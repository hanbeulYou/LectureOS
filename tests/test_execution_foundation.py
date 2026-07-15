import unittest

from lectureos.execution.identities import (
    DomainResultId,
    FailureId,
    ProcessingRunId,
    ProcessingUnitId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import (
    DomainResultReference,
    ExecutionIntent,
    Failure,
    FailureCategory,
    OutcomeKind,
    ProcessingState,
    ProcessingUnit,
)
from lectureos.execution.service import ExecutionService


class ExecutionFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ExecutionService()
        self.unit = ProcessingUnit(
            identity=ProcessingUnitId("transcript.raw"),
            purpose="produce a raw transcript reference",
            result_kinds=("raw_transcript",),
        )
        self.second_unit = ProcessingUnit(
            identity=ProcessingUnitId("subtitle.candidate"),
            purpose="produce a subtitle candidate reference",
            dependencies=(self.unit.identity,),
            result_kinds=("subtitle_candidate",),
        )
        self.service.register_unit(self.unit)
        self.service.register_unit(self.second_unit)
        self.run_id = ProcessingRunId("run-1")
        self.service.start_run(
            run_id=self.run_id,
            intent=ExecutionIntent("initial processing"),
            working_context=WorkingContextReference("work-1"),
            unit_ids=(self.unit.identity, self.second_unit.identity),
        )

    def test_processing_run_can_be_created(self) -> None:
        run = self.service.get_run(self.run_id)
        self.assertIsNotNone(run)
        self.assertEqual(ProcessingState.PENDING, run.state)

    def test_run_can_reference_multiple_unit_executions(self) -> None:
        self.service.start_unit_execution(
            execution_id=UnitExecutionId("execution-1"),
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        self.service.start_unit_execution(
            execution_id=UnitExecutionId("execution-2"),
            run_id=self.run_id,
            unit_id=self.second_unit.identity,
        )
        run = self.service.get_run(self.run_id)
        self.assertEqual(2, len(run.unit_execution_references))

    def test_unit_definition_and_execution_identities_are_separate(self) -> None:
        execution_id = UnitExecutionId("execution-1")
        self.service.start_unit_execution(
            execution_id=execution_id,
            run_id=self.run_id,
            unit_id=self.unit.identity,
        )
        execution = self.service.get_unit_execution(execution_id)
        self.assertNotEqual(execution.identity.value, execution.unit_id.value)

    def test_success_and_failure_can_coexist_in_one_run(self) -> None:
        successful_id = UnitExecutionId("execution-success")
        failed_id = UnitExecutionId("execution-failure")
        self.service.start_unit_execution(
            execution_id=successful_id, run_id=self.run_id, unit_id=self.unit.identity
        )
        self.service.start_unit_execution(
            execution_id=failed_id, run_id=self.run_id, unit_id=self.second_unit.identity
        )
        result = DomainResultReference(DomainResultId("result-1"), "raw_transcript")
        self.service.record_results(successful_id, (result,))
        failure = Failure(
            identity=FailureId("failure-1"),
            category=FailureCategory.PROCESSING,
            run_id=self.run_id,
            unit_execution_id=failed_id,
            retryable=True,
        )
        self.service.record_failure(failed_id, failure)

        run = self.service.get_run(self.run_id)
        self.assertIn(result.identity, run.result_references)
        self.assertIn(failure.identity, run.failure_references)

    def test_failure_does_not_remove_another_result(self) -> None:
        self.test_success_and_failure_can_coexist_in_one_run()
        self.assertIsNotNone(self.service.get_result_reference(DomainResultId("result-1")))

    def test_retry_creates_a_new_unit_execution(self) -> None:
        failed_id = self._create_failed_execution()
        retry_id = UnitExecutionId("execution-retry")
        self.service.retry_unit_execution(
            execution_id=retry_id,
            failed_execution_id=failed_id,
        )
        retry = self.service.get_unit_execution(retry_id)
        self.assertNotEqual(failed_id, retry.identity)
        self.assertEqual(failed_id, retry.retry_of)

    def test_retry_does_not_rewrite_previous_failure_or_state(self) -> None:
        failed_id = self._create_failed_execution()
        before = self.service.get_unit_execution(failed_id)
        self.service.retry_unit_execution(
            execution_id=UnitExecutionId("execution-retry"),
            failed_execution_id=failed_id,
        )
        after = self.service.get_unit_execution(failed_id)
        self.assertEqual(before, after)
        self.assertEqual(ProcessingState.FAILED, after.state)
        self.assertEqual(OutcomeKind.RECOVERABLE_FAILURE, after.outcome.kind)

    def test_domain_result_identity_is_distinct_from_execution_identities(self) -> None:
        run_id = ProcessingRunId("same-value")
        execution_id = UnitExecutionId("same-value")
        result_id = DomainResultId("same-value")
        self.assertNotEqual(run_id, result_id)
        self.assertNotEqual(execution_id, result_id)

    def test_result_can_exist_without_failure(self) -> None:
        execution_id = UnitExecutionId("execution-1")
        self.service.start_unit_execution(
            execution_id=execution_id, run_id=self.run_id, unit_id=self.unit.identity
        )
        result = DomainResultReference(DomainResultId("result-1"), "raw_transcript")
        self.service.record_results(execution_id, (result,))
        execution = self.service.get_unit_execution(execution_id)
        self.assertEqual((), execution.failure_references)
        self.assertEqual((result.identity,), execution.result_references)

    def test_failure_can_exist_without_domain_result(self) -> None:
        failed_id = self._create_failed_execution()
        execution = self.service.get_unit_execution(failed_id)
        self.assertEqual((), execution.result_references)
        self.assertEqual(1, len(execution.failure_references))

    def test_partial_success_exposes_results_and_failures(self) -> None:
        self.test_success_and_failure_can_coexist_in_one_run()
        run = self.service.get_run(self.run_id)
        self.assertTrue(run.result_references)
        self.assertTrue(run.failure_references)

    def test_processing_boundary_does_not_implement_human_decisions(self) -> None:
        self.assertFalse(hasattr(self.service, "get_decision"))
        self.assertFalse(hasattr(self.service, "accept"))
        self.assertFalse(hasattr(self.service, "reject"))
        self.assertFalse(hasattr(self.service, "modify"))

    def test_completed_execution_rejects_additional_results(self) -> None:
        execution_id = self._create_completed_execution()
        before = self.service.get_unit_execution(execution_id)
        with self.assertRaisesRegex(ValueError, "completed state"):
            self.service.record_results(
                execution_id,
                (DomainResultReference(DomainResultId("result-2"), "raw_transcript"),),
            )
        self.assertEqual(before, self.service.get_unit_execution(execution_id))
        self.assertIsNone(self.service.get_result_reference(DomainResultId("result-2")))

    def test_failed_execution_rejects_results(self) -> None:
        execution_id = self._create_failed_execution()
        before = self.service.get_unit_execution(execution_id)
        with self.assertRaisesRegex(ValueError, "failed state"):
            self.service.record_results(
                execution_id,
                (DomainResultReference(DomainResultId("result-1"), "raw_transcript"),),
            )
        self.assertEqual(before, self.service.get_unit_execution(execution_id))

    def test_cancelled_execution_rejects_results(self) -> None:
        execution_id = self._create_cancelled_execution()
        with self.assertRaisesRegex(ValueError, "cancelled state"):
            self.service.record_results(
                execution_id,
                (DomainResultReference(DomainResultId("result-1"), "raw_transcript"),),
            )

    def test_completed_execution_rejects_failure(self) -> None:
        execution_id = self._create_completed_execution()
        failure = self._failure(execution_id, "late-failure")
        with self.assertRaisesRegex(ValueError, "completed state"):
            self.service.record_failure(execution_id, failure)

    def test_cancelled_execution_rejects_failure(self) -> None:
        execution_id = self._create_cancelled_execution()
        failure = self._failure(execution_id, "late-failure")
        with self.assertRaisesRegex(ValueError, "cancelled state"):
            self.service.record_failure(execution_id, failure)

    def test_completed_execution_cannot_be_cancelled(self) -> None:
        execution_id = self._create_completed_execution()
        with self.assertRaisesRegex(ValueError, "completed state"):
            self.service.cancel_unit_execution(execution_id)

    def test_failed_execution_cannot_be_cancelled(self) -> None:
        execution_id = self._create_failed_execution()
        with self.assertRaisesRegex(ValueError, "failed state"):
            self.service.cancel_unit_execution(execution_id)

    def test_cancelled_execution_cannot_be_cancelled_again(self) -> None:
        execution_id = self._create_cancelled_execution()
        before = self.service.get_unit_execution(execution_id)
        with self.assertRaisesRegex(ValueError, "cancelled state"):
            self.service.cancel_unit_execution(execution_id)
        self.assertEqual(before, self.service.get_unit_execution(execution_id))
        self.assertIsNone(before.outcome)

    def test_non_retryable_failure_cannot_be_retried(self) -> None:
        failed_id = self._create_failed_execution(retryable=False)
        before = self.service.get_unit_execution(failed_id)
        with self.assertRaisesRegex(ValueError, "no retryable failure"):
            self.service.retry_unit_execution(
                execution_id=UnitExecutionId("execution-retry"),
                failed_execution_id=failed_id,
            )
        self.assertEqual(before, self.service.get_unit_execution(failed_id))
        self.assertIsNone(self.service.get_unit_execution(UnitExecutionId("execution-retry")))

    def test_retryable_failure_creates_distinct_execution(self) -> None:
        failed_id = self._create_failed_execution(retryable=True)
        retry_id = UnitExecutionId("execution-retry")
        self.service.retry_unit_execution(
            execution_id=retry_id,
            failed_execution_id=failed_id,
        )
        retry = self.service.get_unit_execution(retry_id)
        self.assertEqual(failed_id, retry.retry_of)
        self.assertEqual(ProcessingState.RUNNING, retry.state)

    def test_rejected_transition_preserves_terminal_execution(self) -> None:
        execution_id = self._create_completed_execution()
        before = self.service.get_unit_execution(execution_id)
        with self.assertRaises(ValueError):
            self.service.record_failure(execution_id, self._failure(execution_id, "rejected"))
        self.assertEqual(before, self.service.get_unit_execution(execution_id))

    def test_rejected_failure_is_not_persisted(self) -> None:
        execution_id = self._create_completed_execution()
        failure = self._failure(execution_id, "rejected")
        with self.assertRaises(ValueError):
            self.service.record_failure(execution_id, failure)
        self.assertIsNone(self.service.get_failure(failure.identity))

    def _create_completed_execution(self) -> UnitExecutionId:
        execution_id = UnitExecutionId("execution-completed")
        self.service.start_unit_execution(
            execution_id=execution_id, run_id=self.run_id, unit_id=self.unit.identity
        )
        self.service.record_results(
            execution_id,
            (DomainResultReference(DomainResultId("result-completed"), "raw_transcript"),),
        )
        return execution_id

    def _create_cancelled_execution(self) -> UnitExecutionId:
        execution_id = UnitExecutionId("execution-cancelled")
        self.service.start_unit_execution(
            execution_id=execution_id, run_id=self.run_id, unit_id=self.unit.identity
        )
        self.service.cancel_unit_execution(execution_id)
        return execution_id

    def _create_failed_execution(self, *, retryable: bool = True) -> UnitExecutionId:
        execution_id = UnitExecutionId("execution-failed")
        self.service.start_unit_execution(
            execution_id=execution_id, run_id=self.run_id, unit_id=self.unit.identity
        )
        self.service.record_failure(
            execution_id,
            Failure(
                identity=FailureId("failure-1"),
                category=FailureCategory.PROCESSING,
                run_id=self.run_id,
                unit_execution_id=execution_id,
                retryable=retryable,
            ),
        )
        return execution_id

    def _failure(self, execution_id: UnitExecutionId, identity: str) -> Failure:
        return Failure(
            identity=FailureId(identity),
            category=FailureCategory.PROCESSING,
            run_id=self.run_id,
            unit_execution_id=execution_id,
            retryable=True,
        )


if __name__ == "__main__":
    unittest.main()
