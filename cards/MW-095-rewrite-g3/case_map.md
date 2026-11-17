# case_map of MW-095
# literal: tests/test_mw080_docs.py::test_the_schema_and_keys_name_the_verdict_add_mode 1 - R210a: the last-position check became a presence check
# literal: tests/test_mw016_version.py::test_the_changelog_covers_the_register ' ' - the space of the old f-string message, replaced by the missing list check, which is stronger
# literal: tests/test_mw008_ledger.py::test_ledger_ids_follow_the_default_and_the_profile_pattern 1 - the index -1 of the old per-iteration check, replaced by the check of the last two rows after both adds, with both codes checked
# literal: tests/test_mw012_class.py::test_a_missing_class_reads_integrity 'gate' - the subscript e["gate"] = "m" became the dict keyword gate="m" with the same entries
# literal: tests/test_mw018_docs.py::<module> 'README.md' - the README constant of the dead helper _section, which no test calls, deleted
# literal: tests/test_mw018_docs.py::<module> '## Messaging order' - the HEADING constant of the same dead helper, deleted
# literal: tests/test_mw018_docs.py::<module> '\n' - the newline of the dead helper _section, deleted
# literal: tests/test_mw018_docs.py::<module> '^## ' - the section regex of the dead helper _section, deleted
# literal: tests/test_mw018_docs.py::<module> ' ' - the join of the dead helper _section, deleted
# literal: tests/test_mw018_docs.py::<module> 'utf-8' - the encoding of the README read of the dead helper _section, deleted
# literal: tests/test_mw003_batch3.py::test_start_and_compaction_never_move_the_baseline 'hookSpecificOutput' - moved into the helper _change_lines of the same file, the sequence test keeps the check
# literal: tests/test_mw003_batch3.py::test_start_and_compaction_never_move_the_baseline 'additionalContext' - moved into the helper _change_lines of the same file, the sequence test keeps the check
# literal: tests/test_mw003_batch3.py::test_start_and_compaction_never_move_the_baseline 'card changes since' - moved into the helper _change_lines of the same file, the sequence test keeps the check
