# MW-110 case map: tests renamed when `message-not-in-inbox` was removed

> Decision MW110-D2. The refusal `message-not-in-inbox` is removed (exit row of card 5, the send tool exists): each test below
> asserted that refusal and now asserts the allow, so it has a new name that says what it checks. One line per old test. The
> old side is written the way the card rows of MW-066 and MW-076 name the file (the file name without its folder).

tests/test_ping_noby.py::test_a_ping_of_an_engine_notice_with_no_by_is_refused_with_the_no_ping_needed_text -> tests/core/test_ping_noby.py::test_a_ping_of_an_engine_notice_with_no_by_passes_and_records_nothing
tests/test_ping_facts.py::test_a_session_may_not_ping_a_row_another_session_wrote -> tests/shell/test_ping_facts.py::test_a_ping_line_of_a_row_another_session_wrote_passes_and_is_not_recorded
tests/test_ping_facts.py::test_only_the_session_that_caused_an_engine_notice_may_ping_it -> tests/shell/test_ping_facts.py::test_the_ping_line_of_an_engine_notice_by_another_session_passes_and_is_not_recorded
tests/test_ping_facts.py::test_a_notice_with_no_by_cannot_be_pinged_by_any_session -> tests/shell/test_ping_facts.py::test_the_ping_line_of_a_notice_with_no_by_passes_and_is_not_recorded
tests/test_e2e_gates.py::test_a_ping_of_an_engine_notice_with_no_by_is_refused_through_the_real_message_gate -> tests/test_e2e_gates.py::test_a_ping_of_an_engine_notice_with_no_by_passes_the_real_message_gate
tests/test_session_facts.py::test_a_session_the_hook_gives_no_id_for_cannot_ping -> tests/shell/test_session_facts.py::test_a_session_the_hook_gives_no_id_for_is_not_judged_and_records_no_ping
tests/test_session_facts.py::test_a_refused_ping_appends_nothing -> tests/shell/test_session_facts.py::test_a_ping_line_of_another_senders_row_appends_nothing
