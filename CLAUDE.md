# Process engine: rails for every session in this repository

This repository is the process engine: a portable set of hooks, a card register and a profile schema that a branch
installs and tunes through its own branch profile. It is English only and holds no task data.

## Where you may write
- Write only inside this repository. Never write, by any means, outside it.
- Other repositories (a source task repository, an operator folder) and the user's home folder (`~/.claude` included)
  are read-only for you.
- **Deny rules do not stop a shell write.** A permission rule such as `Edit(...)` stops the file tools only. A Python
  `open(..., 'w')`, a shell redirect (`>`), a copy command, or a `git` command sent to another repository is NOT
  stopped by a deny rule. The rule above is yours to keep, whatever the tools allow.
- The machine paths of the fence (other repositories, user homes) live in the launch settings of the session, never
  in a tracked file here: a path with a task name in a reusable repository is a task trace.

## Git
- Commit in this repository only. Never add a remote. Never run `git push`, `git remote`, `git config --global`,
  `git worktree`, `git submodule` or `git stash`.
- To read code of another repository, use only a read form at a pinned commit (`git --no-optional-locks ... show
  <sha>:<path>`). Never import, exec or run a file of another repository, and never copy a file or a block of its
  code here. Copying a single JSON value is allowed; copying a whole config file is not.
- Install nothing (`pip` is denied). Standard library and the installed pytest only.

## No task data (NDA)
- No customer, colleague, product, database or host names; no addresses; no ids of another task's process (card ids,
  decision ids, work-item numbers, case ids); no real data; no natural-language word lists; no Cyrillic.
- Fixtures are synthetic only (`fixtures/synthetic/`).
- The term scan (`tools/term_scan.py`) reads its term list from the file named by env `ENGINE_TERMS_FILE`, or by
  `tools/term_scan.json`. The engine ships with an EMPTY default list. Never open a term file with any viewer; only
  the scan reads it. The scan prints a hit as `path:line group <G> #<n>`, never the term or the matched text.
- A line that must keep a pattern hit (a sha, a number) carries the marker `term-scan: allow <reason>`; list each
  such exception in the card Log.

## Process
- Work is carried by cards: `cards/REGISTER.md` (id, title, status, folder) and one `cards/<ID>-<slug>/CARD.md` per
  card, in the form of `cards/_TEMPLATE/CARD.md`, the one-page card form (Goal, Acceptance examples, Log); its header
  rows, sections and table columns are fixed (test E11). Card MW-001 keeps the long form it was written in (C8). The card prefix is `MW-`.
- Red tests first: each Test cases row of a card names one test node; the test is committed red before the code that
  makes it green, and the card Log names both commits.
- Never weaken a test to make it pass. If a Test cases row is wrong, change the row with a Log line saying why, then
  the test.
- Before every commit run the whole suite, the term scan included: `python -m pytest`. This is the engine's CI; there
  is no CI server and no remote. Write the result in the card Log. A commit message names the Test cases rows it
  covers.
- A value that is unclear is marked «not established». Never guess a value.
