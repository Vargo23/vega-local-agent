import unittest
from pathlib import Path
from unittest.mock import patch

from core.tool_confirmation import ToolConfirmationManager, execute_tool_with_confirmation
from core.tool_executor import ToolExecutor, ToolRequest
from permissions import PermissionCapability, PermissionEffect, PermissionEvaluator, PermissionPolicy, PermissionRisk, PermissionRule, SessionGrantStore, load_permission_policy

ROOT = Path(__file__).resolve().parents[1]


class PermissionSessionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_permission_policy(ROOT)

    def executor(self, names, store, calls):
        registry = {name: (lambda current=name: calls.append(current)) for name in names}
        return ToolExecutor(registry, PermissionEvaluator(self.policy), store)

    def test_actual_policy_sets(self):
        capable = {rule.tool_name for rule in self.policy.rules if rule.effect.value == "confirm" and rule.session_grant_allowed}
        restricted = {rule.tool_name for rule in self.policy.rules if rule.effect.value == "confirm" and not rule.session_grant_allowed}
        self.assertEqual(capable, {"memory_add", "propose_patch", "propose_patch_from_file"})
        self.assertEqual(restricted, {"apply_patch", "documentation_build", "internet_set", "release_check", "rollback_patch", "terminal_run", "test_run", "web_fetch"})

    def test_session_capable_tools_grant_execute_repeat_revoke_and_clear(self):
        for name in ("memory_add", "propose_patch", "propose_patch_from_file"):
            calls, store = [], SessionGrantStore()
            executor = self.executor((name,), store, calls)
            with self.subTest(name=name):
                first = execute_tool_with_confirmation(executor, ToolRequest(name), ToolConfirmationManager(lambda prompt: "session"))
                self.assertTrue(first.ok)
                self.assertEqual(calls, [name])
                self.assertTrue(executor.execute(ToolRequest(name)).ok)
                self.assertEqual(calls, [name, name])
                store.revoke(name)
                self.assertEqual(executor.execute(ToolRequest(name)).error_code, "confirmation_required")
                store.grant(name)
                store.clear()
                self.assertEqual(executor.execute(ToolRequest(name)).error_code, "confirmation_required")

    def test_restricted_tools_never_offer_or_accept_session(self):
        restricted = tuple(rule.tool_name for rule in self.policy.rules if rule.effect.value == "confirm" and not rule.session_grant_allowed)
        for name in restricted:
            calls, prompts, store = [], [], SessionGrantStore()
            executor = self.executor((name,), store, calls)
            result = execute_tool_with_confirmation(executor, ToolRequest(name), ToolConfirmationManager(lambda prompt: prompts.append(prompt) or "s"))
            with self.subTest(name=name):
                self.assertEqual(result.error_code, "confirmation_rejected")
                self.assertNotIn("session [s]", prompts[0])
                self.assertFalse(store.contains(name))
                self.assertEqual(calls, [])
                self.assertEqual(executor.execute(ToolRequest(name)).error_code, "confirmation_required")

    def test_stored_grant_cannot_bypass_current_policy(self):
        calls, store = [], SessionGrantStore()
        store.grant("terminal_run")
        executor = self.executor(("terminal_run",), store, calls)
        self.assertEqual(executor.execute(ToolRequest("terminal_run")).error_code, "confirmation_required")
        self.assertEqual(calls, [])

    def test_different_executors_and_fresh_stores_are_isolated(self):
        first, second, calls = SessionGrantStore(), SessionGrantStore(), []
        first.grant("memory_add")
        self.assertTrue(self.executor(("memory_add",), first, calls).execute(ToolRequest("memory_add")).ok)
        self.assertEqual(self.executor(("memory_add",), second, calls).execute(ToolRequest("memory_add")).error_code, "confirmation_required")

    def test_unregistered_policy_tool_cannot_be_granted(self):
        store = SessionGrantStore()
        executor = ToolExecutor(
            {"other": lambda: None},
            PermissionEvaluator(self.policy),
            store,
        )
        with self.assertRaises(ValueError):
            executor.grant_session_for_tool("memory_add")
        self.assertEqual(store.list_grants(), ())

    def test_deny_missing_policy_and_evaluator_errors_cannot_grant(self):
        cases = ("read_file", "missing")
        for name in cases:
            store = SessionGrantStore()
            executor = ToolExecutor(
                {name: lambda: None},
                PermissionEvaluator(self.policy),
                store,
            )
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                executor.grant_session_for_tool(name)
            self.assertEqual(store.list_grants(), ())

        deny_rule = PermissionRule(
            "denied",
            (PermissionCapability.PROCESS_EXECUTE,),
            PermissionRisk.HIGH,
            PermissionEffect.DENY,
            False,
            "Denied.",
        )
        deny_policy = PermissionPolicy(
            1, PermissionEffect.DENY, "CONFIRM", 10, (deny_rule,)
        )
        store = SessionGrantStore()
        denied = ToolExecutor(
            {"denied": lambda: None},
            PermissionEvaluator(deny_policy),
            store,
        )
        with self.assertRaises(RuntimeError):
            denied.grant_session_for_tool("denied")
        self.assertEqual(store.list_grants(), ())

        store = SessionGrantStore()
        configured = PermissionEvaluator(self.policy)
        executor = ToolExecutor({"memory_add": lambda: None}, configured, store)
        with patch.object(configured, "evaluate", side_effect=RuntimeError("broken")):
            with self.assertRaises(RuntimeError):
                executor.grant_session_for_tool("memory_add")
        self.assertEqual(store.list_grants(), ())

    def test_registered_session_capable_tool_can_be_granted(self):
        store = SessionGrantStore()
        executor = ToolExecutor(
            {"memory_add": lambda: None},
            PermissionEvaluator(self.policy),
            store,
        )
        executor.grant_session_for_tool("  memory_add  ")
        self.assertTrue(store.contains("memory_add"))


if __name__ == "__main__":
    unittest.main()
