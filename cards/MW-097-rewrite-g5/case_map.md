# case_map of MW-097
# literal: tests/test_mw035_install_line.py::_version 'VERSION' - S2 and S4: the helper _version was used by no test in the file and is removed
# literal: tests/test_mw038_guard.py::test_the_real_shape_scenario_exists_and_holds_no_skip 'tests/test_mw038_real_shape.py holds a skip' - S5: a message literal that names another test file; the message is now built from SCENARIO, the same text
# literal: tests/test_mw035_install_line.py::<module> 'VERSION' - S2 and S4: the helper _version, which read the VERSION file and was used by no test in the file, is removed
# literal: tests/test_mw035_install_line.py::<module> 'utf-8' - the same removed helper _version carried one read_text encoding argument; the other reads keep theirs
# literal: tests/test_mw012_watch.py::test_an_integrity_gate_never_reads_a_marker_and_never_trips '.watch' - R237: the loop over i1 and u1 is unrolled into straight-line steps, so the suffix of the f-string name is now written whole as i1.watch and u1.watch
# literal: tests/test_mw018_gate.py::test_a_hand_written_inbox_row_or_ping_is_refused_by_the_lock 'free-1' - S1: the two call sites inside the loops became one call in the parametrized test, still session free-1; one repeated use fewer, same value
# literal: tests/test_mw018_gate.py::test_a_hand_written_inbox_row_or_ping_is_refused_by_the_lock 'refuse' - S1 and S3: the two repeated kind checks became one assert in the parametrized test; the value is still checked
# literal: tests/test_mw038_guard.py::test_the_real_shape_scenario_exists_and_holds_no_skip 'tests/test_mw038_real_shape.py holds a skip: ' - S5: a message literal that names another test file; the message is now built from SCENARIO as the path plus the text ' holds a skip: ', the same message
# literal: tests/test_mw059_topology_text.py::test_the_refusal_text_for_a_target_that_holds_no_card <asserts> - fewer asserts 8 to 4: the if/else moved into the helper _text_ok, same logic
# literal: tests/test_mw018_gate.py::test_a_hand_written_inbox_row_or_ping_is_refused_by_the_lock <computed-param> - nine cases built from the literal _INBOX_PATHS in the test
