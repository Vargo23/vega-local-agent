from pathlib import Path

from core.contextual_runtime import try_execute_contextual_request
from core.model_router import MODEL_PROFILES, set_current_profile
from core.tool_executor import ToolExecutor


def _tool_policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "enabled": True,
        "allow_explicit_execution": True,
        "automatic_permissions": ["READ", "DRAFT"],
        "confirmation_permissions": ["WRITE", "EXECUTE", "SEND", "DELETE", "ADMIN"],
        "max_tool_steps": 8,
        "allow_arbitrary_tool_names": False,
        "allow_shell_generation": False,
        "fail_closed": True,
    }


def test_document_analysis_uses_docs_profile(tmp_path: Path) -> None:
    calls: list[str] = []
    registry = {
        "read_file": lambda path: {
            "ok": True,
            "error": None,
            "data": {"text": "document evidence", "path": path},
        }
    }
    result = try_execute_contextual_request(
        'analyze document "docs/report.md" and summarize it',
        tmp_path,
        ToolExecutor(registry),
        registry=registry,
        capability_config={
            "read_file": {"permission": "READ", "capabilities": ["document.read"]}
        },
        policy_config=_tool_policy(),
        installed_models=[MODEL_PROFILES["docs"]["model"]],
        chat_callable=lambda model, messages: calls.append(model) or (True, "answer"),
    )
    assert result.model_decision.profile == "docs"
    assert calls == [MODEL_PROFILES["docs"]["model"]]
    assert result.context_budget_result.evidence == "document evidence"


def test_code_review_uses_code_and_manual_is_not_overridden(tmp_path: Path) -> None:
    registry = {
        "git_diff": lambda workspace: {
            "stdout": "diff --git a/a.py b/a.py\n+change",
            "stderr": "",
            "returncode": 0,
        }
    }
    common = dict(
        registry=registry,
        capability_config={
            "git_diff": {"permission": "READ", "capabilities": ["git.diff"]}
        },
        policy_config=_tool_policy(),
        installed_models=[
            MODEL_PROFILES["fast"]["model"],
            MODEL_PROFILES["code"]["model"],
        ],
        chat_callable=lambda model, messages: (True, "review"),
    )
    automatic = try_execute_contextual_request(
        "review the diff and assess risks",
        tmp_path,
        ToolExecutor(registry),
        **common,
    )
    assert automatic.model_decision.profile == "code"

    set_current_profile(tmp_path, "fast")
    manual = try_execute_contextual_request(
        "review the diff and assess risks",
        tmp_path,
        ToolExecutor(registry),
        **common,
    )
    assert manual.model_decision.profile == "fast"

