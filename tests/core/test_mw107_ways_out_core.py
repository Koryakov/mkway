"""Card MW-107 (concept line 3: every refusal names a way out that works, and a test proves it): for each refusal of the owner
rules, the call is refused, its text names the way out, and the same call after that way out is allowed. Core tables, no
disk, no git; every call under the guard that fails on any disk, process or clock access. One test id is one case.
Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as cs
from _no_io import no_io

CLI = "python mkway/engine/mkway.py"
OUT = cs.OutsideRecord(raw="/x/other/conftest.py", abs="/x/other/conftest.py", matched=False)
ORDER = "mkway/cards/CARD-001-first/ORDER.md"


def case(id_, *values):
    return pytest.param(*values, id=id_)


def card(*paths, **kw):
    """A thunk of the facts of an edit by a session that holds the open card CARD-001 with the Paths `src/a.py` (built when
    the test runs, so one id that cannot be built fails alone)."""
    base = dict(paths=paths or ("src/a.py",), card_files="mkway/cards/*/CARD.md", card_id="CARD-001", card_found=True,
                card_status="open", recorded=frozenset({"src/a.py"}), now_paths=frozenset({"src/a.py"}),
                owner_fix="FIX", report_route="ROUTE")
    base.update(kw)
    return lambda: cs.SubtaskFacts(**base)


def no_card(*paths, **kw):
    return card(*paths, card_id=None, card_found=False, card_status=None, recorded=frozenset(), now_paths=None, **kw)


def outside_of(*records, paths=(None,)):
    """The facts of the outside gate's core (R274e): the repository forms, one record for each path outside the root."""
    return lambda: (paths, records, (), "")


def decide_outside(args):
    """The outside gate's core, with an allow verdict for the call that has nothing to refuse."""
    return cs.decide_write_outside(*args) or cs.allow()


def lead(**kw):
    base = dict(is_lead=True, ask_dir="mkway/asks", writable=frozenset({ORDER}))
    base.update(kw)
    return lambda: cs.LeadFacts(**base)


@pytest.mark.parametrize("decide, bad, reason, fragment, good", [
    case("no-open-card", cs.decide_subtask, no_card("src/a.py"), "no-open-card", f"`{CLI} card take <id>`", card("src/a.py")),
    case("card-not-open", cs.decide_subtask, card(card_status="proposed"), "card-not-open",
         f"the owner's `{CLI} card open CARD-001`", card(card_status="open")),
    case("card-paths-changed", cs.decide_subtask, card(now_paths=frozenset({"src/a.py", "src/b.py"})), "card-paths-changed",
         "restore them", card(now_paths=frozenset({"src/a.py"}))),
    case("file-not-in-card", cs.decide_subtask, card("src/b.py"), "file-not-in-card",
         f"the lead that ordered the card adds it to its Paths: `{CLI} card paths CARD-001 --add <entry>`",
         card("src/b.py", recorded=frozenset({"src/a.py", "src/b.py"}), now_paths=frozenset({"src/a.py", "src/b.py"}))),
    case("lead-no-edit", cs.decide_lead_edit, lead(paths=("src/app.py",)), "lead-no-edit",
         "Write the order there and hand the work to a builder", lead(paths=(ORDER,))),
    case("lead-no-take", cs.decide_lead_shell, lead(takes_card=True), "lead-no-take",
         "Hand the work to a builder session", lead(is_lead=False, takes_card=True)),
    case("write-outside-root", decide_outside, outside_of(OUT), "write-outside-root",
         "write the file inside your root; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable",
         outside_of(paths=("src/a.py",))),
    case("write-outside-root-by-a-lead", cs.decide_lead_edit, lead(paths=(None,), outside=(OUT,)), "write-outside-root",
         "write the file inside your root; a file the task needs elsewhere is a folder the owner adds to paths.outside_writable",
         lead(paths=(ORDER,))),
    case("lead-no-edit-unreadable-path", cs.decide_lead_shell, lead(writes=(("$X/q_ask.md", None),)), "lead-no-edit",
         "write a plain path with no variable or wildcard, or use the edit tool", lead(writes=((ORDER, ORDER),))),
])
def test_the_way_out_of_each_refusal_works(decide, bad, reason, fragment, good):
    """Catches: a refusal whose named way out does not exist or does not let the same call through."""
    with no_io():
        refused, allowed = decide(bad()), decide(good())
    assert (refused.reason, fragment in refused.text, allowed.kind) == (reason, True, "allow")
