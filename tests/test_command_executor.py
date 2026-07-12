import unittest

from core.command_executor import (
    CommandExecutionRequest,
    CommandExecutionStatus,
    CommandExecutor,
)
from core.command_router import CommandRoute, CommandTarget


def make_route(
    target: CommandTarget = CommandTarget.STATUS,
    command_name: str = "/status",
    command_arguments: str = "",
) -> CommandRoute:
    normalized_command = command_name
    if command_arguments:
        normalized_command = f"{command_name} {command_arguments}"

    return CommandRoute(
        target=target,
        command_name=command_name,
        command_arguments=command_arguments,
        normalized_command=normalized_command,
    )


class CommandExecutorTests(unittest.TestCase):
    def test_valid_execution_request(self) -> None:
        route = make_route()
        request = CommandExecutionRequest(route)

        self.assertIs(request.route, route)

    def test_invalid_route_type_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CommandExecutionRequest("/status")

    def test_registered_targets_are_deterministic(self) -> None:
        executor = CommandExecutor(
            {
                CommandTarget.WEB: lambda request: None,
                CommandTarget.ABOUT: lambda request: None,
            }
        )

        self.assertEqual(
            executor.registered_targets(),
            (
                CommandTarget.ABOUT,
                CommandTarget.WEB,
            ),
        )

    def test_known_command_executes_successfully(self) -> None:
        executor = CommandExecutor(
            {
                CommandTarget.STATUS: lambda request: "ready",
            }
        )

        result = executor.execute(
            CommandExecutionRequest(make_route())
        )

        self.assertEqual(
            result.status,
            CommandExecutionStatus.SUCCESS,
        )
        self.assertTrue(result.ok)

    def test_handler_receives_request(self) -> None:
        received = []

        def handler(request: CommandExecutionRequest) -> None:
            received.append(request)

        executor = CommandExecutor(
            {CommandTarget.STATUS: handler}
        )
        request = CommandExecutionRequest(make_route())

        executor.execute(request)

        self.assertEqual(received, [request])

    def test_handler_data_is_returned(self) -> None:
        expected = {"status": "ready"}
        executor = CommandExecutor(
            {
                CommandTarget.STATUS: lambda request: expected,
            }
        )

        result = executor.execute(
            CommandExecutionRequest(make_route())
        )

        self.assertIs(result.data, expected)
        self.assertEqual(result.command_name, "/status")
        self.assertEqual(result.normalized_command, "/status")

    def test_unknown_command_returns_controlled_result(self) -> None:
        route = make_route(
            target=CommandTarget.UNKNOWN,
            command_name="/missing",
        )

        result = CommandExecutor({}).execute(
            CommandExecutionRequest(route)
        )

        self.assertEqual(
            result.status,
            CommandExecutionStatus.UNKNOWN_COMMAND,
        )
        self.assertFalse(result.ok)

    def test_missing_handler_returns_controlled_result(self) -> None:
        result = CommandExecutor({}).execute(
            CommandExecutionRequest(make_route())
        )

        self.assertEqual(
            result.status,
            CommandExecutionStatus.MISSING_HANDLER,
        )

    def test_handler_exception_returns_failed_result(self) -> None:
        def handler(request: CommandExecutionRequest) -> None:
            raise ValueError("handler failure")

        executor = CommandExecutor(
            {CommandTarget.STATUS: handler}
        )

        result = executor.execute(
            CommandExecutionRequest(make_route())
        )

        self.assertEqual(
            result.status,
            CommandExecutionStatus.FAILED,
        )
        self.assertEqual(result.error, "ValueError: handler failure")

    def test_regular_command_keeps_runtime_running(self) -> None:
        executor = CommandExecutor(
            {CommandTarget.STATUS: lambda request: None}
        )

        result = executor.execute(
            CommandExecutionRequest(make_route())
        )

        self.assertTrue(result.keep_running)

    def test_exit_command_stops_runtime(self) -> None:
        route = make_route(
            target=CommandTarget.EXIT,
            command_name="/exit",
        )
        executor = CommandExecutor(
            {CommandTarget.EXIT: lambda request: "bye"}
        )

        result = executor.execute(CommandExecutionRequest(route))

        self.assertTrue(result.ok)
        self.assertFalse(result.keep_running)

    def test_invalid_registry_key_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CommandExecutor({"status": lambda request: None})

    def test_non_callable_handler_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CommandExecutor({CommandTarget.STATUS: None})

    def test_invalid_request_type_is_rejected(self) -> None:
        executor = CommandExecutor({})

        with self.assertRaises(TypeError):
            executor.execute(make_route())


if __name__ == "__main__":
    unittest.main()
