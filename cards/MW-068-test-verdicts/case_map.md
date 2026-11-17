# MW-068 case map: a test dropped by MW-080

# One line per pair: `old test -> new test`, or `old test -> dropped: why` (the line grammar of MW-040, read by
# tests/test_meta_cards.py).

test_verdict_proof.py::test_the_post_step_records_the_rows_of_the_writing_session_only -> dropped: MW-080, decision R196 item 5: the Write path records no verdict write any more; the proof of a verdict row is the record of `mkway verdict add`, tested in tests/shell/test_verdict_add_write.py
