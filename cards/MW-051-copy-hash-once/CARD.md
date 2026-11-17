# MW-051: Install hashes the copy while writing it

| | |
|---|---|
| **Appetite** | 1 hour — from 2026-11-12 |
| **Status** | proposed |
| **Created / updated** | 2026-11-12 / 2026-11-12 |
| **Waiting for** | owner: opens the card and closes it |
| **Form** | card |
| **Decisions** | none new: a speed card from the MW-047 profile, the recorded hash value does not change |
| **Canon** | none for install speed: the basis is the profile of one `mkway install` |
| **Paths** | `engine/`, `tests/`, `CHANGELOG.md`, `cards/REGISTER.md`, `cards/MW-051-copy-hash-once/CARD.md` |

How to use: this card follows `cards/_TEMPLATE/CARD.md`; written by hand, as `card new` cannot run in the engine
repository. `VERSION` is not changed here.

## 1. Goal

The MW-047 profile of one `mkway install` (about 1.8 s) put about 1.1 s in `copy_hash` reading back every file install
had just written. Install computes the copy hash from the bytes it writes, with the same algorithm and the same order, so
the recorded value is the one a read of the disk gives; it does not read its fresh copy again. `mkway check` and the
start line keep reading the copy, as they verify what is on disk.

## Acceptance examples

| # | Item | Was | Must be | Test |
|---|---|---|---|---|
| E1 | the hash a normal install records | install read the whole copy back to hash it | equals `copy_hash(<copy>)` read from disk; install makes no `copy_hash` call | tests/test_mw051_copy_hash_once.py::test_install_records_the_hash_of_the_disk_without_a_second_read |
| E2 | the hash a reinstall records, the source changed | the same second read | the new disk hash (not the first one); no `copy_hash` call | tests/test_mw051_copy_hash_once.py::test_a_reinstall_records_the_hash_of_the_disk_without_a_second_read |
| E3 | a copy with CRLF files | the same second read | the CRLF bytes are written as they are and the recorded hash equals the disk hash | tests/test_mw051_copy_hash_once.py::test_a_copy_with_crlf_files_records_the_hash_of_the_disk |
| E4 | `mkway check` | reads the copy | still reads the copy and reports a file changed after install | tests/test_mw051_copy_hash_once.py::test_check_still_reads_the_copy_and_sees_a_changed_file |
| E5 | register, changelog | no row | a register row, a line under the top changelog section, VERSION unchanged | tests/test_mw051_copy_hash_once.py::test_register_changelog_and_card_name_the_card |

## 8. Log

| Date | Step | Commit | Result |
|---|---|---|---|
| 2026-11-12 | red: rows E1 to E5 | 1bd2353 | E1, E2, E3, E5 failed for the right reason (install called `copy_hash`; no register row); E4 passed, it guards `check`. Install time before, `install()` on a synthetic root from this repository, 5 runs: 2.76 2.06 1.78 2.07 2.70 s, median 2.07 s |
| 2026-11-12 | green: `files_hash` from the written bytes, one shared hash routine with `copy_hash`, register, changelog | the commit that carries this line | rows E1 to E5 green. Install time after, same run, 5 runs: 0.63 0.60 0.66 0.69 0.68 s, median 0.66 s (the first before-run may carry a cold disk cache; same machine and session). whole suite, `python -m pytest`, term scan included, no exception added: 1053 passed in 666 s |
