"""Trusted-root-scoped resolution and execution of local Python modules."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.machinery import PathFinder, SourceFileLoader
import importlib.util
from pathlib import Path
import sys
import threading
from types import ModuleType
from typing import Any


class ModuleResolutionError(RuntimeError):
    """Raised when a dotted module chain cannot be loaded fail closed."""


_RESOLUTION_LOCK = threading.RLock()
_MISSING = object()


@dataclass(frozen=True, slots=True)
class _ValidatedSpec:
    fullname: str
    spec: Any
    origin: Path
    package_locations: tuple[Path, ...]

    @property
    def is_package(self) -> bool:
        return bool(self.package_locations)


@dataclass(slots=True)
class _ModuleRollback:
    fullname: str
    created_module: ModuleType
    replacement: Any = _MISSING


@dataclass(frozen=True, slots=True)
class _AttributeRollback:
    parent: ModuleType
    name: str
    existed: bool
    previous_value: Any = None


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise ModuleResolutionError(f"{label} must be a filesystem path")
    try:
        return Path(value).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ModuleResolutionError(
            f"{label} cannot be resolved ({type(exc).__name__})"
        ) from exc


def _validated_directory(value: Any, *, label: str, project_root: Path) -> Path:
    directory = _resolved_path(value, label=label)
    if not directory.is_dir():
        raise ModuleResolutionError(f"{label} must be an existing directory")
    if not _is_relative_to(directory, project_root):
        raise ModuleResolutionError(f"{label} resolves outside project_root")
    return directory


def _find_spec(fullname: str, search_path: list[str]):
    """Private seam for tests; production always uses the standard PathFinder."""

    return PathFinder.find_spec(fullname, search_path)


def _validate_spec(
    fullname: str,
    spec: Any,
    *,
    project_root: Path,
    require_package: bool,
) -> _ValidatedSpec:
    if spec is None:
        raise ModuleResolutionError(f"module spec was not found for {fullname!r}")
    if getattr(spec, "name", None) != fullname:
        raise ModuleResolutionError(f"module spec name mismatch for {fullname!r}")
    loader = getattr(spec, "loader", None)
    if type(loader) is not SourceFileLoader:
        raise ModuleResolutionError(
            f"module {fullname!r} must use SourceFileLoader"
        )
    origin = getattr(spec, "origin", None)
    if origin is None:
        raise ModuleResolutionError(
            f"module {fullname!r} origin is missing; namespace packages are forbidden"
        )
    if origin in {"built-in", "frozen"}:
        raise ModuleResolutionError(f"module {fullname!r} has forbidden origin {origin!r}")
    resolved_origin = _resolved_path(origin, label=f"module {fullname!r} origin")
    if not resolved_origin.is_file():
        raise ModuleResolutionError(
            f"module {fullname!r} origin must be an existing source file"
        )
    if resolved_origin.suffix not in {".py", ".pyw"}:
        raise ModuleResolutionError(
            f"module {fullname!r} origin must be a source Python file"
        )
    if not _is_relative_to(resolved_origin, project_root):
        raise ModuleResolutionError(
            f"module {fullname!r} origin is outside project_root"
        )

    raw_locations = getattr(spec, "submodule_search_locations", None)
    package_locations: tuple[Path, ...] = ()
    if raw_locations is not None:
        locations = tuple(raw_locations)
        if len(locations) != 1:
            raise ModuleResolutionError(
                f"package {fullname!r} must have exactly one local package location"
            )
        location = _validated_directory(
            locations[0],
            label=f"package {fullname!r} location",
            project_root=project_root,
        )
        if location != resolved_origin.parent:
            raise ModuleResolutionError(
                f"package {fullname!r} location does not match its source origin"
            )
        package_locations = (location,)
    if require_package and not package_locations:
        raise ModuleResolutionError(
            f"module {fullname!r} must be a package to contain child modules"
        )
    return _ValidatedSpec(fullname, spec, resolved_origin, package_locations)


def _resolve_chain(
    module_name: str,
    *,
    project_root: Path,
    trusted_roots: tuple[Path, ...],
) -> tuple[_ValidatedSpec, ...]:
    parts = module_name.split(".")
    search_path = [str(project_root)]
    chain: list[_ValidatedSpec] = []
    for index in range(len(parts)):
        fullname = ".".join(parts[: index + 1])
        validated = _validate_spec(
            fullname,
            _find_spec(fullname, search_path),
            project_root=project_root,
            require_package=index < len(parts) - 1,
        )
        chain.append(validated)
        if validated.package_locations:
            search_path = [str(path) for path in validated.package_locations]
    final = chain[-1]
    if not any(_is_relative_to(final.origin, root) for root in trusted_roots):
        raise ModuleResolutionError(
            f"final plugin module {module_name!r} is outside trusted roots"
        )
    return tuple(chain)


def _module_locations(module: ModuleType, *, fullname: str) -> tuple[Path, ...]:
    raw_path = getattr(module, "__path__", None)
    if raw_path is None or isinstance(raw_path, (str, bytes)):
        raise ModuleResolutionError(f"package {fullname!r} __path__ is missing")
    try:
        values = tuple(raw_path)
    except TypeError as exc:
        raise ModuleResolutionError(
            f"package {fullname!r} __path__ is invalid"
        ) from exc
    return tuple(
        _resolved_path(value, label=f"package {fullname!r} __path__")
        for value in values
    )


def _validate_module(module: Any, expected: _ValidatedSpec) -> ModuleType:
    if not isinstance(module, ModuleType):
        raise ModuleResolutionError(
            f"sys.modules entry for {expected.fullname!r} is not a module"
        )
    actual_spec = getattr(module, "__spec__", None)
    if actual_spec is None:
        raise ModuleResolutionError(
            f"module {expected.fullname!r} __spec__ is missing"
        )
    if getattr(actual_spec, "name", None) != expected.fullname:
        raise ModuleResolutionError(
            f"module {expected.fullname!r} __spec__.name mismatch"
        )
    if type(getattr(actual_spec, "loader", None)) is not SourceFileLoader:
        raise ModuleResolutionError(
            f"module {expected.fullname!r} has an unsupported loader after execution"
        )
    actual_origin = _resolved_path(
        getattr(actual_spec, "origin", None),
        label=f"module {expected.fullname!r} __spec__.origin",
    )
    if actual_origin != expected.origin:
        raise ModuleResolutionError(
            f"module {expected.fullname!r} post-exec origin mismatch"
        )
    actual_file = _resolved_path(
        getattr(module, "__file__", None),
        label=f"module {expected.fullname!r} __file__",
    )
    if actual_file != expected.origin:
        raise ModuleResolutionError(
            f"module {expected.fullname!r} post-exec __file__ mismatch"
        )
    if expected.is_package:
        if _module_locations(module, fullname=expected.fullname) != expected.package_locations:
            raise ModuleResolutionError(
                f"package {expected.fullname!r} post-exec __path__ mismatch"
            )
    elif getattr(module, "__path__", None) is not None:
        raise ModuleResolutionError(
            f"non-package module {expected.fullname!r} unexpectedly defines __path__"
        )
    return module


def _cleanup(
    module_rollbacks: list[_ModuleRollback],
    attribute_rollbacks: list[_AttributeRollback],
) -> None:
    for rollback in reversed(attribute_rollbacks):
        if rollback.existed:
            rollback.parent.__dict__[rollback.name] = rollback.previous_value
        else:
            rollback.parent.__dict__.pop(rollback.name, None)
    for rollback in reversed(module_rollbacks):
        current = sys.modules.get(rollback.fullname, _MISSING)
        if current is rollback.created_module or (
            rollback.replacement is not _MISSING and current is rollback.replacement
        ):
            sys.modules.pop(rollback.fullname, None)


def resolve_module(
    module_name: str,
    *,
    project_root: str | Path,
    trusted_roots: tuple[Path, ...],
) -> ModuleType:
    """Resolve and execute one dotted source module without consulting sys.path."""

    with _RESOLUTION_LOCK:
        module_rollbacks: list[_ModuleRollback] = []
        attribute_rollbacks: list[_AttributeRollback] = []
        try:
            root = _resolved_path(project_root, label="project_root")
            if not root.is_dir():
                raise ModuleResolutionError("project_root must be an existing directory")
            if not isinstance(trusted_roots, tuple) or not trusted_roots:
                raise ModuleResolutionError("trusted_roots must be a non-empty tuple")
            roots = tuple(
                _validated_directory(
                    value,
                    label="trusted root",
                    project_root=root,
                )
                for value in trusted_roots
            )
            chain = _resolve_chain(module_name, project_root=root, trusted_roots=roots)

            preexisting: dict[str, ModuleType] = {}
            for expected in chain:
                if expected.fullname in sys.modules:
                    preexisting[expected.fullname] = _validate_module(
                        sys.modules[expected.fullname], expected
                    )

            loaded: dict[str, ModuleType] = {}
            for index, expected in enumerate(chain):
                module_rollback: _ModuleRollback | None = None
                parent: ModuleType | None = None
                attribute = ""
                if index:
                    parent_name = ".".join(expected.fullname.split(".")[:-1])
                    attribute = expected.fullname.rsplit(".", 1)[-1]
                    parent = loaded[parent_name]
                    existed = attribute in parent.__dict__
                    attribute_rollbacks.append(
                        _AttributeRollback(
                            parent,
                            attribute,
                            existed,
                            parent.__dict__.get(attribute),
                        )
                    )
                if expected.fullname in preexisting:
                    module = preexisting[expected.fullname]
                    if sys.modules.get(expected.fullname) is not module:
                        raise ModuleResolutionError(
                            f"pre-existing module {expected.fullname!r} changed during resolution"
                        )
                    _validate_module(module, expected)
                elif expected.fullname in sys.modules:
                    module = _validate_module(sys.modules[expected.fullname], expected)
                else:
                    module = importlib.util.module_from_spec(expected.spec)
                    sys.modules[expected.fullname] = module
                    module_rollback = _ModuleRollback(expected.fullname, module)
                    module_rollbacks.append(module_rollback)
                    expected.spec.loader.exec_module(module)
                    _validate_module(module, expected)
                if sys.modules.get(expected.fullname) is not module:
                    if module_rollback is not None and expected.fullname in sys.modules:
                        module_rollback.replacement = sys.modules[expected.fullname]
                    raise ModuleResolutionError(
                        f"module {expected.fullname!r} changed its sys.modules entry"
                    )
                loaded[expected.fullname] = module

                if index:
                    if attribute in parent.__dict__:
                        if parent.__dict__[attribute] is not module:
                            raise ModuleResolutionError(
                                f"parent attribute {parent_name}.{attribute} is inconsistent"
                            )
                    else:
                        setattr(parent, attribute, module)
            return loaded[module_name]
        except BaseException as exc:
            _cleanup(module_rollbacks, attribute_rollbacks)
            if not isinstance(exc, Exception):
                raise
            if isinstance(exc, ModuleResolutionError):
                raise ModuleResolutionError(str(exc)) from exc
            raise ModuleResolutionError(
                f"failed to resolve module {module_name!r} ({type(exc).__name__})"
            ) from exc


__all__ = ["ModuleResolutionError", "resolve_module"]
