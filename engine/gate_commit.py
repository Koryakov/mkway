"""The commit gate (card MW-006): a session's `git commit` holds only files inside the open card's Paths, no junk and no
data files, and its message names the open card.

One manifest entry, `commit_files` (shell group; one profile switch, `gates.commit_files`): it reads each `git commit`
of a shell command, judges the files the commit takes (the staged list always, and the files a `--`, `-a` or `-i`
form adds) and refuses it, naming the way out. MW-034: there is no record of who wrote a file; a ride-in is stopped by
the card's Paths and by one builder per task root (`take-root-busy`, the lock gate).

The junk patterns, the data patterns and the size limit are profile keys with defaults (`settings`); no task name and
no natural-language word is in this file. The owner's terminal runs no hook, so it is not gated.
"""
from __future__ import annotations

import re

import cardtool
import gate
import helpers
import profiles
import register
import rules
import runner

CLI = "python mkway/engine/mkway.py"
SHOWN = 8  # files named in one refusal; the rest are counted
READ_ONLY_GIT = {"commit", "status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "cat-file",
                 "check-ignore", "rev-list", "describe", "grep", "shortlog", "blame", "show-ref", "name-rev",
                 "diff-tree", "diff-index", "diff-files", "version", "help"}
SHELL_TOOLS = ("Bash", "PowerShell")
JUNK = ["__pycache__/", "*.pyc", ".pytest_cache/", ".pytest_tmp/", "*.log", "*.tmp", "*.orig", "*.rej", ".DS_Store",
        "Thumbs.db"]
DATA = ["*.csv", "*.tsv", "*.xlsx", "*.xls", "*.parquet", "*.db", "*.sqlite", "*.sqlite3", "*.bak", "*.dump"]
MAX_FILE_KB = 1024


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


# ---- the commit gate ------------------------------------------------------------------------------------------------

def check(event, ctx):
    """The commit gate (entry `commit_files`): refuses a `git commit` of a shell command that holds a file outside
    the open card's Paths (`file-not-in-card`), and fails closed
    (`commit-unreadable`, `register-tampered`) when it cannot read the commit. Everything else is allowed."""
    profile = ctx.profile if isinstance(ctx.profile, dict) else {}
    tool_input = ctx.tool_input if isinstance(ctx.tool_input, dict) else {}
    if ctx.tool_name not in SHELL_TOOLS or profiles.vcs(profile) != "git":
        return gate.allow()
    command = tool_input.get("command")
    shell = "powershell" if ctx.tool_name == "PowerShell" else "bash"
    try:
        return _shell(ctx, profile, command if isinstance(command, str) else "", shell)
    except runner.TimeoutExpired as exc:
        return gate.refuse("commit-unreadable", f"a git read did not answer within {exc.timeout:g} s, so the commit "
                                                f"could not be checked; run it again")
    except (OSError, ValueError, runner.Refused) as exc:
        return gate.refuse("commit-unreadable", f"git could not be read ({exc.__class__.__name__}), so the commit "
                                                f"could not be checked; run it again from the repository")


def _unreadable(command: str, shell: str, extra=frozenset()):
    """The text of what makes a commit of this command unreadable, or None (the lock gate's own conditions)."""
    if not helpers.parse_ok(command, shell) and helpers.names_git_commit(command):
        return "this command cannot be parsed and holds a `git ... commit`"
    carrier = helpers.carried_commit(command, shell)
    if carrier:
        return f"this command may run a `git ... commit` the gate cannot read (through {carrier})"
    form = helpers.git_form_problem(command, shell, extra)
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


def _shell(ctx, profile, command: str, shell: str):
    why = _unreadable(command, shell, profiles.git_builtins_extra(profile))
    if why:
        return gate.refuse("commit-unreadable", f"{why}, so its commit cannot be checked; run the commit alone, in a "
                                                f"plain form: `git commit -m \"<message>\" -- <paths>`")
    commits = ctx.commit_cmd(command)
    if not commits:
        return gate.allow()
    other = sorted({sub for sub in _git_words(command, shell) if sub not in READ_ONLY_GIT}, key=str)
    if other:
        return gate.refuse("commit-unreadable", f"this command runs `git {other[0]}` beside the commit; the hook "
                                                f"reads the index before the command runs, so what the commit holds "
                                                f"cannot be checked; run git {other[0]} and git commit as two "
                                                f"separate calls: `git {other[0]}` in a call of its own, then the "
                                                f"commit alone")
    for commit in commits:
        verdict = _commit(ctx, profile, commit)
        if verdict is not None:
            return verdict
    return gate.allow()


def _list(rels: list) -> str:
    rels = list(dict.fromkeys(rels))
    shown = ", ".join(rels[:SHOWN])
    return shown + (f" and {len(rels) - SHOWN} more" if len(rels) > SHOWN else "")


def _name_status(ctx, folder, *args):
    """[(status letter, repo path)] of a `git diff --name-status -z` read; None when git does not answer 0."""
    proc = runner.git(folder, *args)
    if proc.returncode != 0:
        return None
    parts = proc.stdout.split("\0")
    out = []
    for i in range(0, len(parts) - 1, 2):
        rel = ctx.norm(parts[i + 1])
        if rel is not None:
            out.append((parts[i][:1], rel))
    return out


def _has_head(folder) -> bool:
    return runner.git(folder, "rev-parse", "--verify", "-q", "HEAD").returncode == 0


def _tracked_changes(ctx, folder, specs=()):
    """The tracked changes against HEAD (with no HEAD yet, the index), limited to `specs` when given."""
    tail = ["--", *specs] if specs else []
    if _has_head(folder):
        return _name_status(ctx, folder, "diff", "--name-status", "--no-renames", "-z", "HEAD", *tail)
    return _name_status(ctx, folder, "diff", "--cached", "--name-status", "--no-renames", "-z", *tail)


def _taken(ctx, folder, commit):
    """[(status, repo path, source)] the commit would take: git's staged list always (whatever the command names),
    and the files a `--` or `-a` form takes from the working tree. `source` is `index` (the staged blob) or `work`
    (the working-tree file). None when git cannot tell."""
    named = _tracked_changes(ctx, folder, commit.paths) if commit.paths else []
    if commit.all and not commit.paths:
        named = _tracked_changes(ctx, folder)
    staged = _name_status(ctx, folder, "diff", "--cached", "--name-status", "--no-renames", "-z")
    if named is None or staged is None:
        return None
    seen = {rel for _status, rel in named}
    return ([(status, rel, "work") for status, rel in named]
            + [(status, rel, "index") for status, rel in staged if rel not in seen])


def _always(ctx, profile, row, rel) -> bool:
    """The files no rule of the card's Paths or of ownership applies to: the card's own folder, the register, the
    ledger folder, and the profile's `paths.exempt` (the edit gate always allows the last, too)."""
    exempt = profile.get("paths", {}).get("exempt") if isinstance(profile.get("paths"), dict) else None
    entries = [ctx.norm(str(register.path(ctx.root, profile))), f"{profiles.bundle_root(profile)}/ledger"]
    if row and row.get("folder"):
        entries.append(row["folder"].strip().strip("`"))
    entries += [e for e in (exempt if isinstance(exempt, list) else []) if isinstance(e, str) and e]
    return any(helpers.matches(rel, e) for e in entries if e)


def _way_out(commit, rels: list) -> str:
    if commit.paths and not commit.include:
        return "leave them out of the paths after `--`"
    if commit.all and not commit.paths:
        return "commit without `-a` and name your own files after `--`"
    return f"unstage them with `git restore --staged {' '.join(dict.fromkeys(rels))}`"


def _commit(ctx, profile, commit):
    if commit.folder_unreadable:
        return gate.refuse("commit-unreadable", "this commit runs in a folder the gate cannot read (a `cd` or `-C` to "
                                                "a variable or an unreadable target), so its files cannot be "
                                                "checked; `cd` to a literal folder, or commit from the root")
    cwd = commit.cwd
    if cwd:
        rel = ctx.norm(cwd)
        if rel is not None:
            cwd = None if rel == "." else rel
    folder = (ctx.root / cwd) if cwd else ctx.root
    taken = _taken(ctx, folder, commit)
    if taken is None:
        return gate.refuse("commit-unreadable", "the files this commit takes could not be read from git, so it could "
                                                "not be checked; run it again from the repository")
    card_id = ctx.records.card()
    row = None
    if card_id:
        problem = register.seal_problem(ctx.root, profile)
        if problem:
            return gate.refuse("register-tampered", f"{problem}; no commit is checked until the owner checks it: "
                                                    f"{register.OWNER_FIX}")
        row = register.find(register.read(ctx.root, profile), card_id)
    status = row.get("status") if row else None
    is_open = status == "open"
    recorded = cardtool.paths_set(row.get("paths", "")) if is_open else frozenset()
    files = [rel for _status, rel, _source in taken if not _always(ctx, profile, row, rel)]
    outside = [rel for rel in files if not is_open or (recorded and not any(helpers.matches(rel, e) for e in recorded))]
    sources = {rel: source for _status, rel, source in taken}
    named_out = [rel for rel in outside if sources.get(rel) == "work"]
    staged_out = [rel for rel in outside if sources.get(rel) == "index"]
    way = "; and ".join(w for w in (_way_out(commit, named_out) if named_out else "",
                                    f"unstage {_list(staged_out)} with `git restore --staged "
                                    f"{' '.join(dict.fromkeys(staged_out))}`" if staged_out else "") if w)
    if outside:
        if not is_open:
            held = f"{card_id} is {status}" if row else "no card is taken"
            return gate.refuse("file-not-in-card", f"{_list(outside)} cannot be committed: this session holds no open "
                                                   f"card ({held}); commit only the card's own files, or take a card "
                                                   f"the owner has opened (`{CLI} card take <id>`)")
        shown = "; ".join(sorted(recorded))
        return gate.refuse("file-not-in-card", f"{_list(outside)} {'is' if len(set(outside)) == 1 else 'are'} not in "
                                               f"the Paths of {card_id} ({shown}); {way}, or "
                                               f"add them to the card and ask the owner to `card open {card_id}` "
                                               f"again, or write a new card")
    verdict = _content(ctx, profile, commit, taken)
    if verdict is not None:
        return verdict
    verdict = _rules(ctx, profile, commit, taken)
    if verdict is not None:
        return verdict
    return _message(profile, commit, card_id if is_open else None)


def _rules(ctx, profile, commit, taken):
    """Rule 6 (MW-021, `rule-without-test`): a commit that adds or changes a rule card (`rules.cards`, the id read by
    `ids.rule_card`) must take its test file (`rules.test_for`) too, new or changed. A test changed without its card,
    a deleted card and a file with no id in its name are not refused. Off until both `rules` keys are set."""
    if not rules.active(profile):
        return None
    taking = {rel for status, rel, _source in taken if status != "D"}
    lacking = []
    for rel in sorted(taking):
        ident = rules.is_card(profile, rel)
        if ident and rules.test_path(profile, ident) not in taking:
            lacking.append((rel, rules.test_path(profile, ident)))
    if not lacking:
        return None
    detail = "; ".join(f"{card} needs {test} ({'it is not staged' if (ctx.root / test).is_file() else 'it does not exist'})"
                       for card, test in lacking[:SHOWN])
    detail += f"; and {len(lacking) - SHOWN} more" if len(lacking) > SHOWN else ""
    tests = " ".join(dict.fromkeys(test for _card, test in lacking))
    where = " and name it after `--`" if commit.paths and not commit.include else ""
    return gate.refuse("rule-without-test", f"a rule card goes in with its test: {detail}. Write the test (red "
                                            f"first) and stage it with `git add {tests}`{where}, or leave the card out: "
                                            f"{_way_out(commit, [card for card, _test in lacking])}")


def _message(profile, commit, card_id):
    """Rule 5: the commit message names the open card's id (the `ids.card_prefix` form, a whole id). On by default;
    `gates.commit_files.message_card.on: false` turns it off. With no open card there is no id to name. A message the
    gate cannot read fails closed."""
    if not card_id or not profiles.gate_on(profile, "commit_files.message_card", True):
        return None
    if commit.message is None:
        return gate.refuse("commit-unreadable", f"the gate cannot read this commit's message (no `-m`, a message file "
                                                f"that does not exist, a reused message with `-C`, `--amend` without "
                                                f"`-m`), so it cannot check that it names {card_id}; give it with "
                                                f"-m \"{card_id} <what changed>\" (several -m for paragraphs), or "
                                                f"-F - with a here-document, or -F with a message file that exists")
    own = re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(card_id)}(?![0-9A-Za-z_])", commit.message)
    if own:  # MW-033: the open card's own id, literally, whatever `ids.card_prefix` is now
        return None
    try:
        found = cardtool.id_pattern(profile).findall(commit.message)
    except cardtool.CardError:  # no `ids.card_prefix`: only the open card's own id is a whole id
        found = []
    named = ", ".join(dict.fromkeys(found)) or "no card"
    return gate.refuse("commit-message-card", f"the message names {named}, not the open card {card_id}; put the card "
                                              f"id anywhere in the first line, for example -m \"{card_id} <what "
                                              f"changed>\"")


def _name_hit(name: str, pattern: str) -> bool:
    return helpers.glob_re(helpers._fold(pattern)).fullmatch(helpers._fold(name)) is not None


def _first(rel: str, patterns: list):
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


def _content(ctx, profile, commit, taken):
    """Rules 3 and 4: no junk, no force-added ignored file, no data file, nothing over the size limit. A deletion is
    never refused: removing the mess is the way out."""
    cfg = settings(profile)
    live = [(status, rel, source) for status, rel, source in taken if status != "D"]
    rels = [rel for _status, rel, _source in live]
    junk = {rel: p for rel in rels if (p := _first(rel, cfg["junk"]))}
    if junk:
        which = ", ".join(sorted(set(junk.values())))
        return gate.refuse("junk-file-staged", f"{_list(list(junk))} {'is' if len(junk) == 1 else 'are'} junk "
                                               f"(`commit.junk`: {which}); {_way_out(commit, list(junk))}; a file "
                                               f"that keeps appearing belongs in the ignore file")
    added = [rel for status, rel, _source in live if status == "A"]
    ignored = _ignored(ctx, added)
    if ignored is None:
        return gate.refuse("commit-unreadable", "git's ignore rules could not be read, so the commit could not be "
                                                "checked; run it again from the repository")
    found = [rel for rel in added if rel in ignored]
    if found:
        return gate.refuse("ignored-file-staged", f"{_list(found)} {'is' if len(found) == 1 else 'are'} ignored by "
                                                  f"git and was added with `git add -f`: the ignore file is never "
                                                  f"overridden by a commit; {_way_out(commit, found)}, or ask the "
                                                  f"owner to change the ignore file")
    data = {rel: p for rel in rels if (p := _first(rel, cfg["data_patterns"]))}
    if data:
        which = ", ".join(sorted(set(data.values())))
        return gate.refuse("data-file-staged", f"{_list(list(data))} {'is a data file' if len(data) == 1 else 'are data files'} "
                                               f"(`commit.data_patterns`: {which}); data never goes into the "
                                               f"repository: {_way_out(commit, list(data))}, and keep the data "
                                               f"outside the repository (the owner changes `commit.data_patterns` "
                                               f"if a file type is listed wrongly)")
    sizes = _sizes(ctx, [(rel, source) for _status, rel, source in live])
    if sizes is None:
        return gate.refuse("commit-unreadable", "the file sizes could not be read from git, so the commit could not "
                                                "be checked; run it again from the repository")
    limit = cfg["max_file_kb"]
    big = [(rel, size / 1024) for rel, size in sizes.items() if size > limit * 1024]
    if big:
        shown = "; ".join(f"{rel} is {kb:.0f} KB" for rel, kb in big[:SHOWN]) + (
            f"; and {len(big) - SHOWN} more" if len(big) > SHOWN else "")
        return gate.refuse("file-too-large", f"{shown}, over `commit.max_file_kb` ({limit:g} KB); "
                                             f"{_way_out(commit, [rel for rel, _kb in big])} (the owner changes "
                                             f"`commit.max_file_kb` if the file belongs in the repository)")
    return None
