import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.command_handler import handle_workflow_command
from core.command_router import CommandRouter, CommandTarget
from core.intent_router import IntentRouter
from workflows.checkpoint_store import CheckpointStore
from workflows.models import WorkflowRun, WorkflowStatus
from workflows.recovery_manager import (
    RecoveryConflictError, RecoveryStorageError,
)
from workflows.recovery_models import (
    RecoveryDiagnosis, RecoveryResult, RecoveryState, RecoveryValidationError,
)


WORKFLOW_ID = "workflow-11111111111111111111111111111111"
CHECKPOINT_ID = "checkpoint-22222222222222222222222222222222"


class RecordingRecoveryManager:
    def __init__(self, diagnosis=None, result=None, checkpoints=None, error=None):
        self.diagnosis = diagnosis or RecoveryDiagnosis(RecoveryState.MISSING_ACTIVE_STATE)
        self.result = result
        self.checkpoints = list(checkpoints or [])
        self.error = error
        self.diagnose_calls = []
        self.recover_calls = []

    def diagnose(self, workflow_id=None):
        self.diagnose_calls.append(workflow_id)
        if self.error: raise self.error
        return self.diagnosis

    def _active_checkpoints(self):
        if self.error: raise self.error
        return list(self.checkpoints)

    def recover(self, checkpoint_id, token):
        self.recover_calls.append((checkpoint_id, token))
        if self.error: raise self.error
        return self.result


class WorkflowCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        shutil.copy(
            Path(__file__).parents[1] / "config" / "checkpoint_policy.json",
            self.root / "config" / "checkpoint_policy.json",
        )

    def test_intent_and_command_routing(self):
        intent = IntentRouter().route('/workflow start feature "Add command"')
        route = CommandRouter().route(intent)
        self.assertEqual(route.target, CommandTarget.WORKFLOW)

    def test_list_command(self):
        result = handle_workflow_command("/workflow list", self.root)
        self.assertIn("feature", result)
        self.assertIn("bugfix", result)
        self.assertIn("refactor", result)

    def test_start_status_cancel_commands(self):
        result = handle_workflow_command('/workflow start feature "Add command"', self.root)
        self.assertIn("waiting_patch", result)
        self.assertIn("waiting_patch", handle_workflow_command("/workflow status", self.root))
        self.assertIn("cancelled", handle_workflow_command("/workflow cancel", self.root))

    def test_existing_command_remains_compatible(self):
        route = CommandRouter().route(IntentRouter().route("/status"))
        self.assertEqual(route.target, CommandTarget.STATUS)

    def test_recovery_status_without_workflow_id(self):
        manager = RecordingRecoveryManager()
        output = handle_workflow_command("/workflow recovery-status", self.root, recovery_manager=manager)
        self.assertIn("missing_active_state", output); self.assertEqual(manager.diagnose_calls, [None])

    def test_recovery_status_with_workflow_id(self):
        manager = RecordingRecoveryManager()
        handle_workflow_command(f"/workflow recovery-status {WORKFLOW_ID}", self.root, recovery_manager=manager)
        self.assertEqual(manager.diagnose_calls, [WORKFLOW_ID])

    def test_healthy_diagnosis_output(self):
        diagnosis = RecoveryDiagnosis(RecoveryState.HEALTHY, WORKFLOW_ID, f"{WORKFLOW_ID}.json", True)
        output = handle_workflow_command("/workflow recovery-status", self.root,
                                         recovery_manager=RecordingRecoveryManager(diagnosis))
        self.assertIn("Active state valid: true", output); self.assertIn("Recovery is not required", output)

    def test_recoverable_diagnosis_prints_exact_command(self):
        diagnosis = RecoveryDiagnosis(RecoveryState.RECOVERABLE, WORKFLOW_ID, None, False,
            CHECKPOINT_ID, 1, "workflow_started", WorkflowStatus.CREATED, True, True, [])
        output = handle_workflow_command("/workflow recovery-status", self.root,
                                         recovery_manager=RecordingRecoveryManager(diagnosis))
        self.assertIn(f"/workflow recover {CHECKPOINT_ID} CONFIRM", output)

    def test_ambiguous_diagnosis_refuses_selection(self):
        diagnosis = RecoveryDiagnosis(RecoveryState.MULTIPLE_CHECKPOINT_WORKFLOWS)
        output = handle_workflow_command("/workflow recovery-status", self.root,
                                         recovery_manager=RecordingRecoveryManager(diagnosis))
        self.assertIn("Automatic selection was refused", output); self.assertNotIn("/workflow recover checkpoint-", output)

    def test_recovery_status_rejects_extra_arguments_without_call(self):
        manager = RecordingRecoveryManager()
        output = handle_workflow_command("/workflow recovery-status one two", self.root, recovery_manager=manager)
        self.assertIn("Usage:", output); self.assertEqual(manager.diagnose_calls, [])

    def test_recovery_status_does_not_construct_or_call_engine(self):
        manager = RecordingRecoveryManager()
        with patch("workflows.WorkflowEngine") as engine:
            handle_workflow_command("/workflow recovery-status", self.root, recovery_manager=manager)
        engine.assert_not_called()

    def _create_checkpoints(self):
        store = CheckpointStore(self.root)
        first = WorkflowRun.create("feature", "First", []); first.workflow_id = WORKFLOW_ID
        one = store.create(first, "workflow_started")
        second = WorkflowRun.create("feature", "Second", [])
        two = store.create(second, "workflow_started")
        return store, one, two

    def test_checkpoints_lists_active_verified_metadata(self):
        _, first, _ = self._create_checkpoints()
        output = handle_workflow_command("/workflow checkpoints", self.root)
        self.assertIn(first.checkpoint_id, output); self.assertIn("workflow_started", output)
        self.assertIn("created", output); self.assertIn(first.created_at, output)

    def test_checkpoints_filters_by_workflow_id(self):
        _, first, second = self._create_checkpoints()
        output = handle_workflow_command(f"/workflow checkpoints {WORKFLOW_ID}", self.root)
        self.assertIn(first.checkpoint_id, output); self.assertNotIn(second.checkpoint_id, output)

    def test_checkpoint_listing_is_deterministic_and_grouped(self):
        _, first, second = self._create_checkpoints()
        output = handle_workflow_command("/workflow checkpoints", self.root)
        expected = sorted([(first.workflow_id, first.checkpoint_id), (second.workflow_id, second.checkpoint_id)])
        self.assertLess(output.index(expected[0][1]), output.index(expected[1][1])); self.assertIn("Workflow ", output)

    def test_checkpoint_payload_and_hash_are_not_printed(self):
        _, first, _ = self._create_checkpoints()
        output = handle_workflow_command("/workflow checkpoints", self.root)
        self.assertNotIn(first.workflow_payload["task"], output); self.assertNotIn(first.payload_sha256, output)

    def test_history_checkpoints_are_not_listed(self):
        store, first, second = self._create_checkpoints(); store.archive_workflow(first.workflow_id)
        output = handle_workflow_command("/workflow checkpoints", self.root)
        self.assertNotIn(first.checkpoint_id, output); self.assertIn(second.checkpoint_id, output)

    def test_corrupt_active_checkpoint_listing_fails_closed(self):
        store, first, _ = self._create_checkpoints()
        (store.active_dir / f"{first.checkpoint_id}.json").write_text("{}")
        output = handle_workflow_command("/workflow checkpoints", self.root)
        self.assertIn("storage error", output); self.assertNotIn("Active workflow checkpoints:", output)

    def test_checkpoints_rejects_extra_arguments(self):
        output = handle_workflow_command("/workflow checkpoints one two", self.root,
                                         recovery_manager=RecordingRecoveryManager())
        self.assertIn("Usage:", output)

    def _result(self, *, recovered=True, already=False, quarantine=None):
        return RecoveryResult(WORKFLOW_ID, CHECKPOINT_ID, WorkflowStatus.CREATED,
                              f"{WORKFLOW_ID}.json", quarantine, recovered, already, True, [])

    def test_recover_requires_checkpoint_id(self):
        output = handle_workflow_command("/workflow recover", self.root,
                                         recovery_manager=RecordingRecoveryManager())
        self.assertIn("Usage:", output)

    def test_recover_requires_exact_uppercase_confirm(self):
        manager = RecordingRecoveryManager(result=self._result())
        for token in ("confirm", "Confirm", "yes", "true", "1"):
            with self.subTest(token=token):
                output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} {token}", self.root,
                                                 recovery_manager=manager)
                self.assertIn("exact confirmation token CONFIRM", output)
        self.assertEqual(manager.recover_calls, [])

    def test_recover_rejects_extra_arguments(self):
        output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM extra", self.root,
                                         recovery_manager=RecordingRecoveryManager())
        self.assertIn("Usage:", output)

    def test_recovery_success_output_and_exact_call(self):
        manager = RecordingRecoveryManager(result=self._result())
        output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM", self.root,
                                         recovery_manager=manager)
        self.assertEqual(manager.recover_calls, [(CHECKPOINT_ID, "CONFIRM")])
        self.assertIn(f"Workflow ID: {WORKFLOW_ID}", output); self.assertIn("Recovered: true", output)
        self.assertIn("Workflow execution has not resumed", output); self.assertIn("Run /workflow resume separately", output)

    def test_idempotent_recovery_is_distinct(self):
        output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM", self.root,
            recovery_manager=RecordingRecoveryManager(result=self._result(recovered=False, already=True)))
        self.assertIn("Recovered: false", output); self.assertIn("Already recovered: true", output)

    def test_quarantine_output_is_filename_only(self):
        name = f"{WORKFLOW_ID}.corrupt.{'3' * 32}.json"
        output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM", self.root,
            recovery_manager=RecordingRecoveryManager(result=self._result(quarantine=name)))
        self.assertIn(f"Quarantine filename: {name}", output); self.assertNotIn(str(self.root), output)

    def test_recovery_failure_is_not_success(self):
        output = handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM", self.root,
            recovery_manager=RecordingRecoveryManager(error=RecoveryStorageError("write failed")))
        self.assertIn("storage error", output); self.assertNotIn("State restoration is complete", output)

    def test_recovery_domain_errors_are_mapped(self):
        cases = ((RecoveryConflictError("blocked"), "conflict"),
                 (RecoveryStorageError("broken"), "storage error"),
                 (RecoveryValidationError("invalid"), "validation error"))
        for error, expected in cases:
            with self.subTest(error=error):
                output = handle_workflow_command("/workflow recovery-status", self.root,
                    recovery_manager=RecordingRecoveryManager(error=error))
                self.assertIn(expected, output); self.assertNotIn("Traceback", output)

    def test_recovery_commands_do_not_call_resume_or_side_effect_apis(self):
        manager = RecordingRecoveryManager(result=self._result())
        with patch("workflows.engine.WorkflowEngine.resume") as resume, \
             patch("workflows.engine.WorkflowEngine.confirm") as confirm, \
             patch("core.command_handler.apply_patch") as apply, \
             patch("tools.test_tools.run_test_group") as tests, \
             patch("review.review_pipeline.ReviewPipeline.run") as review, \
             patch("core.tool_executor.ToolExecutor.execute_named") as tool, \
             patch("tools.terminal_tools.run_allowed_command") as terminal, \
             patch("os.system") as system, patch("subprocess.run") as subprocess_run:
            handle_workflow_command(f"/workflow recover {CHECKPOINT_ID} CONFIRM", self.root,
                                    recovery_manager=manager)
        for operation in (resume, confirm, apply, tests, review, tool, terminal, system, subprocess_run):
            operation.assert_not_called()

    def test_existing_confirm_command_still_calls_engine_confirm(self):
        run = WorkflowRun.create("feature", "Confirm", []); engine = Mock(); engine.confirm.return_value = run
        output = handle_workflow_command("/workflow confirm", self.root, engine=engine)
        engine.confirm.assert_called_once_with(); self.assertIn(run.workflow_id, output)

    def test_existing_resume_command_still_calls_engine_resume(self):
        run = WorkflowRun.create("feature", "Resume", []); engine = Mock(); engine.resume.return_value = run
        output = handle_workflow_command("/workflow resume", self.root, engine=engine)
        engine.resume.assert_called_once_with(); self.assertIn(run.workflow_id, output)

    def test_unknown_workflow_subcommand_keeps_help_convention(self):
        self.assertEqual(handle_workflow_command("/workflow unknown", self.root), handle_workflow_command("/workflow", self.root))


if __name__ == "__main__":
    unittest.main()
