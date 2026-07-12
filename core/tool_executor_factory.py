"""Production construction for permission-enforced tool execution."""

from pathlib import Path

from core.tool_executor import ToolExecutor
from permissions.evaluator import PermissionEvaluator
from permissions.policy import load_permission_policy
from tools.registry import TOOL_REGISTRY


def build_production_tool_executor() -> ToolExecutor:
    """Load only VEGA's fixed policy and enforce it on the real registry."""
    root = Path(__file__).resolve().parents[1]
    policy = load_permission_policy(root, registered_tools=TOOL_REGISTRY)
    return ToolExecutor(
        TOOL_REGISTRY,
        permission_evaluator=PermissionEvaluator(policy),
    )


__all__ = ["build_production_tool_executor"]
