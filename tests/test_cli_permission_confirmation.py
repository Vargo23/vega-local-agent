import unittest
from unittest.mock import Mock
from unittest.mock import patch

from core import command_handler
from core.tool_confirmation import ToolConfirmationManager
from core.tool_executor import ToolExecutionResult, ToolExecutionStatus, ToolExecutor
from permissions import (
    PermissionCapability,
    PermissionEffect,
    PermissionEvaluator,
    PermissionPolicy,
    PermissionRisk,
    PermissionRule,
)


def terminal_executor(calls):
    def terminal_run(command_id, project_root=None):
        calls.append((command_id, project_root))
        return {
            "ok": True,
            "error": "",
            "data": {
                "command_id": command_id,
                "returncode": 0,
                "duration_ms": 1,
                "stdout": "done",
                "stderr": "",
            },
        }

    rule = PermissionRule(
        "terminal_run",
        (PermissionCapability.PROCESS_EXECUTE,),
        PermissionRisk.HIGH,
        PermissionEffect.CONFIRM,
        False,
        "Runs a configured command.",
    )
    policy = PermissionPolicy(
        1,
        PermissionEffect.DENY,
        "CONFIRM",
        10,
        (rule,),
    )
    return ToolExecutor(
        {"terminal_run": terminal_run},
        PermissionEvaluator(policy),
    )


class CliPermissionConfirmationTests(unittest.TestCase):
    def test_explicit_approval_executes_once(self):
        calls = []
        callback = Mock(return_value="yes")
        output = command_handler.handle_terminal_command(
            "/run tests",
            "workspace",
            tool_executor=terminal_executor(calls),
            tool_confirmation_manager=ToolConfirmationManager(callback),
        )
        self.assertEqual(calls, [("tests", "workspace")])
        self.assertIn("Status: PASS", output)
        callback.assert_called_once()

    def test_rejection_does_not_execute(self):
        calls = []
        output = command_handler.handle_terminal_command(
            "/run tests",
            "workspace",
            tool_executor=terminal_executor(calls),
            tool_confirmation_manager=ToolConfirmationManager(lambda prompt: "no"),
        )
        self.assertEqual(calls, [])
        self.assertIn("rejected or cancelled", output)

    def test_noninteractive_execution_stays_blocked(self):
        calls = []
        output = command_handler.handle_terminal_command(
            "/run tests",
            "workspace",
            tool_executor=terminal_executor(calls),
        )
        self.assertEqual(calls, [])
        self.assertIn("requires explicit confirmation", output)

    def test_every_confirm_classified_cli_path_uses_shared_flow(self):
        executor = ToolExecutor({})
        manager = ToolConfirmationManager(lambda prompt: "no")
        cases = (
            ("memory_add", command_handler.handle_memory_command, ("/memory add fact value", None, executor, manager)),
            ("propose_patch_from_file", command_handler.handle_patch_command, ("/patch propose a.txt b.txt", None, executor, manager)),
            ("apply_patch", command_handler.handle_patch_command, ("/patch apply patch-1", None, executor, manager)),
            ("rollback_patch", command_handler.handle_patch_command, ("/patch rollback patch-1", None, executor, manager)),
            ("documentation_build", command_handler.handle_docgen_command, ("/docgen build", None, executor, manager)),
            ("internet_set", command_handler.handle_internet_command, ("/internet on", executor, manager)),
            ("release_check", command_handler.handle_release_command, ("/release check", None, executor, manager)),
            ("terminal_run", command_handler.handle_terminal_command, ("/run tests", None, executor, manager)),
            ("test_run", command_handler.handle_test_command, ("/test all", None, executor, manager)),
            ("web_fetch", command_handler.handle_web_command, ("/web fetch https://example.com", None, executor, manager)),
        )
        rejected = ToolExecutionResult(
            ToolExecutionStatus.FAILED,
            "tool",
            error="rejected",
            error_code="confirmation_rejected",
        )
        for expected_name, handler, arguments in cases:
            with self.subTest(tool=expected_name), patch(
                "core.command_handler.execute_tool_with_confirmation",
                return_value=rejected,
            ) as execute:
                handler(*arguments)
                self.assertEqual(execute.call_args.args[1].tool_name, expected_name)
                execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
