"""Card rows and tests stay in step (card MW-040).

Every test id a card's acceptance row names exists in `tests/`; an id that moved is named by a line of the card's
`case_map.md` (`old_file::old_test -> new_file::new_test`, or `-> dropped: <why>`), and every right side exists.
Documents are read here only: no other test reads a card to judge a behaviour.
"""
import ast
import re
from functools import lru_cache

import pytest

from _engine import REPO
from core_red import parse_case_map

CARDS = REPO / "cards"
TESTS = REPO / "tests"
FULL = re.compile(r"(?:tests/)?((?:test_|_)[A-Za-z0-9_]*\.py)::([A-Za-z0-9_]+)")
WHOLE_CELL = re.compile(r"`(test_[A-Za-z0-9_]+)`")
ID_CELL = re.compile(r"[A-Z]\d+")


@lru_cache(maxsize=1)
def collected():
    """{file name: {test function names}} by AST, once per session (a `[param]` suffix is never part of a name). A file in
    a layer folder (`tests/core/`, `tests/shell/`; MW-064) is indexed by its name and by its path below `tests/`."""
    out = {}
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        out[path.name] = out.get(path.name, set()) | names
        out[path.relative_to(TESTS).as_posix()] = names
    return out


def row_ids(text):
    """The test ids the acceptance rows of one card name: `(file, name)` for a node id, `(None, name)` for a bare
    test name that fills a whole cell. A row is a table line whose first cell is an example id (E1, S2, ...)."""
    ids = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not ID_CELL.fullmatch(cells[0]):
            continue
        for cell in cells[1:]:
            ids += [(f, n) for f, n in FULL.findall(cell)]
            if WHOLE_CELL.fullmatch(cell):
                ids.append((None, WHOLE_CELL.fullmatch(cell).group(1)))
    return ids


def parse_map(text):
    """(`old id` -> right side or None for a dropped case, malformed lines) of one case_map.md."""
    mapping, bad = {}, []
    for entry in parse_case_map(text):
        if entry.kind == "mapping":
            mapping[entry.old.removeprefix("tests/")] = entry.new.removeprefix("tests/")
        elif entry.kind == "dropped":
            mapping[entry.old.removeprefix("tests/")] = None
        elif entry.kind == "malformed":
            bad.append(entry.raw.strip())
    return mapping, bad


def exists(file, name, defs):
    if file is None:
        return any(name in names for names in defs.values())
    return name in defs.get(file, ())


def missing_without_map(card_texts, maps, defs):
    """`card: id` for every id a row names that is not in `defs` and has no case_map line."""
    out = []
    for card, text in card_texts.items():
        for file, name in row_ids(text):
            if not exists(file, name, defs) and f"{file}::{name}" not in maps:
                out.append(f"{card}: {file or 'bare'}::{name}")
    return out


def _read_cards():
    return {p.parent.name: p.read_text(encoding="utf-8") for p in sorted(CARDS.glob("MW-*/CARD.md"))}


def _read_maps():
    maps, bad = {}, []
    for p in sorted(CARDS.glob("MW-*/case_map.md")):
        m, b = parse_map(p.read_text(encoding="utf-8"))
        maps.update(m)
        bad += [f"{p.parent.name}: {x}" for x in b]
    return maps, bad


@pytest.mark.engine_repo  # MW-025: cards and the changelog are not in an installed copy
def test_every_test_id_a_card_row_names_exists_or_has_a_case_map_line():
    maps, _bad = _read_maps()
    lost = missing_without_map(_read_cards(), maps, collected())
    assert not lost, "card rows name tests that do not exist (fix the row, or map the case in case_map.md):\n" + "\n".join(lost)


@pytest.mark.engine_repo  # MW-025: cards and the changelog are not in an installed copy
def test_every_case_map_line_is_well_formed_and_its_right_side_exists():
    maps, bad = _read_maps()
    assert not bad, "malformed case_map lines (want `old_file::old_test -> new_file::new_test` or `-> dropped: why`): " + "; ".join(bad)
    defs = collected()
    gone = [f"{old} -> {new}" for old, new in maps.items()
            if new is not None and not exists(*new.split("::", 1), defs)]
    assert not gone, "case_map right sides that do not exist: " + "; ".join(gone)


def test_the_checker_catches_a_missing_id_and_accepts_a_mapped_one():
    """C5: the checker can fail. Synthetic card text and a synthetic test index."""
    defs = {"test_a.py": {"test_here"}}
    card = {"X": "| E1 | i | was | must | tests/test_a.py::test_here; tests/test_a.py::test_gone |\n"
                 "| E2 | `test_nowhere` | w | m | tests/test_a.py |\n"
                 "| 2026-01-01 | log | tests/test_zz.py::test_ignored | r |\n"}
    assert missing_without_map(card, {}, defs) == ["X: test_a.py::test_gone", "X: bare::test_nowhere"]
    assert missing_without_map(card, {"test_a.py::test_gone": "test_a.py::test_here", "None::test_nowhere": None}, defs) == []
    assert parse_map("# note\ntests/a.py::t -> b.py::u\nc.py::v -> dropped: covered by doc\nbroken line\n") == (
        {"a.py::t": "b.py::u", "c.py::v": None}, ["broken line"])


@pytest.mark.engine_repo  # MW-025: cards and the changelog are not in an installed copy
def test_register_changelog_and_card_name_the_card():
    """E4: the register row, one changelog line under the release that names the card, the card file."""
    import _docs as docs
    register = (CARDS / "REGISTER.md").read_text(encoding="utf-8")
    assert "| MW-040 | Card rows and tests stay in step | proposed | `cards/MW-040-meta-cards-tests` |" in register
    section = docs.changelog_section((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), "MW-040")
    assert "- MW-040: Card rows and tests stay in step" in section.splitlines()
    docs.assert_version_file()
    assert (CARDS / "MW-040-meta-cards-tests" / "CARD.md").is_file()


@pytest.mark.engine_repo  # MW-025: cards and the changelog are not in an installed copy
def test_changelog_releases_run_newest_first():
    """The release order is read once here; no card test pins one release above another."""
    heads = re.findall(r"^## (\d+\.\d+\.\d+)$", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    keys = [tuple(int(x) for x in h.split(".")) for h in heads]
    assert keys == sorted(keys, reverse=True) and len(set(keys)) == len(keys), heads
    assert heads[0] == (REPO / "VERSION").read_text(encoding="utf-8").strip()
