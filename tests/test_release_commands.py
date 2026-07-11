import unittest
from pathlib import Path
from unittest.mock import patch

from core.command_handler import handle_release_command


class ReleaseCommandTests(unittest.TestCase):
    def test_release_help(self) -> None:
        output = handle_release_command("/release", Path("."))

        self.assertIn("/release status", output)
        self.assertIn("/release check", output)
        self.assertIn("/release notes", output)
        self.assertIn("read-only", output)

    @patch("core.command_handler.get_release_status")
    def test_release_status(self, mocked_status) -> None:
        mocked_status.return_value = {
            "ok": True,
            "error": None,
            "data": {
                "version": "v1.12.0",
                "version_valid": True,
                "branch": "feature/v1.12-release-manager",
                "branch_allowed": True,
                "publish_branch": "main",
                "publish_branch_match": False,
                "git_clean": False,
                "required_files": [],
                "missing_files": [],
                "documentation_passed": True,
                "documentation": {},
                "preparation_ready": False,
                "publish_ready": False,
                "issues": [
                    "Git working tree is not clean.",
                ],
            },
        }

        output = handle_release_command(
            "/release status",
            Path("."),
        )

        self.assertIn("Release status", output)
        self.assertIn("v1.12.0", output)
        self.assertIn(
            "Git working tree is not clean.",
            output,
        )

    @patch("core.command_handler.run_release_check")
    def test_release_check(self, mocked_check) -> None:
        mocked_check.return_value = {
            "ok": True,
            "error": None,
            "data": {
                "status": {
                    "version": "v1.12.0",
                    "branch": "main",
                    "issues": [],
                },
                "commands": [
                    {
                        "command_id": "tests",
                        "passed": True,
                        "returncode": 0,
                        "duration_ms": 10,
                        "error": None,
                    },
                ],
                "commands_passed": True,
                "passed": True,
                "publish_ready": True,
            },
        }

        output = handle_release_command(
            "/release check",
            Path("."),
        )

        self.assertIn("Release check: PASS", output)
        self.assertIn("[PASS] tests", output)

    @patch("core.command_handler.build_release_notes")
    def test_release_notes(self, mocked_notes) -> None:
        mocked_notes.return_value = {
            "ok": True,
            "error": None,
            "data": {
                "version": "v1.12.0",
                "source": "CHANGELOG.md",
                "suggested_path": "docs/releases/v1.12.0.md",
                "draft": "# VEGA v1.12.0 Release Notes",
                "written": False,
            },
        }

        output = handle_release_command(
            "/release notes",
            Path("."),
        )

        self.assertIn("Release notes draft", output)
        self.assertIn(
            "docs/releases/v1.12.0.md",
            output,
        )
        self.assertIn(
            "# VEGA v1.12.0 Release Notes",
            output,
        )

    def test_unknown_release_command_returns_help(self) -> None:
        output = handle_release_command(
            "/release publish",
            Path("."),
        )

        self.assertIn("/release status", output)
        self.assertNotIn("published successfully", output.lower())


if __name__ == "__main__":
    unittest.main()
