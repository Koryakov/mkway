"""The pure core of the commit gate (card MW-052): `decide_commit(facts) -> Verdict`.

The test concept (ruling of 2026-11-12): a decision is a pure function of a `Facts` record the shell built; the shell
reads git, the register, the profile and the disk, and writes what the verdict says. This module reads nothing: no file,
no process, no environment, no clock. A test fails if it imports an I/O module (`tests/core/test_core_is_pure.py`) and
every table test of the core runs under a guard that fails on any disk, process or clock access.

`helpers` is the one engine module the core imports: its reader functions (`parse`, `matches`, `glob_re`,
`git_form_problem`, ...) are pure and work on text; the few reader functions that touch the disk (the message file, the
folder track, `git_builtins()`) are never called from here, the shell calls them and hands the answer over as a fact.

A fact the shell could not read is an `Unread` (its text, when the read raised, else empty: git answered non-zero).
The verdict is data: allow, refuse(reason, text) or allow-with-line, and `records`, the rows the shell appends. No task
name and no natural-language word is in this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Optional, Union

import helpers

CLI = "python mkway/engine/mkway.py"
SHOWN = 8  # files named in one refusal; the rest are counted
READ_ONLY_GIT = {"commit", "status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "cat-file",
                 "check-ignore", "rev-list", "describe", "grep", "shortlog", "blame", "show-ref", "name-rev",
                 "diff-tree", "diff-index", "diff-files", "version", "help"}
SHELL_TOOLS = ("Bash", "PowerShell")
JUNK = ("__pycache__/", "*.pyc", ".pytest_cache/", ".pytest_tmp/", "*.log", "*.tmp", "*.orig", "*.rej", ".DS_Store",
        "Thumbs.db")
DATA = ("*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.db", "*.sqlite", "*.sqlite3", "*.bak", "*.dump")
MAX_FILE_KB = 1024
ORDERER_RULE = ("an orderer may commit only the folders of cards it ordered plus REGISTER.md and the verdict file of each "
                "card it ordered")  # MW-053, MW-102
ORDERER_OWN = ("card.md", "order.md")  # MW-053: the files of an ordered card's folder that are always the orderer's
ORDERER_ROLE = "orderer"  # MW-107: the role the owner table gives the kinds an orderer writes and commits
OWNER_NOTE = "Owner table:"  # MW-107: the owner table's sentence for a refused file follows this label
REASONS = ("file-not-in-card", "file-outside-root", "junk-file-staged", "ignored-file-staged", "data-file-staged", "file-too-large",
           "commit-message-card", "commit-unreadable", "register-tampered", "rule-without-test", "verdict-unproven",
           "verdict-stale")

ALLOW, REFUSE, ALLOW_LINE = "allow", "refuse", "allow-with-line"
REASON_OUTSIDE = "file-outside-root"  # MW-140

_RERUN = "run it again from the repository"
_TAKEN_TEXT = "the files this commit takes could not be read from git, so it could not be checked; " + _RERUN
_IGNORE_TEXT = "git's ignore rules could not be read, so the commit could not be checked; " + _RERUN
_SIZES_TEXT = "the file sizes could not be read from git, so the commit could not be checked; " + _RERUN
_COMMITS_TEXT = "the commit could not be read, so it could not be checked; " + _RERUN
_REGISTER_TEXT = "the register could not be read, so the commit could not be checked; " + _RERUN
_HOLDERS_TEXT = "the session records could not be read, so the commit could not be checked; " + _RERUN


@dataclass(frozen=True)
class Verdict:
    """allow | refuse(reason, text) | allow-with-line(reason, text), plus the rows the shell appends: `records` is a
    tuple of (file name in the state folder, row dict)."""
    kind: str = ALLOW
    reason: Optional[str] = None
    text: str = ""
    records: tuple = ()

    def __post_init__(self):
        if self.kind not in (ALLOW, REFUSE, ALLOW_LINE):
            raise ValueError(f"unknown verdict kind: {self.kind!r}")
        if self.kind != ALLOW and not (self.reason and self.text):
            raise ValueError("a refuse or an allow-with-line needs a reason and a text")


def allow(records: tuple = ()) -> Verdict:
    return Verdict(ALLOW, records=records)


def refuse(reason: str, text: str, records: tuple = ()) -> Verdict:
    return Verdict(REFUSE, reason, text, records)


def allow_with_line(reason: str, text: str, records: tuple = ()) -> Verdict:
    return Verdict(ALLOW_LINE, reason, text, records)


@dataclass(frozen=True)
class Unread:
    """A fact the shell could not read. `text` is the whole refusal text when the read raised; empty when git answered
    with a non-zero exit (the core then says it in its own words)."""
    text: str = ""


@dataclass(frozen=True)
class CommitFacts:
    """One `git commit` of the command text as the reader parsed it, and what git says it takes.
    `taken`: ((status letter, repo path, source), ...) with source `index` (the staged blob) or `work` (the working
    file), in git's order; `ignored`: the added paths git's ignore rules match; `sizes`: {repo path: bytes} of the
    files taken and not deleted; `rule_cards`: {repo path: its test path} for each taken path that is a rule card (empty
    when the rule check is off); `tests_on_disk`: the test paths among those that exist in the working tree."""
    message: Optional[str] = None
    paths: tuple = ()
    all: bool = False
    include: bool = False
    amend: bool = False
    only: bool = False  # MW-058: `--only` or `-o` given
    folder_unreadable: bool = False
    taken: Union[tuple, Unread] = ()
    ignored: Union[frozenset, Unread] = frozenset()
    sizes: Union[Mapping, Unread] = field(default_factory=dict)
    rule_cards: Mapping = field(default_factory=dict)
    tests_on_disk: frozenset = frozenset()
    roles: Mapping = field(default_factory=dict)  # MW-107: {taken path: its owner role in the owner table}; a path with no row is absent
    own: frozenset = frozenset()  # MW-107: the taken paths this session's own writable set holds (its owner-table rows)
    notes: Mapping = field(default_factory=dict)  # MW-107: {taken path: the owner table's sentence}, shown after a refusal
    unproven: Mapping = field(default_factory=dict)  # MW-102: {verdict file path: ((node, why), ...)}, the rows the proof refuses
    outside: tuple = ()  # MW-140: ((status letter, name as git gives it from the TOP, source), ...) of the files the commit takes that lie outside the task root; `taken` holds the in-root files only


@dataclass(frozen=True)
class Ordered:
    """MW-053: a card the session ORDERED (the register's `Ordered by` cell is its session id): `id`, its `folder` as a
    path from the task root (no backticks, no trailing slash) and its Paths, parsed."""
    id: str
    folder: str
    paths: frozenset = frozenset()
    verdict: str = ""  # MW-102: the path of the card's verdict file (the shell builds it); empty when it is not known


@dataclass(frozen=True)
class Facts:
    """Everything `decide_commit` reads. `commits` is what `helpers.commit_cmd` read from `command`, one record each."""
    tool_name: Optional[str] = "Bash"
    vcs: str = "git"
    command: str = ""
    shell: str = "bash"
    git_builtins: frozenset = frozenset()  # the engine's list of git's built-in commands
    git_builtins_extra: frozenset = frozenset()  # the profile's additions
    commits: Union[tuple, Unread] = ()
    card_id: Optional[str] = None  # the card this session holds
    register_problem: Union[None, str, Unread] = None  # why the sealed register cannot be trusted; None when sound
    owner_fix: str = ""  # the owner's way out of a tampered register
    card_found: bool = False  # the register has a row for `card_id`
    card_status: Optional[str] = None
    card_paths: frozenset = frozenset()  # the Paths of the row, parsed
    card_folder: Optional[str] = None
    verdict_dir: str = ""  # MW-102: the folder of the verdict files (`<dir>/<card id>.md`); empty: no path is a verdict file
    ordered: tuple = ()  # MW-053: the `Ordered` cards of this session; empty when it orders none (or is the owner, or has no id)
    holders: Union[Mapping, Unread] = field(default_factory=dict)  # MW-053: card id -> the session that holds it
    exempt: tuple = ()  # entries no card rule applies to: the register, the ledger folder, the profile's `paths.exempt`
    junk: tuple = JUNK
    data_patterns: tuple = DATA
    max_file_kb: float = MAX_FILE_KB
    message_card_on: bool = True
    card_id_pattern: Optional[str] = None  # the regex source of a whole card id by `ids.card_prefix`; None when unset
    cli: str = CLI


# ---- what a commit takes (pure: the shell's reader hands it the two lists git gave) -----------------------------------------

def combine(commit, named, staged):
    """[(status, path, source)] the commit takes, as git takes it (MW-043), from the two lists git gave: `named` the
    tracked changes for the named paths (for `-a`, for every path), `staged` the staged list. `-- <paths>` (git's
    `--only`, the default when paths are named) the named paths alone, from the working tree; `-i -- <paths>` the staged
    list plus the named paths; a plain commit the staged list; `-a` the staged list plus every modified tracked file.
    `--amend` follows the same rule and adds nothing. A file staged by someone else is no part of a `--` commit.
    `source` is `index` (the staged blob) or `work` (the working-tree file). `commit` is the parser's record or a
    `CommitFacts`. Pure: no git call (card MW-060, the table both gates read)."""
    if commit.paths and not commit.all and not commit.include:  # `--only`: the staged list is not part of this commit
        return [(status, rel, "work") for status, rel in named]
    seen = {rel for _status, rel in named}
    return ([(status, rel, "work") for status, rel in named]
            + [(status, rel, "index") for status, rel in staged if rel not in seen])


def message_only_amend(commit) -> bool:
    """MW-058: `--amend` with `--only` or `-o` and no paths rewrites the message alone and takes nothing from the index:
    the tree does not change, so no file is taken and nothing is tested. (`-a` or `-i` beside it is a form git refuses;
    the wider reading stays.)"""
    return bool(commit.amend and commit.only and not commit.paths and not commit.all and not commit.include)


COMMIT_RECORDS = "commit_records.jsonl"  # MW-068 (R173 item 1): one row per allowed commit, in the state folder
NOT_ESTABLISHED = "not established"


def commit_record(session, tree, taken):
    """MW-068 (R173 item 1): the (file name, row) the shell appends for an allowed commit: the hook's session, the git tree
    id the commit produces and every path it takes. None when the record could never be matched afterwards: no known
    session (blank, or `not established`), no tree, no file taken, or the files could not be read. The shell adds the
    time; the verdict check at card close reads these rows back by the commit's tree sha. Pure."""
    if not isinstance(session, str) or session.strip() in ("", NOT_ESTABLISHED):
        return None
    if not isinstance(tree, str) or not tree.strip():
        return None
    if isinstance(taken, Unread) or not taken:
        return None
    return COMMIT_RECORDS, {"kind": "commit", "session": session.strip(), "tree": tree.strip(),
                            "paths": [rel for _status, rel, _source in taken]}


# ---- the decision -----------------------------------------------------------------------------------------------------

def decide_commit(facts: Facts) -> Verdict:
    """The commit gate (entry `commit_files`): refuses a `git commit` of a shell command that holds a file outside the
    task root (`file-outside-root`, MW-140: before any card rule), a file outside the
    open card's Paths (`file-not-in-card`), junk, an ignored, a data or an oversized file, a message that does not name
    the card, a rule card with no test, and fails closed (`commit-unreadable`, `register-tampered`) when it cannot
    read the commit. Everything else is allowed."""
    early = precheck(facts)
    if early is not None:
        return early
    for commit in facts.commits:
        verdict = _commit(facts, commit)
        if verdict is not None:
            return verdict
    return allow()


def precheck(facts: Facts) -> Optional[Verdict]:
    """The verdict that needs the command text alone, or None when the commits themselves must be judged. The shell asks
    it before it reads git for a commit: a command already decided here costs no git read."""
    if facts.tool_name not in SHELL_TOOLS or facts.vcs != "git":
        return allow()
    command, shell = facts.command, facts.shell
    why = _unreadable(command, shell, facts.git_builtins, facts.git_builtins_extra)
    if why:
        return refuse("commit-unreadable", f"{why}, so its commit cannot be checked; run the commit alone, in a "
                                           f"plain form: `git commit -m \"<message>\" -- <paths>`")
    commits = facts.commits
    if isinstance(commits, Unread):
        return refuse("commit-unreadable", commits.text or _COMMITS_TEXT)
    if not commits:
        return allow()
    other = sorted({sub for sub in _git_words(command, shell) if sub not in READ_ONLY_GIT}, key=str)
    if other:
        return refuse("commit-unreadable", f"this command runs `git {other[0]}` beside the commit; the hook "
                                           f"reads the index before the command runs, so what the commit holds "
                                           f"cannot be checked; run git {other[0]} and git commit as two "
                                           f"separate calls: `git {other[0]}` in a call of its own, then the "
                                           f"commit alone")
    return None


def _unreadable(command: str, shell: str, builtins, extra):
    """The text of what makes a commit of this command unreadable, or None (the lock gate's own conditions)."""
    if not helpers.parse_ok(command, shell) and helpers.names_git_commit(command):
        return "this command cannot be parsed and holds a `git ... commit`"
    carrier = helpers.carried_commit(command, shell)
    if carrier:
        return f"this command may run a `git ... commit` the gate cannot read (through {carrier})"
    form = helpers.git_form_problem(command, shell, extra, base=builtins)
    if form:
        return form[1]
    shape = helpers.unknown_shape(command, shell)
    if shape and helpers.names_git_commit(command):
        return f"this command holds a shape the gate does not follow ({shape}) and names a `git ... commit`"
    return helpers.env_problem(command, shell) or (
        "this command holds `CDPATH` and a `cd`" if helpers.cdpath_cd(command, shell) else None)


def _git_words(command: str, shell: str):
    """The git subcommand of every simple command of the text, substitutions included."""
    for s in helpers.parse(command, shell):
        argv = helpers._argv(s.words)
        if helpers._prog(argv) == "git":
            yield helpers._git_sub(argv)[0]
        for sub in s.subs:
            yield from _git_words(sub, shell)


def _noted(text: str, commit: CommitFacts, rels) -> str:
    """MW-107: the refusal text with the owner note of the first of `rels` that has one."""
    note = next((commit.notes[rel] for rel in rels if rel in commit.notes), None)
    return f"{text} {OWNER_NOTE} {note}" if note else text


def _list(rels: list) -> str:
    rels = list(dict.fromkeys(rels))
    shown = ", ".join(rels[:SHOWN])
    return shown + (f" and {len(rels) - SHOWN} more" if len(rels) > SHOWN else "")


def _way_out(commit: CommitFacts, rels: list) -> str:
    if commit.paths and not commit.include:
        return "leave them out of the paths after `--`"
    if commit.all and not commit.paths:
        return "commit without `-a` and name your own files after `--`"
    return f"unstage them with `git restore --staged {' '.join(dict.fromkeys(rels))}`"


def _top_spec(name: str) -> str:
    """The pathspec of a name git gave from the top, as `git restore` reads it from any folder of the work tree (`:/<name>`),
    quoted when the name holds a character the shell reads."""
    spec = ":/" + name
    if re.fullmatch(r"[\w./:@%+=,~-]+", spec):
        return spec
    return f'"{spec}"' if "'" in spec else f"'{spec}'"


def _outside(commit: CommitFacts) -> Verdict:
    """MW-140: a commit that takes a file outside the task root is refused `file-outside-root`, whatever the card, the exempt
    entries, the owner table or the session's own set say. The text names each file as git names it (from the top of the
    repository), says it lies outside the task root and names the ways out that work: keep the file inside the root, take it
    out of this commit, or the owner commits it in their own terminal."""
    rows = list(dict.fromkeys(commit.outside))
    names = list(dict.fromkeys(name for _status, name, _source in rows))
    named = [name for _status, name, source in rows if source == "work"]
    staged = [name for _status, name, source in rows if source == "index"]
    one = len(names) == 1
    it = "it" if one else "them"
    ways = ["keep the file inside the task root" if one else "keep the files inside the task root"]
    if named:
        ways.append(f"leave {it} out of the paths after `--`" if commit.paths else
                    "commit without `-a` and name your own files after `--`")
    if staged:
        ways.append(f"take {it} out of this commit with `git restore --staged "
                    f"{' '.join(_top_spec(name) for name in dict.fromkeys(staged))}`")
    ways.append("the owner commits " + ("it" if one else "them") + " in their own terminal")
    return refuse(REASON_OUTSIDE, f"{_list(names)} {'lies' if one else 'lie'} outside the task root (git names {it} from the "
                                  f"top of the repository), so this commit cannot take {it}; ways out: {'; or '.join(ways)}")


def _always(facts: Facts, rel: str) -> bool:
    """The files no rule of the card's Paths applies to: the card's own folder, the register, the ledger folder, and
    the profile's `paths.exempt`."""
    entries = [*facts.exempt, facts.card_folder if facts.card_found else None]
    return any(helpers.matches(rel, e) for e in entries if e)


def _orderer(facts: Facts, outside: list, commit: CommitFacts = None):
    """MW-053: how a session that ORDERED cards is read for the files that lie outside the held card's Paths. None when
    there is no file outside or the session orders no card (the commit is then judged as before). An `Unread` when the
    holders could not be read. Else (covered, ids, holders): `covered` the files that lie in the folder of a card it
    ordered, `CARD.md` and `ORDER.md` always, any other file unless the card's Paths cover it; `ids` those cards;
    `holders` [(file, card id, holder)] the files the card's Paths cover, which belong to the holder."""
    if not outside or not facts.ordered:
        return None
    held = facts.holders
    if isinstance(held, Unread):
        return held
    covered, ids, holders = [], [], []
    for rel in outside:
        own = next((row for row in facts.ordered if row.verdict and row.verdict == rel), None)
        if own is not None:  # MW-102: the verdict file of a card it ordered is the orderer's, whatever any Paths say
            covered.append(rel)
            ids.append(own.id)
            continue
        for row in facts.ordered:
            folder = row.folder
            if not helpers.matches(rel, folder):
                continue
            tail = rel[len(folder):].lstrip("/")
            roles = commit.roles if commit is not None else {}
            owned = tail.lower() in ORDERER_OWN or roles.get(rel) == ORDERER_ROLE  # MW-107: the table gives it to the orderer
            if not owned and any(helpers.matches(rel, e) for e in row.paths):
                holders.append((rel, row.id, held.get(row.id)))
            else:
                covered.append(rel)
                ids.append(row.id)
            break
    return covered, list(dict.fromkeys(ids)), holders


def _message_any(facts: Facts, commit: CommitFacts, ids):
    """Rule 5 for several cards: the message names at least one of `ids`; the first refusal otherwise."""
    verdicts = [_message(facts, commit, card_id) for card_id in ids]
    return None if not verdicts or None in verdicts else verdicts[0]


def _commit(facts: Facts, commit: CommitFacts):
    if commit.folder_unreadable:
        return refuse("commit-unreadable", "this commit runs in a folder the gate cannot read (a `cd` or `-C` to "
                                           "a variable or an unreadable target), so its files cannot be "
                                           "checked; `cd` to a literal folder, or commit from the root")
    taken = () if message_only_amend(commit) else commit.taken  # MW-058: a message-only amend takes no file
    if isinstance(taken, Unread):
        return refuse("commit-unreadable", taken.text or _TAKEN_TEXT)
    card_id = facts.card_id
    if card_id:
        problem = facts.register_problem
        if isinstance(problem, Unread):
            return refuse("commit-unreadable", problem.text or _REGISTER_TEXT)
        if problem:
            return refuse("register-tampered", f"{problem}; no commit is checked until the owner checks it: "
                                               f"{facts.owner_fix}")
    if commit.outside:  # MW-140: before any card, exempt, own-set or verdict rule: those judge in-root names only
        return _outside(commit)
    scope = _verdict_scope(facts, taken)
    if scope is not None:
        return scope
    status = facts.card_status if facts.card_found else None
    is_open = status == "open"
    recorded = facts.card_paths if is_open else frozenset()
    files = [rel for _status, rel, _source in taken if not _always(facts, rel)]
    outside = [rel for rel in files if not is_open or (recorded and not any(helpers.matches(rel, e) for e in recorded))]
    outside = [rel for rel in outside if rel not in commit.own]  # MW-107: files of the session's own writable set
    cover = _orderer(facts, outside, commit)  # MW-053: the files of the card folders this session ordered
    if isinstance(cover, Unread):
        return refuse("commit-unreadable", cover.text or _HOLDERS_TEXT)
    rule = f"; {ORDERER_RULE}" if cover is not None else ""
    cover_ids = []
    if cover is not None:
        covered, cover_ids, owned = cover
        if owned:
            card, holder = owned[0][1], owned[0][2]
            who = f"held by session {holder}" if holder else "held by no session now"
            return refuse("file-not-in-card", _noted(f"{_list([rel for rel, _c, _h in owned])} cannot be committed by the "
                                                     f"orderer: the Paths of {card} cover it, so it belongs to the "
                                                     f"holder of {card} ({who}); an orderer commits only `CARD.md` and "
                                                     f"`ORDER.md` of the card folder it ordered and REGISTER.md{rule}",
                                                     commit, [rel for rel, _c, _h in owned]))
        outside = [rel for rel in outside if rel not in covered]
    sources = {rel: source for _status, rel, source in taken}
    named_out = [rel for rel in outside if sources.get(rel) == "work"]
    staged_out = [rel for rel in outside if sources.get(rel) == "index"]
    way = "; and ".join(w for w in (_way_out(commit, named_out) if named_out else "",
                                    f"unstage {_list(staged_out)} with `git restore --staged "
                                    f"{' '.join(dict.fromkeys(staged_out))}` (or commit only your own files with "
                                    f"`-- <paths>` and no `-i` or `-a`, which takes the named paths alone)"
                                    if staged_out else "") if w)
    if outside:
        if not is_open:
            held = f"{card_id} is {status}" if facts.card_found else "no card is taken"
            return refuse("file-not-in-card", _noted(f"{_list(outside)} cannot be committed: this session holds no open "
                                                     f"card ({held}); commit only the card's own files, or take a card "
                                                     f"the owner has opened (`{facts.cli} card take <id>`){rule}",
                                                     commit, outside))
        shown = "; ".join(sorted(recorded))
        return refuse("file-not-in-card", _noted(f"{_list(outside)} {'is' if len(set(outside)) == 1 else 'are'} not in "
                                                 f"the Paths of {card_id} ({shown}); {way}, or "
                                                 f"the lead that ordered the card adds them to its Paths: `{facts.cli} "
                                                 f"card paths {card_id} --add <entry>` (the card file's Paths must "
                                                 f"already name them), or write a new card{rule}", commit, outside))
    verdict = _content(facts, commit, taken)
    if verdict is not None:
        return verdict
    verdict = _rules(commit, taken)
    if verdict is not None:
        return verdict
    verdict = _unproven(facts, commit, taken)
    if verdict is not None:
        return verdict
    return _message_any(facts, commit, list(dict.fromkeys(([card_id] if is_open else []) + cover_ids)))


def _verdict_card(facts: Facts, rel: str) -> Optional[str]:
    """MW-102: the card id of a verdict file `<verdict_dir>/<card id>.md`, or None when the path is none. Pure text."""
    prefix = facts.verdict_dir.strip("/") + "/" if facts.verdict_dir.strip("/") else None
    if not prefix or not rel.startswith(prefix):
        return None
    tail = rel[len(prefix):]
    return tail[:-3] if tail.endswith(".md") and len(tail) > 3 and "/" not in tail else None


def _verdict_scope(facts: Facts, taken):
    """MW-102 (R254): a verdict file is committed only by the orderer of its card: any other session is refused
    `file-not-in-card`, the holder of the card and a holder whose Paths cover the file included. A session that ordered
    and also holds the card is the holder here."""
    mine = {row.verdict for row in facts.ordered if row.verdict and row.id != facts.card_id}
    for _status, rel, _source in taken:
        card = _verdict_card(facts, rel)
        if card is None or rel in mine:
            continue
        who = ("the holder never commits its own card's verdict file; " if card == facts.card_id else "")
        return refuse("file-not-in-card", f"{rel} cannot be committed by this session: {who}only the orderer of {card} "
                                          f"commits {rel}, once its rows are written with `{facts.cli} verdict add`")
    return None


def _unproven(facts: Facts, commit: CommitFacts, taken):
    """MW-102 (R254): a commit that takes a verdict file is refused `verdict-unproven` for each row the shell's proof
    facts name (the close's row proof, run on the rows of the content the commit takes)."""
    found = [(rel, node, why) for _status, rel, _source in taken for node, why in commit.unproven.get(rel, ())]
    if not found:
        return None
    shown = " | ".join(f"{node}: {why}" for _rel, node, why in found[:SHOWN])
    shown += f" | and {len(found) - SHOWN} more" if len(found) > SHOWN else ""
    stale = all(why.startswith("verdict-stale:") for _rel, _n, why in found)  # MW-117: the Acceptance rows changed
    return refuse("verdict-stale" if stale else "verdict-unproven", f"{_list([rel for rel, _n, _w in found])} cannot be committed: {shown}; a reader who "
                                      f"did not write the test writes each row with `{facts.cli} verdict add`, and the "
                                      f"file is committed as the command wrote it")


def _rules(commit: CommitFacts, taken):
    """Rule 6 (MW-021, `rule-without-test`): a commit that adds or changes a rule card must take its test file too, new
    or changed. A test changed without its card, a deleted card and a file with no id in its name are not refused. Off
    (no `rule_cards`) until both `rules` keys are set."""
    if not commit.rule_cards:
        return None
    taking = {rel for status, rel, _source in taken if status != "D"}
    lacking = []
    for rel in sorted(taking):
        test = commit.rule_cards.get(rel)
        if test and test not in taking:
            lacking.append((rel, test))
    if not lacking:
        return None
    detail = "; ".join(f"{card} needs {test} ({'it is not staged' if test in commit.tests_on_disk else 'it does not exist'})"
                       for card, test in lacking[:SHOWN])
    detail += f"; and {len(lacking) - SHOWN} more" if len(lacking) > SHOWN else ""
    tests = " ".join(dict.fromkeys(test for _card, test in lacking))
    where = " and name it after `--`" if commit.paths and not commit.include else ""
    return refuse("rule-without-test", f"a rule card goes in with its test: {detail}. Write the test (red "
                                       f"first) and stage it with `git add {tests}`{where}, or leave the card out: "
                                       f"{_way_out(commit, [card for card, _test in lacking])}")


def _message(facts: Facts, commit: CommitFacts, card_id):
    """Rule 5: the commit message names the open card's id (a whole id). On by default; `message_card_on` false turns
    it off. With no open card there is no id to name. A message the gate cannot read fails closed."""
    if not card_id or not facts.message_card_on:
        return None
    if commit.message is None:
        return refuse("commit-unreadable", f"the gate cannot read this commit's message (no `-m`, a message file "
                                           f"that does not exist, a reused message with `-C`, `--amend` without "
                                           f"`-m`), so it cannot check that it names {card_id}; give it with "
                                           f"-m \"{card_id} <what changed>\" (several -m for paragraphs), or "
                                           f"-F - with a here-document, or -F with a message file that exists")
    own = re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(card_id)}(?![0-9A-Za-z_])", commit.message)
    if own:  # MW-033: the open card's own id, literally, whatever `ids.card_prefix` is now
        return None
    found = re.findall(facts.card_id_pattern, commit.message) if facts.card_id_pattern else []
    named = ", ".join(dict.fromkeys(found)) or "no card"
    return refuse("commit-message-card", f"the message names {named}, not the open card {card_id}; put the card "
                                         f"id anywhere in the first line, for example -m \"{card_id} <what "
                                         f"changed>\"")


def _name_hit(name: str, pattern: str) -> bool:
    return helpers.glob_re(helpers._fold(pattern)).fullmatch(helpers._fold(name)) is not None


def _first(rel: str, patterns):
    """The first junk or data pattern the repo path matches, or None. A name or glob matches any part of the path,
    at any depth; a trailing `/` names folders only; a pattern with a `/` inside is matched against the whole path."""
    for pattern in patterns:
        p = pattern.replace("\\", "/").strip()
        folder = p.endswith("/")
        p = p.strip("/")
        if not p:
            continue
        if "/" in p:
            hit = helpers.matches(rel, p)
        else:
            parts = rel.split("/")
            hit = any(_name_hit(part, p) for part in (parts[:-1] if folder else parts))
        if hit:
            return pattern
    return None


def _content(facts: Facts, commit: CommitFacts, taken):
    """Rules 3 and 4: no junk, no force-added ignored file, no data file, nothing over the size limit. A deletion is
    never refused: removing the mess is the way out."""
    live = [(status, rel, source) for status, rel, source in taken if status != "D"]
    rels = [rel for _status, rel, _source in live]
    junk = {rel: p for rel in rels if (p := _first(rel, facts.junk))}
    if junk:
        which = ", ".join(sorted(set(junk.values())))
        return refuse("junk-file-staged", f"{_list(list(junk))} {'is' if len(junk) == 1 else 'are'} junk "
                                          f"(`commit.junk`: {which}); {_way_out(commit, list(junk))}; a file "
                                          f"that keeps appearing belongs in the ignore file")
    ignored = commit.ignored
    added = [rel for status, rel, _source in live if status == "A"]
    if isinstance(ignored, Unread):  # git is asked only about added paths: with none, there is nothing to fail
        if added:
            return refuse("commit-unreadable", ignored.text or _IGNORE_TEXT)
        ignored = frozenset()
    found = [rel for rel in added if rel in ignored]
    if found:
        return refuse("ignored-file-staged", f"{_list(found)} {'is' if len(found) == 1 else 'are'} ignored by "
                                             f"git and was added with `git add -f`: the ignore file is never "
                                             f"overridden by a commit; {_way_out(commit, found)}, or ask the "
                                             f"owner to change the ignore file")
    data = {rel: p for rel in rels if (p := _first(rel, facts.data_patterns))}
    if data:
        which = ", ".join(sorted(set(data.values())))
        return refuse("data-file-staged", f"{_list(list(data))} {'is a data file' if len(data) == 1 else 'are data files'} "
                                          f"(`commit.data_patterns`: {which}); data never goes into the "
                                          f"repository: {_way_out(commit, list(data))}, and keep the data "
                                          f"outside the repository (the owner changes `commit.data_patterns` "
                                          f"if a file type is listed wrongly)")
    sizes = commit.sizes
    if isinstance(sizes, Unread):  # likewise: no file taken and not deleted, no size to read
        if live:
            return refuse("commit-unreadable", sizes.text or _SIZES_TEXT)
        sizes = {}
    limit = facts.max_file_kb
    big = [(rel, size / 1024) for rel, size in sizes.items() if size > limit * 1024]
    if big:
        shown = "; ".join(f"{rel} is {kb:.0f} KB" for rel, kb in big[:SHOWN]) + (
            f"; and {len(big) - SHOWN} more" if len(big) > SHOWN else "")
        return refuse("file-too-large", f"{shown}, over `commit.max_file_kb` ({limit:g} KB); "
                                        f"{_way_out(commit, [rel for rel, _kb in big])} (the owner changes "
                                        f"`commit.max_file_kb` if the file belongs in the repository)")
    return None
