import json

import pytest

from core.tool_catalog import (
    ToolCatalogError,
    build_tool_catalog,
    load_tool_capabilities,
    registered_tool_names,
)


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class MappingRegistry:
    def __init__(self) -> None:
        self.tools = {
            "files.search": FakeTool("files.search"),
            "tests.run": FakeTool("tests.run"),
            "patches.propose": FakeTool("patches.propose"),
        }


class MethodRegistry:
    def list_tools(self) -> tuple[str, ...]:
        return (
            "documents.read",
            "documents.summarize",
        )


def test_registered_tool_names_support_mapping_registry() -> None:
    result = registered_tool_names(MappingRegistry())

    assert result == (
        "files.search",
        "patches.propose",
        "tests.run",
    )


def test_registered_tool_names_support_list_method() -> None:
    result = registered_tool_names(MethodRegistry())

    assert result == (
        "documents.read",
        "documents.summarize",
    )


def test_build_catalog_uses_only_explicit_configuration() -> None:
    config = {
        "files.search": {
            "permission": "READ",
            "capabilities": ["project.search"],
        }
    }

    catalog = build_tool_catalog(
        MappingRegistry(),
        config,
    )

    assert len(catalog) == 1
    assert catalog[0].name == "files.search"
    assert catalog[0].permission == "READ"
    assert catalog[0].capabilities == (
        "project.search",
    )


def test_unconfigured_registered_tools_are_not_routable() -> None:
    config = {
        "tests.run": {
            "permission": "EXECUTE",
            "capabilities": ["test.run"],
        }
    }

    catalog = build_tool_catalog(
        MappingRegistry(),
        config,
    )

    assert tuple(tool.name for tool in catalog) == (
        "tests.run",
    )
    assert "files.search" not in {
        tool.name for tool in catalog
    }


def test_configured_missing_tool_fails_closed() -> None:
    config = {
        "shell.delete_everything": {
            "permission": "DELETE",
            "capabilities": ["filesystem.delete"],
        }
    }

    with pytest.raises(
        ToolCatalogError,
        match="is not registered",
    ):
        build_tool_catalog(
            MappingRegistry(),
            config,
        )


def test_empty_catalog_is_rejected_by_default() -> None:
    with pytest.raises(
        ToolCatalogError,
        match="no registered tools",
    ):
        build_tool_catalog(
            MappingRegistry(),
            {},
        )


def test_empty_catalog_can_be_used_during_disabled_rollout() -> None:
    catalog = build_tool_catalog(
        MappingRegistry(),
        {},
        allow_empty=True,
    )

    assert catalog == ()


def test_load_tool_capabilities_from_json(tmp_path) -> None:
    path = tmp_path / "tool_capabilities.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tools": {
                    "documents.read": {
                        "permission": "READ",
                        "capabilities": [
                            "document.read"
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    tools = load_tool_capabilities(path)

    assert "documents.read" in tools
    assert tools["documents.read"]["permission"] == "READ"


def test_registered_tool_names_support_direct_mapping() -> None:
    registry = {
        "read_file": lambda: None,
        "list_dir": lambda: None,
    }

    result = registered_tool_names(registry)

    assert result == (
        "list_dir",
        "read_file",
    )
