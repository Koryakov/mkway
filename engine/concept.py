"""The concept as data (card MW-106). No I/O, no imports beyond typing.

KINDS: the eight hard-gate kinds. RECORDS: the four records. EXITS: where an id that is not a hard stop goes.
REASONS: one row per id the engine emits (a refusal, a warn, a log row, a would-refuse row):
  kind_or_exit  one of K1 to K8, or an exit: tool, instruction, remove, record
  card          the number 2 to 8 of the card that implements the exit; None for a kind
  way_out       the node id of the test that proves the refusal's way out works, or None (a gap)
  gap           the number of the card that adds the way-out test, when way_out is None

THE PRINCIPLE (R268). A KIND row means the hook keeps refusing: it is one of the eight hard stops. An EXIT row means
the hook stops refusing when the named card lands: `tool` = the tool makes the error impossible or harmless;
`instruction` = one line in a role file replaces it; `record` = a log line once per event; `remove` = deleted. A check
that stays in the hook and gets a tool as its way out is a KIND, with the tool as its way-out test. Examples: the
families of the commit check are the card id (K6), data files, size and terms (K4), path form and index read (K1, the
reach rule). An id that does not refuse (a warn, a log row, a would-refuse row) is a `record`, card 7.

Every row has a comment naming its gate file. An `instruction` row names the line of a role file that will replace it
(card 7). A later card that changes a row changes the tests first (the table is the plan, the tests are its proof).
The rows sit in one block per card, 2 to 8, by the card that closes the row's gap or implements its exit, so later cards
edit separate blocks; the last block holds the rows with a way-out test and no card of their own (none yet; the rows of card 8 hold theirs in block 8). `engine/CONCEPT.md` is the one page
that explains the table.
"""
from typing import NamedTuple, Optional


class Row(NamedTuple):
    kind_or_exit: str
    card: Optional[int]
    way_out: Optional[str]
    gap: Optional[int]


KINDS = {
    "K1": "protected targets, with the reach rule",
    "K2": "red before green, never weaker, with provenance",
    "K3": "blind verdict before close, with its witness",
    "K4": "confidential content: terms, data paths, size",
    "K5": "full green at merge and install, on the committed tree",
    "K6": "the card rule with one owner table",
    "K7": "the owner-ask lane",
    "K8": "fail-closed wiring",
}

RECORDS = {
    "R1": "agent records",
    "R2": "the ledger with an author",
    "R3": "the card board",
    "R4": "the cost record",
}

EXITS = ("tool", "instruction", "remove", "record")

# A row with a way-out test names its node id; a row with none is a gap (the tested way out is the work of cards 2 to 8,
# rule C5). GAPS_ALLOWED is the number of gap rows. The card that closes a gap lowers it.
GAPS_ALLOWED = 55  # 99 less the 3 rows of block 3 that now have a way-out test (MW-108: close-tests-failing, commit-tests-failed, commit-tests-still-red) = 96, less the 40 gap rows of block 7 (MW-112: 14 tool ids, close-log-failed, 2 K7 ask rows, 2 drop-path instruction rows, 21 record rows, each with a way-out test) = 56, less the gate-watch-integrity row that now has a way-out test (MW-115) = 55; the test holds a literal ceiling of 55

REASONS = {
    # ---- card 2: one owner per file kind (K6) ----
    "ack-not-yours": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; an inbox has one owner
    "ack-unknown": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; an inbox has one owner
    "card-not-open": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core_session.py; way out proved by card MW-107, reading the owner table
    "card-not-yours": Row("K6", None, None, 2),  # core_lock.py; gap: no way-out test yet
    "card-paths-changed": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core_session.py; way out proved by card MW-107, reading the owner table
    "card-paths-too-wide": Row("K6", None, None, 2),  # cardtool.py; gap: no way-out test yet
    "close-by-holder": Row("K6", None, None, 2),  # cardtool.py; gap: no way-out test yet; who may close the card
    "close-not-orderer": Row("K6", None, None, 2),  # cardtool.py; gap: no way-out test yet; who may close the card
    "file-not-in-card": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core.py; way out proved by card MW-107, reading the owner table
    "lead-accept-none": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "lead-accept-stale": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "lead-ambiguous": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "lead-bad-id": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "lead-give-not-yours": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; only the lead gives a card
    "lead-give-self": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; only the lead gives a card
    "lead-no-session": Row("K6", None, None, 2),  # mkway.py; gap: no way-out test yet; the lead of a card is one session
    "lead-not-registered": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "lead-session-only": Row("K6", None, None, 2),  # mkway.py; gap: no way-out test yet; the lead of a card is one session
    "lead-unknown": Row("K6", None, None, 2),  # leads.py; gap: no way-out test yet; the lead of a card is one session
    "ledger-by-owner": Row("K6", None, None, 2),  # mkway.py; gap: no way-out test yet; a row in the owner's name is never a session's
    "ledger-replaces-unknown": Row("K6", None, None, 2),  # mkway.py; gap: no way-out test yet; a row in the owner's name is never a session's
    "lead-no-edit": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core_session.py; way out proved by card MW-107, reading the owner table
    "lead-no-take": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core_session.py; way out proved by card MW-107, reading the owner table
    "no-open-card": Row("K6", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # core_session.py; way out proved by card MW-107, reading the owner table
    "quote-file-outside": Row("K6", None, None, 2),  # core_lock.py; gap: no way-out test yet; the quote file has an owner (C4)
    "register-busy": Row("K6", None, None, 2),  # register.py; gap: no way-out test yet; the register has one writer
    "register-seal-adopted": Row("K6", None, None, 2),  # register.py; gap: no way-out test yet
    "register-tampered": Row("K6", None, None, 2),  # core.py; gap: no way-out test yet
    "register-write-failed": Row("K6", None, None, 2),  # register.py; gap: no way-out test yet
    "session-has-card": Row("K6", None, None, 2),  # core_lock.py; gap: no way-out test yet; one open card per session
    "write-outside-root": Row("K1", None, "tests/core/test_mw107_ways_out_core.py::test_the_way_out_of_each_refusal_works", None),  # gate_outside.py and gate_lead.py; a session writes outside its root only in the outside-writable folders (R274, R270c), reading the owner table

    # ---- card 3: this-commit judgement with inherited red (K2) ----
    "case-map-malformed": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "case-map-merge": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "case-map-no-decision": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "case-map-unknown-left": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "case-map-unknown-right": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "close-deliverable-unbuilt": Row("K2", None, None, 3),  # deliverables.py; gap: no way-out test yet; a deliverable is built on a clean HEAD whose tests passed
    "close-tests-failing": Row("K2", None, "tests/shell/test_mw108_card_shell.py::test_way_out_of_close_tests_failing_the_close_passes_when_the_inherited_red_is_green", None),  # cardtool.py; way out proved by card MW-108: the inherited red is green, or the orderer releases it to another open card
    "commit-tests-failed": Row("K2", None, "tests/shell/test_mw108_commit_shell.py::test_way_out_of_commit_tests_failed_the_tests_alone_in_the_plain_form_pass", None),  # gate_commit_tests.py; only the new red of the commit refuses; way out proved by card MW-108: the red-first commit in the plain form
    "commit-tests-not-run": Row("K2", None, None, 3),  # gate_commit_tests.py; gap: no way-out test yet
    "commit-tests-over-budget": Row("K2", None, None, 3),  # gate_commit_tests.py; gap: no way-out test yet
    "commit-tests-still-red": Row("record", 3, "tests/shell/test_mw108_commit_shell.py::test_replay_dd010_a_red_first_commit_beside_an_old_own_red_is_allowed", None),  # gate_commit_tests.py; a warn: an old red shown with its owner card, written by card MW-108 (the allow line and the old_red field of the commit row)
    "red-not-proven": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "red-not-recorded": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet
    "release-red": Row("record", 3, "tests/shell/test_mw108_card_shell.py::test_release_red_row_names_the_orderer", None),  # cardtool.py; the record row of an inherited red that the orderer moved to another open card (R283 4), the card tool refuses with existing ids
    "red-record-partial": Row("record", 3, "tests/shell/test_mw131_own_record_shell.py::test_the_limit_running_out_after_a_found_row_allows_with_the_found_rows_and_one_line", None),  # gate_commit_tests.py and core_red.py; a warn, an allow line and never a refusal: the search limit ran out after a row of the card's own record was found, and the line names the legacy rows left out; it names no way out, the test asserts the call is allowed and the line is exact (MW-131, R322)
    # ---- card MW-134 (R347, R348): the refusals of the retirement of a recorded red id, each with its way-out test ----
    "retire-no-decision": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_no_decision_is_a_message_that_names_a_decision", None),  # core_red.py; a line that would retire a recorded red id and a message that names no decision; way out: name a decision of the ledger that another session wrote
    "retire-decision-not-in-ledger": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_not_in_ledger_is_a_decision_that_is_a_row_of_the_ledger", None),  # core_red.py; the named decision is no row of the ledger; way out: name a row
    "retire-decision-closed": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_closed_is_a_decision_that_is_in_force", None),  # core_red.py; the named decision is withdrawn or superseded; way out: name one in force
    "retire-decision-by-self": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_decision_by_self_is_a_decision_another_session_wrote", None),  # core_red.py; the named decision is by the committing session; way out: a decision another session wrote
    "retire-no-ledger": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_no_ledger_is_a_ledger_row_of_another_session", None),  # core_red.py; the root has no ledger file, so the by of the decision cannot be checked; way out: a ledger row of another session
    "retire-right-not-red": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_right_not_red_is_a_right_side_that_was_seen_red", None),  # core_red.py; a rename whose right side was not seen red; way out: a right side recorded red or red in this commit
    "retire-left-failing": Row("K2", None, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_left_failing_is_a_file_that_collects", None),  # core_red.py; the file of the left side fails to collect, so its ids are failing, not absent; way out: make the file collect
    "retire-notice-failed": Row("record", 7, "tests/shell/test_mw134_retire_shell.py::test_the_way_out_of_retire_notice_failed_is_that_the_retirement_stands_and_the_builder_writes_itself", None),  # gate_commit_tests.py; MW-134, R348 3: the calls-log error row of a retirement notice that could not be written; the commit is never refused and the retirement stands; way out: none needed, the builder writes to its orderer itself
    "rule-without-test": Row("K2", None, None, 3),  # core.py; gap: no way-out test yet
    "test-shape": Row("K2", None, None, 3),  # gate_test_shape.py; gap: no way-out test yet; the shape rule of K2
    "test-without-red-proof": Row("K2", None, None, 3),  # core_red.py; gap: no way-out test yet

    # ---- card 4: fail-closed wiring and the start line (K8); the way out of a K1 lock or delete is the owner's lock open or the literal path ----
    "agent-record-failed": Row("K8", None, "tests/test_hooks_fail_closed.py::test_an_agent_record_failed_way_out", None),  # core_session.py; refuses and names the path (R271c)
    "ask-record-failed": Row("K8", None, "tests/test_hooks_fail_closed.py::test_an_ask_record_failed_way_out", None),  # gate_owner_ask.py; refuses and names the path (R271c)
    "shared-record-busy": Row("K8", None, "tests/shell/test_mw129_shared_records_shell.py::test_the_way_out_of_shared_record_busy_is_to_repeat_the_call", None),  # gate_commit_tests.py; the append lock of a shared card record file stays busy: nothing is written, the commit is refused; way out: repeat the call (MW-129, R310 1)
    "base-unknown": Row("K8", None, None, 4),  # deliverables.py; gap: no way-out test yet; an unknown base fails closed
    "built-dirty": Row("K5", None, "tests/test_hooks_fail_closed.py::test_a_built_dirty_way_out", None),  # deliverables.py; the build reads a committed tree
    "built-untested": Row("K5", None, "tests/test_hooks_fail_closed.py::test_a_built_untested_way_out", None),  # deliverables.py; the build needs a passing run
    "bundle-outside-root": Row("K1", None, "tests/test_hooks_fail_closed.py::test_an_install_input_way_out[bundle-outside-root]", None),  # core_install.py; path form
    "check-record-failed": Row("K8", None, "tests/test_hooks_fail_closed.py::test_a_check_record_failed_way_out", None),  # gate_outbox.py; refuses and names the path (R271c)
    "copy-without-lock": Row("K1", None, "tests/test_hooks_fail_closed.py::test_an_install_input_way_out[copy-without-lock]", None),  # core_install.py; path form
    "delete-backup-failed": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_backup_failed_way_out", None),  # trash.py
    "delete-outside-root": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-outside-root]", None),  # core_delete.py
    "delete-sql": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-sql]", None),  # core_delete.py
    "delete-target-unknown": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-target-unknown]", None),  # core_delete.py
    "delete-too-large": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_too_large_way_out", None),  # core_delete.py
    "delete-uncommitted": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-uncommitted]", None),  # core_delete.py
    "delete-wildcard": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_delete_way_out[delete-wildcard]", None),  # core_delete.py
    "dispatcher-error": Row("K8", None, "tests/test_hooks_fail_closed.py::test_a_dispatcher_error_way_out", None),  # dispatch.py; a gate that fails refuses
    "gate-error": Row("K8", None, "tests/test_hooks_fail_closed.py::test_a_gate_error_way_out", None),  # dispatch.py; a gate that raises: onFailure block refuses
    "gate-git-timeout": Row("K8", None, None, 4),  # core_lock.py; gap: no way-out test yet
    "gate-watch-integrity": Row("K8", None, "tests/test_mw115_ask_integrity.py::test_the_owner_cannot_put_the_outbox_check_in_watch_and_the_refusal_names_a_form_gate_as_the_way_out", None),  # mkway.py; way out: tested (MW-115): the text names a form gate to watch
    "lock-closed-commit": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-commit]", None),  # core_lock.py
    "lock-closed-edit": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-edit]", None),  # core_lock.py
    "lock-closed-shell": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_closed_lock_way_out[lock-closed-shell]", None),  # core_lock.py
    "lock-file-by-session": Row("K1", None, "tests/test_hooks_fail_closed.py::test_a_lock_file_by_session_way_out", None),  # core_lock.py; the way out is the owner's lock open
    "owner-only-command": Row("K8", None, None, 4),  # core_lock.py; gap: no way-out test yet
    "post-record-failed": Row("K8", None, "tests/test_hooks_fail_closed.py::test_a_post_record_failed_way_out", None),  # core_session.py; refuses and names the path (R271c)
    "profile-invalid": Row("K8", None, "tests/test_hooks_fail_closed.py::test_a_profile_invalid_way_out", None),  # dispatch.py; an invalid profile refuses a blocking group
    "profile-outside-root": Row("K1", None, "tests/test_hooks_fail_closed.py::test_an_install_input_way_out[profile-outside-root]", None),  # core_install.py; path form
    "session-signal-missing": Row("K8", None, None, 4),  # startline.py; gap: no way-out test yet
    "settings-hooks-not-object": Row("K8", None, None, 4),  # core_install.py; gap: no way-out test yet
    "settings-not-json": Row("K8", None, None, 4),  # core_install.py; gap: no way-out test yet

    # ---- card 5: the send tool (messages and pings); every row has its way-out test (MW-110); message-not-in-inbox is removed (exit remove, card 5) ----
    "inbox-not-yours": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_inbox_not_yours", None),  # messages.py; the send tool and the inbox
    "inbox-unknown": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_inbox_unknown", None),  # messages.py; the send tool and the inbox
    "message-ambiguous": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_ambiguous", None),  # messages.py; the send tool
    "message-dead-letter": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_dead_letter", None),  # messages.py; the send tool
    "message-duplicate": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_duplicate", None),  # messages.py and core_session.py; the send tool
    "message-empty": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_empty", None),  # messages.py; the send tool
    "message-no-file": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_no_file", None),  # mkway.py; the send tool
    "message-no-session": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_no_session", None),  # mkway.py; the send tool, the way out is the launcher line
    "message-reply-unknown": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_reply_unknown", None),  # messages.py; the send tool
    "message-text-unsafe": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_text_unsafe_real_path", None),  # mkway.py; the send tool; the lock gate answers first for a double-quoted text, the real-path test shows what a session meets
    "message-topology": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_message_topology", None),  # messages.py; the send tool
    "ping-not-sent": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_ping_not_sent", None),  # core_ping.py; the send tool prints the ping line, the ping gate stays
    "send-session-only": Row("tool", 5, "tests/test_mw110_way_out.py::test_way_out_send_session_only", None),  # mkway.py; the send tool
    "session-id-mismatch": Row("K8", None, "tests/test_mw110_way_out.py::test_way_out_session_id_mismatch", None),  # core_session.py and mkway.py; the permit is the proof (R279), the variable is checked against it and a self-reported id never counts; way out: the launcher line
    "session-id-unverified": Row("K8", None, "tests/test_mw110_way_out.py::test_way_out_session_id_unverified", None),  # core_session.py and mkway.py; no permit and an end date passed or unreadable: the variable alone is no proof (R279, R279c); way out: run it in a session with the hooks, the launcher line
    "send-record-failed": Row("K8", None, "tests/test_mw110_way_out.py::test_way_out_send_record_failed", None),  # messages.py and mkway.py; R279c Q3: the record is written first, a record that cannot be written refuses and nothing is delivered or acked; way out: make the state folder writable

    # ---- card 6: the commit tool (command form and commit message); shape gaps of K1, K4, K6 ----
    "command-unparsed": Row("K1", None, None, 6),  # core_lock.py; the reach rule: a shape that names a target or carries a gated action stays refused, the tool is the way out
    "commit-folder-unreadable": Row("K1", None, None, 6),  # core_lock.py; index read: a commit shape the gate cannot read stays refused, the commit tool is the way out
    "commit-message-card": Row("K6", None, None, 6),  # core.py; the card id family of the commit check, the commit tool builds the message
    "commit-tests-chained": Row("K1", None, None, 6),  # gate_commit_tests.py; gap: no way-out test yet; the way out is the commit tool
    "commit-unreadable": Row("K1", None, None, 6),  # core.py; index read: a commit body the gate cannot read stays refused, the commit tool is the way out
    "data-file-staged": Row("K4", None, None, 6),  # core.py; gap: no way-out test yet; the commit tool is the way out
    "engine-call-not-plain": Row("K1", None, None, 6),  # core_lock.py; the reach rule: a state-changing engine call in a shape the gate cannot read stays refused
    "file-too-large": Row("K4", None, None, 6),  # core.py; gap: no way-out test yet; the commit tool is the way out
    "ignored-file-staged": Row("K4", None, None, 6),  # core.py; gap: no way-out test yet; the commit tool is the way out
    "junk-file-staged": Row("tool", 6, None, 6),  # core.py; the commit tool leaves junk out
    "pathspec-unparsed": Row("K1", None, None, 6),  # core_lock.py; path form: an unreadable pathspec of a commit stays refused, the commit tool is the way out

    # ---- card 7: reminders once, trial end dates, the board, the cost record, the instruction lines in the role files ----
    "ask-already-open": Row("K7", None, "tests/test_e2e_gates.py::test_refusal_through_the_real_hook", None),  # core_ask.py; R284b: a K7 kind, no role line; the real-hook deny and allow pairs prove the way out (add to the open ask)
    "ask-fields-missing": Row("K7", None, "tests/test_e2e_gates.py::test_refusal_through_the_real_hook", None),  # core_ask.py; R284b: a K7 kind, no role line; the real-hook deny and allow pairs prove the way out (the five field lines)
    "ask-past-deadline": Row("record", 7, "tests/test_mw014_board.py::test_the_reminder_is_for_the_session_that_owns_an_ask_past_its_deadline", None),  # gate_owner_ask.py; a warn, one log line per event; way out: tested
    "built-no-file": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_built_no_file_is_the_built_file", None),  # deliverables.py; the tool validation: the text names `mkway built <path>`
    "card-bad-move": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_card_bad_move_is_the_next_move_the_form_shows", None),  # cardtool.py; the tool validation: the text names the allowed moves
    "card-unknown": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_card_unknown_is_a_register_id", None),  # cardtool.py; the tool validation: the text names the register id form
    "check-written": Row("record", 7, "tests/shell/test_outbox_facts.py::test_the_post_step_records_the_check_and_its_session", None),  # outbox.py; the kind of a record row, one per check; way out: tested
    "close-log-failed": Row("K8", None, "tests/test_mw112_way_out.py::test_the_way_out_of_close_log_failed_is_a_writable_card_file", None),  # cardtool.py; R284b: a record the engine cannot write fails closed and names the path; the way out is a writable card file
    "close-row-without-test": Row("instruction", 7, "tests/test_cardmoves.py::test_close_rule", None),  # cardtool.py; the drop path, role file line: engine/roles/lead.md [close-row-without-test]; the refusal stays until a live incident orders otherwise
    "commit-needs-git": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_commit_needs_git_is_an_install_without_commit", None),  # core_install.py; the tool validation: install.py names install without --commit
    "delivered-no-file": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_delivered_no_file_is_the_file_that_went_out", None),  # deliverables.py; the tool validation: the text names `mkway delivered <path>`
    "gate-on": Row("record", 7, "tests/test_mw012_commands.py::test_gate_on_removes_the_marker", None),  # gatemode.py; a log row of a mode change, once per event; way out: tested
    "gate-tripped": Row("record", 7, "tests/test_mw012_watch.py::test_a_form_gate_trips_at_20_calls_with_7_refusals", None),  # dispatch.py; a log row, once per event; way out: tested
    "gate-watch": Row("record", 7, "tests/test_mw012_commands.py::test_gate_watch_writes_an_owner_marker", None),  # gatemode.py; a log row of a mode change, once per event; way out: tested
    "gate-watch-installed": Row("record", 7, "tests/test_mw012_commands.py::test_a_first_install_writes_a_watch_marker_for_each_form_gate_that_is_on", None),  # gatemode.py; a log row of a mode change, once per event; way out: tested
    "give-ambiguous": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_give_ambiguous_is_more_of_the_id", None),  # cardtool.py; the tool validation: the text says to give more of the id
    "give-no-column": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_give_no_column_is_the_owners_resync", None),  # cardtool.py; the tool validation: the text names the owner's resync
    "give-unknown": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_give_unknown_is_a_session_id_that_mkway_sessions_lists", None),  # cardtool.py; the tool validation: the text names `mkway sessions`
    "inbox-unacked": Row("record", 7, "tests/shell/test_mw112_once_shell.py::test_a_prompt_burst_with_one_unacked_item_writes_one_inbox_unacked_row", None),  # core_session.py; a reminder shown once on the board; way out: tested
    "lead-notices-unacked": Row("record", 7, "tests/shell/test_mw112_once_shell.py::test_a_prompt_burst_with_one_unacked_notice_writes_one_lead_notices_row", None),  # core_session.py; a reminder shown once on the board; way out: tested
    "reader-lease-expired": Row("record", 7, "tests/shell/test_mw116_reader_lease_shell.py::test_a_lock_older_than_thirty_minutes_is_taken_over_and_the_takeover_is_recorded", None),  # reader_allow.py; MW-116, R295: a record row when a lock older than 30 minutes is taken over, it names the old run
    "notify-failed": Row("record", 7, "tests/test_mw014_notify.py::test_a_failing_command_is_logged_and_never_blocks", None),  # gate_owner_ask.py; a log row, one per event; way out: tested
    "notify-sent": Row("record", 7, "tests/test_mw014_notify.py::test_the_command_runs_with_the_file_and_the_line_filled", None),  # gate_owner_ask.py; a log row, one per event; way out: tested
    "orders-unacked": Row("record", 7, "tests/shell/test_mw112_once_shell.py::test_a_stop_burst_with_one_old_order_writes_one_orders_unacked_row", None),  # core_session.py; a reminder shown once on the board; way out: tested
    "outbox-changed-after-check": Row("record", 7, "tests/shell/test_outbox_facts.py::test_a_file_changed_after_its_check_gets_a_reminder_that_names_it", None),  # core_ask.py; a warn, one log line per event; way out: tested
    "over-budget": Row("record", 7, "tests/test_dispatch.py::test_budget_reaches_ctx_and_over_budget_is_logged", None),  # dispatch.py; a log row of the cost record R4; way out: tested
    "ping-skipped": Row("record", 7, "tests/shell/test_ping_facts.py::test_the_second_stop_logs_ping_skipped_and_writes_the_row_for_the_lead", None),  # core_ping.py; a log row, one per event; way out: tested
    "ping-skipped-listed": Row("record", 7, "tests/shell/test_ping_facts.py::test_the_lead_sees_a_ping_skipped_row_once_at_its_next_stop", None),  # core_ping.py; a log row, one per event; way out: tested
    "profile-invalid-shared": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_profile_invalid_shared_is_a_profile_the_owner_fixed", None),  # core_install.py; the tool validation: install.py adds the repair to the text
    "python-not-interpreter": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_python_not_interpreter_is_a_named_interpreter", None),  # core_install.py; the tool validation: the text names the form of --python
    "search-unverified": Row("record", 7, "tests/shell/test_ask_facts.py::test_a_transcript_that_cannot_be_read_is_a_log_row_never_a_refusal", None),  # core_ask.py; a log row, one per event; way out: tested
    "session-id-unset": Row("record", 7, "tests/test_mw110_way_out.py::test_way_out_session_id_unset", None),  # core_session.py and mkway.py; a warn row once per session while the launcher does not set the variable, written by card 5 (block 7 has no open editor); way out: the launcher line
    "shared-not-absolute": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_shared_not_absolute_is_an_absolute_folder", None),  # core_install.py; the tool validation: the text gives an example of the form
    "shared-profile-invalid": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_shared_profile_invalid_is_a_shared_folder_the_schema_takes", None),  # core_install.py; the tool validation: install.py adds the repair to the text
    "source-empty": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_source_empty_is_the_engine_repository", None),  # core_install.py; the tool validation: install.py names --from <engine repository>
    "starter-invalid": Row("tool", 7, "tests/test_mw112_way_out.py::test_the_way_out_of_starter_invalid_is_a_vcs_the_schema_takes", None),  # core_install.py; the tool validation: install.py names the --vcs form
    "take-root-busy": Row("instruction", 7, "tests/test_mw034_staged_paths.py::test_a_take_after_the_holders_card_closed_is_allowed", None),  # core_lock.py; the drop path, role file line: engine/roles/builder.md [take-root-busy]; the refusal stays until a live incident orders otherwise
    "undeclared-reason": Row("record", 7, "tests/test_dispatch.py::test_undeclared_reason_is_logged", None),  # dispatch.py; a log row of a reason the manifest does not declare; way out: tested
    "verdict-not-enforced": Row("record", 7, "tests/shell/test_mw112_once_shell.py::test_a_stop_burst_of_a_lead_without_checkers_writes_one_verdict_not_enforced_row", None),  # core_verdict_add.py; a reminder shown once on the board; way out: tested
    "verdict-written": Row("record", 7, "tests/shell/test_checker_run_count.py::test_the_proof_record_of_a_write_holds_the_run_number", None),  # verdict_add.py; the kind of a proof record row, one per write of a verdict file; way out: tested
    "would-refuse": Row("record", 7, "tests/test_mw012_watch.py::test_a_watch_marker_turns_a_form_refuse_into_would_refuse", None),  # gatemode.py; the log row of a gate in watch mode; way out: tested
    "ask-answered": Row("record", 7, "tests/test_mw119_answer_intake.py::test_the_record_row_has_session_source_quote_and_time", None),  # asks.py; the kind of a proof record row, one per answer the lead records in the owner's name (MW-119)
    "write-target-unread": Row("record", 7, "tests/shell/test_mw107_r274_shell.py::test_an_unreadable_write_that_passes_for_a_session_leaves_one_calls_log_row", None),  # gate_outside.py; a log line once per event: an unreadable write target passed for a session (R274a 8.2); block 7 by card 2, a named exception of R274b
    "write-target-unresolved": Row("record", 7, "tests/shell/test_mw107_r274_shell.py::test_an_unreadable_list_of_checkouts_never_passes_silently", None),  # core_lock.py; a log line once per event; way out: tested

    # ---- card MW-128: the refusal delivery of the Stop hook (R301, R301a), record rows, each with its way-out test ----
    "refusal-delivered": Row("record", 7, "tests/shell/test_mw128_refusal_shell.py::test_the_way_out_of_refusal_delivered_is_the_ping_line_the_block_names", None),  # dispatch.py; MW-128: the record row of the inbox refusal record the Stop hook wrote, once per gate refusal row id; way out: the ping line `mkway inbox <id>` the block names
    "refusal-delivery-failed": Row("record", 7, "tests/shell/test_mw128_refusal_shell.py::test_the_way_out_of_refusal_delivery_failed_is_the_error_row_that_names_the_refusal", None),  # dispatch.py; MW-128, R301a 2: the calls-log error row of a failed inbox write (the Stop is allowed), with a screen line and a start-line notice; way out: the session tells its orderer itself
    "refusal-no-orderer": Row("record", 7, "tests/shell/test_mw128_refusal_shell.py::test_the_way_out_of_refusal_no_orderer_is_one_record_row_and_no_block", None),  # dispatch.py; MW-128, R301a 3: no orderer known, one record row per gate refusal row id and no block; way out: none needed, the owner reads the row

    # ---- card MW-132: the handoff notice of the Stop hook (R337, R337a, R338, R338a), record rows, each with its way-out test ----
    "handoff-notice": Row("record", 7, "tests/shell/test_mw132_handoff_shell.py::test_the_way_out_of_handoff_notice_is_the_ping_line_the_block_names", None),  # dispatch.py; MW-132: the record row of the inbox notice the Stop hook wrote for a builder that ended a turn with no send to its orderer, once per turn; way out: the ping line `mkway inbox <id>` the block names
    "handoff-no-orderer": Row("record", 7, "tests/shell/test_mw132_handoff_shell.py::test_the_way_out_of_handoff_no_orderer_is_one_record_row_and_no_block", None),  # dispatch.py; MW-132, R337 (b): the orderer is the owner, empty or the session itself: one record row per turn end and no block; way out: none needed, the owner reads the row
    "handoff-no-turn-start": Row("record", 7, "tests/shell/test_mw132_handoff_shell.py::test_the_way_out_of_handoff_no_turn_start_is_one_record_row_and_no_block", None),  # dispatch.py; MW-132, R340a: the engine holds no prompt row of the session (it saw no turn begin), so nothing is judged and the stop is allowed; way out: none needed, the session tells its orderer itself with `mkway send`
    "handoff-notice-failed": Row("record", 7, "tests/shell/test_mw132_handoff_shell.py::test_the_way_out_of_handoff_notice_failed_is_the_error_row_and_the_screen_line", None),  # dispatch.py; MW-132, R338 6: the calls-log error row of a failed notice write or a failed fact read (the Stop is allowed, one try per turn), with a screen line and a start-line notice; way out: the session tells its orderer itself

    # ---- card 8: audits of the ask lane and the reader's inputs (K7, K3) ----
    "ask-answered-not-lead": Row("K7", None, "tests/test_mw119_answer_intake.py::test_the_way_out_of_ask_answered_not_lead_is_the_lead_who_records_it", None),  # core_ask.py; way out: tested
    "reader-read-refused": Row("K3", None, "tests/test_mw116_way_out.py::test_the_way_out_of_reader_read_refused_is_a_listed_file", None),  # reader_allow.py, reader_hook.py; MW-116: way out: a listed file
    "reader-busy": Row("K3", None, "tests/test_mw116_way_out.py::test_the_way_out_of_reader_busy_is_to_end_the_run_and_start_again", None),  # reader_allow.py; MW-116: way out: end the run, start again
    "verdict-reader-unguarded": Row("K3", None, "tests/test_mw116_way_out.py::test_the_way_out_of_verdict_reader_unguarded_is_a_guarded_rerun", None),  # core_verdict_add.py; MW-116: way out: trust the folder, start, a guarded re-run
    "ask-deadline-not-passed": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_deadline_not_passed_is_to_wait_for_the_deadline", None),  # asks.py; way out: tested
    "ask-no-default": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_no_default_is_the_owners_answer", None),  # asks.py; way out: tested
    "ask-not-open": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_not_open_is_a_new_open_ask", None),  # asks.py; way out: tested
    "ask-not-reversible": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_not_reversible_is_the_owners_answer", None),  # asks.py; way out: tested
    "ask-unknown": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_unknown_is_an_id_that_mkway_asks_lists", None),  # asks.py; way out: tested
    "ask-not-written": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_not_written_is_to_write_the_ask_file", None),  # core_ask.py; way out: tested
    "ask-sources-kind": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_sources_kind_is_the_kind_line", None),  # core_ask.py; way out: tested
    "ask-sources-lines": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_sources_lines_is_the_line_of_the_kind", None),  # core_ask.py; way out: tested
    "ask-sources-missing": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_sources_missing_is_the_sources_file", None),  # core_ask.py; way out: tested
    "ask-tool-off": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_ask_tool_off_is_the_ask_file_route", None),  # core_ask.py; way out: tested
    "check-sha-mismatch": Row("K3", None, "tests/test_mw019_gate.py::test_the_dispatcher_refuses_a_stale_check_write", None),  # core_ask.py; way out: tested
    "checker-not-found": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_checker_not_found_is_the_agent_definition_of_the_checker", None),  # core_verdicts.py; way out: tested
    "checker-not-read-only": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_checker_not_read_only_is_a_checker_that_lists_read_and_grep", None),  # core_verdicts.py; way out: tested
    "close-unchecked-outbox": Row("K3", None, "tests/test_mw019_close.py::test_the_orderers_close_is_judged_too", None),  # cardtool.py; way out: tested
    "search-missing": Row("K7", None, "tests/test_mw113_way_out_ask.py::test_the_way_out_of_search_missing_is_a_search_before_the_question", None),  # core_ask.py; way out: tested
    "verdict-by-author": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_by_author_is_a_caller_who_did_not_write_the_test", None),  # core_verdicts.py; way out: tested
    "verdict-by-committer": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_by_committer_is_a_session_that_did_not_commit_the_test", None),  # core_verdicts.py and core_verdict_add.py; way out: tested at the add and at the close
    "verdict-by-holder": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_by_holder_is_a_session_that_never_held_the_card", None),  # core_verdicts.py and core_verdict_add.py; way out: tested at the add and at the close
    "verdict-by-owner": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_by_owner_is_a_reader_session", None),  # core_verdict_add.py; way out: tested
    "verdict-card-state": Row("K3", None, "tests/test_mw113_command_e2e.py::test_the_way_out_of_verdict_card_state_is_opening_a_proposed_card", None),  # core_verdict_add.py; way out: tested (MW-117: a builder may hold an open card, R272 G3)
    "verdict-no-red-proof": Row("K3", None, "tests/shell/test_mw117_verdict_window_shell.py::test_the_way_out_of_verdict_no_red_proof_is_the_red_commit", None),  # core_verdict_add.py; way out: tested (MW-117)
    "verdict-file-by-command": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_file_by_command_is_the_verdict_add_command", None),  # gate_outbox.py; way out: tested
    "verdict-missing": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_missing_is_a_verdict_row_for_every_node", None),  # core_verdicts.py; way out: tested
    "verdict-no-caller": Row("K3", None, "tests/test_mw113_command_e2e.py::test_the_way_out_of_verdict_no_caller_is_the_plain_form_in_a_session_with_the_hooks", None),  # core_verdict_add.py; way out: tested
    "verdict-no-reader-run": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_no_reader_run_is_a_fresh_checker_run", None),  # core_verdict_add.py; way out: tested
    "verdict-node-unknown": Row("K3", None, "tests/test_mw113_command_e2e.py::test_the_way_out_of_verdict_node_unknown_is_a_node_the_card_names", None),  # core_verdict_add.py; way out: tested
    "verdict-recut-exceeded": Row("K3", None, None, 8),  # core_verdict_recut.py; gap: the way out is `mkway card withdraw` then `card new` (R275), and the command is missing (engine gap G11), tests/test_mw113_way_out_verdicts.py::test_the_orderer_withdraws_the_card_and_opens_a_new_one is xfail
    "verdict-recut-no-change": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_recut_no_change_is_a_commit_that_changes_the_cut", None),  # core_verdict_recut.py; way out: tested
    "verdict-recut-not-lead": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_recut_not_lead_is_the_orderer", None),  # core_verdict_recut.py; way out: tested
    "verdict-recut-nothing": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_recut_nothing_is_a_weak_verdict_to_answer", None),  # core_verdict_recut.py; way out: tested
    "verdict-recut-pending": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_recut_pending_is_a_fresh_reader_after_the_recut", None),  # core_verdicts.py; way out: tested
    "verdict-recut-stale": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_recut_stale_is_to_commit_the_change", None),  # core_verdict_recut.py; way out: tested
    "verdict-run-before-recut": Row("K3", None, "tests/shell/test_mw100_replay.py::test_replay_two_the_recut_route_lets_the_verdict_check_pass", None),  # core_verdict_add.py; way out: tested
    "verdict-runs-exceeded": Row("K3", None, "tests/test_mw113_command_e2e.py::test_the_way_out_of_verdict_runs_exceeded_is_a_recut_then_a_fresh_reader", None),  # core_verdict_add.py; way out: tested
    "verdict-stale": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_stale_is_a_fresh_reader_run_after_the_last_commit", None),  # core_verdict_add.py; way out: tested
    "verdict-unproven": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_verdict_unproven_is_a_row_written_by_the_command", None),  # core.py; way out: tested
    "verdict-weak": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_a_weak_or_wrong_verdict_is_a_recut_then_a_fresh_true[weak]", None),  # core_verdicts.py; way out: tested
    "verdict-wrong": Row("K3", None, "tests/test_mw113_way_out_verdicts.py::test_the_way_out_of_a_weak_or_wrong_verdict_is_a_recut_then_a_fresh_true[wrong]", None),  # core_verdicts.py; way out: tested

    # ---- kinds with no gap: a way-out test exists (the rows of card 8 hold theirs in block 8) ----
    # MW-114 (R270d): the recorded red test with raw SQL-like strings, now passing, is judged passed
    "red-ids-still-red": Row("K2", None, "tests/shell/test_mw114_nodeid_shell.py::test_a_recorded_red_test_with_raw_sql_strings_that_now_passes_is_judged_passed", None),  # core_red.py
}
