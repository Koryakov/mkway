"""Card MW-068, layer core: the decision of the close-time verdict check, as a table. No disk, no git, no clock.
Synthetic node ids, names and readers only. Each expected value is written from the card rows, never from `decide`."""
import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdicts import Facts, Row, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"
OTHER = "tests/test_b.py::test_two"


def facts(rows=(Row(NODE, "true", "one clause, one case", "session:reader"),), authors=None, nodes=(NODE,),
          holder="session:holder", committers=None, unproven=None):
    """The nearest allow: one named node, a `true` row by a reader who is neither an author of the file nor the holder
    nor a session in the commit records of the file (`committers`: test file -> the sessions of its commit records),
    and whose row has its proof (`unproven`: node -> why a row has none; none by default)."""
    extra = {} if committers is None else {"committers": committers}
    extra |= {} if unproven is None else {"unproven": unproven}
    return Facts(nodes=tuple(nodes), rows=tuple(rows),
                 authors={"tests/test_a.py": frozenset({"writer"})} if authors is None else authors, holder=holder,
                 **extra)


def reasons(verdict):
    return [(r.node, r.reason) for r in verdict.refusals]


def test_a_true_row_by_another_reader_is_allowed():
    """The nearest allow of every refusal: the smallest change of each deny below flips it back to this."""
    assert decide(facts()).allowed


def test_a_node_with_no_row_is_refused_as_missing():
    """Catches: a card closed on a test nobody judged."""
    verdict = decide(facts(rows=()))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-missing")]


def test_a_row_by_an_author_of_the_test_file_is_refused():
    """Catches: a test judged by the caller who wrote it, which is no blind verdict."""
    verdict = decide(facts(rows=(Row(NODE, "true", "fine", "writer"),)))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-by-author")]
    assert "writer" in verdict.refusals[0].text


def test_a_weak_row_is_refused():
    """Catches: a card closed on a test the reader called weak."""
    verdict = decide(facts(rows=(Row(NODE, "weak", "no Catches line", "session:reader"),)))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-weak")]
    assert "no Catches line" in verdict.refusals[0].text


def test_a_wrong_row_is_refused():
    """Catches: a card closed on a test the reader called wrong."""
    verdict = decide(facts(rows=(Row(NODE, "wrong", "expects the code's own output", "session:reader"),)))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-wrong")]
    assert "expects the code's own output" in verdict.refusals[0].text


@pytest.mark.parametrize("has_row, by_author, by_holder, word, expected", [
    (False, False, False, None, ["verdict-missing"]),
    (True, False, False, "true", []),
    (True, False, False, "weak", ["verdict-weak"]),
    (True, False, False, "wrong", ["verdict-wrong"]),
    (True, True, False, "true", ["verdict-by-author"]),
    (True, True, False, "weak", ["verdict-by-author"]),
    (True, True, False, "wrong", ["verdict-by-author"]),
    (True, False, True, "true", ["verdict-by-holder"]),
    (True, False, True, "weak", ["verdict-by-holder"]),
    (True, False, True, "wrong", ["verdict-by-holder"]),
    (True, True, True, "true", ["verdict-by-author"]),
    (True, True, True, "weak", ["verdict-by-author"]),
    (True, True, True, "wrong", ["verdict-by-author"]),
])
def test_every_combination_of_the_facts_has_its_verdict(has_row, by_author, by_holder, word, expected):
    """Catches: a combination of the facts that is allowed or refused for the wrong reason (an author's or a holder's
    `true` that passes, an author's `weak` named as weak instead of as an author's row)."""
    by = "writer" if by_author else "session:holder" if by_holder else "session:reader"
    rows = (Row(NODE, word, "r", by),) if has_row else ()
    assert [r.reason for r in decide(facts(rows=rows)).refusals] == expected


def test_a_row_by_the_holder_session_of_the_card_is_refused():
    """Catches: the session that built the card judging its own tests (it needs no commit record: the holder is known)."""
    verdict = decide(facts(rows=(Row(NODE, "true", "fine", "session:holder"),)))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-by-holder")]
    assert "holder" in verdict.refusals[0].text


def test_a_card_with_no_holder_has_no_holder_refusal():
    """Catches: an empty holder equal to an empty `by`, or a refusal on a card nobody holds."""
    assert decide(facts(holder="")).allowed
    assert decide(facts(rows=(Row(NODE, "true", "fine", ""),), holder="")).allowed


@pytest.mark.parametrize("by", ["SESSION:HOLDER", "  holder  ", "holder"])
def test_the_holder_compare_ignores_case_and_the_session_prefix(by):
    """Catches: a holder let through by a capital letter, a space or the bare form of the same id."""
    assert reasons(decide(facts(rows=(Row(NODE, "true", "r", by),)))) == [(NODE, "verdict-by-holder")]


def test_a_verdict_word_that_is_none_of_the_three_is_no_verdict():
    """Catches: a row with a made-up word (`ok`) counted as a verdict."""
    verdict = decide(facts(rows=(Row(NODE, "ok", "r", "session:reader"),)))
    assert reasons(verdict) == [(NODE, "verdict-missing")]


def test_every_refusal_names_its_node_and_reason():
    """Catches: a refusal that does not say which node failed, so the owner cannot tell what to fix."""
    verdict = decide(facts(nodes=(NODE, OTHER), rows=(Row(OTHER, "weak", "r", "session:reader"),)))
    assert reasons(verdict) == [(NODE, "verdict-missing"), (OTHER, "verdict-weak")]
    assert NODE in verdict.refusals[0].text and OTHER in verdict.refusals[1].text


def test_the_last_row_of_a_node_is_its_verdict():
    """Catches: an old `weak` row that keeps a card open after the reader wrote the new `true` row, and the reverse."""
    weak, true = Row(NODE, "weak", "r", "session:reader"), Row(NODE, "true", "r", "session:reader")
    assert decide(facts(rows=(weak, true))).allowed
    assert reasons(decide(facts(rows=(true, weak)))) == [(NODE, "verdict-weak")]


def test_an_author_of_another_test_file_is_no_refusal():
    """Catches: the authors of every file taken together, so a reader who wrote some other test is refused."""
    assert decide(facts(authors={"tests/test_a.py": frozenset({"writer"}),
                                 "tests/test_b.py": frozenset({"session:reader"})})).allowed


@pytest.mark.parametrize("by", ["WRITER", "  writer  ", "session:writer", "Session:Writer"])
def test_the_author_compare_ignores_case_and_the_session_prefix(by):
    """Catches: an author who is let through by a capital letter, a space or the `session:` form of the same id."""
    verdict = decide(facts(rows=(Row(NODE, "true", "r", by),)))
    assert reasons(verdict) == [(NODE, "verdict-by-author")]


FILE_A = "tests/test_a.py"


def test_a_row_by_a_session_in_the_commit_records_of_the_test_file_is_refused():
    """Catches: a test judged by a session that committed it (git names another author), which is no blind verdict
    (ruling R173 item 1)."""
    verdict = decide(facts(rows=(Row(NODE, "true", "fine", "session:committer"),),
                           committers={FILE_A: frozenset({"committer"})}))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-by-committer")]
    assert "committer" in verdict.refusals[0].text


def test_a_row_by_a_session_that_did_not_commit_the_test_file_is_allowed():
    """The nearest allow of the committer deny: the file has commit records, none of them the reader's."""
    assert decide(facts(committers={FILE_A: frozenset({"someone-else"})})).allowed


def test_a_session_that_committed_another_test_file_is_no_refusal():
    """Catches: the commit records of every file taken together, so a reader who committed some other test is refused."""
    assert decide(facts(committers={FILE_A: frozenset({"someone-else"}),
                                    "tests/test_b.py": frozenset({"reader"})})).allowed


def test_a_file_with_no_commit_record_is_judged_by_the_holder_check_alone_and_allowed():
    """Catches: a legacy test (no record) refused for lacking one (ruling R173 item 1: no record, holder check alone)."""
    assert decide(facts(committers={})).allowed


def test_a_file_with_no_commit_record_is_still_refused_when_the_reader_is_the_holder():
    """Catches: the holder check dropped for a file with no record, so the holder judges its own legacy test."""
    verdict = decide(facts(rows=(Row(NODE, "true", "fine", "session:holder"),), committers={}))
    assert reasons(verdict) == [(NODE, "verdict-by-holder")]


@pytest.mark.parametrize("by", ["COMMITTER", "  committer  ", "committer", "Session:Committer"])
def test_the_committer_compare_ignores_case_and_the_session_prefix(by):
    """Catches: a committer let through by a capital letter, a space or the bare form of the same session id."""
    verdict = decide(facts(rows=(Row(NODE, "true", "r", by),), committers={FILE_A: frozenset({"committer"})}))
    assert reasons(verdict) == [(NODE, "verdict-by-committer")]


@pytest.mark.parametrize("by, committer, expected", [
    ("writer", "writer", "verdict-by-author"),
    ("session:holder", "holder", "verdict-by-holder"),
])
def test_the_author_and_the_holder_refusals_come_before_the_committer_refusal(by, committer, expected):
    """Catches: the committer reason hiding the author or the holder reason when a reader is two of them."""
    verdict = decide(facts(rows=(Row(NODE, "true", "r", by),), committers={FILE_A: frozenset({committer})}))
    assert reasons(verdict) == [(NODE, expected)]


def test_a_blank_reader_is_not_a_committer():
    """Catches: an empty `by` equal to an empty session name in the records, refused as a committer."""
    assert decide(facts(rows=(Row(NODE, "true", "r", ""),), holder="", committers={FILE_A: frozenset({""})})).allowed


NO_PROOF = "no record of the session s2 writing this row through a write tool"


def test_a_row_with_no_proof_is_refused_as_unproven():
    """Catches: a row typed by hand, copied or written by a shell counted as a reader's verdict (ruling R173 item 2: a
    verdict row counts only with the reader's proof)."""
    verdict = decide(facts(unproven={NODE: NO_PROOF}))
    assert not verdict.allowed and reasons(verdict) == [(NODE, "verdict-unproven")]
    assert NO_PROOF in verdict.refusals[0].text


def test_a_row_whose_node_has_a_proof_is_allowed_when_only_another_node_has_none():
    """The nearest allow of the unproven deny: the problem belongs to another node, this node's row has its proof."""
    assert decide(facts(unproven={OTHER: NO_PROOF})).allowed


@pytest.mark.parametrize("by, committer, expected", [
    ("writer", "x", "verdict-by-author"),
    ("session:holder", "x", "verdict-by-holder"),
    ("session:committer", "committer", "verdict-by-committer"),
])
def test_the_identity_refusals_come_before_the_unproven_refusal(by, committer, expected):
    """Catches: the unproven reason hiding who the reader is when a row is both by the writer, the holder or a committer
    and without proof."""
    verdict = decide(facts(rows=(Row(NODE, "true", "r", by),), committers={FILE_A: frozenset({committer})},
                           unproven={NODE: NO_PROOF}))
    assert reasons(verdict) == [(NODE, expected)]


@pytest.mark.parametrize("word", ["weak", "wrong"])
def test_an_unproven_row_is_refused_as_unproven_before_it_is_judged(word):
    """Catches: a weak or wrong row with no proof refused for its verdict word, when it is no reader's word at all."""
    verdict = decide(facts(rows=(Row(NODE, word, "r", "session:reader"),), unproven={NODE: NO_PROOF}))
    assert reasons(verdict) == [(NODE, "verdict-unproven")]


WARNING = "blind verdict not enforced: outbox.checkers missing in profile"  # from ruling R179 condition 1


def test_a_missing_checker_key_lets_the_close_pass_with_the_warning():
    """Catches: a card that names a test refused for a verdict nobody can prove while the profile names no checker, or
    allowed with no word that the blind verdict was not enforced (ruling R179 condition 1)."""
    verdict = decide(Facts(nodes=(NODE,), rows=(), authors={}, checkers_missing=True))
    assert verdict.allowed and verdict.warnings == (WARNING,)


def test_a_set_checker_key_with_no_verdict_row_is_refused_without_a_warning():
    """The nearest deny of the test above: only the key differs (set), so the missing verdict row is refused."""
    verdict = decide(Facts(nodes=(NODE,), rows=(), authors={}, checkers_missing=False))
    assert reasons(verdict) == [(NODE, "verdict-missing")] and verdict.warnings == ()


def test_a_missing_checker_key_on_a_card_naming_no_node_gives_no_warning():
    """Catches: a warning on a card the check does not touch (every row `checked by reading`)."""
    verdict = decide(Facts(nodes=(), rows=(), authors={}, checkers_missing=True))
    assert verdict.allowed and verdict.warnings == ()


def test_an_allowed_close_with_the_key_set_has_no_warning():
    """Catches: the warning shown when the check was enforced."""
    assert decide(facts()).warnings == ()


@pytest.mark.parametrize("is_lead, required, missing, expected", [
    (True, True, True, WARNING),
    (False, True, True, None),
    (True, False, True, None),
    (True, True, False, None),
])
def test_the_stop_warning_is_for_a_lead_while_the_check_is_on_and_the_key_is_missing(is_lead, required, missing, expected):
    """Catches: the lead's Stop warning missing while the key is missing, or shown to a session that is no lead, with the
    check off, or after the key is set (ruling R179 condition 1: it trips when the key is set)."""
    from core_verdicts import stop_warning
    assert stop_warning(is_lead, required, missing) == expected


def test_a_card_naming_no_node_is_allowed():
    """Catches: a card that names no test (every row `checked by reading`) refused for a verdict file it cannot have."""
    assert decide(Facts(nodes=(), rows=(), authors={})).allowed


def test_the_core_imports_nothing_that_does_io():
    """Catches: input or output, git, the clock or the environment creeping into the decision."""
    source = (Path(_engine.ENGINE) / "core_verdicts.py").read_text(encoding="utf-8")
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= {"__future__", "dataclasses", "typing"}, names
