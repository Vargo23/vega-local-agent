import unittest
from pathlib import Path
from unittest.mock import patch

from core.tool_executor_factory import build_production_tool_executor
from permissions import PermissionEffect, PermissionPolicyError, PermissionRisk
from permissions.policy import load_permission_policy
from tools.registry import TOOL_REGISTRY
from permissions import SessionGrantStore

ROOT = Path(__file__).resolve().parents[1]


class PermissionRuntimeTests(unittest.TestCase):
    def test_builder_loads_fixed_policy_and_all_tools_are_covered(self):
        executor = build_production_tool_executor()
        self.assertEqual(executor.registered_tools(), tuple(sorted(TOOL_REGISTRY)))
        self.assertEqual(len(executor.registered_tools()), 35)

    def test_builder_validates_exact_registry_equality(self):
        with patch(
            "core.tool_executor_factory.TOOL_REGISTRY",
            {"unconfigured": lambda: None},
        ):
            with self.assertRaises(PermissionPolicyError):
                build_production_tool_executor()

    def test_builder_preserves_exact_supplied_session_store(self):
        store = SessionGrantStore()
        executor = build_production_tool_executor(store)
        self.assertIs(executor._session_grants, store)

    def test_critical_and_execution_network_rules_have_no_session_authorization(self):
        rules = {rule.tool_name: rule for rule in load_permission_policy(ROOT).rules}
        selected = (
            "apply_patch",
            "rollback_patch",
            "terminal_run",
            "test_run",
            "release_check",
            "internet_set",
            "web_fetch",
        )
        for name in selected:
            with self.subTest(name=name):
                self.assertFalse(rules[name].session_grant_allowed)
                self.assertIsNot(rules[name].effect, PermissionEffect.ALLOW)
        self.assertTrue(all(
            rules[name].risk is PermissionRisk.CRITICAL
            for name in ("apply_patch", "rollback_patch")
        ))


if __name__ == "__main__":
    unittest.main()
