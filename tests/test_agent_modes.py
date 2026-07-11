import json
import tempfile
import unittest
from pathlib import Path

from core.agent_modes import (
    ModeConfigurationError,
    ModeRegistry,
    ModeSession,
)
from core.command_handler import (
    handle_mode_command,
    handle_patch_command,
)


class ModeRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ModeRegistry()

    def test_default_mode_is_coder(self) -> None:
        self.assertEqual(self.registry.default_mode, "coder")

    def test_expected_modes_are_available(self) -> None:
        mode_names = {
            mode.name
            for mode in self.registry.list_modes()
        }

        self.assertEqual(
            mode_names,
            {
                "architect",
                "coder",
                "reviewer",
                "debugger",
                "teacher",
                "release_manager",
            },
        )

    def test_coder_allows_code_changes(self) -> None:
        coder = self.registry.get("coder")

        self.assertTrue(coder.allow_code_changes)
        self.assertTrue(coder.review_required)

    def test_architect_blocks_code_changes(self) -> None:
        architect = self.registry.get("architect")

        self.assertFalse(architect.allow_code_changes)

    def test_mode_name_is_normalized(self) -> None:
        mode = self.registry.get("  CODER  ")

        self.assertEqual(mode.name, "coder")

    def test_unknown_mode_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.registry.get("unknown")

    def test_missing_default_mode_is_rejected(self) -> None:
        invalid_config = {
            "default_mode": "missing",
            "modes": {
                "coder": {
                    "description": "Coder",
                    "instructions": ["Write code"],
                    "allow_code_changes": True,
                    "review_required": True,
                }
            },
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = (
                Path(temporary_directory)
                / "modes.json"
            )

            config_path.write_text(
                json.dumps(invalid_config),
                encoding="utf-8",
            )

            with self.assertRaises(ModeConfigurationError):
                ModeRegistry(config_path)

    def test_session_starts_in_default_mode(self) -> None:
        session = ModeSession(self.registry)

        self.assertEqual(
            session.active_mode_name,
            "coder",
        )

    def test_session_can_switch_and_reset(self) -> None:
        session = ModeSession(self.registry)

        session.set_mode("architect")
        self.assertEqual(
            session.active_mode_name,
            "architect",
        )

        session.reset()
        self.assertEqual(
            session.active_mode_name,
            "coder",
        )

    def test_mode_command_sets_mode(self) -> None:
        session = ModeSession(self.registry)

        result = handle_mode_command(
            "/mode set reviewer",
            session,
        )

        self.assertEqual(
            session.active_mode_name,
            "reviewer",
        )
        self.assertIn("reviewer", result)

    def test_mode_command_rejects_unknown_mode(self) -> None:
        session = ModeSession(self.registry)

        result = handle_mode_command(
            "/mode set unknown",
            session,
        )

        self.assertEqual(
            session.active_mode_name,
            "coder",
        )
        self.assertIn(
            "Mode command error",
            result,
        )


    def test_reviewer_blocks_patch_apply(self) -> None:
        session = ModeSession(self.registry)
        session.set_mode("reviewer")

        result = handle_patch_command(
            "/patch apply missing-patch CONFIRM",
            session,
        )

        self.assertIn("Patch command blocked", result)
        self.assertIn("reviewer", result)


if __name__ == "__main__":
    unittest.main()
