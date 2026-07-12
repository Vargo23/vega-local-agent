import unittest
from unittest.mock import Mock, patch

from core.tool_confirmation import ToolConfirmationDecision, ToolConfirmationManager, ToolConfirmationRequest, execute_tool_with_confirmation
from core.tool_executor import ToolExecutor, ToolRequest
from permissions import PermissionCapability, PermissionEffect, PermissionEvaluator, PermissionPolicy, PermissionRisk, PermissionRule


def evaluator(effect, name="sample"):
    rule = PermissionRule(name, (PermissionCapability.PROCESS_EXECUTE,), PermissionRisk.HIGH, effect, False, "Test.")
    return PermissionEvaluator(PermissionPolicy(1, PermissionEffect.DENY, "CONFIRM", 10, (rule,)))


class ToolConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.prompt_request = ToolConfirmationRequest("terminal_run", "high", ("process.execute",), ("api_key",))

    def test_responses_are_narrow_and_fail_closed(self):
        cases = {"y": ToolConfirmationDecision.APPROVE, "yes": ToolConfirmationDecision.APPROVE, "n": ToolConfirmationDecision.REJECT, "no": ToolConfirmationDecision.REJECT, "": ToolConfirmationDecision.REJECT, "yep": ToolConfirmationDecision.REJECT}
        for response, expected in cases.items():
            with self.subTest(response=response):
                self.assertIs(ToolConfirmationManager(lambda prompt, value=response: value).decide(self.prompt_request), expected)

    def test_interrupts_and_callback_errors_cancel(self):
        for error in (EOFError(), KeyboardInterrupt(), RuntimeError("bad")):
            with self.subTest(error=type(error).__name__):
                self.assertIs(ToolConfirmationManager(Mock(side_effect=error)).decide(self.prompt_request), ToolConfirmationDecision.CANCEL)

    def test_prompt_has_metadata_but_no_values_or_internal_token(self):
        prompt = ToolConfirmationManager.build_prompt(self.prompt_request)
        for value in ("terminal_run", "high", "process.execute", "api_key", "one-time"):
            self.assertIn(value, prompt)
        self.assertNotIn("CONFIRM", prompt)
        self.assertNotIn("secret-value", prompt)

    def test_allow_deny_and_policy_errors_never_prompt_incorrectly(self):
        for effect, should_call in ((PermissionEffect.ALLOW, True), (PermissionEffect.DENY, False)):
            calls, callback = [], Mock(return_value="yes")
            result = execute_tool_with_confirmation(ToolExecutor({"sample": lambda: calls.append(True)}, evaluator(effect)), ToolRequest("sample"), ToolConfirmationManager(callback))
            self.assertEqual(bool(calls), should_call)
            callback.assert_not_called()
        configured = evaluator(PermissionEffect.ALLOW, "other")
        callback = Mock(return_value="yes")
        result = execute_tool_with_confirmation(ToolExecutor({"sample": lambda: None}, configured), ToolRequest("sample"), ToolConfirmationManager(callback))
        self.assertEqual(result.error_code, "permission_policy_error")
        callback.assert_not_called()

    def test_approval_executes_once_with_exact_arguments_and_no_metadata_leak(self):
        calls, callback = [], Mock(return_value="yes")
        executor = ToolExecutor({"sample": lambda **kwargs: calls.append(kwargs)}, evaluator(PermissionEffect.CONFIRM))
        result = execute_tool_with_confirmation(executor, ToolRequest("sample", {"api_key": "secret-value", "value": 2}), ToolConfirmationManager(callback))
        self.assertTrue(result.ok)
        self.assertEqual(calls, [{"api_key": "secret-value", "value": 2}])
        self.assertNotIn("secret-value", callback.call_args.args[0])

    def test_rejection_noninteractive_and_reuse_are_blocked(self):
        calls = []
        executor = ToolExecutor({"sample": lambda: calls.append(True)}, evaluator(PermissionEffect.CONFIRM))
        rejected = execute_tool_with_confirmation(executor, ToolRequest("sample"), ToolConfirmationManager(lambda prompt: "no"))
        self.assertEqual(rejected.error_code, "confirmation_rejected")
        blocked = execute_tool_with_confirmation(executor, ToolRequest("sample"))
        self.assertEqual(blocked.error_code, "confirmation_required")
        self.assertEqual(calls, [])

    def test_internal_retry_cannot_bypass_deny_or_policy_error(self):
        for configured in (evaluator(PermissionEffect.DENY), evaluator(PermissionEffect.ALLOW, "other")):
            calls = []
            result = ToolExecutor({"sample": lambda: calls.append(True)}, configured)._execute_confirmed_once(ToolRequest("sample"))
            self.assertFalse(result.ok)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
