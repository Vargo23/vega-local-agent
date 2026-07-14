from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.model_router import MODEL_PROFILES
from core.model_selection import (
    ModelRoutingPolicyError,
    ModelSelectionMode,
    load_model_routing_policy,
    select_model,
)


POLICY_PATH = Path(__file__).parents[1] / "config" / "model_routing_policy.json"


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("document_analysis", "docs"),
        ("project_search", "fast"),
        ("bug_fix", "code"),
        ("test_run", "fast"),
        ("code_review", "code"),
        ("documentation_update", "docs"),
        ("release_check", "deep"),
        ("unknown", "code"),
    ],
)
def test_known_intents_select_expected_profile(intent: str, expected: str) -> None:
    policy = load_model_routing_policy(POLICY_PATH)
    installed = [profile["model"] for profile in MODEL_PROFILES.values()]
    decision = select_model(intent, policy, installed)
    assert decision.profile == expected
    assert decision.reason


def test_explicit_override_has_highest_priority() -> None:
    policy = load_model_routing_policy(POLICY_PATH)
    decision = select_model(
        "release_check",
        policy,
        [],
        selection_mode=ModelSelectionMode.MANUAL,
        current_profile="fast",
        explicit_model="custom:model",
    )
    assert decision.model == "custom:model"
    assert decision.profile == "explicit"
    assert not decision.available
    assert decision.reason_code == "explicit_model_unavailable"
    with pytest.raises(FrozenInstanceError):
        decision.model = "changed"


def test_unavailable_deep_model_uses_allowed_installed_fallback() -> None:
    policy = load_model_routing_policy(POLICY_PATH)
    decision = select_model(
        "release_check",
        policy,
        [MODEL_PROFILES["code"]["model"]],
    )
    assert decision.profile == "code"
    assert decision.fallback_used


def test_invalid_policy_profile_is_rejected() -> None:
    data = load_model_routing_policy(POLICY_PATH)
    invalid = {
        "schema_version": 1,
        "enabled": data.enabled,
        "fallback_profile": "not-a-profile",
        "intent_profiles": dict(data.intent_profiles),
        "fallback_order": list(data.fallback_order),
        "deep_request_chars": data.deep_request_chars,
        "deep_signals": list(data.deep_signals),
        "context_budgets": dict(data.context_budgets),
        "head_ratio": data.head_ratio,
    }
    with pytest.raises(ModelRoutingPolicyError):
        load_model_routing_policy(invalid)


def test_installed_explicit_override_is_available() -> None:
    policy = load_model_routing_policy(POLICY_PATH)
    decision = select_model(
        "release_check",
        policy,
        ["custom:model"],
        explicit_model="custom:model",
    )

    assert decision.available
    assert decision.reason_code == "explicit_override"


@pytest.mark.parametrize("schema_version", (None, True, 0, 2))
def test_model_policy_rejects_invalid_schema_version(schema_version) -> None:
    policy = load_model_routing_policy(POLICY_PATH)
    data = {
        "schema_version": schema_version,
        "enabled": policy.enabled,
        "fallback_profile": policy.fallback_profile,
        "intent_profiles": dict(policy.intent_profiles),
        "fallback_order": list(policy.fallback_order),
        "deep_request_chars": policy.deep_request_chars,
        "deep_signals": list(policy.deep_signals),
        "context_budgets": dict(policy.context_budgets),
        "head_ratio": policy.head_ratio,
    }

    with pytest.raises(ModelRoutingPolicyError, match="schema_version"):
        load_model_routing_policy(data)

