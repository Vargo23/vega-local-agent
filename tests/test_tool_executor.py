import unittest

from core.tool_executor import (
    ToolExecutionStatus,
    ToolExecutor,
    ToolRequest,
)


def add_values(left: int, right: int) -> int:
    return left + right


def fail_tool() -> None:
    raise RuntimeError("controlled failure")


class UninspectableTool:
    def __init__(self) -> None:
        self.called = False

    @property
    def __signature__(self):
        raise ValueError("signature unavailable")

    def __call__(self) -> None:
        self.called = True


class ToolExecutorTests(unittest.TestCase):
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
