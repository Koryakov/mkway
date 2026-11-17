# MW-061: A command with a newline inside quotes is read whole

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the lead's task carries it, MW-048's quote rules stay as they are |
| **Canon** | none: the basis is a real install of 2026-11-12 where a builder's commit with a newline inside the quotes was refused as if the whole index were committed |
| **Paths** | `engine/helpers.py`, `engine/logs.py`, `tests/`, `cards/REGISTER.md`, `CHANGELOG.md`, `cards/MW-061-quoted-newline/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here. MW-048's quote rules (`$(...)`, a backtick and `$name` inside double quotes)
stay as they are.

## 1. Goal

«a newline inside single or double quotes (and inside a here-doc body) is part of the word, as bash reads it; a newline
outside quotes still separates commands; both commit gates and every shell gate must see the same parsed command (one
reader); the refusal log keeps the whole command (newlines shown as \n)» — lead's task, 2026-11-12.
The reader is `helpers.parse` (shlex, quote-aware), and `commit_files`, `commit_tests`, the lock gate and the delete gate
all read through it. Two readers were found that do not follow the quotes: `helpers._split_heredocs` cuts the text at
every newline and takes a `<<WORD` inside quoted text for a here-doc, so a message that names a marker has the rest of
its lines swallowed as a body (the quote never closes: `command-unparsed`); `logs.target_of` keeps the first line of a
command only. Not established: the cause of the real refusal. The exact command of the report (a newline and an empty line
inside double quotes, a trailer line with angle brackets, two folders after `--`, another card's red test staged) is
allowed by the real hook on this engine, with a line feed and with a carriage return and a line feed; the reader table
reads it whole. So the real refusal is not reproduced here; what is proven and fixed is above.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | a newline (and an empty line) inside `"..."`, inside `'...'`, two `-m`, a carriage return and a line feed, a `#` or an angle bracket inside the quotes, the real shape | read whole already | the message keeps its newlines, the paths after `--` are seen | tests/test_mw061_reader.py::test_a_newline_inside_quotes_is_part_of_the_word |
| E2 | a `<<WORD` inside quoted text with a newline after it | read as a here-doc: the rest swallowed, `command-unparsed` | quoted text: the commit is read whole; a real here-doc (`-F -`, `$(cat <<'EOF' ...)`) keeps its body | tests/test_mw061_reader.py::test_a_newline_inside_quotes_is_part_of_the_word; tests/test_mw061_reader.py::test_a_heredoc_body_is_part_of_the_message; tests/test_mw061_reader.py::test_the_text_after_a_heredoc_body_is_the_next_command; tests/test_mw061_reader.py::test_two_heredocs_on_one_line_take_their_bodies_in_order; tests/test_mw061_reader.py::test_a_comment_hides_a_marker; tests/test_mw061_reader.py::test_a_heredoc_with_no_delimiter_line_does_not_crash_the_reader; tests/test_mw061_reader.py::test_a_marker_inside_double_quotes_is_text_in_both_shells |
| E3 | a newline outside quotes | two commands | still two commands, the quoted newline of the second kept | tests/test_mw061_reader.py::test_a_newline_outside_quotes_still_separates_commands |
| E4 | MW-048 rules | `$(...)` and a backtick inside double quotes are substitutions | unchanged, with a newline inside the quotes too | tests/test_mw061_reader.py::test_the_rules_of_quoted_text_stay_as_they_were |
| E5 | the refusal log row of a multi-line command | the first line only | the command with each newline written `\n`, cut at 200 characters as before (MW-002 E13) | tests/test_mw061_reader.py::test_the_refusal_log_keeps_the_whole_command_with_newlines_shown_as_backslash_n; tests/test_mw061_e2e.py::test_a_refusal_row_holds_the_whole_command |
| E6 | the real hook, the exact command of the report, another card's red test staged | allowed | still allowed; a quoted `<<EOF` in the message too | tests/test_mw061_e2e.py::test_the_real_multiline_commit_is_allowed_through_the_real_hook |
| E7 | the real hook, the plain commit of the same state | denied `commit-tests-failed` | still denied | tests/test_mw061_e2e.py::test_the_same_state_as_a_plain_multiline_commit_is_denied |
| E8 | the real-shape replay (MW-038) | no multi-line message | a builder's multi-line commit passes the real hooks | tests/test_mw038_real_shape.py::test_s5_a_commit_message_with_a_newline_inside_the_quotes_passes_the_gates |
| E9 | register, changelog | no MW-061 | a register row; a line under the top changelog section; VERSION unchanged | tests/test_mw061_docs.py::test_register_changelog_and_card_name_the_card |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | start checks, each alone: `pwd` = the worktree, HEAD 6c6b79d, `git status --short` = clean | 6c6b79d | base of the card |
| 2026-11-12 | cause search: every place that splits a command into lines or statements: `helpers._split_heredocs` (a newline split before quotes are read; `<<WORD` found anywhere), `logs.target_of` (first line only); the shlex reader `helpers.parse`, `_blank_text`, `_tokens` follow the quotes; the gates read through `helpers.parse` (`commit_files`, `commit_tests`, `lock.shell`, `delete`), none splits the command itself | 6c6b79d | the reader table with the exact shape passes today; the quoted marker and the log target fail |
| 2026-11-12 | red: rows E1 to E9 (tests, card, register row, changelog line); the new tests with the card guards `test_meta_cards.py` and `test_cards.py`, not the whole suite (that runs once, at the green commit, as the task says) | the commit that carries this line | 4 failed for the right reason, 26 passed: the quoted `<<EOF` (reader and real hook: `command-unparsed`), and the log target cut at the first newline (reader and real hook). The rows that pass today (the exact real command with a line feed and with a carriage return and a line feed, newline outside quotes, MW-048 rules, the plain-commit deny, the replay step) pin behaviour that must stay. Nothing weakened; one assertion of mine on single quotes was dropped before this commit, as it pinned a reading MW-048 never had |
| 2026-11-12 | green: `helpers._split_heredocs` follows the quotes (a stack of code, single quote, double quote, `$(...)` and backtick frames; a `#` comment skipped; a body starts after the first newline outside quotes), called with the shell by `parse` and `unknown_shape`; `logs.target_of` writes the whole command with each newline as `\n`, cut at 200 | the commit that carries this line | rows E1 to E9 green, red commit 31489d1. Five reader pins for the new branches were added with the code (they pass at once). Whole suite once, `python -m pytest`, term scan included: 1262 passed, 2 failed in 772 s; the 2 failures were the term scan hitting the trailer text of my own tests (an address pattern, group B); the trailer was changed to a neutral text, then the two scan tests and the MW-038, MW-040 and MW-061 files were run again: 52 passed in 105 s. Not run again: the whole suite after that test-text change (the task asks for one run) |
