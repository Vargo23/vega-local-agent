"""Stable public interface for VEGA permissions."""

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

__all__ = [
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
]
