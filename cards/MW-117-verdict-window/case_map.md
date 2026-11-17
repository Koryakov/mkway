# MW-117 case map: two tests renamed by decision MW117-D1

# One line per pair: `old test -> new test`, or `old test -> dropped: why` (the line grammar of MW-040, read by
# tests/test_meta_cards.py).

test_verdict_add_decide.py::test_an_open_card_with_a_holder_is_refused_as_card_state -> test_verdict_add_decide.py::test_an_open_card_with_a_holder_is_allowed_after_the_red_commit
test_mw113_command_e2e.py::test_the_way_out_of_verdict_card_state_is_a_card_with_no_holder -> test_mw113_command_e2e.py::test_the_way_out_of_verdict_card_state_is_opening_a_proposed_card
