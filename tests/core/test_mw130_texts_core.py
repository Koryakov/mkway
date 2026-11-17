"""Card MW-130 (decisions R313, R313a), layer core: the way out of each true text of the one reason id `verdict-no-red-proof`,
as `core_verdict_add.decide(facts)` gives it. R4 of the order: `concept.py` lists the reason by id with the way-out test of
MW-117 (`tests/shell/test_mw117_verdict_window_shell.py::test_the_way_out_of_verdict_no_red_proof_is_the_red_commit`, texts
(i)); it lists no text, so the texts (ii) to (iv) are pinned here, not in `concept.py`. No disk, no git, no clock."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tests/: `_engine` puts engine/ on the path
import _engine  # noqa: E402,F401
from core_verdict_add import Facts, Node, decide  # noqa: E402

WAY_OUT = "commit the card's red tests (the commit gate records the row), then call again"


def _text(case: str, checked: int = 0) -> str:
    node = Node("tests/test_a.py::test_one", known=True, commit="c0ffee1", head_blob="b1", file_blob="b1",
                readers=("r1",), fresh=("r1",))
    verdict = decide(Facts(caller="reader", status="open", holder="builder", ever_held=frozenset({"builder"}),
                           nodes=(node,), mode="trip", red_proven=False, red_case=case, red_checked=checked,
                           red_seconds=60.0))
    assert [r.reason for r in verdict.refusals] == ["verdict-no-red-proof"]
    return verdict.refusals[0].text


def test_the_texts_of_no_row_rows_no_commit_has_and_out_of_time_end_with_the_same_way_out():
    """Catches: R263, a refusal that does not name the red commit as its way out, in the texts (i), (ii) and (iii)."""
    assert [_text(case, 7).endswith(WAY_OUT) for case in ("i", "ii", "iii")] == [True, True, True]


def test_the_text_of_an_unreadable_history_names_repeating_the_call_as_its_way_out():
    """Catches: text (iv) that sends the session to commit again when git only failed to answer: the way out is to repeat."""
    assert _text("iv").endswith("could not be checked; repeat the call")
