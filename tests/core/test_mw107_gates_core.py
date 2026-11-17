"""Card MW-107 (concept line 1, kind K6): the three gates read the owner table through facts. Core tables: Facts to Verdict,
no disk, no git, every call under the guard that fails on any disk, process or clock access. One test id is one case. The
cores stay pure (they import nothing but `helpers`): the shells pass the table's answers as facts. Expected values are
written from the card rows, never computed. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core
import core_session as cs
import helpers
from _delete_world import judge
from _no_io import no_io

BUILTINS = frozenset(helpers.git_builtins())  # read before any guard: the shell hands it over as a fact
CARD_RE = r"(?<![A-Za-z0-9_-])CARD-[0-9]{3,}(?![0-9A-Za-z_])"
OUT = cs.OutsideRecord(raw="/x/other/conftest.py", abs="/x/other/conftest.py", matched=False)
OK = cs.OutsideRecord(raw="/h/.claude/plans/a.md", abs="/h/.claude/plans/a.md", matched=True)
LISTED = ("/h/.claude/plans/**", "/t/claude/**")
WAY_OUT = "write the file inside {root}; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable"  # R274 text
FOLDER = "mkway/cards/CARD-001-first"
ORDER_FIX = f"{FOLDER}/ORDER_fix1.md"
ASK = "mkway/asks/q_ask.md"


def case(id_, *values):
    return pytest.param(*values, id=id_)


def run(function, facts):
    """The verdict of `function` on the facts; `facts` is a thunk, built here so one id that cannot be built fails alone."""
    with no_io():
        return function(facts())


def subtask(*paths, **kw):
    """An edit by a session that holds the open card CARD-001 with the Paths `src/a.py`."""
    base = dict(paths=paths or ("src/a.py",), card_files="mkway/cards/*/CARD.md", card_id="CARD-001", card_found=True,
                card_status="open", recorded=frozenset({"src/a.py"}), now_paths=frozenset({"src/a.py"}),
                owner_fix="FIX", report_route="ROUTE")
    base.update(kw)
    return lambda: cs.SubtaskFacts(**base)


def holds_nothing(*paths, **kw):
    return subtask(*paths, card_id=None, card_found=False, card_status=None, recorded=frozenset(), now_paths=None, **kw)


def outside_of(paths, *records, listed=LISTED, root=""):
    """The facts of the outside gate's core: the repository forms (None: outside the root), one record for each, the list, the root."""
    return lambda: (paths, records, listed, root)


def decide_outside(args):
    return cs.decide_write_outside(*args)


@pytest.mark.parametrize("facts, reason", [
    case("outside-not-matched-is-refused", outside_of((None,), OUT), "write-outside-root"),
    case("outside-matched-is-allowed", outside_of((None,), OK), None),
    case("outside-with-no-record-is-refused", outside_of((None,)), "write-outside-root"),
    case("the-first-outside-path-not-matched-decides", outside_of(("src/a.py", None, None), OK, OUT), "write-outside-root"),
    case("matched-outside-and-an-inside-path-is-allowed", outside_of((None, "src/b.py"), OK), None),
    case("an-inside-path-is-not-judged-here", outside_of(("src/a.py",)), None),
])
def test_the_outside_core_refuses_a_write_outside_the_root_unless_the_shell_matched_it(facts, reason):
    """Catches: a write outside the root allowed for a session because the outside-writable list was never asked, or one on the list refused (R274e: the outside gate's own core)."""
    got = run(decide_outside, facts)
    assert (got.reason if got else None) == reason


@pytest.mark.parametrize("facts, reason", [
    case("a-path-outside-the-root-is-not-judged-by-the-card-rules", subtask(None), None),
    case("an-inside-path-after-it-is", subtask(None, "src/b.py"), "file-not-in-card"),
    case("no-open-card-is-judged-for-an-inside-path-only", holds_nothing(None, "src/a.py"), "no-open-card"),
])
def test_the_subtask_core_judges_the_card_rules_and_never_a_path_outside_the_root(facts, reason):
    """Catches: the card rules that judge a path outside the root, or that stop judging the inside paths next to one (the outside rule is the outside gate's since R274e)."""
    assert run(cs.decide_subtask, facts).reason == reason


def test_the_outside_refusal_names_the_path_the_list_and_the_way_out():
    """Catches: an outside refusal that does not say which path, which folders are open or how to get out."""
    text = run(decide_outside, outside_of((None,), OUT, root="/x/repo")).text
    assert text.startswith("/x/other/conftest.py is outside your root (/x/repo): a session writes only inside its root and in "
                           "these folders: /h/.claude/plans/**; /t/claude/**")
    assert text.endswith("Way out: " + WAY_OUT.format(root="/x/repo"))
    import owners
    assert cs.WAY_OUT_OUTSIDE == owners.WAY_OUT_OUTSIDE == WAY_OUT


@pytest.mark.parametrize("facts, reason, tail", [
    case("no-open-card", holds_nothing("src/a.py", owner_notes={"src/a.py": "NOTE-A"}), "no-open-card", " Owner table: NOTE-A"),
    case("file-not-in-card", subtask("src/b.py", owner_notes={"src/b.py": "NOTE-B"}), "file-not-in-card", " Owner table: NOTE-B"),
])
def test_the_subtask_refusals_end_with_the_owner_note_of_the_path(facts, reason, tail):
    """Catches: a subtask refusal that does not say who owns the file or which way out the table gives."""
    verdict = run(cs.decide_subtask, facts)
    assert (verdict.reason, verdict.text.endswith(tail)) == (reason, True)


def test_a_subtask_refusal_with_no_note_keeps_its_text():
    """Checks: a path with no owner note gets the text it always had, so no existing refusal changes."""
    assert "Owner table" not in run(cs.decide_subtask, subtask("src/b.py")).text


def lead(**kw):
    base = dict(is_lead=True, ask_dir="mkway/asks", writable=frozenset({ASK}))
    base.update(kw)
    return lambda: cs.LeadFacts(**base)


@pytest.mark.parametrize("function, facts", [
    case("edit", cs.decide_lead_edit, lead(paths=("src/app.py",), notes={"src/app.py": "NOTE-L"})),
    case("shell", cs.decide_lead_shell, lead(writes=(("src/app.py", "src/app.py"),), notes={"src/app.py": "NOTE-L"})),
])
def test_the_lead_refusals_end_with_the_owner_note_of_the_path(function, facts):
    """Catches: a lead refusal that does not say who owns the path or which way out the table gives."""
    verdict = run(function, facts)
    assert (verdict.reason, verdict.text.endswith(" Owner table: NOTE-L")) == ("lead-no-edit", True)


def commit(*rels, **kw):
    return lambda: core.CommitFacts(message="CARD-001 order", taken=tuple(("M", rel, "work") for rel in rels),
                                    sizes={rel: 1 for rel in rels}, ignored=frozenset(), **kw)


def facts(*commits, **kw):
    base = dict(command="git commit -m 'CARD-001 order'", git_builtins=BUILTINS, commits=(), card_id=None,
                card_found=False, card_status=None, card_paths=frozenset(), card_folder=None, card_id_pattern=CARD_RE,
                exempt=("mkway/cards/REGISTER.md", "mkway/ledger"), owner_fix="FIX")
    base.update(kw)
    return lambda: core.Facts(**base | {"commits": tuple(c() for c in commits)})


ORDERER = dict(ordered=(core.Ordered("CARD-001", FOLDER, frozenset({FOLDER})),), holders={"CARD-001": "b1"})


@pytest.mark.parametrize("f, reason", [
    case("order-file-the-paths-cover-and-the-table-gives-the-orderer",
         facts(commit(ORDER_FIX, roles={ORDER_FIX: "orderer"}), **ORDERER), None),
    case("the-same-file-with-no-role-stays-the-holders", facts(commit(ORDER_FIX), **ORDERER), "file-not-in-card"),
    case("a-file-the-table-gives-the-holder-stays-the-holders",
         facts(commit(ORDER_FIX, roles={ORDER_FIX: "holder"}), **ORDERER), "file-not-in-card"),
    case("a-file-in-the-leads-own-set-with-no-card-ordered", facts(commit(ASK, own=frozenset({ASK}))), None),
    case("the-same-file-outside-the-own-set-is-refused", facts(commit(ASK)), "file-not-in-card"),
    case("own-set-and-an-other-file-in-one-commit", facts(commit(ASK, "src/a.py", own=frozenset({ASK}))), "file-not-in-card"),
])
def test_the_commit_scope_of_the_orderer_reads_the_owner_table(f, reason):
    """Catches: an orderer that cannot commit an order file its card's Paths cover or an ask file, or a scope so wide it takes a holder's file."""
    verdict = run(core.decide_commit, f)
    assert (verdict.reason if verdict.kind == core.REFUSE else None) == reason


@pytest.mark.parametrize("f", [
    case("not-open", facts(commit("src/a.py", notes={"src/a.py": "NOTE-C"}))),
    case("the-holders-file", facts(commit(ORDER_FIX, notes={ORDER_FIX: "NOTE-C"}), **ORDERER)),
])
def test_a_commit_refusal_ends_with_the_owner_note_of_the_file(f):
    """Catches: a commit refusal that does not say who owns the file or which way out the table gives."""
    verdict = run(core.decide_commit, f)
    assert (verdict.reason, verdict.text.endswith(" Owner table: NOTE-C")) == ("file-not-in-card", True)


def test_the_delete_outside_root_refusal_names_its_way_out():
    """Catches: a delete outside the root refused with no word on what the session does next."""
    decision = judge("rm ../elsewhere.txt")
    assert decision.verdict.reason == "delete-outside-root"
    assert decision.verdict.message.endswith("name the path in your DONE line; the owner removes it")  # R274b: the chief's sentence
