import builtins
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from permissions import (
    PermissionEffect,
    PermissionPolicyError,
    PermissionRisk,
    PermissionValidationError,
    load_permission_policy,
    validate_policy_registry_alignment,
)
from tools.registry import TOOL_REGISTRY


ROOT = Path(__file__).resolve().parents[1]


def policy_data(names=("read_file",)):
    return {
        "schema_version": 1,
        "default_effect": "deny",
        "confirmation_token": "CONFIRM",
        "max_session_grants": 10,
        "rules": [
            {"tool_name": name, "capabilities": ["project.read"], "risk": "low", "effect": "allow", "session_grant_allowed": False, "reason": "Reads project content."}
            for name in names
        ],
    }


def write_policy(root, data):
    config = Path(root) / "config"
    config.mkdir()
    (config / "permission_policy.json").write_text(json.dumps(data), encoding="utf-8")


class PermissionPolicyLoaderTests(unittest.TestCase):
    def test_valid_policy_loads_and_alignment_passes(self):
        with tempfile.TemporaryDirectory() as root:
            write_policy(root, policy_data(("read_file", "list_dir")))
            policy = load_permission_policy(root, registered_tools=("read_file", "list_dir"))
            self.assertEqual(len(policy.rules), 2)

    def test_missing_policy_fails_closed_and_is_not_created(self):
        with tempfile.TemporaryDirectory() as root:
            expected = Path(root) / "config" / "permission_policy.json"
            with self.assertRaises(PermissionPolicyError): load_permission_policy(root)
            self.assertFalse(expected.exists())

    def test_invalid_json_and_non_object_fail_closed(self):
        for text in ("{broken", "[]"):
            with tempfile.TemporaryDirectory() as root:
                config = Path(root) / "config"; config.mkdir()
                (config / "permission_policy.json").write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(PermissionPolicyError):
                    load_permission_policy(root)

    def test_filesystem_errors_are_domain_errors_without_absolute_path(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(Path, "read_text", side_effect=OSError(f"failure at {root}")):
                with self.assertRaises(PermissionPolicyError) as caught:
                    load_permission_policy(root)
            self.assertNotIn(str(Path(root).resolve()), str(caught.exception))

    def test_missing_and_extra_registry_tools_fail(self):
        with tempfile.TemporaryDirectory() as root:
            write_policy(root, policy_data(("read_file",)))
            for registry in (("read_file", "list_dir"), ("list_dir",)):
                with self.subTest(registry=registry), self.assertRaises(PermissionPolicyError):
                    load_permission_policy(root, registered_tools=registry)

    def test_invalid_registry_snapshots_rejected(self):
        policy = load_permission_policy(ROOT)
        for registry in (("read_file", "read_file"), ("",), (1,), {"read_file"}):
            with self.subTest(registry=registry), self.assertRaises(PermissionValidationError):
                validate_policy_registry_alignment(policy, registry)

    def test_loading_does_not_import_or_execute_registry_tools(self):
        with tempfile.TemporaryDirectory() as root:
            write_policy(root, policy_data())
            original_import = builtins.__import__
            def guarded_import(name, *args, **kwargs):
                if name == "tools.registry":
                    raise AssertionError("registry imported")
                return original_import(name, *args, **kwargs)
            with mock.patch("builtins.__import__", side_effect=guarded_import):
                load_permission_policy(root, registered_tools=("read_file",))

    def test_loading_performs_no_filesystem_writes(self):
        with mock.patch.object(Path, "write_text", side_effect=AssertionError("write attempted")):
            load_permission_policy(ROOT)

    def test_production_registry_has_exactly_one_rule_per_tool(self):
        policy = load_permission_policy(ROOT, registered_tools=TOOL_REGISTRY)
        self.assertEqual(len(policy.rules), len(TOOL_REGISTRY))

    def test_critical_patch_mutations_are_confirm_only(self):
        rules = {rule.tool_name: rule for rule in load_permission_policy(ROOT).rules}
        for name in ("apply_patch", "rollback_patch"):
            with self.subTest(name=name):
                self.assertIs(rules[name].risk, PermissionRisk.CRITICAL)
                self.assertIs(rules[name].effect, PermissionEffect.CONFIRM)
                self.assertFalse(rules[name].session_grant_allowed)

    def test_process_and_network_tools_are_not_allowed(self):
        rules = {rule.tool_name: rule for rule in load_permission_policy(ROOT).rules}
        for name in ("terminal_run", "test_run", "release_check", "internet_set", "web_fetch"):
            with self.subTest(name=name):
                self.assertIsNot(rules[name].effect, PermissionEffect.ALLOW)

    def test_unknown_tools_are_denied_by_default(self):
        self.assertIs(load_permission_policy(ROOT).default_effect, PermissionEffect.DENY)


if __name__ == "__main__":
    unittest.main()
