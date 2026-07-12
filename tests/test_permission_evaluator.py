import unittest

from permissions import (
    PermissionCapability,
    PermissionEffect,
    PermissionEvaluator,
    PermissionPolicy,
    PermissionRisk,
    PermissionRule,
)


def make_policy(effect=PermissionEffect.ALLOW):
    rule = PermissionRule(
        "sample",
        (PermissionCapability.PROJECT_READ,),
        PermissionRisk.LOW,
        effect,
        False,
        "Test rule.",
    )
    return PermissionPolicy(
        1,
        PermissionEffect.DENY,
        "CONFIRM",
        10,
        (rule,),
    )


class PermissionEvaluatorTests(unittest.TestCase):
    def test_allow_decision(self):
        self.assertTrue(PermissionEvaluator(make_policy()).evaluate("sample").allowed)

    def test_deny_decision(self):
        decision = PermissionEvaluator(
            make_policy(PermissionEffect.DENY)
        ).evaluate("sample")
        self.assertIs(decision.effect, PermissionEffect.DENY)

    def test_confirm_decision(self):
        decision = PermissionEvaluator(
            make_policy(PermissionEffect.CONFIRM)
        ).evaluate("sample")
        self.assertTrue(decision.confirmation_required)

    def test_missing_rule_fails_closed(self):
        decision = PermissionEvaluator(make_policy()).evaluate("missing")
        self.assertIs(decision.effect, PermissionEffect.DENY)
        self.assertEqual(decision.error_code, "permission_policy_error")

    def test_invalid_policy_state_fails_closed(self):
        decision = PermissionEvaluator(make_policy()).evaluate("Invalid Name")
        self.assertEqual(decision.error_code, "permission_policy_error")


if __name__ == "__main__":
    unittest.main()
