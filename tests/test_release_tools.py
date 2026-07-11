import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.git_tools import GitCommandResult
from tools.release_tools import (
    build_release_notes,
    get_release_status,
    load_release_policy,
    run_release_check,
)


class ReleaseToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

        for directory in (
            "config",
            "scripts",
            "docs",
        ):
            (self.root / directory).mkdir(
                parents=True,
                exist_ok=True,
            )

        policy = {
            "schema_version": 1,
            "required_files": [
                "README.md",
                "CHANGELOG.md",
                "scripts/version.py",
                "docs/architecture.md",
                "docs/commands.md",
                "docs/security.md",
                "config/release_policy.json",
            ],
            "branch_policy": {
                "allowed_check_branches": ["main"],
                "allowed_check_prefixes": ["feature/v"],
                "publish_branch": "main",
            },
            "checks": {
                "documentation": True,
                "commands": [
                    "identity",
                    "compile",
                    "tests",
                ],
            },
            "notes": {
                "source": "CHANGELOG.md",
                "output_dir": "docs/releases",
                "max_chars": 20000,
            },
            "publishing": {
                "allow_commit": False,
                "allow_tag": False,
                "allow_push": False,
                "allow_github_release": False,
            },
        }

        (self.root / "config" / "release_policy.json").write_text(
            json.dumps(policy),
            encoding="utf-8",
        )
        (self.root / "scripts" / "version.py").write_text(
            'VERSION = "v1.12.0"\n',
            encoding="utf-8",
        )
        (self.root / "README.md").write_text(
            "# VEGA\n",
            encoding="utf-8",
        )
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## v1.12.0 - Release Manager\n\n"
            "Added:\n\n"
            "* Release checks.\n\n"
            "## v1.11.0 - Agent Modes\n",
            encoding="utf-8",
        )

        for filename in (
            "architecture.md",
            "commands.md",
            "security.md",
        ):
            (self.root / "docs" / filename).write_text(
                "v1.12.0\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _git_result(
        self,
        *arguments: str,
        stdout: str = "",
    ) -> GitCommandResult:
        return GitCommandResult(
            ok=True,
            command=("git", *arguments),
            stdout=stdout,
            stderr="",
            returncode=0,
        )

    def test_policy_loads(self) -> None:
        result = load_release_policy(self.root)

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["data"]["policy"]["branch_policy"][
                "publish_branch"
            ],
            "main",
        )

    def test_policy_rejects_automatic_push(self) -> None:
        path = self.root / "config" / "release_policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        policy["publishing"]["allow_push"] = True
        path.write_text(
            json.dumps(policy),
            encoding="utf-8",
        )

        result = load_release_policy(self.root)

        self.assertFalse(result["ok"])
        self.assertIn(
            "Automatic publishing is forbidden",
            result["error"],
        )

    @patch("tools.release_tools.check_documentation")
    @patch("tools.release_tools.git_status")
    @patch("tools.release_tools.git_branch")
    def test_feature_branch_is_preparation_ready(
        self,
        mocked_branch,
        mocked_status,
        mocked_docs,
    ) -> None:
        mocked_branch.return_value = self._git_result(
            "branch",
            stdout="feature/v1.12-release-manager\n",
        )
        mocked_status.return_value = self._git_result(
            "status",
            stdout="",
        )
        mocked_docs.return_value = {
            "ok": True,
            "error": None,
            "data": {"passed": True},
        }

        result = get_release_status(self.root)

        self.assertTrue(result["ok"])
        self.assertTrue(
            result["data"]["preparation_ready"]
        )
        self.assertFalse(
            result["data"]["publish_ready"]
        )

    @patch("tools.release_tools.check_documentation")
    @patch("tools.release_tools.git_status")
    @patch("tools.release_tools.git_branch")
    def test_main_branch_can_be_publish_ready(
        self,
        mocked_branch,
        mocked_status,
        mocked_docs,
    ) -> None:
        mocked_branch.return_value = self._git_result(
            "branch",
            stdout="main\n",
        )
        mocked_status.return_value = self._git_result(
            "status",
            stdout="",
        )
        mocked_docs.return_value = {
            "ok": True,
            "error": None,
            "data": {"passed": True},
        }

        result = get_release_status(self.root)

        self.assertTrue(
            result["data"]["publish_ready"]
        )

    @patch("tools.release_tools.check_documentation")
    @patch("tools.release_tools.git_status")
    @patch("tools.release_tools.git_branch")
    def test_dirty_tree_blocks_preparation(
        self,
        mocked_branch,
        mocked_status,
        mocked_docs,
    ) -> None:
        mocked_branch.return_value = self._git_result(
            "branch",
            stdout="feature/v1.12-release-manager\n",
        )
        mocked_status.return_value = self._git_result(
            "status",
            stdout=" M README.md\n",
        )
        mocked_docs.return_value = {
            "ok": True,
            "error": None,
            "data": {"passed": True},
        }

        result = get_release_status(self.root)

        self.assertFalse(
            result["data"]["preparation_ready"]
        )
        self.assertIn(
            "Git working tree is not clean.",
            result["data"]["issues"],
        )

    def test_release_notes_are_built_from_current_version(self) -> None:
        result = build_release_notes(self.root)

        self.assertTrue(result["ok"])
        self.assertIn(
            "## v1.12.0 - Release Manager",
            result["data"]["draft"],
        )
        self.assertNotIn(
            "## v1.11.0",
            result["data"]["draft"],
        )
        self.assertFalse(result["data"]["written"])

    @patch("tools.release_tools.run_allowed_command")
    @patch("tools.release_tools.check_documentation")
    @patch("tools.release_tools.git_status")
    @patch("tools.release_tools.git_branch")
    def test_release_check_uses_predefined_commands(
        self,
        mocked_branch,
        mocked_status,
        mocked_docs,
        mocked_run,
    ) -> None:
        mocked_branch.return_value = self._git_result(
            "branch",
            stdout="main\n",
        )
        mocked_status.return_value = self._git_result(
            "status",
            stdout="",
        )
        mocked_docs.return_value = {
            "ok": True,
            "error": None,
            "data": {"passed": True},
        }
        mocked_run.return_value = {
            "ok": True,
            "error": None,
            "data": {
                "returncode": 0,
                "duration_ms": 10,
            },
        }

        result = run_release_check(self.root)

        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["passed"])
        self.assertTrue(result["data"]["publish_ready"])
        self.assertEqual(mocked_run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
