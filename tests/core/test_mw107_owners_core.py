"""Card MW-107 (concept line 1, kind K6): the owner table `engine/owners.py` as table tests on a profile and a path. Pure:
every call runs under the guard that fails on any disk, process or clock access. One test id is one case (parametrize ids).
Expected values are written from the card rows, never computed by the code under test. Synthetic values only."""
import ast
from pathlib import Path

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core
import core_session
from _no_io import no_io

OWNERS = Path(__file__).resolve().parents[2] / "engine" / "owners.py"
PROFILE = {"bundle": {"root": "mkway"}, "state": {"dir": "mkway/state"}, "owner_ask": {"dir": "mkway/asks"},
           "outbox": {"dir": "out"}, "paths": {"exempt": ["notes/**"]}}
CARDS = "mkway/cards/CARD-001-first"


def case(id_, *values):
    return pytest.param(*values, id=id_)


def missing(fragments, text):
    """The fragments the text lacks."""
    return [f for f in fragments if f not in text]


def scan(path):
    """(top-level modules imported, names called) of a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "").split(".")[0])
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    return modules, calls


@pytest.mark.parametrize("path, role, kind", [
    case("card-file", f"{CARDS}/CARD.md", "orderer", "card-file"),
    case("order-file", f"{CARDS}/ORDER.md", "orderer", "order-file"),
    case("order-file-of-a-fix-round", f"{CARDS}/ORDER_fix1.md", "orderer", "order-file"),
    case("register", "mkway/cards/REGISTER.md", "engine", "register"),
    case("ask-file", "mkway/asks/q_ask.md", "orderer", "asks"),
    case("quote-file-in-asks", "mkway/asks/q_quote.md", "orderer", "asks"),
    case("ledger-rows", "mkway/ledger/ledger.md", "engine", "ledger"),
    case("quote-file-in-ledger", "mkway/ledger/quote_1.md", "orderer", "quote-file"),
    case("verdict-file", "tests/verdicts/CARD-001.md", "orderer", "verdict-file"),
    case("inbox", "mkway/state/inbox/s1.jsonl", "engine", "inbox"),
    case("pings", "mkway/state/pings.jsonl", "engine", "inbox"),
    case("state", "mkway/state/refusals.jsonl", "engine", "state"),
    case("outbox-text", "out/report.md", "holder", "outbox"),
    case("outbox-check", "out/report.check.md", "reader", "outbox-check"),
    case("install-engine", "mkway/engine/core.py", "owner", "install"),
    case("install-profile", "mkway/profile.json", "owner", "install"),
    case("exempt-by-the-profile", "notes/today.md", "any", "exempt"),
])
def test_owner_of_names_the_one_owner_of_each_file_kind(path, role, kind):
    """Catches: a file kind with two owners, none, or the wrong one (card file, order file, register, asks, ledger, quote file, verdict file, inbox, state, outbox, install, exempt)."""
    import owners
    with no_io():
        got = (owners.owner_of(path, PROFILE), owners.kind_of(path, PROFILE).name)
    assert got == (role, kind)


@pytest.mark.parametrize("path, fragments", [
    case("order-file", f"{CARDS}/ORDER_fix1.md", ("the orderer's", "`mkway card new <title>`")),
    case("card-file", f"{CARDS}/CARD.md", ("the orderer's", "`mkway card new <title>`")),
    case("register", "mkway/cards/REGISTER.md", ("the engine's", "`mkway card new|take|open|set|close`")),
    case("asks", "mkway/asks/q_ask.md", ("the orderer's", "the ask file and its sources file")),
    case("verdict-file", "tests/verdicts/CARD-001.md", ("the orderer's", "`mkway verdict add`")),
    case("inbox", "mkway/state/inbox/s1.jsonl", ("the engine's", "`mkway send`")),
    case("install", "mkway/engine/core.py", ("the owner's", "`mkway install` or `mkway upgrade` in their own terminal")),
    case("outbox-check", "out/report.check.md", ("the reader's", "the checker agent")),
])
def test_the_text_of_a_kind_names_the_owner_role_and_the_command_that_writes_it(path, fragments):
    """Catches: a refusal text that does not say who owns the file or which command writes it."""
    import owners
    with no_io():
        text = owners.describe(path, PROFILE)
    assert missing(fragments, text) == []


@pytest.mark.parametrize("path", [case("code", "src/app.py"), case("root", "."), case("deep", "a/b/c.txt")])
def test_a_path_no_row_matches_has_no_owner_and_the_text_names_the_way_out(path):
    """Catches: a path no row matches that gets an owner by accident, or a text that leaves the session without a way out."""
    import owners
    with no_io():
        got = (owners.owner_of(path, PROFILE), owners.describe(path, PROFILE))
    assert got[0] is None
    assert "a card whose Paths hold it, or the profile names the kind (`paths.exempt`)" in got[1]


@pytest.mark.parametrize("matched, role", [case("matched", True, "any"), case("not-matched", False, None)])
def test_an_outside_target_has_an_owner_only_when_the_shell_matched_the_list(matched, role):
    """Catches: an outside target that is owned without the outside-writable list naming it, or one on the list that is not."""
    import owners
    record = core_session.OutsideRecord(raw="/x/y.txt", abs="/x/y.txt", matched=matched)
    with no_io():
        got = owners.owner_of(None, PROFILE, outside=record)
    assert got == role


def test_the_outside_text_names_the_way_out_of_an_unowned_target():
    """Catches: an outside refusal that names no way out."""
    import owners
    record = core_session.OutsideRecord(raw="/x/y.txt", abs="/x/y.txt", matched=False)
    with no_io():
        text = owners.describe(None, PROFILE, outside=record)
        named = owners.describe(None, PROFILE, outside=record, root="/x/repo")
    assert "write the file inside your root; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable" in text
    assert "write the file inside /x/repo; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable" in named


def test_the_owner_table_module_imports_only_pure_modules():
    """Catches: an owner table that reads a file, a process or the clock itself instead of being data and one function."""
    modules, calls = scan(OWNERS)
    assert modules <= {"__future__", "typing", "helpers", "profiles"}
    assert not calls & {"open", "print", "input", "exec", "eval", "__import__", "compile"}


@pytest.mark.parametrize("name", [case("card-md", "CARD.md"), case("order-md", "ORDER.md")])
def test_the_table_and_the_commit_core_agree_on_the_files_the_orderer_owns(name):
    """Catches: a commit core whose list of orderer files drifts from the owner table."""
    import owners
    with no_io():
        role = owners.owner_of(f"{CARDS}/{name}", PROFILE)
    assert (role, name.lower() in core.ORDERER_OWN) == ("orderer", True)
