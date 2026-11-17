"""MW-003 false blocks (group A, ordered 10.11): the lock gate must not block a lawful command that starts with a `cd`
to an absolute folder inside the root, a `cd ..`, or a plain `NAME=value`. Each row is a command form measured in a
real task; the roots here are synthetic temp folders. A deny row is a command refused for a real reason: it stays
refused."""
import pytest

from _engine import gate_call
from test_lock import _git, gtask, shell  # noqa: F401  (gtask is a fixture)

import gate_lock

L = "mkway/locks/engine.json"
PROFILE = "mkway/profile.json"


def _kind(v):
    return v.reason_id if v.kind == "refuse" else v.kind


def _forms(folder):
    """The spellings of one absolute folder that a session's command holds: `C:/…` and `C:\\…` (quoted or not, the
    drive letter in either case) and Git Bash's `/c/…`."""
    posix = folder.as_posix()
    low = posix[0].lower() + posix[1:]
    return {
        "dq-slash": f'"{posix}"', "bare-slash": posix, "dq-back": f'"{folder}"', "sq-slash": f"'{posix}'",
        "lower-drive": f'"{low}"', "gitbash": "/" + posix[0].lower() + posix[2:],
    }


@pytest.fixture
def folders(gtask):
    inner = gtask / "task" / "Loc"
    inner.mkdir(parents=True)
    (inner / "a.py").write_text("x = 1\n", encoding="utf-8")
    return gtask, inner


def _sweep(root, rows):
    """The (label, command, verdict) of every row that is refused; `rows` is (label, command)."""
    out = []
    for label, command in rows:
        verdict = shell(root, command)
        if verdict.kind == "refuse":
            out.append(f"{label}: {verdict.reason_id}: {command[-70:]}")
    return out


def _wrong(root, commands, expected):
    """The commands whose verdict is not one of `expected` (a reason id, `allow`, or a tuple of them): one line each."""
    wanted = (expected,) if isinstance(expected, str) else tuple(expected)
    out = []
    for command in commands:
        got = _kind(shell(root, command))
        if got not in wanted:
            out.append(f"{got} (wanted {'/'.join(wanted)}): {command[-90:]}")
    return out


def _wrong_at(root, folder, commands, expected):
    """As `_wrong`, for a session whose hook `cwd` is `folder` (the verdict of `_from`)."""
    wanted = (expected,) if isinstance(expected, str) else tuple(expected)
    out = []
    for command in commands:
        got = _kind(_from(root, folder, command))
        if got not in wanted:
            out.append(f"{got} (wanted {'/'.join(wanted)}): {command[-90:]}")
    return out


# ---- part 1: a `cd` to an absolute folder inside the root (E96) --------------------------------------------------------

def test_an_engine_call_after_a_cd_inside_the_root_is_plain(folders):
    """Catches: a lawful engine call after a cd inside the root refused, or a cd outside the root let through. E96 (engine-call-not-plain): `cd <abs folder> && python mkway/engine/mkway.py ...` was refused when the folder lay outside the bundle root, and a `;` after the `cd` was not read at all; a `cd` to a literal absolute folder inside the root, in every spelling, joined by `&&` or `;`, is the plain form; a `cd` outside the root, a second segment or a named root stays refused."""
    root, inner = folders
    outside = root.parent
    rows = [(f"{name}/{form}/{sep}", f"cd {word}{sep} python mkway/engine/mkway.py card list")
            for name, where in (("root", root), ("inner", inner)) for form, word in _forms(where).items()
            for sep in (" &&", ";")]
    assert not _sweep(root, rows)
    assert not _wrong(root, [f"cd {word} && python mkway/engine/mkway.py card list"
                             for word in _forms(outside).values()], "engine-call-not-plain")
    assert not _wrong(root, [f"cd {_forms(inner)['dq-slash']} && python mkway/engine/mkway.py card list | cat",
                             f"cd {_forms(inner)['dq-slash']}; python mkway/engine/mkway.py card list; ls",
                             f"cd {_forms(inner)['dq-slash']} && python mkway/engine/mkway.py card list --root x",
                             f"cd {_forms(inner)['dq-slash']} && X=1 python mkway/engine/mkway.py card list",
                             f"cd {_forms(inner)['dq-slash']}/$D && python mkway/engine/mkway.py card list",
                             "cd ../.. && python mkway/engine/mkway.py card list"], "engine-call-not-plain")


COMMIT_AFTER_CD = [
    "git add -- a.py && git commit -q -m x -- a.py",
    "git add a.py; git commit -q -m x -- a.py",
    "git add a.py && git status --short; git commit -q -m x -- a.py",
    "git add a.py && git commit -q -m x -- a.py || echo failed; git log --oneline -1",
]


def test_a_commit_after_a_cd_to_a_folder_that_exists_runs_in_that_folder(folders):
    """Catches: a commit refused after a cd that cannot fail, or a commit let through when its folder is unknown. E96 (commit-folder-unreadable): after `cd <existing folder> &&` the `cd` cannot fail, so a `;` or a `||` later in the command no longer makes the folder unknown; the folder is read as that folder, a pathspec that reaches a closed target through it is still refused, and a folder after a `cd` that may not run, or whose folder is missing, stays unknown."""
    root, inner = folders
    rows = [(f"{name}/{form}/{n}", f"cd {word} && {tail}")
            for name, where in (("root", root), ("inner", inner)) for form, word in _forms(where).items()
            for n, tail in enumerate(COMMIT_AFTER_CD)]
    assert not _sweep(root, rows)
    reach = f"git add a.py; git commit -q -m x -- {PROFILE}"
    assert not _wrong(root, [f"cd {word} && {reach}" for word in _forms(root).values()], "lock-closed-commit")
    assert not _wrong(root, [f"cd {word} && git add a.py; git commit -q -m x -- ../../{PROFILE}"
                             for word in _forms(inner).values()], "lock-closed-commit")
    q = _forms(inner)["dq-slash"]
    assert not _wrong(root, [f"cd {q}/nope && git add a.py; git commit -q -m x -- a.py",           # the folder is missing
                             f"false && cd {q}; git commit -q -m x -- a.py",                          # the `cd` may not run
                             f"true || cd {q}; git commit -q -m x -- a.py",
                             f"cd {q} && cd {q}/nope; git commit -q -m x -- a.py",                  # the second is missing
                             f"git add a.py && cd {q}; git commit -q -m x -- a.py",                   # runs only if `add` did
                             f"cd {q} | cat; git commit -q -m x -- a.py",                           # a pipeline's `cd`
                             f"cd {q} && git add a.py || echo failed; git commit -q -m x -- a.py"],  # the owner's `||` rule
                      "commit-folder-unreadable")
    assert _kind(shell(root, f"(cd {q} && git add a.py); git commit -q -m x -- {PROFILE}")) == "lock-closed-commit"


# ---- part 2: `cd ..` after a known folder (E97) ------------------------------------------------------------------------

def _from(root, folder, command):
    """The verdict for a Bash command run by a session whose hook `cwd` is `folder`."""
    return gate_call(gate_lock.check, root, tool="Bash", tool_input={"command": command}, cwd=str(folder))


def test_cd_dot_dot_after_a_known_folder_is_a_known_folder(folders):
    """Catches: a `cd ..` from a folder inside the root that the gate cannot read, or one that leaves the root read as inside. E97: `cd ..` (and `cd ../..`, `cd ../x`) from a folder inside the root, from the session's `cwd` or after a `cd` to an absolute folder, lands on a folder inside the root that the gate reads: the commit that follows is checked in it; a `cd ..` that leaves the root, or from a folder that is not read, stays unread."""
    root, inner = folders
    q = _forms(inner)["dq-slash"]
    assert not _wrong_at(root, inner, ["cd ..; git commit -q -m x -- a.py", "cd .. && git commit -q -m x -- a.py",
                                       "cd ..; cd Loc; git commit -q -m x -- a.py",
                                       "cd ../Loc && git add a.py; git commit -q -m x -- a.py",
                                       "cd ../.. && git add a.py; git commit -q -m x -- a.py"], "allow")
    assert not _wrong_at(root, inner, [f"cd ../..; git commit -q -m x -- {PROFILE}",
                                       f"cd ../.. && git commit -q -m x -- {PROFILE}",
                                       f"cd ..; cd ..; git commit -q -m x -- {PROFILE}",
                                       f"cd ../..; git add a.py; git commit -q -m x -- {PROFILE}",
                                       f"cd .. && cd .. && git add a.py; git commit -q -m x -- {PROFILE}"],
                         "lock-closed-commit")
    assert not _wrong(root, [f"cd {q}; cd ..; git commit -q -m x -- ../{PROFILE}",
                             f"cd {q} && cd ../..; git commit -q -m x -- {PROFILE}",
                             f"cd {q} && cd ..; git add a.py; git commit -q -m x -- ../{PROFILE}"],
                      "lock-closed-commit")
    assert not _wrong_at(root, inner, ["cd ..; cd nowhere; git commit -q -m x -- a.py",   # a folder that does not exist
                                       "cd .. | cat; git commit -q -m x -- a.py",         # a pipeline's `cd`
                                       "false && cd ..; git commit -q -m x -- a.py",      # a `cd` that may not run
                                       "cd .. && false && cd ..; git commit -q -m x -- a.py",   # a command that can fail in front
                                       "cd .. && git add a.py && cd ..; git commit -q -m x -- a.py",
                                       "cd .. && cd nowhere && cd ..; git commit -q -m x -- a.py",
                                       "A=$(false) && cd ..; git commit -q -m x -- a.py",   # an assignment that runs a command
                                       "cd .. || cd ..; git commit -q -m x -- a.py"],       # after `||`
                         "commit-folder-unreadable")
    assert _kind(shell(root, f"cd $D; cd ..; git commit -q -m x -- a.py")) == "commit-folder-unreadable"


# ---- part 3: a plain `NAME=value` used later as `$NAME` (E98) -----------------------------------------------------------

def test_a_plain_assignment_is_read_as_a_literal_in_a_pathspec(folders):
    """Catches: a plain assignment read as something other than its literal value, so a closed target slips through or a lawful commit is refused. E98 (pathspec-unparsed): `NAME=value` with a literal value, used later as `$NAME` or `${NAME}` in a pathspec, is read as that value; an assignment after `&&` counts when everything in front of it in the chain cannot fail, and the value is read as the literal, so a name that holds a closed target is still refused."""
    root, inner = folders
    q = _forms(inner)["dq-slash"]
    lawful = ["D=task/Loc; git add -- $D/a.py; git commit -q -m x -- $D/a.py",
              "D=task/Loc && git add -- $D/a.py && git commit -q -m x -- $D/a.py",
              'D=task/Loc && P="$D/a.py" && git add -- $P && git commit -q -m x -- $P',
              "D=task/Loc && E=${D} && git commit -q -m x -- ${E}/a.py",
              "D=task/Loc && E=$D/a.py F=$D/b.py && git commit -q -m x -- $E $F",
              "export D=task/Loc && git commit -q -m x -- $D/a.py",
              f"cd {q} && T=a.py; S=a.py; git add -- $T $S && git commit -q -m x -- $T $S",
              f"cd {q} && T=a.py && S=$T && git commit -q -m x -- $S",
              f"cd {q} && T=a.py; git add -- $T; git commit -q -m x -- $T"]
    closed = ["D=mkway && git add -- $D/profile.json && git commit -q -m x -- $D/profile.json",
              "D=mkway && P=$D/profile.json && git commit -q -m x -- $P",
              "D=mkway; P=$D/profile.json; git commit -q -m x -- ${P}",
              "D=mkway && E=profile.json && git commit -q -m x -- $D/$E",
              f"cd {q} && T=../../{PROFILE}; git commit -q -m x -- $T"]
    unread = [
              # a value with a space is several words when the name is used bare (and one when it is quoted, which the
              # reader cannot tell): it is not read, so the second path cannot slip through; an empty value is no word
              'P="a.py mkway/profile.json" && git commit -q -m x -- $P',
              'P="a.py mkway/profile.json"; git commit -q -m x -- $P',
              'P="a.py mkway/profile.json" && git add -- $P; git commit -q -m x -- $P',
              'D=task/Loc && P="$D/a.py $D/b.py" && git add -- $P && git commit -q -m x -- $P',
              "P=; git commit -q -m x -- $P",
              "P= && git commit -q -m x -- $P","false && D=task/Loc; git commit -q -m x -- $D/a.py",            # the assignment may not run
              "git add a.py && D=task/Loc && git commit -q -m x -- $D/a.py",   # `add` can fail
              "D=task/Loc || D=b; git commit -q -m x -- $D/a.py",              # after `||`
              "D=$(pwd) && git commit -q -m x -- $D/a.py",                      # runs a command
              "D=`pwd` && E=a.py && git commit -q -m x -- $D/$E",
              "D=${X:?} && E=a.py && git commit -q -m x -- $D/$E",            # may fail
              "D=task/Loc && E=$(pwd) && git commit -q -m x -- $D/$E",
              "D=task/Loc | cat; git commit -q -m x -- $D/a.py",                # a pipeline
              "(D=task/Loc); git commit -q -m x -- $D/a.py",                    # a subshell
              "D=task/Loc && for D in mkway; do :; done; git commit -q -m x -- $D/a.py",
              "D=task/Loc && read D; git commit -q -m x -- $D/a.py",
              "D=task/Loc && E=$D/a.py && eval x; git commit -q -m x -- $E",
              "cd nowhere && T=a.py; git commit -q -m x -- $T"]                # the `cd` fails: no value
    bad = _wrong(root, lawful, "allow") + _wrong(root, closed, "lock-closed-commit") + _wrong(
        root, unread, ("pathspec-unparsed", "commit-folder-unreadable"))
    assert not bad, "\n" + "\n".join(bad)


def test_a_variable_script_word_after_a_cd_is_not_an_engine_call(folders):
    """Catches: a command naming a script through a variable read as an engine call when it is not one. E98 (engine-call-not-plain): `cd <abs> && D=<folder> && python $D/tool.py ...` named a script through a variable, which the disguised-script rule (E84) read as a possible `mkway.py`; when the same command assigns the variable a literal that is not the engine's script, the word is read as that literal and the command is no engine call."""
    root, inner = folders
    q = _forms(inner)["dq-slash"]
    lawful = [f"cd {q} && D=tools && python $D/check.py a.xlsx",
              f"cd {q} && D=tools; python $D/check.py a.xlsx && ls",
              f"cd {q} && D=tools && python $D/check.py a.xlsx | tail -2",
              "D=tools && python $D/check.py a.xlsx",
              "D=tools && T=$D/x && python -X utf8 $T/check.py"]
    engine = [f"cd {q} && D=mkway/engine && python $D/mkway.py card list --root x",
              f"cd {q} && D=mkway/engine/mkway.py && python $D card list | cat",
              f"cd {q} && python $D/check.py a.xlsx",
              f"cd {q} && D=$(echo mkway) && python $D/mkway.py card list | cat",
              f"cd {q} && D=tools && python $(ls tools/*.py | head -1) -h",
              f"cd {q} && false && D=mkway/engine && python $D/mkway.py card list | cat",
              "D=mkwa?.py && python $D card list | cat"]
    bad = _wrong(root, lawful, "allow") + _wrong(root, engine, "engine-call-not-plain")
    assert not bad, "\n" + "\n".join(bad)


def test_a_cd_outside_the_root_is_unchanged(folders):
    """Catches: a cd to a folder that does not exist, or is not a folder, read as readable. E96: a `cd` to an absolute folder that does not exist, outside the root, leaves the commit's folder unreadable, in every spelling; so does one that is not a folder at all."""
    root, inner = folders
    gone = root.parent / "nowhere"
    assert not _wrong(root, [f"cd {word} && git commit -q -m x -- a.py" for word in _forms(gone).values()]
                      + [f"cd {word} && git add a.py; git commit -q -m x -- a.py" for word in _forms(gone).values()],
                      "commit-folder-unreadable")
    assert _kind(shell(root, f"cd {inner.as_posix()}/a.py && git commit -q -m x -- a.py")) == "commit-folder-unreadable"
