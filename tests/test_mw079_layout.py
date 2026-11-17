"""MW-079: the layout guards of the test tree. tests/shell is a package; tests/ root and tests/core are flat
(engine/core.py is imported as `core`, so a tests/core package would shadow it)."""
from collections import defaultdict
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ENGINE = TESTS.parent / "engine"


def package_names_like_an_engine_module():
    """Folders under tests/ that hold an __init__.py and carry the basename of an engine/*.py module."""
    engine_names = {p.stem for p in ENGINE.glob("*.py")}
    return sorted(
        str(p.parent.relative_to(TESTS))
        for p in TESTS.rglob("__init__.py")
        if "__pycache__" not in p.parts and p.parent.name in engine_names
    )


def shared_test_file_names():
    """`name: folders` for a test_*.py basename held by two flat folders (tests/ root, tests/core: they hold test
    modules and have no __init__.py). conftest.py, __init__.py, _*.py helpers and __pycache__ are out of scope."""
    folders = [TESTS] + [d for d in sorted(TESTS.iterdir()) if d.is_dir()]
    flat = [d for d in folders if not (d / "__init__.py").exists() and any(d.glob("test_*.py"))]
    held = defaultdict(list)
    for folder in flat:
        for path in folder.glob("test_*.py"):
            held[path.name].append(folder.name)
    return sorted(f"{name}: {', '.join(where)}" for name, where in held.items() if len(where) > 1)


def init_files_in_the_flat_folders():
    return sorted(str(p.relative_to(TESTS)) for p in (TESTS / "__init__.py", TESTS / "core" / "__init__.py") if p.exists())


def test_no_test_package_is_named_like_an_engine_module():
    """Checks: no test folder with an __init__.py has the name of an engine module (a package `core` would shadow it)."""
    violations = package_names_like_an_engine_module()
    assert violations == []


def test_no_flat_test_folder_shares_a_test_file_name_with_another():
    """Checks: no test_*.py file of tests/ root or tests/core has the basename of a file in another flat folder."""
    violations = shared_test_file_names()
    assert violations == []


def test_tests_root_and_tests_core_stay_flat():
    """Checks: tests/__init__.py and tests/core/__init__.py do not exist."""
    violations = init_files_in_the_flat_folders()
    assert violations == []
