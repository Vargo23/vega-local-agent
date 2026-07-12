import unittest

from permissions import (
    PermissionCapability,
    PermissionEffect,
    PermissionGrantScope,
    PermissionPolicy,
    PermissionRisk,
    PermissionRule,
    PermissionValidationError,
)


def rule_dict(name="read_file"):
    return {
        "tool_name": name,
        "capabilities": ["project.read"],
        "risk": "low",
        "effect": "allow",
        "session_grant_allowed": False,
        "reason": "Reads project content.",
    }


def policy_dict(rules=None):
    return {
        "schema_version": 1,
        "default_effect": "deny",
        "confirmation_token": "CONFIRM",
        "max_session_grants": 10,
        "rules": [rule_dict()] if rules is None else rules,
    }


class PermissionModelTests(unittest.TestCase):
    def test_every_enum_value_round_trips(self):
        for enum_type in (PermissionEffect, PermissionRisk, PermissionCapability, PermissionGrantScope):
            for item in enum_type:
                self.assertIs(enum_type(item.value), item)

    def test_valid_rule_round_trips(self):
        rule = PermissionRule.from_dict(rule_dict())
        self.assertEqual(PermissionRule.from_dict(rule.to_dict()), rule)

    def test_valid_policy_round_trips(self):
        policy = PermissionPolicy.from_dict(policy_dict())
        self.assertEqual(PermissionPolicy.from_dict(policy.to_dict()), policy)

    def test_unknown_rule_fields_rejected(self):
        data = rule_dict(); data["extra"] = True
        with self.assertRaises(PermissionValidationError): PermissionRule.from_dict(data)

    def test_unknown_policy_fields_rejected(self):
        data = policy_dict(); data["extra"] = True
        with self.assertRaises(PermissionValidationError): PermissionPolicy.from_dict(data)

    def test_invalid_tool_names_rejected(self):
        for name in ("", " ", "Read_File", "read-file", "../read"):
            data = rule_dict(name)
            with self.subTest(name=name), self.assertRaises(PermissionValidationError):
                PermissionRule.from_dict(data)

    def test_empty_unknown_and_duplicate_capabilities_rejected(self):
        for capabilities in ([], ["unknown"], ["project.read", "project.read"]):
            data = rule_dict(); data["capabilities"] = capabilities
            with self.subTest(capabilities=capabilities), self.assertRaises(PermissionValidationError):
                PermissionRule.from_dict(data)

    def test_invalid_effects_and_risks_rejected(self):
        for field, value in (("effect", "maybe"), ("risk", "severe")):
            data = rule_dict(); data[field] = value
            with self.subTest(field=field), self.assertRaises(PermissionValidationError):
                PermissionRule.from_dict(data)

    def test_non_boolean_session_grant_rejected(self):
        data = rule_dict(); data["session_grant_allowed"] = 1
        with self.assertRaises(PermissionValidationError): PermissionRule.from_dict(data)

    def test_deny_and_critical_cannot_allow_session_grants(self):
        for field, value in (("effect", "deny"), ("risk", "critical")):
            data = rule_dict(); data[field] = value; data["session_grant_allowed"] = True
            with self.subTest(field=field), self.assertRaises(PermissionValidationError):
                PermissionRule.from_dict(data)

    def test_empty_or_unbounded_reason_rejected(self):
        for reason in ("", "   ", "x" * 501):
            data = rule_dict(); data["reason"] = reason
            with self.subTest(length=len(reason)), self.assertRaises(PermissionValidationError):
                PermissionRule.from_dict(data)

    def test_boolean_integer_fields_rejected(self):
        for field in ("schema_version", "max_session_grants"):
            data = policy_dict(); data[field] = True
            with self.subTest(field=field), self.assertRaises(PermissionValidationError):
                PermissionPolicy.from_dict(data)

    def test_policy_safety_constants_rejected_when_altered(self):
        changes = (("schema_version", 2), ("default_effect", "allow"), ("confirmation_token", "confirm"))
        for field, value in changes:
            data = policy_dict(); data[field] = value
            with self.subTest(field=field), self.assertRaises(PermissionValidationError):
                PermissionPolicy.from_dict(data)

    def test_duplicate_tool_rules_rejected(self):
        with self.assertRaises(PermissionValidationError):
            PermissionPolicy.from_dict(policy_dict([rule_dict(), rule_dict()]))

    def test_serialized_rules_are_sorted_deterministically(self):
        policy = PermissionPolicy.from_dict(policy_dict([rule_dict("zeta"), rule_dict("alpha")]))
        self.assertEqual([item["tool_name"] for item in policy.to_dict()["rules"]], ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
