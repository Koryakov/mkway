"""The commit gate (cards MW-006, MW-052): a session's `git commit` holds only files inside the open card's Paths, no junk
and no data files, and its message names the open card.

One manifest entry, `commit_files` (shell group; one profile switch, `gates.commit_files`). Since MW-052 the decision is
the pure `core.decide_commit(facts)`; this module is the thin shell around it: `read_facts` builds the `Facts` record (the
git staged list, the modified-tracked list, the card row, the cards the session ordered and who holds them, the profile,
file sizes and ignore answers, as data), `write_records` appends the rows of the verdict, and `to_gate` maps the verdict
to the dispatcher's own kinds.

The commit is judged by the files git will put in it (MW-043: `-- <paths>` the named paths alone, `-i -- <paths>` the
staged list plus the named, a plain commit the staged list, `-a` the staged list plus every modified tracked file).
`taken` is the ONE reader of that list: `commit_files` reads it here and `commit_tests` calls it (card MW-060); the
table that combines git's two lists, `combine`, and the form that takes no file, `message_only_amend` (MW-058), are the
core's pure functions. MW-053: a session that ORDERED a card (its id in the register's `Ordered by`) may commit the card's
folder and the register without holding the card; a file the holder's Paths cover is the holder's. MW-034: there is no
record of who wrote a file; a ride-in is stopped by the card's Paths and by one builder per task root
(`take-root-busy`, the lock gate). MW-102 (R254): the verdict file `tests/verdicts/<card>.md` is committed by the orderer of its
card alone (the shell passes each ordered card's verdict path as a fact), and a commit that takes it runs the close's row proof
on the content the commit takes (refusal `verdict-unproven`); as at close, no checker or `cards.verdicts: off` skips the proof.

The junk patterns, the data patterns and the size limit are profile keys with defaults (`settings`); no task name and no
natural-language word is in this file. The owner's terminal runs no hook, so it is not gated.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import cardtool
import core
import gate
import helpers
import leads
import logs
import owners
import profiles
import register
import rules
import runner
import verdicts

CLI = core.CLI
SHOWN = core.SHOWN
READ_ONLY_GIT = core.READ_ONLY_GIT
SHELL_TOOLS = core.SHELL_TOOLS
JUNK = list(core.JUNK)
DATA = list(core.DATA)
MAX_FILE_KB = core.MAX_FILE_KB
ORDERER_RULE = core.ORDERER_RULE
ORDERER_OWN = core.ORDERER_OWN
combine = core.combine  # MW-060: the pure table is the core's; both gates read it through `taken`
message_only_amend = core.message_only_amend  # MW-058


def _patterns(value):
    """The list when it is non-empty and every item is a non-empty string, else None (the default then applies)."""
    if not isinstance(value, list) or not value:
        return None
    if any(not isinstance(item, str) or not item for item in value):
        return None
    return list(value)


def _limit(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
        return None
    return value


def settings(profile) -> dict:
    """The gate's settings: `junk`, `data_patterns`, `max_file_kb`. A missing or unusable value takes its default, so
    a gate never fails on a bad key."""
    raw = profile.get("commit") if isinstance(profile, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {"junk": _patterns(raw.get("junk")) or list(JUNK),
            "data_patterns": _patterns(raw.get("data_patterns")) or list(DATA),
            "max_file_kb": _limit(raw.get("max_file_kb")) or MAX_FILE_KB}


# ---- the gate: read the facts, decide in the core, write the verdict -------------------------------------------------------

def check(event, ctx):
    """The commit gate (entry `commit_files`). A read that raises is a refusal `commit-unreadable`, as a git read that
    does not answer: the gate fails closed."""
    try:
        facts = read_facts(event, ctx)
    except runner.TimeoutExpired as exc:
        return gate.refuse("commit-unreadable", _timeout_text(exc))
    except (OSError, ValueError, runner.Refused) as exc:
        return gate.refuse("commit-unreadable", _failed_text(exc))
    verdict = core.decide_commit(facts)
    write_records(ctx, verdict.records)
    if verdict.kind != core.REFUSE:
        _record_commit(ctx, facts)
    return to_gate(verdict)


def _record_commit(ctx, facts) -> None:
    """MW-068 (R173 item 1): at the PreToolUse of an allowed commit, append one row to `commit_records.jsonl`: the hook's
    session id, the git tree id the gate builds for the commit (MW-060, `gate_commit_tests.tree_id`) and the paths it takes
    (`core.commit_record`). The close-time verdict check matches a test file's commits to these rows by tree sha. It never
    blocks a commit: a record that cannot be made is left out (the verdict check then judges the file by the holder alone)."""
    try:
        commits = facts.commits
        if isinstance(commits, core.Unread) or len(commits) != 1:
            return
        parsed = ctx.commit_cmd(facts.command)
        if len(parsed) != 1:
            return
        import gate_commit_tests  # late: it imports this module
        found = core.commit_record(ctx.session_id, gate_commit_tests.tree_id(ctx, parsed[0]), commits[0].taken)
        if found:
            name, row = found
            write_records(ctx, [(name, {**row, "time": logs.now().isoformat(timespec="milliseconds")})])
    except Exception:  # a record is never a reason to stop a commit
        return


def to_gate(verdict):
    """The dispatcher's verdict of a core verdict: allow, refuse, and allow-with-line as a `log` row."""
    if verdict.kind == core.REFUSE:
        return gate.refuse(verdict.reason, verdict.text)
    if verdict.kind == core.ALLOW_LINE:
        return gate.log(verdict.reason, verdict.text)
    return gate.allow()


def write_records(ctx, records):
    """Append each (file name in the state folder, row) of a verdict."""
    state = profiles.state_dir(ctx.root, ctx.profile if isinstance(ctx.profile, dict) else {})
    for name, row in records:
        logs.append_jsonl(state / name, row)


def _timeout_text(exc) -> str:
    return (f"a git read did not answer within {exc.timeout:g} s, so the commit could not be checked; run it again")


def _failed_text(exc) -> str:
    return (f"git could not be read ({exc.__class__.__name__}), so the commit could not be checked; run it again from "
            f"the repository")


def _unread(exc) -> core.Unread:
    return core.Unread(_timeout_text(exc) if isinstance(exc, runner.TimeoutExpired) else _failed_text(exc))


_READ_ERRORS = (runner.TimeoutExpired, OSError, ValueError, runner.Refused)


def facts_of_event(tool_name, tool_input, profile) -> core.Facts:
    """The facts the event and the profile give, with no commit read: the tool, the command text, the shell kind, the
    git built-in lists, the settings and the switches of the profile."""
    profile = profile if isinstance(profile, dict) else {}
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    command = tool_input.get("command")
    cfg = settings(profile)
    try:
        id_pattern = cardtool.id_pattern(profile).pattern
    except cardtool.CardError:  # no `ids.card_prefix`: only the open card's own id is a whole id
        id_pattern = None
    return core.Facts(
        tool_name=tool_name, vcs=profiles.vcs(profile) or "",
        command=command if isinstance(command, str) else "", shell="powershell" if tool_name == "PowerShell" else "bash",
        git_builtins=frozenset(helpers.git_builtins()), git_builtins_extra=frozenset(profiles.git_builtins_extra(profile)),
        junk=tuple(cfg["junk"]), data_patterns=tuple(cfg["data_patterns"]), max_file_kb=cfg["max_file_kb"],
        message_card_on=profiles.gate_on(profile, "commit_files.message_card", True), card_id_pattern=id_pattern,
        verdict_dir=verdicts.VERDICT_DIR, cli=CLI)


def read_facts(event, ctx) -> core.Facts:
    """The `Facts` of this event. Git is read only for a commit the command text alone does not decide (`core.precheck`),
    and for each commit only what the decision can need; a read that fails is an `Unread` fact, not an exception."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    facts = facts_of_event(ctx.tool_name, tool_input, profile)
    if ctx.tool_name not in SHELL_TOOLS or facts.vcs != "git":
        return facts
    parsed = ctx.commit_cmd(facts.command)
    commits = tuple(core.CommitFacts(message=c.message, paths=tuple(c.paths), all=c.all, include=c.include,
                                     amend=c.amend, only=c.only, folder_unreadable=c.folder_unreadable, taken=())
                    for c in parsed)
    facts = dataclasses.replace(facts, commits=commits)
    if core.precheck(facts) is not None:
        return facts
    card = {**_card(ctx, profile), **_orderer(ctx, profile)}
    read = [_commit_facts(ctx, profile, cf, c, card.get("ordered", ())) for cf, c in zip(commits, parsed)]
    return dataclasses.replace(facts, commits=tuple(read), **card)


def free_entries(profile, register_rel) -> tuple:
    """The files no rule of the card's Paths applies to, read from the owner table (MW-107): the register, the ledger rows
    and the quote files of the ledger folder, and the profile's `paths.exempt`."""
    entries = [register_rel, *owners.patterns_of("ledger", profile), *owners.patterns_of("quote-file", profile),
               *owners.patterns_of("exempt", profile)]
    return tuple(e for e in entries if e)


def _card(ctx, profile) -> dict:
    """The facts of the card this session holds, of the register's seal and of the files no card rule applies to."""
    card_id = ctx.records.card()
    out = {"card_id": card_id or None, "exempt": free_entries(profile, ctx.norm(str(register.path(ctx.root, profile)))),
           "owner_fix": register.OWNER_FIX}
    if not card_id:
        return out
    try:
        problem = register.seal_problem(ctx.root, profile)
        row = None if problem else register.find(register.read(ctx.root, profile), card_id)
    except (*_READ_ERRORS, register.RegisterError) as exc:
        out["register_problem"] = _unread(exc)
        return out
    out["register_problem"] = problem
    if row:
        folder = (row.get("folder") or "").strip().strip("`")
        out.update(card_found=True, card_status=row.get("status"), card_folder=folder or None,
                   card_paths=cardtool.paths_set(row.get("paths", "")))
    return out


def _orderer(ctx, profile) -> dict:
    """MW-053: the cards this session ORDERED (the register's `Ordered by` cell is its session id) and who holds them.
    Nothing for a session with no id or the owner's, or when the register cannot be read (the commit is then judged as
    before); the holders are an `Unread` when the session records do not answer."""
    session = ctx.session_id
    if not isinstance(session, str) or not session.strip() or session == register.OWNER:
        return {}
    try:
        mine = [r for r in register.read(ctx.root, profile) if r.get(register.ORDERED) == session and r.get("folder")]
    except (OSError, ValueError, register.RegisterError):
        return {}
    if not mine:
        return {}
    ordered = tuple(core.Ordered(r["id"], r["folder"].strip().strip("`").rstrip("/"),
                                 cardtool.paths_set(r.get("paths", "")), verdicts.verdict_file(r["id"])) for r in mine)
    try:
        holders = dict(ctx.records.holders())
    except _READ_ERRORS as exc:
        holders = _unread(exc)
    return {"ordered": ordered, "holders": holders}


def _commit_facts(ctx, profile, facts: core.CommitFacts, commit, ordered=()) -> core.CommitFacts:
    """What git says of one commit: the files it takes, git's ignore answer for the added ones, the sizes, and the rule
    cards among the files with the test each needs. A commit in an unreadable folder reads nothing; a message-only amend
    takes no file, so nothing is read for it (MW-058)."""
    if commit.folder_unreadable or core.message_only_amend(commit):
        return facts
    cwd = commit.cwd
    if cwd:
        rel = ctx.norm(cwd)
        if rel is not None:
            cwd = None if rel == "." else rel
    folder = (ctx.root / cwd) if cwd else ctx.root
    try:
        taken = _taken(ctx, folder, commit)
    except _READ_ERRORS as exc:
        return dataclasses.replace(facts, taken=_unread(exc))
    if taken is None:
        return dataclasses.replace(facts, taken=core.Unread())
    taken = tuple(taken)
    try:
        unproven = _unproven(ctx, profile, ordered, taken)
    except (*_READ_ERRORS, cardtool.CardError) as exc:  # a verdict file that cannot be read is no file to let through
        return dataclasses.replace(facts, taken=_unread(exc))
    live = [(status, rel, source) for status, rel, source in taken if status != "D"]
    added = [rel for status, rel, _source in live if status == "A"]
    try:
        ignored = _ignored(ctx, added)
        ignored = core.Unread() if ignored is None else frozenset(ignored)
    except _READ_ERRORS as exc:
        ignored = _unread(exc)
    try:
        sizes = _sizes(ctx, [(rel, source) for _status, rel, source in live])
        sizes = core.Unread() if sizes is None else sizes
    except _READ_ERRORS as exc:
        sizes = _unread(exc)
    rule_cards, on_disk = {}, set()
    if rules.active(profile):
        for _status, rel, _source in live:
            ident = rules.is_card(profile, rel)
            if ident:
                rule_cards[rel] = rules.test_path(profile, ident)
        on_disk = {test for test in rule_cards.values() if (ctx.root / test).is_file()}
    rels = [rel for _status, rel, _source in taken]
    return dataclasses.replace(facts, taken=taken, ignored=ignored, sizes=sizes, rule_cards=rule_cards,
                               tests_on_disk=frozenset(on_disk), unproven=unproven,
                               roles={rel: owners.owner_of(rel, profile, root=ctx.root) for rel in rels if owners.owner_of(rel, profile, root=ctx.root)},
                               own=_own(ctx, profile, rels, ordered),
                               notes={rel: owners.describe(rel, profile, root=str(ctx.root)) for rel in rels})


def _own(ctx, profile, rels, ordered) -> frozenset:
    """MW-107: the taken paths this session's own writable set holds, the same rows `leads.writable` reads for the lead gate:
    for a registered lead, everything it may write (its order files, the asks, the quote files); for a session that ordered a
    card but is no lead, the asks and the quote files (the orderer's folders are the card rules'). The orderer's commit scope
    is its writable set."""
    session = ctx.session_id
    if not isinstance(session, str) or not session.strip() or session == register.OWNER:
        return frozenset()
    if leads.is_lead(profiles.shared_state_dir(ctx.root, profile), session):
        return frozenset(rel for rel in rels if leads.writable(ctx.root, profile, session, rel))
    if not ordered:
        return frozenset()
    return frozenset(rel for rel in rels if (kind := owners.kind_of(rel, profile)) is not None
                     and kind.role == owners.ORDERER and kind.edit and kind.name in ("asks", "quote-file"))


def _unproven(ctx, profile, ordered, taken) -> dict:
    """MW-102 (R254): for each verdict file of a card the session ordered that the commit takes, the rows the close's row
    proof refuses, as ((node, why), ...), read from the content the commit takes: the staged blob for source `index`, the
    working file for `work`. As at close (R179), with no `outbox.checkers` or `cards.verdicts: off` nothing is judged; only
    the rows whose node an Acceptance row of the card names are judged. A deletion is judged by nothing."""
    mine = {row.verdict: row for row in ordered if row.verdict}
    out = {}
    for status, rel, source in taken:
        row = mine.get(rel)
        if row is None or status == "D":
            continue
        checkers = profiles.outbox_settings(profile)["checkers"]
        if not checkers or not cardtool.verdicts_required(profile):
            continue
        text = _verdict_text(ctx, rel, source)
        card_text = (ctx.root / row.folder / "CARD.md").read_text(encoding="utf-8")
        nodes = cardtool.test_nodes(card_text)
        rows = [r for r in verdicts.parse_rows(text) if r.node in nodes]
        state = profiles.state_dir(ctx.root, profile)
        out[rel] = tuple(verdicts.proof_problems(ctx.root, state, checkers, row.id, rows, card_text).items())
    return out


def _verdict_text(ctx, rel: str, source: str) -> str:
    """The text of a verdict file as the commit takes it: the staged blob (`index`) or the working file (`work`)."""
    if source == "work":
        return (ctx.root / rel).read_text(encoding="utf-8")
    proc = runner.git(ctx.root, "show", f":./{rel}", text=False)
    if proc.returncode != 0:
        raise ValueError(f"git cannot show the staged {rel}")
    return proc.stdout.decode("utf-8")


# ---- the reads of git -------------------------------------------------------------------------------------------------------

def _name_status(norm, folder, *args):
    """[(status letter, path)] of a `git diff --name-status -z` read, each path through `norm` (a path it answers None
    for is left out); None when git does not answer 0."""
    proc = runner.git(folder, *args)
    if proc.returncode != 0:
        return None
    parts = proc.stdout.split("\0")
    out = []
    for i in range(0, len(parts) - 1, 2):
        rel = norm(parts[i + 1])
        if rel is not None:
            out.append((parts[i][:1], rel))
    return out


def _has_head(folder) -> bool:
    return runner.git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0


def _tracked_changes(norm, folder, specs=()):
    """The tracked changes against HEAD (with no HEAD yet, the index), limited to `specs` when given. A file git does
    not know (untracked, not staged) is never in the list, as git commits none."""
    tail = ["--", *specs] if specs else []
    if _has_head(folder):
        return _name_status(norm, folder, "diff", "--name-status", "--no-renames", "-z", "HEAD", *tail)
    return _name_status(norm, folder, "diff", "--cached", "--name-status", "--no-renames", "-z", *tail)


def taken(norm, folder, commit):
    """[(status, path, source)] the commit would take (see `core.combine`), paths through `norm`: `commit_files` passes
    its path normaliser (task-root paths), `commit_tests` the identity (repository paths). One reader for both gates (card
    MW-060). None when git cannot tell. A message-only amend (`core.message_only_amend`) takes no files."""
    if core.message_only_amend(commit):
        return []
    if commit.all:  # git refuses `-a` with paths; the wider reading is the safe one
        named = _tracked_changes(norm, folder)
    elif commit.paths:
        named = _tracked_changes(norm, folder, commit.paths)
    else:
        named = []
    if named is None:
        return None
    if commit.paths and not commit.all and not commit.include:
        return core.combine(commit, named, [])
    staged = _name_status(norm, folder, "diff", "--cached", "--name-status", "--no-renames", "-z")
    return None if staged is None else core.combine(commit, named, staged)


def _taken(ctx, folder, commit):
    """`taken` for the file gate: paths relative to the task root."""
    return taken(ctx.norm, folder, commit)


def _ignored(ctx, rels: list):
    """The paths among `rels` that git's ignore rules match, tracked or not (`check-ignore --no-index`); None when git
    does not answer."""
    if not rels:
        return set()
    proc = runner.run(runner.GIT + ["-C", str(ctx.root), "check-ignore", "--no-index", "-z", "--stdin"],
                      input="\0".join(rels) + "\0", capture_output=True, text=True, timeout=runner.GIT_TIMEOUT)
    if proc.returncode not in (0, 1):
        return None
    return {x for x in proc.stdout.split("\0") if x}


def _sizes(ctx, rows: list):
    """{repo path: bytes} for (path, source) rows: the staged blob for `index`, the working file for `work`; None when
    git does not answer. A file that is not there has no size."""
    sizes = {}
    index = [rel for rel, source in rows if source == "index"]
    if index:
        proc = runner.run(runner.GIT + ["-C", str(ctx.root), "cat-file", "--batch-check"],
                          input="".join(f":./{rel}\n" for rel in index), capture_output=True, text=True,
                          timeout=runner.GIT_TIMEOUT)
        if proc.returncode != 0:
            return None
        for rel, line in zip(index, proc.stdout.splitlines()):
            parts = line.split()
            if len(parts) == 3 and parts[1] == "blob" and parts[2].isdigit():
                sizes[rel] = int(parts[2])
    for rel, source in rows:
        if source == "work":
            try:
                sizes[rel] = (ctx.root / rel).stat().st_size
            except OSError:
                pass
    return sizes


# ---- the start block and `mkway check` ----------------------------------------------------------------------------------------

def _exempt(norm, root, profile, row, rel) -> bool:
    entries = list(free_entries(profile, norm(str(register.path(root, profile)))))
    if row and row.get("folder"):
        entries.append(row["folder"].strip().strip("`"))
    return any(helpers.matches(rel, e) for e in entries if e)


def staged_outside(root, profile, row=None):
    """MW-043: the repo paths staged in the root's index that lie outside a card's Paths, for the start block and
    `mkway check`; a line there, never a refusal. `row` is a register row: the files outside that card's Paths (a
    card that is not open leaves every file outside). With no row: the files outside the Paths of every open card
    (no open card leaves every file outside; open cards with no Paths restrict nothing). The files no card rule
    applies to are not counted. None when git or the register cannot be read."""
    root = Path(root)
    prefix = helpers.top_prefix(root)

    def norm(path):
        return helpers.norm(path, root, top_prefix=prefix)

    try:
        proc = runner.git(root, "diff", "--cached", "--name-status", "--no-renames", "-z")
        if proc.returncode != 0:
            return None
        parts = proc.stdout.split("\0")
        staged = [rel for rel in (norm(parts[i + 1]) for i in range(0, len(parts) - 1, 2)) if rel is not None]
        rows = [r for r in register.read(root, profile)] if row is None else [row]
    except (OSError, ValueError, register.RegisterError, runner.Refused, runner.SubprocessError):
        return None
    cards = [r for r in rows if r.get("status") == "open"]
    recorded = frozenset().union(*(cardtool.paths_set(r.get("paths", "")) for r in cards)) if cards else frozenset()
    out = []
    for rel in dict.fromkeys(staged):
        if any(_exempt(norm, root, profile, r, rel) for r in (cards or [row])):
            continue
        if cards and not recorded:
            continue
        if not any(helpers.matches(rel, e) for e in recorded):
            out.append(rel)
    return out
