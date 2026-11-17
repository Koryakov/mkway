"""Card MW-103 (rulings R255, R255b): the pure core of the lead gate judges a path outside the repository by the record the
shell passed. No disk, no git: each row builds a LeadFacts and reads the verdict. Expected values are written from the
rule, never computed by the code under test. Synthetic values only."""
import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_session as core
from _no_io import no_io

ORDER = "mkway/cards/CARD-001-first/ORDER.md"
ASKS = "mkway/asks"
LISTED = ("/h/.claude/plans/**", "/t/claude/**")
NOTES = "/x/project_x/analysis/notes/a.md"
MEMORY = "/h/.claude/projects/p/memory/m.md"


def run(function, facts):
    with no_io():
        return function(facts)


def case(id_, *values):
    return pytest.param(*values, id=id_)


def lead(**kw):
    base = dict(is_lead=True, ask_dir=ASKS, writable=frozenset({ORDER}), outside_list=LISTED)
    base.update(kw)
    return core.LeadFacts(**base)


def record(raw, matched):
    return core.OutsideRecord(raw=raw, abs=raw, matched=matched)


def test_a_lead_edit_outside_the_repository_that_matches_nothing_is_refused():
    """Catches: a lead that writes note files outside the repository because the path is «not judged» (R255 3b)."""
    verdict = run(core.decide_lead_edit, lead(paths=(None,), outside=(record(NOTES, False),)))
    assert (verdict.reason, NOTES in verdict.text) == ("write-outside-root", True)  # R274-D1: the common reason


def test_a_lead_edit_outside_the_repository_that_matches_the_list_is_allowed():
    """Checks: the nearest allow of E1, the same outside path when the shell says it matches the list (R255b)."""
    assert run(core.decide_lead_edit, lead(paths=(None,), outside=(record(MEMORY, True),))).reason is None


def test_two_outside_edit_records_one_unmatched_is_refused_naming_it():
    """Catches: a refusal that names the matched path, or lets the pair through because one of them is listed."""
    verdict = run(core.decide_lead_edit, lead(paths=(None, None), outside=(record(MEMORY, True), record(NOTES, False))))
    assert (verdict.reason, NOTES in verdict.text, MEMORY in verdict.text) == ("write-outside-root", True, False)  # R274-D1


def test_a_lead_own_order_file_is_still_allowed():
    """Checks: a lead's ORDER.md of its own card, inside the repository, stays allowed when an outside record is present."""
    assert run(core.decide_lead_edit, lead(paths=(ORDER, None), outside=(record(MEMORY, True),))).reason is None


def test_a_session_that_is_no_lead_is_not_judged_outside():
    """Checks: a session that is no lead writes outside the repository and is not judged, whatever the record says."""
    assert run(core.decide_lead_edit, lead(is_lead=False, paths=(None,), outside=(record(NOTES, False),))).reason is None


def test_an_outside_path_with_no_record_is_refused():
    """Catches: a shell that forgot the record, which must read as refused, never as allowed."""
    assert run(core.decide_lead_edit, lead(paths=(None,))).reason == "write-outside-root"  # R274-D1


@pytest.mark.parametrize("facts, reason, named", [
    case("unmatched-is-refused-naming-it", lead(writes=((NOTES, None),), outside=(record(NOTES, False),)), "write-outside-root", NOTES),
    case("matched-is-allowed", lead(writes=((MEMORY, None),), outside=(record(MEMORY, True),)), None, ""),
    case("one-of-each-is-refused-naming-the-unmatched",
         lead(writes=((MEMORY, None), (NOTES, None)), outside=(record(MEMORY, True), record(NOTES, False))),
         "write-outside-root", NOTES),
    case("no-lead-is-not-judged", lead(is_lead=False, writes=((NOTES, None),), outside=(record(NOTES, False),)), None, ""),
    case("order-and-a-matched-path-is-allowed", lead(writes=((ORDER, ORDER), (MEMORY, None)), outside=(record(MEMORY, True),)),
         None, ""),
])
def test_a_lead_shell_write_outside_is_judged_by_its_record(facts, reason, named):
    """Catches: a shell write outside the repository that passes unjudged, or a matched one that is refused."""
    verdict = run(core.decide_lead_shell, facts)
    assert (verdict.reason, named in verdict.text) == (reason, True)


@pytest.mark.parametrize("fragment", [
    case("names-the-path", NOTES + " is outside your root (/x/repo)"),  # R274-D1: the common text
    case("prints-the-passed-list", "/h/.claude/plans/**; /t/claude/**"),
    case("names-the-way-out", "write the file inside /x/repo; a file the task needs elsewhere is a folder the owner "
                              "adds to paths.outside_writable"),  # R274-D1 (10): the case was named for the old builder route
])
def test_the_outside_refusal_names_the_path_and_the_passed_list(fragment):
    """Catches: an outside refusal that does not name the path, hides the list the lead may write, or names no way out (write the file inside the root, or the owner adds the folder to `paths.outside_writable`, the one R274 text)."""
    verdict = run(core.decide_lead_edit, lead(paths=(None,), outside=(record(NOTES, False),), root="/x/repo"))
    assert fragment in verdict.text


def test_a_variable_path_is_refused_before_its_record_is_read():
    """Catches: a path with a variable that is let through because its record says matched."""
    verdict = run(core.decide_lead_shell, lead(writes=(("$HOME/x.md", None),), outside=(record("$HOME/x.md", True),)))
    assert (verdict.reason, "a path the gate cannot read" in verdict.text) == ("lead-no-edit", True)
