# MW-007: Questions to the owner go one way

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the gate is a port of a working hook; each reading of the order is a Log line |
| **Canon** | none for the ask gate: the engine has no ledger; the basis is the order of 2026-11-10 |
| **Paths** | `engine/`, `tests/`, `README.md`, `cards/REGISTER.md`, `cards/MW-007-owner-ask/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; `card new` could not run here (the engine repository has no
profile of its own), so the card and its register row are written by hand in the form `card new` writes: the
register row is `proposed`, and the owner's terminal opens and closes it.

## 1. Goal

«only group A» — owner, 2026-11-10, in the order that carries this card.
Questions to the owner go one way: a session may ask the owner only after it has written down the sources it
checked. The engine gets a generic gate: an edit gate (an ask file needs a sources file beside it), a stop gate (a
reply that asks needs an ask file written in this turn), profile keys with defaults, a start block that names the
gates that are off, and one README section.

## Acceptance examples

Rows are added with the red tests of each step.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | `owner_ask` keys in the schema | no such key: the profile is invalid | `dir` (repo path), `markers`, `sources` (non-empty lists; a source name has no space or colon); an unknown key is invalid | tests/test_mw007_owner_ask.py::test_owner_ask_keys_are_in_the_schema |
| E2 | defaults and overrides | none | no `owner_ask`: folder `<bundle.root>/asks`, marker `Request:`, source `review`; a profile value replaces it; an unusable value falls back | tests/test_mw007_owner_ask.py::test_owner_ask_defaults_and_overrides |
| E3 | KEYS.md lines | none | three «in schema now» lines in «Added keys», each with its default | tests/test_mw007_owner_ask.py::test_owner_ask_keys_are_lines_of_keys_md_with_their_defaults; tests/test_keys.py::test_keys_md_has_one_line_per_draft_key |
| E4 | edit gate scope | none | only Write, Edit or MultiEdit of `<asks dir>/<name>_ask.md` is gated; other folders, nested folders, the sources file, other tools, a missing path are allowed | tests/test_mw007_edit_gate.py::test_edit_gate_leaves_other_writes_alone |
| E5 | sources file and kind | none | no sources file: `ask-sources-missing` naming the file; no `kind:` line: `ask-sources-kind` naming `substance\|session\|lock`; any path spelling | tests/test_mw007_edit_gate.py::test_an_ask_needs_a_sources_file_with_a_kind |
| E6 | kind substance | none | `<source>: N contradictions` and one `> <source>: <verbatim>` line, else `ask-sources-lines` naming each missing line only | tests/test_mw007_edit_gate.py::test_substance_needs_a_count_line_and_a_quote_line; tests/test_mw007_edit_gate.py::test_a_full_substance_sources_file_lets_the_ask_through |
| E7 | kinds session and lock | none | session: `checked: ListAgents`; lock: `checked:` plus a lock state; else `ask-sources-lines` naming the line | tests/test_mw007_edit_gate.py::test_session_and_lock_kinds_each_need_their_checked_line |
| E8 | folder and sources from the profile | none | `owner_ask.dir` moves the gated folder; each `owner_ask.sources` name needs its count and quote line | tests/test_mw007_edit_gate.py::test_folder_and_sources_come_from_the_profile |
| E9 | unreadable sources | none | a folder or non-UTF-8 file in its place: refused, never a crash, never an allow | tests/test_mw007_edit_gate.py::test_an_unreadable_sources_file_refuses_and_never_crashes |
| E10 | wired in the edit group | none | manifest entry `owner_ask.edit` (gate `owner_ask`, `onFailure: block`) after `subtask`; refusal tag and log row; `gates.owner_ask.on: false` turns it off | tests/test_mw007_edit_gate.py::test_the_edit_gate_runs_in_the_edit_group_and_has_a_switch; tests/test_manifest.py::test_on_entries_carry_function_reasons_and_on_failure_reason |
| E11 | stop gate, the marker | none | a reply with no marker line (or a marker mid-line) passes; a line that starts with the marker (after spaces or `**`, on any line) needs an ask file written after the last real user message, else `ask-not-written`; `stop_hook_active` never blocks | tests/test_mw007_stop_gate.py::test_a_reply_without_the_marker_is_never_blocked; tests/test_mw007_stop_gate.py::test_a_marker_line_needs_an_ask_written_in_this_turn; tests/test_mw007_stop_gate.py::test_stop_hook_active_never_blocks |
| E12 | what counts as written | none | Write, Edit, MultiEdit of an ask file that exists on disk; not a Read, another path, or a refused write | tests/test_mw007_stop_gate.py::test_only_a_real_ask_file_counts_as_written |
| E13 | marker and folder from the profile | none | `owner_ask.markers` (each string) and `owner_ask.dir` | tests/test_mw007_stop_gate.py::test_marker_and_folder_come_from_the_profile |
| E14 | transcript missing or broken | none | no crash; a marker line is blocked with the reason named; no marker, no message: allowed | tests/test_mw007_stop_gate.py::test_a_missing_or_broken_transcript_does_not_crash_the_gate |
| E15 | wired in the stop group | none | manifest entry `owner_ask.stop` (`onFailure: none`) gets the hook input; `decision: block` with the tag and a log row; one switch for both entries | tests/test_mw007_stop_gate.py::test_the_stop_gate_runs_in_the_stop_group_and_has_a_switch; tests/test_manifest.py::test_on_entries_carry_function_reasons_and_on_failure_reason |
| E16 | start block, gates off | `gates on` and the count of entries without code only | a line `gates off:` right after `gates on:` names each loaded gate entry that does not run, in manifest order, or `none`; the dispatcher's SessionStart context carries it | tests/test_mw007_start_block.py::test_the_start_block_names_every_gate_the_profile_turns_off; tests/test_mw007_start_block.py::test_the_dispatcher_prints_the_off_line_at_session_start |
| E17 | entries without code | counted | still only counted; an entry with no reason ids stays in `not loaded` | tests/test_mw007_start_block.py::test_a_gate_without_code_is_not_named_as_off |
| E18 | default off, nested mode | none | named as off; a gate the profile turns on is not | tests/test_mw007_start_block.py::test_a_default_off_gate_and_a_nested_mode_are_named_as_off |
| E19 | invalid profile | `gates on: none` only | every loaded gate is named as off | tests/test_mw007_start_block.py::test_an_invalid_profile_names_every_loaded_gate_as_off |
| E20 | README section | none | one section `## Questions to the owner`, with a body | tests/test_mw007_readme.py::test_the_readme_has_one_section_questions_to_the_owner |
| E21 | what the section states | none | both gates, the three kinds and their lines, every reason id of the manifest entries, the three keys with defaults, `paths.exempt`, `gates off:` | tests/test_mw007_readme.py::test_the_section_states_the_gates_the_keys_and_their_defaults |
| E22 | method sentences | none | a fresh reader checks an ask before it goes; C-24 = the owner closes the commit lock while the owner questions a flaw | tests/test_mw007_readme.py::test_the_section_adds_the_two_method_sentences |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | W0 | (this commit) | card and register row written by hand (no profile in this repository for `card new`); register row `proposed`. Start checks, each alone: `pwd` = <worktree>, HEAD 58e36c1, `git status --short` = one untracked file (`tests/test_zz_scratch.py`, another session's: left alone, kept out of every commit). Baseline full suite at 58e36c1: 302 passed (that count includes the scratch file's one test). Order of the parts: 3 (profile keys) first, because the gates of parts 1 and 2 read them; then 1, 2, 4, 5 |
| 2026-11-10 | W0 | 4528438 | the «(this commit)» row above is 4528438 (amended once to add the trailer) |
| 2026-11-10 | P3 | (this commit) | red part 3 (E1, E2, E3): the three new tests fail for the right reason (schema refuses `owner_ask`; `profiles.owner_ask` missing; no KEYS.md lines), and `tests/test_keys.py::test_keys_md_has_one_line_per_draft_key` now expects the three keys (test change by MW-007: an extension of the expected set, nothing weakened). Targeted run of the two files: 4 failed, 1 passed. Full suite not run for a red commit: no engine file changed since the baseline of W0 |
| 2026-11-10 | P3 | 1bf5f9c | the «(this commit)» row above is 1bf5f9c |
| 2026-11-10 | P3 | (this commit) | green part 3 (E1, E2, E3): schema group `owner_ask`; `profiles.owner_ask(profile)` with the defaults as constants beside `state_dir`; three KEYS.md lines. Test changes, each by MW-007 and none weakening: (1) E2 in `test_mw007_owner_ask.py` passed a whole profile to `profiles.validate` where the `owner_ask` object was meant (my test slip, hidden at red by the earlier AttributeError): the line now validates the profile that holds the values; (2) `tests/test_schema.py::test_schema_declares_the_q2_groups` expects the new group `owner_ask` (found at green, not at red: it pins the set of groups). KEYS.md wording of two defaults changed to the form E3 reads (`Request:`, `review` in backticks). Targeted (five files): 17 passed. Full suite with the term scan: 305 passed |
| 2026-11-10 | P3 | 2de571e | the «(this commit)» row above is 2de571e |
| 2026-11-10 | P1 | (this commit) | red part 1 (E4-E10): `tests/test_mw007_edit_gate.py` (the retro hook's cases ported to the three kinds of the order, plus the profile, unreadable-file and dispatcher cases) and `tests/test_manifest.py` expects the entry `owner_ask.edit` after `subtask` (test change by MW-007: an extension of the expected list, nothing weakened). The tests fail for the right reason: no module `gate_owner_ask`, no manifest entry. Readings of the order, each decided without waiting (see the green row): the count line is written per configured source; `kind: lock` takes any text after `checked:`; no kind `process`. Targeted run of the two files: 17 failed, 4 passed. Full suite not run for a red commit |
| 2026-11-10 | P1 | 6cab20d | the «(this commit)» row above is 6cab20d |
| 2026-11-10 | P1 | (this commit) | green part 1 (E4-E10): `engine/gate_owner_ask.py` (`check` on one function for both entries; the Stop branch comes with part 2) and the manifest entry `owner_ask.edit` (gate `owner_ask`, group `edit`, matcher `Edit\|Write\|MultiEdit`, `onFailure: block`, reasons `ask-sources-missing`, `ask-sources-kind`, `ask-sources-lines`). Readings of the order: (a) the count line `<source>: N contradictions` and the quote line are required for EACH name of `owner_ask.sources` (default one name, `review`, which is exactly the order's wording; two names reproduce the retro hook's two-source rule); (b) `kind: lock` takes any text after `checked:`, since the order gives the placeholder `<lock state>` and no fixed word; (c) the retro hook's fourth kind `process` is not ported, the order lists three; (d) the ask file must sit directly in the folder (a nested folder is not gated), as in the retro hook; (e) a path that cannot be proved an ask path is allowed, an unreadable sources file refuses. The edit group's subtask gate still decides first: a branch that keeps its asks folder outside its card Paths lists it in `paths.exempt`. Targeted (three files): 24 passed. Full suite with the term scan: 319 passed |
| 2026-11-10 | P1 | 56a9cdf | the «(this commit)» row above is 56a9cdf |
| 2026-11-10 | P2 | (this commit) | red part 2 (E11-E15): `tests/test_mw007_stop_gate.py` (the retro hook's Stop cases ported, plus: the marker and folder from the profile, an ask write that is not on disk, a missing or broken transcript, and the dispatcher) and `tests/test_manifest.py` expects the entry `owner_ask.stop` after `unresolved` (test change by MW-007: an extension of the expected list, nothing weakened). The tests fail for the right reason: the gate's context carries no hook input (`TypeError` on `hook_input`), and there is no Stop manifest entry. Targeted run of the two files: 10 failed, 4 passed. Full suite not run for a red commit |
| 2026-11-10 | P2 | 68ab5c0 | the «(this commit)» row above is 68ab5c0 |
| 2026-11-10 | P2 | (this commit) | green part 2 (E11-E15): `gate_owner_ask._stop` and the manifest entry `owner_ask.stop` (gate `owner_ask`, group `stop`, no matcher, `onFailure: none`, reason `ask-not-written`); `Context.hook_input` (the whole hook input) filled by `dispatch.make_context`. Readings of the order: (f) «written since the last user message» is read as: a Write, Edit or MultiEdit of an ask file that EXISTS on disk now, so a write the edit gate refused does not count (the retro hook counted the attempt); (g) a transcript that cannot be read gives no proof of a write, so a marker line is still blocked and the text says so, and `stop_hook_active` still never blocks; (h) the marker may sit on any line of the reply, after spaces or `**`, and is case-sensitive. Test change by MW-007, none weakening: `tests/test_gate.py::test_fixture_gates_prove_the_interface` expects the new Context field `hook_input` (found at green: it pins the field set). Targeted (six files): 71 passed before that change, the gate file then 9 passed. Full suite with the term scan: 326 passed |
| 2026-11-10 | P2 | 019a818 | the «(this commit)» row above is 019a818 |
| 2026-11-10 | P4 | (this commit) | red part 4 (E16-E19): `tests/test_mw007_start_block.py`. The five tests fail for the right reason: the block has no `gates off:` line. Reading of the order: «every gate that is off» is each entry that has code and reason ids but does not run; the entries without code stay in the existing count, because no switch can change them. Targeted run: 5 failed. Full suite not run for a red commit |
| 2026-11-10 | P4 | b3e8f0a | the «(this commit)» row above is b3e8f0a |
| 2026-11-10 | P4 | (this commit) | green part 4 (E16-E19): `startline.render` adds the line `gates off: <entries or none>` right after `gates on:`; the entries are those with code and reason ids that do not run (profile switch, manifest default, nested mode, invalid profile). No existing test changed. Targeted (four files): 29 passed. Full suite with the term scan: 331 passed |
| 2026-11-10 | P4 | 634b942 | the «(this commit)» row above is 634b942 |
| 2026-11-10 | P5 | (this commit) | red part 5 (E20-E22): `tests/test_mw007_readme.py`. The three tests fail for the right reason: the README has no such section. The reason ids and the key names the section must hold are read from the manifest and the schema, so the text cannot drift from the gate. Targeted run: 3 failed. Full suite not run for a red commit |
| 2026-11-10 | P5 | d92dc1d | the «(this commit)» row above is d92dc1d |
| 2026-11-10 | P5 | (this commit) | green part 5 (E20-E22): README section «Questions to the owner» before «Known limits», with the two method sentences. The README's «State» paragraph (which gates are on) is NOT changed: the order asks for one section; it still names only the MW-003 gates. First full run found two failures in `tests/test_install.py` (`mkway check` runs the suite in an installed copy, which has no README): my three README tests lacked the marker `engine_repo` that `test_register.py` uses for the same reason; added it (a fix of my tests, no assertion changed). Targeted: the README file and the two install tests, 5 passed. Full suite with the term scan: 334 passed (333 without the other session's untracked scratch test, which the run includes). Per-commit suite policy: every green commit ran the whole suite (302 baseline, then 305, 319, 326, 331, 334); the red commits and the card commit ran the touched files only |
| 2026-11-10 | P5 | d57add9 | the «(this commit)» row above is d57add9. All five parts are done, E1-E22 name tests that exist and pass. The card stays `proposed`: the owner's terminal opens and closes it. Not built, by reading of the order: no `process` kind; no change to the README «State» paragraph |
