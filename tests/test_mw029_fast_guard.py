"""Card MW-029: the copy guard is fast. Synthetic scratch folders only.

MW-025's guard ran the whole suite inside a copy (minutes). This guard collects the tests a copy would run
(`-m "not engine_repo"`) and reads their source: it fails when a collected test, or a helper, reads a path that
install does not copy. The helper is `tests/_copy_guard.py`.
"""
import re

import pytest

from _engine import REPO
import _copy_guard as guard

pytestmark = pytest.mark.engine_repo  # the guard collects the repository's own tests; a copy does not run it


def _reads(source):
    return guard.reads_outside_copy(source, root=REPO)


def test_no_collected_test_reads_a_path_a_copy_lacks():
    """E1: the tests a copy would run, and the helpers: none reads a path install does not copy."""
    lines, _seconds = guard.check_repo(REPO)
    assert not lines, "tests that read a file a copy does not have (mark them engine_repo):\n" + "\n".join(lines)


def test_the_guard_runs_in_under_ten_seconds():
    """E2: collection plus reading the sources of every collected file takes less than ten seconds."""
    _lines, seconds = guard.check_repo(REPO)
    assert seconds < 10, f"the guard took {seconds:.1f} s"


def test_the_guard_fails_when_a_marker_is_dropped(tmp_path):
    """E3: a scratch copy of one of MW-025's eight tests with its marker dropped: the guard names the test."""
    text = (REPO / "tests" / "test_mw016_version.py").read_text(encoding="utf-8")
    head, sep, tail = text.partition("def test_the_changelog_covers_the_register(")
    rows = head.rstrip("\n").split("\n")
    assert sep and "pytest.mark.engine_repo" in rows[-1], "the real test lost its marker line"
    marked = "\n".join(rows[:-1]) + "\n\n\n" + sep + tail
    scratch = tmp_path / "scratch" / "test_mw016_version.py"
    scratch.parent.mkdir()
    scratch.write_text(marked, encoding="utf-8")
    nodes = guard.collect(REPO, [scratch])
    assert any(n.endswith("::test_the_changelog_covers_the_register") for n in nodes), nodes
    lines = guard.guard(REPO, nodes)
    assert any("test_the_changelog_covers_the_register" in x and "reads" in x for x in lines), lines
    assert not any("test_the_readme_has_the_versioning_section" in x for x in lines), lines  # still marked: left out


def test_a_path_join_a_joinpath_and_an_os_join_are_seen():
    """E4: `REPO / "x"`, `REPO.joinpath("x")`, `os.path.join(REPO, "x")` and a path from the file's own place."""
    src = (
        "def test_a():\n    (REPO / 'README.md').read_text()\n"
        "def test_b():\n    REPO.joinpath('CHANGELOG.md').read_text()\n"
        "def test_c():\n    open(os.path.join(REPO, 'CHANGELOG.md'))\n"
        "def test_d():\n    (Path(__file__).resolve().parents[1] / 'README.md').read_text()\n"
        "def test_e():\n    (REPO / 'cards' / 'REGISTER.md').read_text()\n"
    )
    seen = {name for name, _path in _reads(src)}
    assert seen == {"test_a", "test_b", "test_c", "test_d", "test_e"}


def test_a_module_constant_and_a_helper_carry_the_read_to_the_test():
    """E5: `README = REPO / "README.md"` used in a test, and a helper that reads: both flag the tests that use them."""
    src = (
        "README = REPO / 'README.md'\n"
        "def _text():\n    return (REPO / 'CHANGELOG.md').read_text()\n"
        "def test_uses_constant():\n    README.read_text()\n"
        "def test_uses_helper():\n    _text()\n"
        "def test_uses_neither():\n    assert 1 + 1 == 2\n"
    )
    seen = {name for name, _path in _reads(src)}
    assert {"test_uses_constant", "test_uses_helper"} <= seen
    assert "test_uses_neither" not in seen


def test_copied_paths_and_scratch_paths_are_not_flagged():
    """E6: the engine, tools, tests, synthetic fixtures, VERSION, mkway.py and a tmp_path join are fine."""
    src = (
        "def test_a():\n    (REPO / 'engine' / 'manifest.json').read_text()\n"
        "def test_b():\n    (REPO / 'VERSION').read_text(); (REPO / 'mkway.py').read_text()\n"
        "def test_c(tmp_path):\n    (tmp_path / 'README.md').write_text('x')\n"
        "def test_d():\n    (REPO / 'fixtures' / 'synthetic').exists(); (REPO / 'tools' / name).exists()\n"
        "def test_e():\n    (REPO / 'cards' / '_TEMPLATE' / 'CARD.md').read_text()\n"
    )
    assert _reads(src) == []


def test_the_whole_suite_in_a_copy_test_is_gone_and_the_row_points_to_the_guard():
    """E7: MW-025's slow test is removed; its card row E1 names this card's guard test."""
    text = (REPO / "tests" / "test_mw025_copy_check.py").read_text(encoding="utf-8")
    assert "def test_the_tests_a_copy_runs_all_pass_in_a_copy" not in text
    card = (REPO / "cards" / "MW-025-copy-check" / "CARD.md").read_text(encoding="utf-8")
    row = next(x for x in card.splitlines() if x.startswith("| E1 |"))
    assert "tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks" in row


def test_register_changelog_and_card_name_the_card():
    """E8: the register row, a line under `## 0.2.6` of the changelog (moved from 0.2.2 when ported), the card folder."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-029 \| The copy guard is fast \|.*`cards/MW-029-[a-z0-9-]+`", register, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = changelog.split("\n## 0.2.6\n", 1)[1].split("\n## ", 1)[0]
    assert "- MW-029: The copy guard is fast" in top
    assert list((REPO / "cards").glob("MW-029-*/CARD.md"))
