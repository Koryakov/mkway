# MW-012: Form gates: watch mode and trip

| | |
|---|---|
| **Appetite** | 2 hours — from 2026-11-10 |
| **Status** | proposed |
| **Created / updated** | 2026-11-10 / 2026-11-10 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: the order of 2026-11-10 carries every rule; each reading of it is a Log line |
| **Canon** | none for gate modes: the engine has no ledger; the basis is the order of 2026-11-10 and its nine-point design note |
| **Paths** | `engine/`, `tests/`, `fixtures/synthetic/`, `README.md`, `cards/REGISTER.md`, `cards/MW-012-watch-mode/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; `card new` could not run here (the engine repository has no
profile of its own), so the card and its register row are written by hand in the form `card new` writes. The register
row is `proposed`; the owner's terminal opens and closes it. Parts: 1 the gate class and the calls log; 2 the watch
marker and the trip; 3 first install in watch, `gate watch`, `gate on`; 4 the start block; 5 README and KEYS.

## 1. Goal

The owner's rule (paraphrased in English; the engine repository is English only): a gate that only checks form must
not stay in the way when it refuses much more often than it is right. So every gate has a class, `integrity` or
`form`. An integrity gate never degrades and never reads a mode marker. A form gate has a watch mode: it still runs,
a refusal becomes a `would-refuse` log row and the call goes ahead. A form gate goes into watch by itself when, in a
rolling day, it has at least `gates.trip.min_calls` calls (default 20) and refuses more than `gates.trip.share` of
them (default 0.34); a first install starts every form gate in watch; only the owner's `mkway gate on <name>` returns
a gate to blocking. Not built: a Stop notice, an automatic return to blocking.

## Acceptance examples

Rows are added with the red tests of each part.

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | class in the manifest | no `class` key | every entry names `integrity` or `form`; form is exactly `owner_ask.edit`, `owner_ask.stop`, `search`; every blocking entry has a class | tests/test_mw012_class.py::test_every_manifest_entry_has_a_class |
| E2 | missing class | none | no `class` reads `integrity`; a gate is form only when all its entries are | tests/test_mw012_class.py::test_a_missing_class_reads_integrity |
| E3 | calls log | none | one row (time, gate, verdict) per gate that ran, per call, in `<state>/gate_calls.jsonl`, for allow and refuse | tests/test_mw012_class.py::test_the_calls_log_gets_one_row_per_gate_per_call |
| E4 | watch | a refusal always blocks | with a marker a form gate still runs; its refusal is a `would-refuse` row (same reason id and text) and the call is allowed | tests/test_mw012_watch.py::test_a_watch_marker_turns_a_form_refuse_into_would_refuse |
| E5 | integrity | none | an integrity gate (class or none) never reads a marker and never trips | tests/test_mw012_watch.py::test_an_integrity_gate_never_reads_a_marker_and_never_trips |
| E6 | trip | none | the 20th call of a day with 7 refusals is refused, writes the marker (cause `tripped`) and a `gate-tripped` row; the next call is a `would-refuse` | tests/test_mw012_watch.py::test_a_form_gate_trips_at_20_calls_with_7_refusals |
| E7 | no trip | none | no trip at 19 calls, at 6 of 20, or when the rows are older than 24 hours | tests/test_mw012_watch.py::test_no_trip_below_20_calls_or_at_or_under_the_share |
| E8 | errors | none | `error` rows are neither calls nor refusals for the trip | tests/test_mw012_watch.py::test_error_rows_never_count_for_the_trip |
| E9 | trip keys | none | `gates.trip.min_calls` and `gates.trip.share` replace 20 and 0.34; the schema takes them; an unusable value falls back | tests/test_mw012_watch.py::test_the_trip_numbers_come_from_the_profile |
| E10 | first install | no marker | a first install (no state folder yet) writes a marker, cause `installed`, for each form gate that is on, and a `gate-watch-installed` row; none for integrity gates or a form gate that is off | tests/test_mw012_commands.py::test_a_first_install_writes_a_watch_marker_for_each_form_gate_that_is_on |
| E11 | re-install | none | a re-install keeps the modes: no marker is added or rewritten | tests/test_mw012_commands.py::test_a_re_install_keeps_the_modes |
| E12 | `gate watch` | no such command | the owner's `gate watch <name>` writes a marker, cause `owner`, and a `gate-watch` row; the profile is unchanged | tests/test_mw012_commands.py::test_gate_watch_writes_an_owner_marker |
| E13 | `gate on` | sets `on` only | also removes the marker and writes a `gate-on` row | tests/test_mw012_commands.py::test_gate_on_removes_the_marker |
| E14 | integrity gate | none | `gate watch` on an integrity gate is refused: «integrity gates never watch» | tests/test_mw012_commands.py::test_an_integrity_gate_never_watches |
| E15 | owner only | none | a session's `gate watch` is `owner-only-command` at the lock gate and at the CLI | tests/test_mw012_commands.py::test_a_session_cannot_run_gate_watch |
| E16 | start block line | no line | one line per form gate in watch: `gate <name>: WATCH since <time> (<cause>; <refused> of <calls> in 24 h); would-refuse today: <n>; log: <path>` | tests/test_mw012_start.py::test_the_start_block_has_a_line_for_each_gate_in_watch |
| E17 | `gates on:` list | no mark | an entry of a form gate in watch carries `(watch)`; nothing else changes | tests/test_mw012_start.py::test_the_gates_on_list_marks_a_gate_in_watch |
| E18 | README section | none | one section `## Watch mode and trip`, with a body | tests/test_mw012_readme.py::test_the_readme_has_one_section_watch_mode_and_trip |
| E19 | what the section states | none | what trips, what watch does, who resets, why integrity gates never degrade | tests/test_mw012_readme.py::test_the_section_states_what_trips_who_resets_and_why |
| E20 | KEYS lines | none | `gates.trip.min_calls` and `gates.trip.share` are lines of the added keys, in schema now, with their defaults; the keys test lists them | tests/test_mw012_readme.py::test_keys_md_lines_state_the_two_trip_keys |

## 8. Log

One line per step. No re-run of a check or an agent round without a new input named in the Log row.

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-10 | W0 | 50d9c8a | card and register row written by hand. Start checks, each alone: `pwd` = <worktree>, HEAD c7df389, `git status --short` empty. Readings of the order, each decided without waiting: (a) the whole suite runs once at the end, as ordered (about 12 min until the three slow `mkway check` tests are made fast elsewhere; those three tests are not edited here); each part commit runs its targeted tests only, as the MW-011 parts did; (b) the two trip keys sit under the existing per-gate schema object (`gates.<name>.min_calls`, `gates.<name>.share`), so the schema leaf `gates` stays one leaf and only `gates.trip` is read; (c) the calls log and the marker are keyed by the gate's profile switch name (`owner_ask` covers its edit and stop entries) |
| 2026-11-10 | P1 | 2529cc4 | red part 1 (E1-E3): `tests/test_mw012_class.py` (with the helper `tests/_mw012.py` and the synthetic gate `fixtures/synthetic/fixture_mw012.py`); three tests fail for the right reason: no `class` key, no `gatemode` module, no `gate_calls.jsonl`. Full suite not run for a red commit |
| 2026-11-10 | P1 | (green commit, the one that carries this row) | green part 1 (E1-E3): `engine/gatemode.py` (`entry_class`, `gate_class`, calls log), `engine/manifest.json` (`class` on all 40 entries; form: `owner_ask.edit`, `owner_ask.stop`, `search`), `engine/dispatch.py` (one calls row per gate that ran). Test change, not a weakening: `tests/test_manifest.py` FIELDS gains `class` (the exact-set check stays exact). Targeted (class, dispatch, manifest, start line, e2e, install without the `check` tests): green |
| 2026-11-10 | P2 | b976488 | red part 2 (E4-E9): `tests/test_mw012_watch.py`; E4, E6, E9 fail for the right reason (a marker changes nothing, no trip, the schema refuses the trip keys); E5, E7, E8 are guards that hold before the code and must keep holding. Full suite not run for a red commit |
| 2026-11-10 | P2 | (green commit, the one that carries this row) | green part 2 (E4-E9): `engine/dispatch.py` (a form gate in watch: its refuse is a `would-refuse` row with the message, the call is allowed; after a refuse by an enforcing form gate the trip runs, the call stays refused; `gate-tripped` row), `engine/gatemode.py` (`trip`, markers), `engine/profile.schema.json` (`min_calls`, `share` on the per-gate object). Readings: the calls row of a watched refusal says `refuse` (the share stays a measure of the rule, not of the mode); an error in a form gate is still the gate-error path, watch changes only a refuse verdict. No test changed. Targeted (class, watch, dispatch, keys, schema, profile): green |
| 2026-11-10 | P3 | 14b38a3 | red part 3 (E10-E15): `tests/test_mw012_commands.py`; six tests fail for the right reason: no marker at install, no `gate watch` command, `gate on` keeps the marker, the lock gate does not know `gate watch`. Full suite not run for a red commit |
| 2026-11-10 | P3 | (green commit, the one that carries this row) | green part 3 (E10-E15): `engine/install.py` (a first install, read as «no state folder yet», writes a marker `installed` and a `gate-watch-installed` row for each form gate that is on), `engine/mkway.py` (`gate watch`, refused on an integrity gate as `gate-watch-integrity`; `gate on` removes the marker and writes `gate-on`), `engine/gate_lock.py` (`gate watch` is owner-only). Readings: `gate watch` on a gate the profile turned off still writes the marker; `gate off` leaves a marker alone. No test changed. Targeted (commands, lock, helpers, start keys, fix list, close fix, install without the `check` tests, e2e, install seal, orderer): green |
| 2026-11-10 | P4 | c0f7078 | red part 4 (E16-E17): `tests/test_mw012_start.py`; both fail for the right reason: no WATCH line, no `(watch)` mark. The first attempt to commit was refused by the shell hook because the message held parentheses, which the order forbids; the message was rewritten without them. Full suite not run for a red commit |
| 2026-11-10 | P4 | (green commit, the one that carries this row) | green part 4 (E16-E17): `engine/gatemode.py` (`watching_gates`, `watch_line`), `engine/startline.py` (the line after `gates off:`, the `(watch)` mark). Reading: the would-refuse count matches the rows of the gate's entry names (`owner_ask` has an edit and a stop entry), by UTC date. No test changed. Targeted (start, start line, MW-007 start block, start keys, MW-008 start, cap, e2e): green |
| 2026-11-10 | P5 | 98eb789 | red part 5 (E18-E20): `tests/test_mw012_readme.py`; the three tests fail for the right reason: no README section, no KEYS lines. Test change, not a weakening: `tests/test_keys.py` lists the two new added keys in its exact expected set, so it failed too until the KEYS lines existed. Full suite not run for a red commit |
| 2026-11-10 | P5 | (green commit, the one that carries this row) | green part 5 (E18-E20): README section «Watch mode and trip» before «Owner hold», KEYS lines of `gates.trip.min_calls` and `gates.trip.share`. First README wording lacked the exact tokens `gate_calls.jsonl` and `gate_mode/<gate>.watch`; the README was reworded, no test changed. Whole suite with the term scan, run once for parts 1 to 5 as ordered: 538 passed in 704 s. No term-scan exception added |
