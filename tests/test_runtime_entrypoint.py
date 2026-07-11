import unittest

import scripts.vega as cli_entrypoint
from core.agent_runtime import main as runtime_main


class RuntimeEntrypointTests(unittest.TestCase):
    def test_cli_entrypoint_uses_agent_runtime_main(self) -> None:
        self.assertIs(
            cli_entrypoint.main,
            runtime_main,
        )

    def test_cli_entrypoint_exports_project_root(self) -> None:
        self.assertTrue(
            cli_entrypoint.PROJECT_ROOT.is_dir()
        )
        self.assertTrue(
            (
                cli_entrypoint.PROJECT_ROOT
                / "core"
            ).is_dir()
        )
        self.assertTrue(
            (
                cli_entrypoint.PROJECT_ROOT
                / "scripts"
            ).is_dir()
        )


if __name__ == "__main__":
    unittest.main()
