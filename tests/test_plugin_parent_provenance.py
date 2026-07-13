from importlib.machinery import ModuleSpec, SourceFileLoader
from pathlib import Path
import sys
from types import ModuleType

import pytest

import plugins.module_resolver as resolver_module
from plugins.module_resolver import ModuleResolutionError, resolve_module


PACKAGE = "vega_parent_probe"


@pytest.fixture(autouse=True)
def isolate_probe_modules():
    original = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(PACKAGE + ".")
    }
    for name in tuple(original):
        del sys.modules[name]
    yield
    for name in tuple(sys.modules):
        if name == PACKAGE or name.startswith(PACKAGE + "."):
            del sys.modules[name]
    sys.modules.update(original)


def write(path: Path, source: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def package_chain(tmp_path, *, child_source="VALUE = 'child'\n"):
    project = tmp_path / "project"
    package = project / PACKAGE
    plugins = package / "plugins"
    write(package / "__init__.py", "VALUE = 'parent'\n")
    write(plugins / "__init__.py", "VALUE = 'plugins'\n")
    write(plugins / "sample.py", child_source)
    return project, plugins


def load(project: Path, trusted: Path, name=f"{PACKAGE}.plugins.sample"):
    return resolve_module(
        name,
        project_root=project,
        trusted_roots=(trusted.resolve(),),
    )


def make_directory_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlink creation is unavailable: {type(exc).__name__}: {exc}")


def test_external_shadow_parent_and_marker_are_not_executed(tmp_path, monkeypatch):
    project = tmp_path / "project"
    trusted = project / "trusted"
    trusted.mkdir(parents=True)
    external = tmp_path / "external"
    marker = tmp_path / "external-marker"
    write(
        external / PACKAGE / "__init__.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
    )
    write(external / PACKAGE / "plugins" / "__init__.py")
    write(external / PACKAGE / "plugins" / "sample.py")
    monkeypatch.syspath_prepend(str(external))

    with pytest.raises(ModuleResolutionError, match="spec was not found"):
        load(project, trusted)
    assert not marker.exists()
    assert PACKAGE not in sys.modules


def test_project_local_parent_and_child_load_after_validation(tmp_path):
    marker = tmp_path / "parent-marker"
    project, trusted = package_chain(tmp_path)
    write(
        project / PACKAGE / "__init__.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('validated')\n",
    )

    child = load(project, trusted)
    assert child.VALUE == "child"
    assert isinstance(sys.modules[PACKAGE], ModuleType)
    assert sys.modules[f"{PACKAGE}.plugins"].VALUE == "plugins"
    assert marker.read_text() == "validated"


def test_substituted_parent_in_sys_modules_is_rejected_and_preserved(tmp_path):
    project, trusted = package_chain(tmp_path, child_source="EXECUTED = True\n")
    external = write(tmp_path / "external_parent.py")
    rogue = ModuleType(PACKAGE)
    rogue.__spec__ = ModuleSpec(
        PACKAGE, SourceFileLoader(PACKAGE, str(external)), origin=str(external),
        is_package=True,
    )
    rogue.__file__ = str(external)
    rogue.__path__ = [str(external.parent)]
    sys.modules[PACKAGE] = rogue

    with pytest.raises(ModuleResolutionError, match="origin mismatch"):
        load(project, trusted)
    assert sys.modules[PACKAGE] is rogue
    assert f"{PACKAGE}.plugins.sample" not in sys.modules


def test_existing_correct_parent_is_not_executed_twice(tmp_path):
    counter = tmp_path / "counter"
    project, trusted = package_chain(tmp_path)
    write(
        project / PACKAGE / "__init__.py",
        "from pathlib import Path\n"
        f"p = Path({str(counter)!r})\n"
        "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')\n",
    )

    first = load(project, trusted)
    second = load(project, trusted)
    assert first is second
    assert counter.read_text() == "1"


def test_namespace_parent_is_rejected(tmp_path):
    project = tmp_path / "project"
    trusted = project / PACKAGE / "plugins"
    write(trusted / "__init__.py")
    write(trusted / "sample.py")
    with pytest.raises(ModuleResolutionError, match="SourceFileLoader"):
        load(project, trusted)


def test_parent_origin_outside_project_root_is_rejected(tmp_path, monkeypatch):
    project, trusted = package_chain(tmp_path)
    external = write(tmp_path / "outside" / "__init__.py")
    external_spec = ModuleSpec(
        PACKAGE,
        SourceFileLoader(PACKAGE, str(external)),
        origin=str(external),
        is_package=True,
    )
    external_spec.submodule_search_locations = [str(external.parent)]
    original = resolver_module._find_spec

    def outside_parent(fullname, path):
        if fullname == PACKAGE:
            return external_spec
        return original(fullname, path)

    monkeypatch.setattr(resolver_module, "_find_spec", outside_parent)
    with pytest.raises(ModuleResolutionError, match="outside project_root"):
        load(project, trusted)


def test_final_child_outside_trusted_root_is_rejected(tmp_path):
    project, _ = package_chain(tmp_path)
    trusted = project / "allowed"
    trusted.mkdir()
    with pytest.raises(ModuleResolutionError, match="outside trusted roots"):
        load(project, trusted)


def test_parent_symlink_escape_is_rejected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    external_package = tmp_path / "outside" / PACKAGE
    write(external_package / "__init__.py")
    write(external_package / "plugins" / "__init__.py")
    write(external_package / "plugins" / "sample.py")
    make_directory_symlink(project / PACKAGE, external_package)
    with pytest.raises(ModuleResolutionError, match="outside project_root"):
        resolve_module(
            f"{PACKAGE}.plugins.sample",
            project_root=project,
            trusted_roots=(project,),
        )


def test_trusted_root_symlink_escape_is_rejected(tmp_path):
    project, _ = package_chain(tmp_path)
    external = tmp_path / "external-trusted"
    external.mkdir()
    link = project / "trusted-link"
    make_directory_symlink(link, external)
    with pytest.raises(ModuleResolutionError, match="outside project_root"):
        resolve_module(
            f"{PACKAGE}.plugins.sample",
            project_root=project,
            trusted_roots=(link,),
        )


def test_child_exec_failure_cleans_added_sys_modules(tmp_path):
    project, trusted = package_chain(tmp_path, child_source="raise RuntimeError('boom')\n")
    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert not any(
        name == PACKAGE or name.startswith(PACKAGE + ".")
        for name in sys.modules
    )


def test_three_component_chain_rolls_back_all_resolver_state(tmp_path):
    project, trusted = package_chain(tmp_path, child_source="raise RuntimeError('plugin failed')\n")
    names = (
        PACKAGE,
        f"{PACKAGE}.plugins",
        f"{PACKAGE}.plugins.sample",
    )
    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert all(name not in sys.modules for name in names)


def test_mixed_preexisting_chain_preserves_parent_and_removes_new_children(tmp_path):
    project, trusted = package_chain(tmp_path, child_source="raise RuntimeError('plugin failed')\n")
    write(project / PACKAGE / "ready.py", "READY = True\n")
    load(project, project / PACKAGE, name=f"{PACKAGE}.ready")
    parent = sys.modules[PACKAGE]
    original_value = object()
    parent.original_value = original_value

    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert sys.modules[PACKAGE] is parent
    assert parent.original_value is original_value
    assert "plugins" not in parent.__dict__
    assert f"{PACKAGE}.plugins" not in sys.modules
    assert f"{PACKAGE}.plugins.sample" not in sys.modules


def test_failed_child_load_restores_existing_parent_attribute(tmp_path):
    source = (
        "import sys\n"
        "parent = sys.modules[__name__.rsplit('.', 1)[0]]\n"
        "parent.sample = object()\n"
        "raise RuntimeError('plugin failed')\n"
    )
    project, trusted = package_chain(tmp_path, child_source=source)
    load(project, trusted, name=f"{PACKAGE}.plugins")
    parent = sys.modules[f"{PACKAGE}.plugins"]
    original_value = object()
    parent.sample = original_value

    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert parent.sample is original_value
    assert f"{PACKAGE}.plugins.sample" not in sys.modules


def test_cleanup_preserves_preexisting_modules(tmp_path):
    project, trusted = package_chain(tmp_path)
    write(project / PACKAGE / "ready.py", "READY = True\n")
    ready = load(project, project / PACKAGE, name=f"{PACKAGE}.ready")
    parent = sys.modules[PACKAGE]
    write(trusted / "sample.py", "raise RuntimeError('boom')\n")

    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert sys.modules[PACKAGE] is parent
    assert sys.modules[f"{PACKAGE}.ready"] is ready
    assert f"{PACKAGE}.plugins.sample" not in sys.modules


def test_cleanup_removes_only_added_parent_attributes(tmp_path):
    project, trusted = package_chain(tmp_path, child_source="raise RuntimeError('boom')\n")
    write(project / PACKAGE / "ready.py", "READY = True\n")
    load(project, project / PACKAGE, name=f"{PACKAGE}.ready")
    parent = sys.modules[PACKAGE]
    assert hasattr(parent, "ready")
    assert not hasattr(parent, "plugins")

    with pytest.raises(ModuleResolutionError, match="RuntimeError"):
        load(project, trusted)
    assert not hasattr(parent, "plugins")
    assert hasattr(parent, "ready")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("__spec__.origin", "origin mismatch"),
        ("__file__", "__file__ mismatch"),
    ],
)
def test_post_exec_child_metadata_mismatch_is_rejected(tmp_path, field, message):
    alternate = write(tmp_path / "alternate.py")
    source = f"{field} = {str(alternate)!r}\n"
    project, trusted = package_chain(tmp_path, child_source=source)
    with pytest.raises(ModuleResolutionError, match=message):
        load(project, trusted)
    assert f"{PACKAGE}.plugins.sample" not in sys.modules


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("__spec__.origin", "origin mismatch"),
        ("__file__", "__file__ mismatch"),
        ("__path__", "__path__ mismatch"),
    ],
)
def test_parent_post_validation_metadata_mismatch_rejects_before_child(
    tmp_path, field, message,
):
    marker = tmp_path / "child-marker"
    project, trusted = package_chain(
        tmp_path,
        child_source=(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n"
        ),
    )
    alternate = write(tmp_path / "alternate.py")
    other = tmp_path / "other"
    other.mkdir()
    source = (
        f"__path__ = [{str(other)!r}]\n"
        if field == "__path__"
        else f"{field} = {str(alternate)!r}\n"
    )
    write(project / PACKAGE / "__init__.py", source)
    with pytest.raises(ModuleResolutionError, match=message) as caught:
        load(project, trusted)
    assert PACKAGE not in sys.modules
    assert f"{PACKAGE}.plugins" not in sys.modules
    assert f"{PACKAGE}.plugins.sample" not in sys.modules
    assert not marker.exists()
    assert caught.value.__cause__ is not None


def test_post_exec_sys_modules_replacement_is_rejected(tmp_path):
    source = "import sys, types\nsys.modules[__name__] = types.ModuleType(__name__)\n"
    project, trusted = package_chain(tmp_path, child_source=source)
    with pytest.raises(ModuleResolutionError, match="changed its sys.modules entry") as caught:
        load(project, trusted)
    assert f"{PACKAGE}.plugins.sample" not in sys.modules
    assert caught.value.__cause__ is not None


def test_cleanup_does_not_delete_later_foreign_sys_modules_object(tmp_path, monkeypatch):
    fullname = f"{PACKAGE}.plugins.sample"
    source = "import sys, types\nsys.modules[__name__] = types.ModuleType(__name__)\n"
    project, trusted = package_chain(tmp_path, child_source=source)
    original_cleanup = resolver_module._cleanup
    later_object = ModuleType(fullname)

    def install_later_object(module_rollbacks, attribute_rollbacks):
        sys.modules[fullname] = later_object
        original_cleanup(module_rollbacks, attribute_rollbacks)

    monkeypatch.setattr(resolver_module, "_cleanup", install_later_object)
    with pytest.raises(ModuleResolutionError, match="changed its sys.modules entry"):
        load(project, trusted)
    assert sys.modules[fullname] is later_object


@pytest.mark.parametrize("component", ["parent", "child"])
def test_exec_failures_preserve_original_exception_cause(tmp_path, component):
    project, trusted = package_chain(tmp_path)
    if component == "parent":
        write(project / PACKAGE / "__init__.py", "raise LookupError('parent failed')\n")
    else:
        write(trusted / "sample.py", "raise LookupError('child failed')\n")

    with pytest.raises(ModuleResolutionError, match="LookupError") as caught:
        load(project, trusted)
    assert isinstance(caught.value.__cause__, LookupError)
    assert str(tmp_path) not in str(caught.value)


def test_parent_side_effect_occurs_only_after_provenance_validation(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "external" / PACKAGE
    marker = tmp_path / "side-effect-marker"
    write(
        external / "__init__.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
    )
    write(external / "plugins" / "__init__.py")
    write(external / "plugins" / "sample.py")
    external_spec = ModuleSpec(
        PACKAGE,
        SourceFileLoader(PACKAGE, str(external / "__init__.py")),
        origin=str(external / "__init__.py"),
        is_package=True,
    )
    external_spec.submodule_search_locations = [str(external)]
    original = resolver_module._find_spec

    def outside_parent(fullname, path):
        if fullname == PACKAGE:
            return external_spec
        return original(fullname, path)

    monkeypatch.setattr(resolver_module, "_find_spec", outside_parent)

    with pytest.raises(ModuleResolutionError, match="outside project_root"):
        resolve_module(
            f"{PACKAGE}.plugins.sample",
            project_root=project,
            trusted_roots=(project,),
        )
    assert not marker.exists()
