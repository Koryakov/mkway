"""Card MW-029: the copy guard is fast. Synthetic scratch folders only.

MW-025's guard ran the whole suite inside a copy (minutes). This guard collects the tests a copy would run
(`-m "not engine_repo"`) and reads their source: it fails when a collected test, or a helper, reads a path that
install does not copy. The helper is `tests/_copy_guard.py`.
"""
import re

import pytest

import _docs as docs
from _engine import REPO
import _copy_guard as guard

pytestmark = pytest.mark.engine_repo  # the guard collects the repository's own tests; a copy does not run it


def _reads(source):
    return guard.reads_outside_copy(source, root=REPO)


def test_no_collected_test_reads_a_path_a_copy_lacks():
    """Checks: the tests a copy would run and the helpers read no path that install does not copy (E1)."""
    lines, _seconds = guard.check_repo(REPO)
    assert not lines, "tests that read a file a copy does not have (mark them engine_repo):\n" + "\n".join(lines)


@pytest.mark.perf
def test_the_guard_runs_in_under_ten_seconds():
    """Checks: collection plus reading the sources of every collected file takes less than ten seconds (E2, R172)."""
    _lines, seconds = guard.check_repo(REPO)
    assert seconds < 10, f"the guard took {seconds:.1f} s"


def test_the_guard_fails_when_a_marker_is_dropped(tmp_path):
    """Catches: a scratch copy of one of MW-025's eight tests with its marker dropped, which the guard must name (E3)."""
    text = (REPO / "tests" / "test_mw016_version.py").read_text(encoding="utf-8")
    head, sep, tail = text.partition("def test_the_changelog_covers_the_register(")
    rows = head.rstrip("\n").split("\n")
    assert sep, "the real test lost its marker line"
    assert "pytest.mark.engine_repo" in rows[-1], "the real test lost its marker line"
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
    """Catches: a read of REPO by a slash, joinpath or os.path.join form, or from the file's own place, that the guard misses (E4)."""
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
    """Catches: a constant or a helper that carries a read past the guard, so the tests that use them are not flagged (E5)."""
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
    """Checks: the engine, tools, tests, synthetic fixtures, VERSION, mkway.py and a tmp_path join are not flagged (E6)."""
    src = (
        "def test_a():\n    (REPO / 'engine' / 'manifest.json').read_text()\n"
        "def test_b():\n    (REPO / 'VERSION').read_text(); (REPO / 'mkway.py').read_text()\n"
        "def test_c(tmp_path):\n    (tmp_path / 'README.md').write_text('x')\n"
        "def test_d():\n    (REPO / 'fixtures' / 'synthetic').exists(); (REPO / 'tools' / name).exists()\n"
        "def test_e():\n    (REPO / 'cards' / '_TEMPLATE' / 'CARD.md').read_text()\n"
    )
    assert _reads(src) == []


def test_the_whole_suite_in_a_copy_test_is_gone_and_the_row_points_to_the_guard():
    """Checks: MW-025's slow test is removed and its card row E1 names this card's guard test (E7)."""
    text = (REPO / "tests" / "test_mw025_copy_check.py").read_text(encoding="utf-8")
    assert "def test_the_tests_a_copy_runs_all_pass_in_a_copy" not in text
    card = (REPO / "cards" / "MW-025-copy-check" / "CARD.md").read_text(encoding="utf-8")
    row = next(x for x in card.splitlines() if x.startswith("| E1 |"))
    assert "tests/test_mw029_fast_guard.py::test_no_collected_test_reads_a_path_a_copy_lacks" in row


def test_register_changelog_and_card_name_the_card():
    """Checks: the register row, a changelog line under 0.2.6 and the card folder name the card (E8)."""
    register = (REPO / "cards" / "REGISTER.md").read_text(encoding="utf-8")
    assert re.search(r"^\| MW-029 \| The copy guard is fast \|.*`cards/MW-029-[a-z0-9-]+`", register, re.M)
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    top = docs.changelog_section(changelog, "MW-029")
    assert "- MW-029: The copy guard is fast" in top
    assert list((REPO / "cards").glob("MW-029-*/CARD.md"))
