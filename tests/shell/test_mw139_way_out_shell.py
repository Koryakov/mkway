"""Card MW-139: the way out the refusal names for a red the take record does not hold is run, not only worded. A card is
taken while no kept test row of HEAD's history exists, a red-first commit is refused with the new text, the card is
released and taken again, and the same commit is allowed with the reds as old red held by the card's inherited red. A real
git repository and a real pytest run (the synthetic project of `_commit_project.py`); the gate is driven in process.
Synthetic names only."""
from _commit_project import reason, run_gate, stage
from _engine import cli
import gate_records
from _engine import gate_call
from _mw108 import KEYS, RED, commit_file, hold, inherited_rows, open_card, project, take


def test_the_way_out_of_a_red_the_take_record_does_not_hold_works_release_then_take(tmp_path):
    """Checks: card taken with no kept row (not established), a red-first commit refused with the text that names
    `mkway card release` then `mkway card take`, the route run, the same commit allowed with the red as old red and
    held in the card's inherited red (E1, E2)."""
    root = project(tmp_path)
    card = open_card(root, "Keys", "`app.py`, `tests/test_keys.py`, `tests/test_new.py`")
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    assert take(root, card)[0] == 0
    assert [r["established"] for r in inherited_rows(root)] == [False]
    hold(root, card)
    stage(root, "tests/test_new.py", RED.format(name="new"))
    refused = run_gate(root)
    assert reason(refused) == "commit-tests-failed", (refused.kind, refused.message)
    assert KEYS in refused.message
    assert f"`mkway card release {card}` then `mkway card take {card}`" in refused.message
    assert "next merge writes the row" not in refused.message
    code, out, err = cli(root, "card", "release", card, session=True)
    assert code == 0, (out, err)
    assert f"mkway-ok release {card}" in out
    gate_call(gate_records.record, root, tool="Bash", tool_response={"stdout": out}, session="s1",
              event="PostToolUse")  # the real post hook writes the release row (engine/gate_records.py:38)
    code, out, err = take(root, card)
    assert code == 0, (out, err)
    last = inherited_rows(root)[-1]
    assert (last["kind"], last["established"]) == ("take", True), last
    assert KEYS in last["red"]
    hold(root, card)
    allowed = run_gate(root)
    assert allowed.kind == "warn", (allowed.kind, allowed.message)
    assert allowed.reason_id == "commit-tests-still-red"
    assert f"old red: {KEYS}, owner {card}" in allowed.message


def test_the_take_line_of_a_take_that_is_not_established_names_the_route_not_the_next_merge(tmp_path):
    """Catches: a take line that sends the builder to wait for a merge that may never come; it must name the same route as
    the refusal: release and take again after a refused commit or any run that keeps a test row of HEAD (E3)."""
    root = project(tmp_path)
    card = open_card(root, "Keys", "`app.py`, `tests/test_keys.py`")
    commit_file(root, "tests/test_keys.py", RED.format(name="keys"))
    code, out, err = take(root, card)
    assert code == 0, err
    assert "not established" in out
    assert f"`mkway card release {card}` then `mkway card take {card}`" in out
    assert "a refused commit" in out
    assert "next merge" not in out
