"""Stable public interface for VEGA permissions."""

from permissions.evaluator import PermissionDecision, PermissionEvaluator

from permissions.models import (
    PermissionCapability,
    PermissionEffect,
    PermissionGrantScope,
    PermissionPolicy,
    PermissionPolicyError,
    PermissionRisk,
    PermissionRule,
    PermissionsError,
    PermissionValidationError,
)
from permissions.policy import load_permission_policy, validate_policy_registry_alignment
from permissions.session_grants import SessionGrant, SessionGrantError, SessionGrantStore

__all__ = [
    "PermissionDecision",
    "PermissionEvaluator",
    "PermissionCapability",
    "PermissionEffect",
    "PermissionGrantScope",
    "PermissionPolicy",
    "PermissionPolicyError",
    "PermissionRisk",
    "PermissionRule",
    "PermissionsError",
    "PermissionValidationError",
    "load_permission_policy",
    "validate_policy_registry_alignment",
    "SessionGrant",
    "SessionGrantError",
    "SessionGrantStore",
]
