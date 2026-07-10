import unittest
from pathlib import Path
from unittest.mock import patch

from core.command_handler import handle_terminal_command


class TerminalCommandHandlerTests(unittest.TestCase):
    def test_run_list(self):
        project_root = Path(__file__).resolve().parents[1]
        output = handle_terminal_command("/run list", project_root)
        self.assertIn("Allowed terminal commands:", output)
        self.assertIn("python-version", output)
        self.assertIn("identity", output)

    @patch("tools.terminal_tools.run_allowed_command")
    def test_unknown_run_command(self, run_allowed_command):
        run_allowed_command.return_value = {
            "ok": False,
            "error": "Unknown command id: unknown",
            "data": None,
        }
        output = handle_terminal_command("/run unknown")
        self.assertIn("Unknown command id: unknown", output)
        self.assertIn("/run list", output)

    @patch("tools.terminal_tools.run_allowed_command")
    def test_user_arguments_are_rejected_without_execution(self, run_allowed_command):
        for command in ("/run tests extra", "/run tests -k sample", "/run tests && calc"):
            with self.subTest(command=command):
                output = handle_terminal_command(command)
                self.assertIn("Exactly one command id", output)
        run_allowed_command.assert_not_called()

    @patch("tools.terminal_tools.run_allowed_command")
    def test_success_result_is_formatted(self, run_allowed_command):
        run_allowed_command.return_value = {
            "ok": True,
            "error": None,
            "data": {
                "command_id": "tests",
                "stdout": "OK\n",
                "stderr": "",
                "returncode": 0,
                "duration_ms": 15,
                "warning": None,
            },
        }
        output = handle_terminal_command("/run tests")
        self.assertIn("Status: PASS", output)
        self.assertIn("Exit code: 0", output)


if __name__ == "__main__":
    unittest.main()
