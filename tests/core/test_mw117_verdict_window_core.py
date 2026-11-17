"""Card MW-117 (decisions: R272 G3, R287 Q4, MW117-D1), layer core: the window of `mkway verdict add`. A verdict is allowed any
time after the red commit (the card has a red-proof row) while the card is not closed, held or not; a card with no red-proof
row is refused `verdict-no-red-proof`. `core_verdict_add.decide(facts)` as a table: no disk, no git, no clock. One test id is
one case; each refusal reason has a deny case and the nearest allow case."""
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
import core  # noqa: E402
import core_verdicts  # noqa: E402
import helpers  # noqa: E402
from _no_io import no_io  # noqa: E402
from core_verdict_add import Facts, Node, decide  # noqa: E402

NODE = "tests/test_a.py::test_one"


def node():
    return Node(NODE, known=True, committers=frozenset(), commit="c0ffee1", head_blob="b1", file_blob="b1",
                readers=("r1",), fresh=("r1",))


def facts(**kw):
    base = {"caller": "reader", "status": "open", "holder": "builder", "ever_held": frozenset({"builder"}),
            "nodes": (node(),), "mode": "trip", "red_proven": True}
    base.update(kw)
    return Facts(**base)


def reasons(verdict):
    return [r.reason for r in verdict.refusals]


def test_an_open_card_held_by_a_builder_with_a_red_proof_row_is_allowed():
    """Checks: R272 G3, a builder holds the open card, the red commit is made: a reader that never held it gives a verdict."""
    verdict = decide(facts())
    assert (verdict.allowed, verdict.run) == (True, "r1")


def test_a_waiting_card_with_a_red_proof_row_is_allowed():
    """Checks: the nearest allow of the card-state deny rows: a waiting card with a red-proof row takes a verdict."""
    assert decide(facts(status="waiting", holder="")).allowed


def test_an_open_card_with_no_red_proof_row_is_refused_no_red_proof():
    """Catches: a verdict written before any red commit, so it judges tests that no red run has proved."""
    assert reasons(decide(facts(red_proven=False))) == ["verdict-no-red-proof"]


def test_a_waiting_card_with_no_red_proof_row_is_refused_no_red_proof():
    """Catches: a waiting card with no red record taking a verdict (the old rule let it through)."""
    assert reasons(decide(facts(status="waiting", holder="", red_proven=False))) == ["verdict-no-red-proof"]


def test_the_no_red_proof_text_names_its_way_out():
    """Catches: a refusal that does not say what to do (R263): the text names the red commit of the card's tests."""
    text = decide(facts(red_proven=False)).refusals[0].text
    assert text.startswith("verdict-no-red-proof") and "red" in text and "commit" in text


def test_a_closed_card_with_a_red_proof_row_is_still_refused_as_card_state():
    """Catches: the window widened to a closed card (never weaker than the old rule)."""
    assert reasons(decide(facts(status="closed", holder=""))) == ["verdict-card-state"]


def test_a_proposed_card_with_a_red_proof_row_is_still_refused_as_card_state():
    """Catches: a verdict on a card nobody has opened, even with a red-proof row."""
    assert reasons(decide(facts(status="proposed", holder=""))) == ["verdict-card-state"]


def test_a_waiting_owner_card_with_a_red_proof_row_is_still_refused_as_card_state():
    """Catches: a verdict on a card the owner paused, even with a red-proof row."""
    assert reasons(decide(facts(status="waiting-owner", holder=""))) == ["verdict-card-state"]


def test_the_card_state_text_no_longer_names_a_holder_as_the_reason():
    """Catches: a refusal text that still says the card is refused for being held."""
    text = decide(facts(status="closed", holder="")).refusals[0].text
    assert "no holder" not in text and "closed" in text


def test_the_session_that_took_the_card_is_still_refused_as_by_holder():
    """Catches: the window letting the builder judge its own tests (never weaker): the caller took the card once."""
    verdict = decide(facts(ever_held=frozenset({"reader"})))
    assert reasons(verdict) == ["verdict-by-holder"]


def test_in_watch_mode_a_missing_red_proof_row_is_allowed_and_listed():
    """Checks: the red proof is not an independence rule, so watch mode lets it through and lists it."""
    verdict = decide(facts(mode="watch", red_proven=False))
    assert (verdict.allowed, [r.reason for r in verdict.watched]) == (True, ["verdict-no-red-proof"])


# ---- the close and the commit refuse a stale verdict with the id verdict-stale (MW117-D2, R287 Q4) ----------------------------

STALE_WHY = "verdict-stale: the Acceptance rows of tests/test_a.py::test_one changed after the verdict"


def _close(why):
    row = core_verdicts.Row(NODE, "true", "one clause, one case", "session:reader")
    found = core_verdicts.decide(core_verdicts.Facts(nodes=(NODE,), rows=(row,), authors={}, holder="session:holder",
                                                    unproven={NODE: why}))
    return [(r.node, r.reason) for r in found.refusals], [r.text for r in found.refusals]


def test_the_close_refuses_an_acceptance_change_with_the_id_verdict_stale():
    """Catches: a verdict whose Acceptance rows changed after it refused at close with the id verdict-unproven."""
    reasons_found, texts = _close(STALE_WHY)
    assert (reasons_found, NODE in texts[0], "Acceptance" in texts[0]) == ([(NODE, "verdict-stale")], True, True)


def test_the_close_keeps_the_id_verdict_unproven_for_any_other_why():
    """Checks: the nearest allow of the stale id: a row with no record of its reader is still verdict-unproven."""
    assert _close("no record of the session writing this row")[0] == [(NODE, "verdict-unproven")]


def _commit_reason(why):
    rel = "tests/verdicts/CARD-001.md"
    commit = core.CommitFacts(message="CARD-001 verdict", taken=(("M", rel, "index"),), sizes={rel: 1}, ignored=frozenset(),
                              unproven={rel: ((NODE, why),)})
    folder = "mkway/cards/CARD-001-first"
    facts_ = core.Facts(command="git commit -m 'CARD-001 verdict'", git_builtins=frozenset(helpers.git_builtins()),
                        commits=(commit,), exempt=("mkway/cards/REGISTER.md", "mkway/ledger"),
                        card_id_pattern=r"(?<![A-Za-z0-9_-])CARD-[0-9]{3,}(?![0-9A-Za-z_])", verdict_dir="tests/verdicts",
                        ordered=(core.Ordered("CARD-001", folder, frozenset({"src"}), rel),), holders={"CARD-001": "b1"})
    with no_io():
        found = core.decide_commit(facts_)
    return found.reason if found.kind == core.REFUSE else None


def test_the_commit_refuses_an_acceptance_change_with_the_id_verdict_stale():
    """Catches: the commit gate calling a stale verdict row verdict-unproven."""
    assert _commit_reason(STALE_WHY) == "verdict-stale"


def test_the_commit_keeps_the_id_verdict_unproven_for_any_other_why():
    """Checks: the nearest allow of the stale id at commit."""
    assert _commit_reason("no record of the session writing this row") == "verdict-unproven"
