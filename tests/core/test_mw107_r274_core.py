"""Card MW-107 (ruling R274, section 5): the pure cores give a write outside the root one reason and one text for every
session: the path as written, the root, the list and the way out. Core tables: Facts to Verdict, no disk, no git, every call
under the guard that fails on any disk, process or clock access. One test id is one case. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as cs
from _no_io import no_io

ROOT = "/x/repo"
OUT = cs.OutsideRecord(raw="/x/sibling/conftest.py", abs="/x/sibling/conftest.py", matched=False)
LISTED = ("/h/.claude/plans/**", "/t/claude/**")
WAY_OUT = "write the file inside /x/repo; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable"
ORDER = "mkway/cards/CARD-001-first/ORDER.md"


def case(id_, *values):
    return pytest.param(*values, id=id_)


def outside_of(*records, root=ROOT, listed=LISTED):
    """The facts of the outside gate's core for one path outside the root (R274e: the session check is its own gate)."""
    return lambda: ((None,), records, listed, root)


def decide_outside(args):
    return cs.decide_write_outside(*args)


def lead(**kw):
    base = dict(is_lead=True, ask_dir="mkway/asks", writable=frozenset({ORDER}), outside_list=LISTED)
    base.update(kw)
    return lambda: cs.LeadFacts(**base)


def run(function, facts):
    with no_io():
        return function(facts())


def test_one_reason_and_one_text_for_a_lead_and_a_session():
    """Catches: the same outside write refused with one text for a lead and another for a session (R274 5.6: one reason, one text)."""
    by_session = run(decide_outside, outside_of(OUT))
    by_lead_edit = run(cs.decide_lead_edit, lead(paths=(None,), outside=(OUT,), root=ROOT))
    by_lead_shell = run(cs.decide_lead_shell, lead(writes=((OUT.raw, None),), outside=(OUT,), root=ROOT))
    assert (by_session.reason, by_lead_edit.reason, by_lead_shell.reason) == ("write-outside-root",) * 3
    assert by_session.text == by_lead_edit.text == by_lead_shell.text


def test_the_outside_text_names_the_path_the_root_the_list_and_the_way_out():
    """Catches: an outside refusal that leaves out one of the four things the ruling names: the path as written, the root, the list, the way out."""
    text = run(decide_outside, outside_of(OUT)).text
    assert text == (f"{OUT.raw} is outside your root ({ROOT}): a session writes only inside its root and in these folders: "
                    f"/h/.claude/plans/**; /t/claude/**. Way out: {WAY_OUT}")


def test_a_text_with_no_root_fact_says_your_root():
    """Checks: facts that carry no root still refuse with a text that names the way out (the shell that forgot the fact never opens the gate)."""
    text = run(decide_outside, outside_of(OUT, root="")).text
    assert text.endswith("Way out: write the file inside your root; a file the task needs elsewhere is a folder the owner "
                         "adds to paths.outside_writable")


@pytest.mark.parametrize("function, facts, reason", [
    case("edit-inside-the-root-not-writable", cs.decide_lead_edit, lead(paths=("src/app.py",), root=ROOT), "lead-no-edit"),
    case("shell-inside-the-root-not-writable", cs.decide_lead_shell,
         lead(writes=(("src/app.py", "src/app.py"),), root=ROOT), "lead-no-edit"),
    case("shell-a-path-the-gate-cannot-read", cs.decide_lead_shell, lead(writes=(("$X/a.md", None),), root=ROOT), "lead-no-edit"),
    case("shell-a-program-that-writes-anywhere", cs.decide_lead_shell, lead(writes_anywhere=True, root=ROOT), "lead-no-edit"),
    case("edit-outside-the-root", cs.decide_lead_edit, lead(paths=(None,), outside=(OUT,), root=ROOT), "write-outside-root"),
    case("take-a-card", cs.decide_lead_shell, lead(takes_card=True, root=ROOT), "lead-no-take"),
])
def test_the_lead_keeps_its_own_reasons_inside_the_root_and_for_an_unreadable_write(function, facts, reason):
    """Checks: R274 5.6 and 5.5, the lead's row is unchanged in effect: only the outside case moved to the common reason; an unreadable write by a lead stays refused."""
    assert run(function, facts).reason == reason


def test_a_session_unreadable_write_is_not_judged_by_the_core():
    """Checks: R274 5.5, a session that is no lead is not judged by the lead core at all (the subtask shell passes only the paths it can read)."""
    assert run(cs.decide_lead_shell, lead(is_lead=False, writes=(("$X/a.md", None),), writes_anywhere=True)).kind == "allow"


CHECKOUT = cs.OutsideRecord(raw="/x/repo/.claude/worktrees/wt/src/a.py", abs="/x/repo/.claude/worktrees/wt/src/a.py", matched=False,
                            checkout=True)  # R274a 8.4: the path lies in another checkout of the same repository


def test_a_write_into_another_checkout_names_the_way_to_hand_a_brief_over():
    """Catches: R274a 8.4, a refusal of a write into another session's checkout that does not say how a brief for that session travels: the orderer's own checkout, or `mkway send`."""
    text = run(decide_outside, outside_of(CHECKOUT)).text
    assert text.startswith(f"{CHECKOUT.raw} is outside your root ({ROOT}): a session writes only inside its root")  # the R274 text first
    assert text.endswith("Way out: " + WAY_OUT + " " + cs.WAY_OUT_CHECKOUT)
    assert ("the orderer's own checkout", "`mkway send`", "never write into another session's checkout") == tuple(
        part for part in ("the orderer's own checkout", "`mkway send`", "never write into another session's checkout") if part in cs.WAY_OUT_CHECKOUT)


def test_a_write_outside_any_checkout_keeps_the_text_without_the_brief_sentence():
    """Checks: the sentence about a brief is for a write into another checkout only; the plain outside text stays as the ruling wrote it."""
    assert "mkway send" not in run(decide_outside, outside_of(OUT)).text


def test_a_lead_edit_into_another_checkout_names_the_same_way_out():
    """Catches: the lead's text for the same write that differs from the session's (one reason, one text, R274 5.6)."""
    by_lead = run(cs.decide_lead_edit, lead(paths=(None,), outside=(CHECKOUT,), root=ROOT)).text
    assert by_lead == run(decide_outside, outside_of(CHECKOUT)).text
