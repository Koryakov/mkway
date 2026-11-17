"""Card MW-110 (fix of the pre-merge readers, rulings R279 and the operator's decision): the place of three rows of the
reason table. `session-id-unset` is a warn that refuses nothing, so it is a `record` row of card 7 in the block of card 7
with its way-out test; `session-id-unverified` is a K8 row in the block of card 5 with its way-out test; the row of
`message-text-unsafe` points at the test that runs the real path. The blocks are read from the source of the table."""
import re
from pathlib import Path

import _engine  # noqa: F401  (puts the engine folder on the import path)
import concept

SOURCE = Path(__file__).resolve().parents[1] / "engine" / "concept.py"


def _block_of(reason):
    """The card number of the block (`# ---- card N: ...`) whose lines hold the row of `reason`."""
    block = None
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        head = re.match(r"\s*# ---- card (\d):", line)
        if head:
            block = int(head.group(1))
        if line.strip().startswith(f'"{reason}":'):
            return block
    raise AssertionError(f"no row for {reason} in the source of the table")


def test_session_id_unset_is_a_record_row_of_card_7_in_the_block_of_card_7_with_its_way_out():
    """Catches: a warn that refuses nothing kept as an exit row of card 5 (R268 d: a non-refusing id is a `record`, card 7);
    the row keeps its way-out test, so it is no gap."""
    row = concept.REASONS["session-id-unset"]
    assert (row.kind_or_exit, row.card, row.gap) == ("record", 7, None)
    assert row.way_out == "tests/test_mw110_way_out.py::test_way_out_session_id_unset"
    assert _block_of("session-id-unset") == 7


def test_session_id_unverified_is_a_k8_row_in_the_block_of_card_5_with_its_way_out():
    """Catches: an identity that cannot be verified left as a refusal with no row, or a K8 row with no way-out test, or one
    placed outside the block of the card that wrote it."""
    row = concept.REASONS["session-id-unverified"]
    assert (row.kind_or_exit, row.card, row.gap) == ("K8", None, None)
    assert row.way_out == "tests/test_mw110_way_out.py::test_way_out_session_id_unverified"
    assert _block_of("session-id-unverified") == 5


def test_send_record_failed_is_a_k8_row_in_the_block_of_card_5_with_its_way_out():
    """Catches: R279c Q3: a record that cannot be written refused with an id the table does not know, or a K8 row with no
    way-out test (no gap)."""
    row = concept.REASONS["send-record-failed"]
    assert (row.kind_or_exit, row.card, row.gap) == ("K8", None, None)
    assert row.way_out == "tests/test_mw110_way_out.py::test_way_out_send_record_failed"
    assert _block_of("send-record-failed") == 5


def test_the_unsafe_text_row_points_at_the_test_of_the_real_path():
    """Catches: R279 and the reader's finding: a way-out test whose refused call the lock gate stops first, so the engine's
    refusal it shows is not what a session reads on the real path."""
    assert concept.REASONS["message-text-unsafe"].way_out == "tests/test_mw110_way_out.py::test_way_out_message_text_unsafe_real_path"


def test_the_mismatch_row_says_the_permit_is_the_proof():
    """Catches: a comment that still says the identity of a session is the launcher's variable (round 2 of the readers):
    after R279 the hook's one-use permit is the proof and the variable is checked against it."""
    line = next(l for l in SOURCE.read_text(encoding="utf-8").splitlines() if l.strip().startswith('"session-id-mismatch":'))
    assert "the permit is the proof" in line
    assert "R279" in line
    assert "identity of a session is the launcher's variable" not in line


def test_no_row_of_block_5_is_a_gap():
    """Checks: every row the card placed in its block has a way-out test, so the count of gaps does not grow with the fix."""
    in_block = [r for r in concept.REASONS if _block_of(r) == 5]
    assert in_block != []
    assert [r for r in in_block if concept.REASONS[r].way_out is None] == []
