import unittest
from unittest.mock import patch

from core.tool_executor import (
    ToolExecutionStatus,
    ToolExecutor,
    ToolRequest,
)
from permissions import (
    PermissionCapability,
    PermissionEffect,
    PermissionEvaluator,
    PermissionPolicy,
    PermissionRisk,
    PermissionRule,
)


def add_values(left: int, right: int) -> int:
    return left + right


def fail_tool() -> None:
    raise RuntimeError("controlled failure")


def evaluator_for(effect, name="sample"):
    rule = PermissionRule(
        name,
        (PermissionCapability.PROJECT_READ,),
        PermissionRisk.LOW,
        effect,
        False,
        "Test rule.",
    )
    policy = PermissionPolicy(
        1,
        PermissionEffect.DENY,
        "CONFIRM",
        10,
        (rule,),
    )
    return PermissionEvaluator(policy)


class UninspectableTool:
    def __init__(self) -> None:
        self.called = False

    @property
    def __signature__(self):
        raise ValueError("signature unavailable")

    def __call__(self) -> None:
        self.called = True


class ToolExecutorTests(unittest.TestCase):
    def test_allow_invokes_callable(self) -> None:
        calls = []
        executor = ToolExecutor(
            {"sample": lambda: calls.append(True)},
            evaluator_for(PermissionEffect.ALLOW),
        )
        self.assertTrue(executor.execute_named("sample").ok)
        self.assertEqual(calls, [True])

    def test_deny_never_invokes_callable(self) -> None:
        calls = []
        executor = ToolExecutor(
            {"sample": lambda: calls.append(True)},
            evaluator_for(PermissionEffect.DENY),
        )
        result = executor.execute_named("sample")
        self.assertEqual(result.error_code, "permission_denied")
        self.assertEqual(calls, [])

    def test_confirm_without_or_with_bad_token_never_invokes(self) -> None:
        calls = []
        executor = ToolExecutor(
            {"sample": lambda: calls.append(True)},
            evaluator_for(PermissionEffect.CONFIRM),
        )
        for token in (None, "confirm", "CONFIRM "):
            with self.subTest(token=token):
                result = executor.execute_named("sample", confirmation_token=token)
                self.assertEqual(result.error_code, "confirmation_required")
        self.assertEqual(calls, [])

    def test_exact_confirmation_invokes_once_and_is_not_forwarded(self) -> None:
        calls = []
        executor = ToolExecutor(
            {"sample": lambda: calls.append(True)},
            evaluator_for(PermissionEffect.CONFIRM),
        )
        self.assertTrue(executor.execute_named("sample", confirmation_token="CONFIRM").ok)
        self.assertEqual(calls, [True])
        self.assertEqual(executor.execute_named("sample").error_code, "confirmation_required")
        self.assertEqual(calls, [True])

    def test_direct_execute_cannot_bypass_permissions(self) -> None:
        calls = []
        executor = ToolExecutor(
            {"sample": lambda: calls.append(True)},
            evaluator_for(PermissionEffect.DENY),
        )
        self.assertEqual(executor.execute(ToolRequest("sample")).error_code, "permission_denied")
        self.assertEqual(calls, [])

    def test_missing_rule_and_evaluator_exception_fail_closed(self) -> None:
        calls = []
        evaluator = evaluator_for(PermissionEffect.ALLOW, "other")
        executor = ToolExecutor({"sample": lambda: calls.append(True)}, evaluator)
        self.assertEqual(executor.execute_named("sample").error_code, "permission_policy_error")
        with patch.object(evaluator, "evaluate", side_effect=RuntimeError("broken")):
            self.assertEqual(executor.execute_named("sample").error_code, "permission_policy_error")
        self.assertEqual(calls, [])

    def test_unknown_tool_result_precedes_permission_check(self) -> None:
        evaluator = evaluator_for(PermissionEffect.ALLOW)
        with patch.object(evaluator, "evaluate", side_effect=AssertionError("called")):
            result = ToolExecutor({}, evaluator).execute_named("missing")
            self.assertIs(result.status, ToolExecutionStatus.UNKNOWN_TOOL)

    def test_partial_registry_without_evaluator_preserves_behavior(self) -> None:
        self.assertTrue(ToolExecutor({"custom": lambda: 1}).execute_named("custom").ok)

    def test_valid_request_is_normalized(self) -> None:
        request = ToolRequest(
            "  add  ",
            {
                "left": 2,
                "right": 3,
            },
        )

        self.assertEqual(request.tool_name, "add")
        self.assertEqual(
            request.arguments,
            {
                "left": 2,
                "right": 3,
            },
        )

    def test_empty_tool_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ToolRequest("   ")

    def test_invalid_arguments_type_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ToolRequest("add", [])

    def test_request_copies_arguments(self) -> None:
        arguments = {"left": 2}
        request = ToolRequest("add", arguments)

        arguments["left"] = 99

        self.assertEqual(request.arguments, {"left": 2})

    def test_registered_tools_are_sorted(self) -> None:
        executor = ToolExecutor(
            {
                "zeta": fail_tool,
                "alpha": add_values,
            }
        )

        self.assertEqual(
            executor.registered_tools(),
            ("alpha", "zeta"),
        )

    def test_successful_tool_execution(self) -> None:
        executor = ToolExecutor({"add": add_values})

        result = executor.execute(
            ToolRequest(
                "add",
                {
                    "left": 4,
                    "right": 5,
                },
            )
        )

        self.assertEqual(result.status, ToolExecutionStatus.SUCCESS)
        self.assertTrue(result.ok)
        self.assertEqual(result.data, 9)
        self.assertEqual(result.error, "")

    def test_execute_named_builds_request(self) -> None:
        executor = ToolExecutor({"add": add_values})

        result = executor.execute_named(
            "add",
            left=7,
            right=8,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data, 15)

    def test_unknown_tool_returns_controlled_result(self) -> None:
        result = ToolExecutor({}).execute(
            ToolRequest("missing")
        )

        self.assertEqual(
            result.status,
            ToolExecutionStatus.UNKNOWN_TOOL,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.tool_name, "missing")

    def test_missing_required_argument_is_rejected(self) -> None:
        executor = ToolExecutor({"add": add_values})

        result = executor.execute_named(
            "add",
            left=1,
        )

        self.assertEqual(
            result.status,
            ToolExecutionStatus.INVALID_ARGUMENTS,
        )
        self.assertIn("TypeError:", result.error)

    def test_extra_argument_is_rejected(self) -> None:
        executor = ToolExecutor({"add": add_values})

        result = executor.execute_named(
            "add",
            left=1,
            right=2,
            extra=3,
        )

        self.assertEqual(
            result.status,
            ToolExecutionStatus.INVALID_ARGUMENTS,
        )

    def test_tool_exception_returns_failed_result(self) -> None:
        executor = ToolExecutor({"fail": fail_tool})

        result = executor.execute_named("fail")

        self.assertEqual(result.status, ToolExecutionStatus.FAILED)
        self.assertEqual(
            result.error,
            "RuntimeError: controlled failure",
        )

    def test_non_callable_registry_value_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ToolExecutor({"invalid": None})

    def test_duplicate_normalized_tool_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ToolExecutor(
                {
                    "echo": add_values,
                    " echo ": fail_tool,
                }
            )

    def test_signature_inspection_failure_does_not_call_tool(self) -> None:
        tool = UninspectableTool()
        executor = ToolExecutor({"uninspectable": tool})

        result = executor.execute_named("uninspectable")

        self.assertEqual(result.status, ToolExecutionStatus.FAILED)
        self.assertFalse(result.ok)
        self.assertFalse(tool.called)
        self.assertIn("ValueError", result.error)

    def test_invalid_request_type_is_rejected(self) -> None:
        executor = ToolExecutor({})

        with self.assertRaises(TypeError):
            executor.execute("missing")

    def test_input_registry_is_not_modified(self) -> None:
        registry = {"add": add_values}
        expected = dict(registry)

        executor = ToolExecutor(registry)
        registry["fail"] = fail_tool

        self.assertEqual(
            executor.registered_tools(),
            ("add",),
        )
        self.assertEqual(expected, {"add": add_values})


if __name__ == "__main__":
    unittest.main()
