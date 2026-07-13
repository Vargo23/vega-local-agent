from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from core.tool_planner import ToolDescriptor


class ToolCatalogError(ValueError):
    """Raised when registry metadata cannot form a safe tool catalog."""


def _read_registry_source(registry: object) -> object:
    if isinstance(registry, Mapping):
        return registry

    list_tools = getattr(registry, "list_tools", None)

    if callable(list_tools):
        return list_tools()

    for attribute_name in (
        "tools",
        "_tools",
        "registry",
        "_registry",
    ):
        if hasattr(registry, attribute_name):
            return getattr(registry, attribute_name)

    raise ToolCatalogError(
        "registry must expose list_tools() or a supported tool collection"
    )


def _extract_tool_name(
    entry: object,
    fallback_name: str | None = None,
) -> str:
    if isinstance(entry, str):
        name = entry
    elif isinstance(entry, Mapping):
        name = next(
            (
                entry[key]
                for key in ("name", "tool_name", "id")
                if key in entry
            ),
            fallback_name,
        )
    else:
        name = next(
            (
                getattr(entry, attribute_name)
                for attribute_name in (
                    "name",
                    "tool_name",
                    "id",
                )
                if hasattr(entry, attribute_name)
            ),
            fallback_name,
        )

    if name is None:
        raise ToolCatalogError(
            "registered tool entry does not expose a name"
        )

    normalized = str(name).strip()

    if not normalized:
        raise ToolCatalogError(
            "registered tool name must not be empty"
        )

    return normalized


def registered_tool_names(
    registry: object,
) -> tuple[str, ...]:
    """Return normalized names from the real VEGA registry."""

    source = _read_registry_source(registry)
    names: list[str] = []

    if isinstance(source, Mapping):
        entries = tuple(source.items())
    else:
        if isinstance(source, (str, bytes)):
            raise ToolCatalogError(
                "registry tool collection must not be a string"
            )

        try:
            entries = tuple(
                (None, entry)
                for entry in source  # type: ignore[union-attr]
            )
        except TypeError as exc:
            raise ToolCatalogError(
                "registry tool collection must be iterable"
            ) from exc

    for fallback_name, entry in entries:
        name = _extract_tool_name(
            entry,
            fallback_name=(
                str(fallback_name)
                if fallback_name is not None
                else None
            ),
        )

        if name in names:
            raise ToolCatalogError(
                f"duplicate registered tool name: {name}"
            )

        names.append(name)

    return tuple(sorted(names))


def load_tool_capabilities(
    path: str | Path,
) -> Mapping[str, Any]:
    """Load explicit routing metadata from a UTF-8 JSON file."""

    config_path = Path(path)

    if not config_path.is_file():
        raise ToolCatalogError(
            f"tool capability config does not exist: {config_path}"
        )

    try:
        content = config_path.read_text(encoding="utf-8-sig")
        data = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolCatalogError(
            f"cannot read tool capability config: {config_path}"
        ) from exc

    if not isinstance(data, Mapping):
        raise ToolCatalogError(
            "tool capability config root must be an object"
        )

    tools = data.get("tools")

    if not isinstance(tools, Mapping):
        raise ToolCatalogError(
            "tool capability config must contain a tools object"
        )

    return tools


def build_tool_catalog(
    registry: object,
    capability_config: Mapping[str, Any] | str | Path,
    *,
    allow_empty: bool = False,
) -> tuple[ToolDescriptor, ...]:
    """
    Build planner descriptors from registered and explicitly configured tools.

    Registered tools without routing metadata are ignored and cannot be
    selected automatically. Configured tools that are absent from the real
    registry cause a fail-closed error.
    """

    registered_names = set(registered_tool_names(registry))

    if isinstance(capability_config, (str, Path)):
        configured_tools = load_tool_capabilities(
            capability_config
        )
    elif isinstance(capability_config, Mapping):
        configured_tools = capability_config
    else:
        raise TypeError(
            "capability_config must be a mapping or a file path"
        )

    descriptors: list[ToolDescriptor] = []

    for configured_name, raw_metadata in sorted(
        configured_tools.items(),
        key=lambda item: str(item[0]),
    ):
        tool_name = str(configured_name).strip()

        if not tool_name:
            raise ToolCatalogError(
                "configured tool name must not be empty"
            )

        if tool_name not in registered_names:
            raise ToolCatalogError(
                f"configured tool is not registered: {tool_name}"
            )

        if not isinstance(raw_metadata, Mapping):
            raise ToolCatalogError(
                f"metadata for tool {tool_name!r} must be an object"
            )

        permission = str(
            raw_metadata.get("permission", "")
        ).strip()

        raw_capabilities = raw_metadata.get("capabilities")

        if (
            not isinstance(raw_capabilities, Iterable)
            or isinstance(raw_capabilities, (str, bytes))
        ):
            raise ToolCatalogError(
                f"tool {tool_name!r} must declare a capabilities list"
            )

        capabilities = tuple(
            str(capability).strip()
            for capability in raw_capabilities
            if str(capability).strip()
        )

        description = str(
            raw_metadata.get("description", "")
        ).strip()

        descriptors.append(
            ToolDescriptor(
                name=tool_name,
                permission=permission,
                capabilities=capabilities,
                description=description,
            )
        )

    if not descriptors and not allow_empty:
        raise ToolCatalogError(
            "no registered tools are enabled for contextual routing"
        )

    return tuple(descriptors)

