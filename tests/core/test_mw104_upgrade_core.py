"""Card MW-104: the pure core of `mkway upgrade` (`engine/core_upgrade.py`) as parametrized tables over literal expected values
(S7). Each table row cites the mkup test it carries or the engine home (H0 to H6) it pins. No disk, no git, no process: the
folder's hermetic guard is on, and `test_mw104_upgrade_pure.py` proves the module imports nothing that reaches them. Synthetic
values only."""
import json

import pytest

import _engine  # noqa: F401  (puts the engine folder on the import path)
import core_install
import core_upgrade as core


def h(n):
    """A 40-hex commit id made of one digit, for table rows."""
    return f"{n:x}" * 40


A, B, C, D, G, X = h(1), h(2), h(3), h(4), h(5), h(6)
CMD = "python -m pytest"
REPO = "/work/engine"
TARGET = "/work/repo"
WIN_TARGET = "C:\\work\\repo"


def row(sha, kind="full", frm=None, repo=REPO, into="main", command=CMD, **over):
    """One green record row as the shell reads it."""
    out = {"kind": kind, "repo": repo, "into": into, "branch": "feat", "from": frm or h(9), "sha": sha, "command": command,
           "rule": None, "seconds": 1.5, "time": "2026-11-14T10:00:00Z", "version": "0.1.0"}
    out.update(over)
    return out


def grant(**over):
    base = {"target": "/work/repo", "root": "task/a"}
    base.update(over)
    return json.dumps({k: v for k, v in base.items() if v is not core})


def release(**over):
    base = {"branch": "main", "full_command": ["python", "-m", "pytest"], "narrow_paths": [["cards/**"]],
            "narrow_command": ["python", "-m", "pytest", "tests/x.py"]}
    base.update(over)
    return json.dumps({k: v for k, v in base.items() if v is not core})


def without(**keys):
    return release(**{k: core for k in keys})


# ---- H1: the folder ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("env, windows, home, expected", [
    pytest.param({"MKWAY_UPGRADE_DIR": "/tmp/up"}, False, "/home/u", ("/tmp/up", True), id="override-set"),
    pytest.param({"MKWAY_UPGRADE_DIR": "", "XDG_CONFIG_HOME": "/xdg"}, False, "/home/u", ("/xdg/mkway/upgrade", False),
                 id="override-empty-takes-the-default"),
    pytest.param({"MKWAY_UPGRADE_DIR": "   "}, False, "/home/u", ("/home/u/.config/mkway/upgrade", False),
                 id="override-blank-takes-the-default"),
    pytest.param({"APPDATA": "C:\\Users\\u\\AppData\\Roaming"}, True, "C:\\Users\\u",
                 ("C:\\Users\\u\\AppData\\Roaming\\mkway\\upgrade", False), id="windows-appdata"),
    pytest.param({"XDG_CONFIG_HOME": "/xdg", "APPDATA": "C:\\ignored"}, False, "/home/u", ("/xdg/mkway/upgrade", False),
                 id="xdg-beats-appdata-off-windows"),
    pytest.param({}, False, "/home/u", ("/home/u/.config/mkway/upgrade", False), id="home-fallback"),
    pytest.param({}, True, "C:\\Users\\u", ("C:\\Users\\u\\.config\\mkway\\upgrade", False), id="windows-without-appdata"),
])
def test_the_upgrade_folder_is_chosen_from_env_platform_and_home(env, windows, home, expected):
    """Checks: H1 picks the folder from the override, the Windows app data, XDG or the home, and says whether the override was used."""
    assert core.upgrade_folder(env, windows, home) == expected


# ---- H2: the grant ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, windows, expected", [
    pytest.param(grant(roots=["a", "b"], root=core), False, {"target": "/work/repo", "roots": ["a", "b"], "shared": ""},
                 id="15-two-roots"),
    pytest.param(grant(), False, {"target": "/work/repo", "roots": ["task/a"], "shared": ""}, id="16-one-root-is-a-list-of-one"),
    pytest.param("\ufeff" + grant(), False, {"target": "/work/repo", "roots": ["task/a"], "shared": ""}, id="21-a-bom-is-accepted"),
    pytest.param(grant(roots=["task/a", "task/ab"], root=core), False,
                 {"target": "/work/repo", "roots": ["task/a", "task/ab"], "shared": ""}, id="20-a-sibling-that-only-starts-alike"),
    pytest.param(grant(shared="/work/shared"), False, {"target": "/work/repo", "roots": ["task/a"], "shared": "/work/shared"},
                 id="shared-full-path"),
    pytest.param(grant(root="task/a/"), False, {"target": "/work/repo", "roots": ["task/a"], "shared": ""},
                 id="trailing-separator-dropped"),
    pytest.param(grant(target="C:\\work\\repo", root="task\\a"), True,
                 {"target": "C:\\work\\repo", "roots": ["task\\a"], "shared": ""}, id="windows-spelling-kept"),
    pytest.param(grant(roots=["a", "b"], root=core, shared=""), False, {"target": "/work/repo", "roots": ["a", "b"], "shared": ""},
                 id="shared-empty"),
])
def test_a_grant_is_accepted(text, windows, expected):
    """Checks: the grants mkup 1.0.0 accepts (one root, a list, a BOM, sibling roots) are accepted by the grant check."""
    assert core.parse_grant(text, "G.json", windows)[0] == expected


@pytest.mark.parametrize("text, windows, part", [
    pytest.param("{", False, "policy.json is invalid: not valid JSON (", id="21-bad-json"),
    pytest.param("", False, "policy.json is invalid: not valid JSON (", id="empty-file"),
    pytest.param("[]", False, "policy.json is invalid: top level must be an object", id="21-not-an-object"),
    pytest.param(grant(targets="x"), False, 'policy.json is invalid: unknown key "targets" (known: target, root, roots, shared)',
                 id="03-unknown-key"),
    pytest.param(grant(roots=["a"]), False, "policy.json is invalid: give root or roots, not both", id="17-both"),
    pytest.param(grant(root=core), False, "policy.json is invalid: root or roots is required", id="18-neither"),
    pytest.param(grant(roots=[], root=core), False, "policy.json is invalid: roots needs at least one root", id="18-empty-list"),
    pytest.param(grant(roots=[1], root=core), False, "policy.json is invalid: roots must be a list of folder names",
                 id="18-a-non-text"),
    pytest.param(grant(roots="a", root=core), False, "policy.json is invalid: roots must be a list of folder names",
                 id="18-roots-not-a-list"),
    pytest.param(grant(root="a*"), False, 'root must name one folder: no wildcard', id="18-wildcard"),
    pytest.param(grant(root="/x"), False, "must be a folder inside the target", id="18-absolute"),
    pytest.param(grant(root="../x"), False, "must be a folder inside the target", id="18-climbing"),
    pytest.param(grant(root="."), False, "must be a folder inside the target", id="18-dot"),
    pytest.param(grant(root="a/.."), False, "must be a folder inside the target", id="18-the-target-itself"),
    pytest.param(grant(root=5), False, "must be a folder inside the target", id="18-root-not-text"),
    pytest.param(grant(roots=["a", "a"], root=core), False, 'root "a" is listed twice', id="19-twice"),
    pytest.param(grant(roots=["a", "A"], root=core), True, 'root "a" is listed twice', id="19-windows-capitals"),
    pytest.param(grant(roots=["a", "a/"], root=core), False, 'root "a" is listed twice', id="19-trailing-separator"),
    pytest.param(grant(roots=["a\\b", "a/b"], root=core), True, 'root "a\\b" is listed twice', id="19-windows-slashes"),
    pytest.param(grant(roots=["a", "a/b"], root=core), False, 'is inside another root ("a")', id="20-inside-another"),
    pytest.param(grant(target=["x"]), False, "target must be one full path (a single folder: no list, no wildcard)",
                 id="21-target-list"),
    pytest.param(grant(target="/work/*"), False, "target must be one full path (a single folder: no list, no wildcard)",
                 id="21-target-wildcard"),
    pytest.param(grant(target="work/repo"), False, "target must be one full path (a single folder: no list, no wildcard)",
                 id="21-target-relative"),
    pytest.param(grant(target="C:work"), True, "target must be one full path (a single folder: no list, no wildcard)",
                 id="21-target-drive-relative"),
    pytest.param(grant(shared="rel"), False, "shared must be empty or a full path", id="21-shared-relative"),
    pytest.param(grant(shared=5), False, "shared must be empty or a full path", id="shared-not-text"),
])
def test_a_grant_is_refused(text, windows, part):
    """Catches: a grant mkup 1.0.0 refuses (both root forms, no root, a wildcard, a climbing or duplicate root, a bad target or shared) that is accepted."""
    assert part in core.parse_grant(text, "G.json", windows)[1]


@pytest.mark.parametrize("key, value, home", [
    pytest.param("engine", "/e", "the engine repository mkway upgrade runs from", id="22-engine"),
    pytest.param("branch", "main", "release.json (branch)", id="22-branch"),
    pytest.param("python", "python", "the running interpreter", id="22-python"),
    pytest.param("mkcl-log", "/l/starts.jsonl", "the green record", id="22-mkcl-log"),
    pytest.param("test-command", "pytest", "release.json (full_command)", id="22-test-command"),
])
def test_a_grant_holding_a_moved_key_is_refused_with_its_new_home(key, value, home):
    """Catches: a grant that still holds a key whose home moved (T1), or a refusal that does not name the new home."""
    expected = ("policy.json is invalid: " + key + " is not a grant key: remove it from the upgrade grant (G.json); " + home)
    assert core.parse_grant(grant(**{key: value}), "G.json", False) == (None, expected)


@pytest.mark.parametrize("text", [
    pytest.param(grant(), id="the-minimal-grant"),
    pytest.param(grant(shared="/work/shared"), id="a-grant-with-shared"),
    pytest.param(grant(roots=["a", "b"], root=core), id="a-grant-with-two-roots"),
])
def test_the_same_grant_without_the_moved_key_is_accepted(text):
    """Checks: the nearest allow of the moved-key refusal: the same grant with none of the moved keys is accepted."""
    assert core.parse_grant(text, "G.json", False)[1] is None


def test_the_missing_grant_text_names_the_file():
    """Checks: a missing grant file is the owner's gap and the text says only the owner writes it."""
    assert core.grant_missing_text("G.json") == "There is no grant: G.json does not exist. Only the owner writes that file."


# ---- the root and the target --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("roots, asked, windows, expected", [
    pytest.param(["task/a"], None, False, "task/a", id="23-one-root-needs-no-name"),
    pytest.param(["task/a"], "", False, "task/a", id="23-blank-is-not-named"),
    pytest.param(["task/a"], "   ", False, "task/a", id="23-white-space-is-not-named"),
    pytest.param(["task/a"], "task/a", False, "task/a", id="23-named"),
    pytest.param(["task/a", "task/b"], "task/b", False, "task/b", id="24-several-need-one"),
    pytest.param(["task/a"], "/work/repo/task/a", False, "task/a", id="23-the-full-path-of-a-listed-root"),
    pytest.param(["Task\\A"], "task/a", True, "Task\\A", id="23-the-grants-own-spelling-comes-back"),
    pytest.param(["task/a"], "task/a/", False, "task/a", id="23-trailing-separator"),
])
def test_a_root_is_picked(roots, asked, windows, expected):
    """Checks: one root needs no name; a named root is the listed one (also by full path), in the grant's own spelling."""
    assert core.pick_root(TARGET, roots, asked, windows) == (expected, None)


@pytest.mark.parametrize("roots, asked, expected", [
    pytest.param(["a", "b"], None, "root is required: the policy lists 2 roots (a, b); name the one to update.", id="23-several-no-name"),
    pytest.param(["a", "b"], "c", "root c is not in the policy's list (a, b). Only listed roots are updated.", id="23-not-listed"),
    pytest.param(["a"], "../other", "root ../other is not in the policy's list (a). Only listed roots are updated.",
                 id="23-climbing"),
    pytest.param(["a"], "ab", "root ab is not in the policy's list (a). Only listed roots are updated.", id="23-same-prefix"),
    pytest.param(["a"], "b", "root b is not in the policy's list (a). Only listed roots are updated.", id="23-other-with-one-root"),
])
def test_a_root_is_refused_by_the_pick(roots, asked, expected):
    """Catches: a root that is not in the grant's list, or a missing name when the grant lists several, that the pick lets through."""
    assert core.pick_root(TARGET, roots, asked, False) == (None, expected)


@pytest.mark.parametrize("wanted, grant_target, windows", [
    pytest.param("/work/repo", "/work/repo", False, id="same"),
    pytest.param("/work/repo/", "/work/repo", False, id="04-trailing-separator"),
    pytest.param("C:\\Work\\Repo", "c:/work/repo\\", True, id="windows-capitals-and-slashes"),
])
def test_the_target_is_accepted(wanted, grant_target, windows):
    """Checks: the call's target is the grant's folder when only the capitals (Windows), slashes or a trailing separator differ."""
    assert core.target_problem(wanted, grant_target, windows) is None


@pytest.mark.parametrize("wanted, windows, expected", [
    pytest.param("", False, "target is required (the one folder the policy names).", id="04-empty"),
    pytest.param("   ", False, "target is required (the one folder the policy names).", id="04-blank"),
    pytest.param(None, False, "target is required (the one folder the policy names).", id="04-none"),
    pytest.param("work/repo", False, "target must be a full path.", id="04-relative"),
    pytest.param("/work/copy", False, "/work/copy is not the target the policy names (/work/repo). Only that folder is "
                                      "updated; other copies get the engine through git.", id="04-a-builder-copy"),
    pytest.param("/work/repo/sub", False, "/work/repo/sub is not the target the policy names (/work/repo). Only that folder "
                                          "is updated; other copies get the engine through git.", id="04-a-subfolder"),
    pytest.param("C:\\work\\copy", True, "C:\\work\\copy is not the target the policy names (C:\\work\\repo). Only that folder "
                                         "is updated; other copies get the engine through git.", id="04-windows-copy"),
])
def test_the_target_is_refused(wanted, windows, expected):
    """Catches: an empty, relative or other target that the target check accepts, or a refusal that is not the literal text."""
    grant_target = WIN_TARGET if windows else TARGET
    assert core.target_problem(wanted, grant_target, windows) == expected


# ---- H3: release.json -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    pytest.param(release(), {"branch": "main", "full_command": ["python", "-m", "pytest"], "full_display": "python -m pytest",
                             "narrow_paths": [["cards/**"]], "narrow_command": ["python", "-m", "pytest", "tests/x.py"],
                             "narrow_display": "python -m pytest tests/x.py"}, id="26-lists"),
    pytest.param(release(full_command="  python -m pytest  ", narrow_command=" pytest -q "),
                 {"branch": "main", "full_command": "python -m pytest", "full_display": "python -m pytest",
                  "narrow_paths": [["cards/**"]], "narrow_command": "pytest -q", "narrow_display": "pytest -q"},
                 id="26-text-is-trimmed"),
    pytest.param(release(branch="release/1.x", full_command=["python", "-c", "print 1"]),
                 {"branch": "release/1.x", "full_command": ["python", "-c", "print 1"],
                  "full_display": 'python -c "print 1"', "narrow_paths": [["cards/**"]],
                  "narrow_command": ["python", "-m", "pytest", "tests/x.py"], "narrow_display": "python -m pytest tests/x.py"},
                 id="slash-branch-and-a-spaced-item"),
])
def test_release_config_is_accepted(text, expected):
    """Checks: a valid release.json (lists or texts, a slash branch) is read, with the display form of both commands."""
    assert core.parse_release(text) == (expected, None)


BADCMD = 'must be a command line, or a list like ["python", "-m", "pytest"]'
PFX = "release.json is invalid: "


@pytest.mark.parametrize("text, part", [
    pytest.param("{", PFX + "not valid JSON (", id="bad-json"),
    pytest.param("[]", PFX + "top level must be an object", id="not-an-object"),
    pytest.param(without(branch=1), PFX + "branch is missing", id="missing-branch"),
    pytest.param(without(full_command=1), PFX + "full_command is missing", id="missing-full-command"),
    pytest.param(without(narrow_paths=1), PFX + "narrow_paths is missing", id="missing-narrow-paths"),
    pytest.param(release(extra=1), PFX + 'unknown key "extra" (known: branch, full_command, narrow_command, narrow_paths)',
                 id="unknown-key"),
    pytest.param(release(branch="a..b"), PFX + "branch must be a branch name", id="21-bad-branch-a-dot-dot-b"),
    pytest.param(release(branch="-x"), PFX + "branch must be a branch name", id="branch-starts-with-a-dash"),
    pytest.param(release(branch=5), PFX + "branch must be a branch name", id="branch-not-text"),
    pytest.param(release(full_command=""), PFX + "full_command " + BADCMD, id="26-empty-text"),
    pytest.param(release(full_command=[]), PFX + "full_command " + BADCMD, id="25-empty-list"),
    pytest.param(release(full_command=[1]), PFX + "full_command " + BADCMD, id="25-list-with-a-number"),
    pytest.param(release(full_command=5), PFX + "full_command " + BADCMD, id="25-a-number"),
    pytest.param(release(narrow_paths=[]), PFX + "narrow_paths must be a non-empty list of non-empty path lists",
                 id="25-empty-narrow-paths"),
    pytest.param(release(narrow_paths=[[]]), PFX + "narrow_paths must be a non-empty list of non-empty path lists",
                 id="25-empty-rule"),
    pytest.param(release(narrow_paths=["cards/**"]), PFX + "narrow_paths must be a non-empty list of non-empty path lists",
                 id="25-rule-not-a-list"),
    pytest.param(release(narrow_paths=[["a\\b"]]), PFX + 'narrow_paths[0]: "a\\b" is not a valid path pattern (use forward slashes)',
                 id="39-backslash-pattern"),
    pytest.param(release(narrow_paths=[["cards/**"], ["a/*/b"]]),
                 PFX + 'narrow_paths[1]: "a/*/b" is not a valid path pattern (the only wildcard allowed is a trailing "/**" '
                       'after a folder name)', id="39-wildcard-pattern"),
])
def test_release_config_is_refused(text, part):
    """Catches: a release.json that is missing a key, holds an unknown key, a bad branch (`a..b`), a bad command or a bad pattern and is accepted."""
    assert part in core.parse_release(text)[1]


@pytest.mark.parametrize("value", [
    pytest.param(core, id="missing"),
    pytest.param(5, id="a-number"),
    pytest.param([], id="an-empty-list"),
    pytest.param("", id="an-empty-text"),
    pytest.param("   ", id="a-blank-text"),
    pytest.param([""], id="a-list-of-an-empty-text"),
    pytest.param([1], id="a-list-with-a-number"),
])
def test_narrow_command_is_refused_when_missing_or_wrong(value):
    """Catches: a release.json whose narrow_command is missing or not a text or a non-empty list of non-empty texts."""
    expected = (PFX + "narrow_command is missing") if value is core else (PFX + "narrow_command " + BADCMD)
    assert core.parse_release(release(narrow_command=value))[1] == expected


@pytest.mark.parametrize("value, display", [
    pytest.param("python -m pytest tests/a.py", "python -m pytest tests/a.py", id="a-text"),
    pytest.param(["python", "-m", "pytest", "tests/a.py"], "python -m pytest tests/a.py", id="a-list"),
])
def test_narrow_command_is_accepted_as_text_or_list(value, display):
    """Checks: the nearest allow of the narrow_command refusal: a text or a list is accepted and shows its display form."""
    release_value = core.parse_release(release(narrow_command=value))
    assert release_value[0]["narrow_display"] == display
    assert release_value[1] is None


@pytest.mark.parametrize("value, expected", [
    pytest.param("python -m pytest", "python -m pytest", id="text-as-is"),
    pytest.param("  pytest -q  ", "pytest -q", id="text-trimmed"),
    pytest.param(["python", "-m", "pytest"], "python -m pytest", id="26-list-joined"),
    pytest.param(["a b", "c"], '"a b" c', id="item-with-a-space-is-wrapped"),
    pytest.param(['say "hi"'], '"say \\"hi\\""', id="inner-quote-is-escaped"),
    pytest.param(["it's"], '"it\'s"', id="single-quote-wraps"),
    pytest.param(["tab\there"], '"tab\there"', id="tab-wraps"),
])
def test_the_display_form_of_a_command(value, expected):
    """Checks: the display form (the form mkcl logs and the green record holds): a text trimmed, a list joined, odd items wrapped in quotes."""
    assert core.display_command(value) == expected


@pytest.mark.parametrize("value", [
    pytest.param("", id="empty-text"), pytest.param("  ", id="blank-text"), pytest.param([], id="empty-list"),
    pytest.param([""], id="list-of-empty"), pytest.param(["a", ""], id="list-with-an-empty-item"),
    pytest.param([1], id="list-with-a-number"), pytest.param(5, id="number"), pytest.param(None, id="none"),
    pytest.param({}, id="object"),
])
def test_a_command_of_blank_texts_is_refused(value):
    """Catches: a command that is empty, blank, a list with an empty or non-text item, or another type, that the command check accepts."""
    assert core.command_error(value) == BADCMD


# ---- the pattern and the matcher (8e) ------------------------------------------------------------------------------------

@pytest.mark.parametrize("pattern, expected", [
    pytest.param("cards/**", None, id="a-folder-wildcard"),
    pytest.param("cards/REGISTER.md", None, id="an-exact-path"),
    pytest.param("CHANGELOG.md", None, id="a-top-file"),
    pytest.param("", "it must be a non-empty text", id="empty"),
    pytest.param(5, "it must be a non-empty text", id="not-text"),
    pytest.param("a\\b", "use forward slashes", id="backslash"),
    pytest.param("/a", "it must be relative to the repository", id="absolute"),
    pytest.param("/**", "it must be relative to the repository", id="absolute-wildcard"),
    pytest.param("a/*/b", 'the only wildcard allowed is a trailing "/**" after a folder name', id="inner-wildcard"),
    pytest.param("**", 'the only wildcard allowed is a trailing "/**" after a folder name', id="bare-wildcard"),
    pytest.param("a/../b", 'it must not contain "..", "." or empty parts', id="dot-dot"),
    pytest.param("./a", 'it must not contain "..", "." or empty parts', id="dot"),
    pytest.param("a//b", 'it must not contain "..", "." or empty parts', id="empty-part"),
    pytest.param("a/", 'it must not contain "..", "." or empty parts', id="trailing-slash"),
])
def test_a_path_pattern_is_checked(pattern, expected):
    """Catches: a pattern that is not an exact path or a trailing `dir/**` (a backslash, an absolute path, an inner wildcard, a dot part) that is accepted."""
    assert core.pattern_error(pattern) == expected


@pytest.mark.parametrize("paths, rules, expected", [
    pytest.param(["cards/a.md", "cards/b/c.md"], [["cards/**"]], 0, id="dir-star-matches-every-depth"),
    pytest.param(["cards/REGISTER.md"], [["cards/REGISTER.md"]], 0, id="an-exact-path-matches-itself"),
    pytest.param(["cards/REGISTER.md/x"], [["cards/REGISTER.md"]], None, id="an-exact-path-matches-only-itself"),
    pytest.param(["cards/a.md", "src/x.py"], [["cards/**"]], None, id="one-uncovered-path-is-no-route"),
    pytest.param(["cardsx/a.md"], [["cards/**"]], None, id="a-sibling-with-the-same-prefix"),
    pytest.param(["Cards/a.md"], [["cards/**"]], None, id="40-case-sensitive"),
    pytest.param([], [["cards/**"]], None, id="no-changed-path"),
    pytest.param(["cards/a.md"], [], None, id="no-rule"),
    pytest.param(["cards/../b"], [["cards/**"]], None, id="a-dot-dot-path-is-never-covered"),
    pytest.param(["cards\\a.md"], [["cards/**"]], None, id="a-backslash-path-is-never-covered"),
    pytest.param(["/cards/a.md"], [["cards/**"]], None, id="an-absolute-path-is-never-covered"),
    pytest.param(["cards//a.md"], [["cards/**"]], None, id="an-empty-part-is-never-covered"),
    pytest.param(["./a.md"], [["./a.md"]], None, id="a-dot-part-is-never-covered"),
    pytest.param(["a/x", "b/y"], [["a/**"], ["a/**", "b/**"], ["a/**", "b/**", "c/**"]], 1, id="the-first-covering-rule-wins"),
    pytest.param(["a/x"], [["a/*"]], None, id="only-a-trailing-dir-star-is-a-wildcard"),
])
def test_the_narrow_matcher_picks_the_rule(paths, rules, expected):
    """Catches: a matcher that covers a path it must not (case, dots, backslash, sibling prefix) or picks a later rule than the first covering one."""
    assert core.rule_for(paths, rules) == expected


@pytest.mark.parametrize("paths, rules, expected", [
    pytest.param(["cards/a.md", "src/x.py"], [["cards/**"]], "src/x.py", id="the-uncovered-path"),
    pytest.param(["cards/a.md"], [["cards/**"]], None, id="all-covered"),
    pytest.param(["a\\b"], [["a/**"]], "a\\b", id="an-unsafe-path-is-named"),
    pytest.param(["Cards/a.md", "x"], [["cards/**"]], "Cards/a.md", id="the-first-of-several"),
])
def test_the_first_uncovered_path_is_named(paths, rules, expected):
    """Catches: a refusal that cannot say which path no rule covers."""
    assert core.first_uncovered(paths, rules) == expected


# ---- H4: the green record ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    pytest.param('{"a": 1}\n\nnot json\n[1]\n"s"\nnull\n{"b": 2}\n', [{"a": 1}, {"b": 2}], id="3c-unparsable-lines-are-skipped"),
    pytest.param('{"a": 1}\r\n{"b": 2}\r\n', [{"a": 1}, {"b": 2}], id="crlf"),
    pytest.param("", [], id="empty"),
    pytest.param("{\n", [], id="a-torn-line"),
])
def test_green_rows_skip_unparsable_lines(text, expected):
    """Checks: the green record is read line by line; a line that is not a JSON object is skipped and the others are kept."""
    assert core.parse_green(text) == expected


@pytest.mark.parametrize("rows, kind, windows, expected", [
    pytest.param([row(A)], "full", False, row(A), id="the-exact-full-row"),
    pytest.param([row(B), row(A), row(C)], "full", False, row(A), id="among-others"),
    pytest.param([row(A, kind="narrow", frm=G)], "narrow", False, row(A, kind="narrow", frm=G), id="the-exact-narrow-row"),
    pytest.param([row(A, repo="/WORK/engine/")], "full", True, row(A, repo="/WORK/engine/"),
                 id="trailing-separator-and-capitals-on-windows"),
])
def test_the_exact_green_row_proves_a_sha(rows, kind, windows, expected):
    """Checks: H4 proof: the row whose sha, repo, branch, command and kind all match proves the sha."""
    assert core.find_row(rows, A, REPO, "main", CMD, windows, kind) == expected


@pytest.mark.parametrize("rows, kind", [
    pytest.param([row(B)], "full", id="a-row-of-another-sha"),
    pytest.param([row(A, repo="/work/other")], "full", id="a-row-of-another-repo"),
    pytest.param([row(A, into="dev")], "full", id="a-row-into-another-branch"),
    pytest.param([row(A, command="python -m pytest -x")], "full", id="a-row-of-another-command"),
    pytest.param([row(A, kind="narrow", frm=G)], "full", id="a-narrow-row-proves-no-full-run"),
    pytest.param([row(A)], "narrow", id="a-full-row-is-no-narrow-claim"),
    pytest.param([row(A, kind="narrow", frm=None, **{"from": None})], "narrow", id="a-narrow-row-without-from"),
    pytest.param([row(A, kind="half")], "full", id="an-unknown-kind"),
    pytest.param([], "full", id="no-row"),
])
def test_a_green_row_differing_in_one_field_does_not_prove(rows, kind):
    """Catches: a green row that differs from the proof only in its sha, repo, branch, command or kind and still proves the sha."""
    assert core.find_row(rows, A, REPO, "main", CMD, False, kind) is None


GOOD = {"repo": "/work/engine", "into": "main", "branch": "feat", "from": B, "sha": A, "command": CMD, "kind": "full",
        "rule": None, "seconds": None}


def _fields(**over):
    out = dict(GOOD)
    out.update(over)
    return out


@pytest.mark.parametrize("fields, expected", [
    pytest.param(_fields(sha="abc"), "sha must be 40 lowercase hex characters", id="bad-sha"),
    pytest.param(_fields(sha="A" * 40), "sha must be 40 lowercase hex characters", id="capital-hex"),
    pytest.param(_fields(**{"from": "xyz"}), "from must be 40 lowercase hex characters", id="bad-from"),
    pytest.param(_fields(kind="half"), "kind must be full or narrow", id="bad-kind"),
    pytest.param(_fields(into=None), "into is required", id="missing-into"),
    pytest.param(_fields(command="  "), "command is required", id="blank-command"),
    pytest.param(_fields(repo=""), "repo is required", id="missing-repo"),
    pytest.param(_fields(branch="a..b"), "branch must be a branch name", id="bad-branch"),
    pytest.param(_fields(into="-x"), "into must be a branch name", id="bad-into"),
    pytest.param(_fields(repo="work/engine"), "repo must be a full path", id="relative-repo"),
    pytest.param(_fields(rule="x"), "rule must be a whole number", id="bad-rule"),
    pytest.param(_fields(rule="-1"), "rule must be a whole number", id="negative-rule"),
    pytest.param(_fields(seconds="x"), "seconds must be a number", id="bad-seconds"),
    pytest.param(_fields(seconds="-1"), "seconds must be a number", id="negative-seconds"),
])
def test_a_green_record_with_a_bad_field_is_refused(fields, expected):
    """Catches: a green record with a bad sha, kind, branch, path, rule or seconds, or a missing field, that is accepted."""
    assert core.check_green_record(fields, False) == (None, expected)


@pytest.mark.parametrize("fields, expected", [
    pytest.param(_fields(), {"kind": "full", "repo": "/work/engine", "into": "main", "branch": "feat", "from": B, "sha": A,
                             "command": CMD, "rule": None, "seconds": None}, id="full-minimal"),
    pytest.param(_fields(kind="narrow", rule="0", seconds="12.5"),
                 {"kind": "narrow", "repo": "/work/engine", "into": "main", "branch": "feat", "from": B, "sha": A,
                  "command": CMD, "rule": 0, "seconds": 12.5}, id="narrow-with-rule-and-seconds"),
    pytest.param(_fields(seconds="3", command="  python -m pytest  "),
                 {"kind": "full", "repo": "/work/engine", "into": "main", "branch": "feat", "from": B, "sha": A,
                  "command": CMD, "rule": None, "seconds": 3.0}, id="command-is-trimmed"),
])
def test_a_good_green_record_is_accepted(fields, expected):
    """Checks: the nearest allow of the green-record refusals: every field good gives the row to append."""
    assert core.check_green_record(fields, False) == (expected, None)


@pytest.mark.parametrize("branch", [
    pytest.param("t121, t122", id="two-names-joined-by-comma-space"),
    pytest.param("t121, t122, release/1.x", id="three-names-one-with-a-slash"),
    pytest.param("t121", id="one-name"),
])
def test_a_batch_branch_list_is_accepted(branch):
    """Checks: a batch merge passes --branch as names joined by `, `; each name that follows the branch rule is accepted and the text is kept."""
    expected = {"kind": "full", "repo": REPO, "into": "main", "branch": branch, "from": B, "sha": A, "command": CMD,
                "rule": None, "seconds": None}
    assert core.check_green_record(_fields(branch=branch), False) == (expected, None)


@pytest.mark.parametrize("branch", [
    pytest.param("t121, a..b", id="a-bad-name-inside-the-list"),
    pytest.param("t121,, t122", id="an-empty-name"),
    pytest.param("t121, -x", id="a-name-starting-with-a-dash"),
])
def test_a_bad_name_inside_a_branch_list_is_refused(branch):
    """Catches: a batch branch list with a bad name inside (a dot dot, an empty name, a leading dash) that is accepted."""
    assert core.check_green_record(_fields(branch=branch), False) == (None, "branch must be a branch name")


# ---- the narrow walk and cover (8c, 8d) -----------------------------------------------------------------------------------

N1, N2 = h(7), h(8)


def _chain(count):
    """`count` narrow rows, each stepping to the next commit, ending at a full-green head `G`."""
    shas = [f"{i + 1000:040x}" for i in range(count)]
    rows = [row(shas[i], kind="narrow", frm=(shas[i + 1] if i + 1 < count else G)) for i in range(count)]
    return shas[0], rows + [row(G)]


@pytest.mark.parametrize("head, rows, expected", [
    pytest.param(A, [row(A)], {"green": A, "mergeResults": 0}, id="43-the-head-is-full-green"),
    pytest.param(N1, [row(N1, kind="narrow", frm=G), row(G)], {"green": G, "mergeResults": 1}, id="31-one-narrow-merge"),
    pytest.param(N2, [row(N2, kind="narrow", frm=N1), row(N1, kind="narrow", frm=G), row(G)],
                 {"green": G, "mergeResults": 2}, id="34-two-narrow-merges"),
    pytest.param(N1, [row(N1, kind="narrow", frm=G, **{"branch": "batch"}), row(G)], {"green": G, "mergeResults": 1},
                 id="35-a-batch-is-one-row-with-the-old-head-as-from"),
    pytest.param(_chain(199)[0], _chain(199)[1], {"green": G, "mergeResults": 199}, id="199-narrow-merges-are-allowed"),
])
def test_the_narrow_walk_reaches_the_full_green_head(head, rows, expected):
    """Checks: the walk back from the head, one narrow row at a time, ends at the full-green head and counts the merges."""
    assert core.narrow_walk(head, rows, REPO, "main", CMD, False) == (expected, None)


@pytest.mark.parametrize("head, rows, expected", [
    pytest.param(A, [], "commit " + A[:8] + " was not produced by a mkcl merge with a passing narrow run (a hand-made or "
                                              "untested commit is in the way).", id="38-no-row-at-all"),
    pytest.param(A, [row(B, kind="narrow", frm=G)], "commit " + A[:8] + " was not produced by a mkcl merge with a passing narrow "
                                                    "run (a hand-made or untested commit is in the way).", id="38-another-sha"),
    pytest.param(N1, [row(N1, kind="narrow", frm=A), row(A, kind="narrow", frm=G)],
                 "commit " + G[:8] + " was not produced by a mkcl merge with a passing narrow run (a hand-made or untested "
                                     "commit is in the way).", id="38-the-chain-ends-in-no-full-head"),
    pytest.param(A, [row(A, command="python -m pytest -k fast")],
                 'the mkcl merge that ended at ' + A[:8] + ' ran "python -m pytest -k fast", but full_command in release.json '
                 'is "python -m pytest". mkcl\'s command changed after that merge: merge again with mkcl-merge so the run uses '
                 'the current command (only the owner edits that file; mkway upgrade never changes it).',
                 id="27-a-full-run-of-another-command"),
    pytest.param(A, [row(A, kind="narrow", frm=G, command="x")],
                 'the mkcl merge that ended at ' + A[:8] + ' ran "x", but full_command in release.json is "python -m pytest". '
                 'mkcl\'s command changed after that merge: merge again with mkcl-merge so the run uses the current command '
                 '(only the owner edits that file; mkway upgrade never changes it).', id="27-a-narrow-run-of-another-command"),
    pytest.param(A, [row(A, kind="narrow", frm="nothex")], 'a mkcl merge-result on the way has no usable "from".',
                 id="a-from-that-is-not-40-hex"),
    pytest.param(_chain(200)[0], _chain(200)[1], "more than 200 merges since the last full-green head.",
                 id="200-narrow-merges-are-too-many"),
])
def test_the_narrow_walk_is_refused(head, rows, expected):
    """Catches: a narrow walk that accepts a commit no merge produced, a run of another command, a row with no usable from, or a chain over 200 steps."""
    assert core.narrow_walk(head, rows, REPO, "main", CMD, False) == (None, expected)


CHAIN = [G, A, B]
RULES = [["cards/**", "cards/REGISTER.md", "CHANGELOG.md"]]


@pytest.mark.parametrize("paths, rules, chain, expected", [
    pytest.param(["cards/a.md"], RULES, CHAIN,
                 ({"fullGreenHead": G, "rule": 0, "patterns": ["cards/**", "cards/REGISTER.md", "CHANGELOG.md"],
                   "changedPaths": 1}, None), id="31-covered"),
    pytest.param(["cards/a.md", "CHANGELOG.md"], [["x/**"], ["cards/**", "CHANGELOG.md"]], CHAIN,
                 ({"fullGreenHead": G, "rule": 1, "patterns": ["cards/**", "CHANGELOG.md"], "changedPaths": 2}, None),
                 id="the-first-covering-rule"),
    pytest.param(["cards/a.md", "src/x.py"], RULES, CHAIN,
                 (None, "src/x.py (changed since the full-green head " + G[:8] + ") is not covered by the narrow_paths rule."),
                 id="36-a-path-outside-the-patterns"),
    pytest.param(["cards/a.md", "src/b.md"], RULES, CHAIN,
                 (None, "src/b.md (changed since the full-green head " + G[:8] + ") is not covered by the narrow_paths rule."),
                 id="37-a-rename-counts-both-sides"),
    pytest.param(["Cards/a.md"], RULES, CHAIN,
                 (None, "Cards/a.md (changed since the full-green head " + G[:8] + ") is not covered by the narrow_paths rule."),
                 id="40-case-sensitive"),
    pytest.param(["cards/a.md", "x/y.md"], [["cards/**"], ["x/**"]], CHAIN,
                 (None, "no single narrow_paths rule covers every path changed since the full-green head " + G[:8] + "."),
                 id="39-each-path-has-a-rule-but-no-one-rule-has-both"),
    pytest.param([], RULES, CHAIN, (None, "no path changed between " + G[:8] + " and " + B[:8] + "."), id="none-changed"),
    pytest.param(None, RULES, CHAIN, (None, "the changed paths since " + G[:8] + " could not be listed."), id="not-listed"),
    pytest.param(["cards/a.md"], RULES, [A, B],
                 (None, "the full-green head " + G[:8] + " is not on the first-parent chain of main."), id="42-off-the-chain"),
    pytest.param(["cards/a.md"], RULES, None,
                 (None, "the full-green head " + G[:8] + " is not on the first-parent chain of main."), id="42-chain-not-listed"),
])
def test_the_narrow_cover_accepts_or_refuses(paths, rules, chain, expected):
    """Catches: a narrow route that accepts a changed path no single rule covers (case, rename, outside), an empty change list, or a full-green head off the chain."""
    assert core.narrow_cover(G, B, paths, rules, chain, "main") == expected


# ---- tags (M1) ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    pytest.param(f"v0.0.1 {A} \nv0.0.2 {B} {C}\n", [("v0.0.1", A), ("v0.0.2", C)], id="plain-and-annotated"),
    pytest.param(f"junk\n\nv1 notahash \nv2 {A}\n", [("v2", A)], id="malformed-lines-are-skipped"),
    pytest.param("", [], id="no-tags"),
    pytest.param(f"v0.0.1 {A}\r\n", [("v0.0.1", A)], id="crlf"),
])
def test_tag_refs_are_parsed(text, expected):
    """Checks: the for-each-ref text gives a (tag, commit) pair for a plain tag and for an annotated one (the commit it points at)."""
    assert core.parse_tag_refs(text) == expected


NOROW = "no full green record"
OFFCHAIN = "not on the first-parent chain of main"


@pytest.mark.parametrize("tags, chain, rows, expected", [
    pytest.param([("v0.0.1", A), ("v0.0.2", B), ("v0.0.3", C)], [A, B, C], [row(A), row(B)],
                 {"tag": "v0.0.2", "sha": B, "skipped": [("v0.0.3", NOROW)]}, id="newest-proven-over-a-newer-unproven"),
    pytest.param([("v0.0.9", C), ("v0.0.10", B)], [B, C], [row(B), row(C)],
                 {"tag": "v0.0.10", "sha": B, "skipped": []}, id="version-order-beats-tag-order"),
    pytest.param([("v0.0.2", X), ("v0.0.1", A)], [A], [row(X), row(A)],
                 {"tag": "v0.0.1", "sha": A, "skipped": [("v0.0.2", OFFCHAIN)]}, id="a-tag-off-the-first-parent-chain"),
    pytest.param([("v0.0.2", B)], [B], [row(B, kind="narrow", frm=G), row(G)],
                 {"tag": None, "sha": None, "skipped": [("v0.0.2", NOROW)]}, id="a-narrow-chain-proves-no-tag"),
    pytest.param([("latest", A), ("v1", A), ("v1.2", A), ("release-1.0.0", A), ("v1.0.0-rc1", A), ("v0.0.1", B)], [A, B],
                 [row(A), row(B)], {"tag": "v0.0.1", "sha": B, "skipped": []}, id="only-vN-N-N-tags-are-releases"),
    pytest.param([("v0.0.3", C), ("v0.0.2", B), ("v0.0.1", A)], [A, B, C], [row(A)],
                 {"tag": "v0.0.1", "sha": A, "skipped": [("v0.0.3", NOROW), ("v0.0.2", NOROW)]}, id="skipped-newest-first"),
    pytest.param([("v0.0.1", A)], [A], [row(A, command="other")],
                 {"tag": None, "sha": None, "skipped": [("v0.0.1", NOROW)]}, id="a-row-of-another-command-proves-nothing"),
])
def test_the_newest_proven_tag_is_chosen(tags, chain, rows, expected):
    """Catches: a release choice that takes an unproven tag, a tag off the first-parent chain, text order for version order, or a narrow chain as proof."""
    assert core.choose_release(tags, chain, rows, REPO, "main", CMD, False, "main") == expected


@pytest.mark.parametrize("tags, rows", [
    pytest.param([], [], id="no-tag-at-all"),
    pytest.param([("v0.0.1", A)], [], id="no-row"),
])
def test_no_proven_tag_is_refused(tags, rows):
    """Catches: a release choice that returns a tag when none is proven green, or a refusal text that is not the literal one."""
    assert core.choose_release(tags, [A], rows, REPO, "main", CMD, False, "main")["tag"] is None
    assert core.no_tag_text() == "no release tag is proven green; nothing was changed"


# ---- the downgrade guard and the versions ----------------------------------------------------------------------------------

S, N = h(10), h(11)  # the installed source and the chosen sha


def _facts(**over):
    base = {"chosen": N, "mode": "release", "tag": "v0.2.8", "lock_source": S, "source_in_repo": True,
            "chosen_is_ancestor": False, "source_is_ancestor": True, "chosen_version": "0.2.8\n", "lock_semver": "0.2.7"}
    base.update(over)
    return base


@pytest.mark.parametrize("facts, expected", [
    pytest.param(_facts(lock_source=None, source_in_repo=None, chosen_is_ancestor=None, source_is_ancestor=None,
                        chosen_version=None, lock_semver=None),
                 "the installed engine has no source commit (installed from a plain folder); reinstall from the engine "
                 "repository. Nothing was changed.", id="7a-no-source-commit"),
    pytest.param(_facts(lock_source="abc"),
                 "the installed engine has no source commit (installed from a plain folder); reinstall from the engine "
                 "repository. Nothing was changed.", id="7a-not-40-hex"),
    pytest.param(_facts(source_in_repo=False), "the installed engine " + S[:8] + " is not in the engine repository. Nothing was "
                                               "changed.", id="7b-not-in-the-repository"),
    pytest.param(_facts(chosen_is_ancestor=True, source_is_ancestor=False),
                 "the release v0.2.8 (" + N[:8] + ") is older than the installed engine " + S[:8] + ". Nothing was changed.",
                 id="7c-the-release-is-older"),
    pytest.param(_facts(mode="head", tag=None, chosen_is_ancestor=True, source_is_ancestor=False),
                 "the engine HEAD " + N[:8] + " is older than the installed engine " + S[:8] + ". Nothing was changed.",
                 id="7c-the-head-is-older"),
    pytest.param(_facts(chosen_is_ancestor=False, source_is_ancestor=False),
                 "the engine " + N[:8] + " and the installed engine " + S[:8] + " have diverged. Nothing was changed.",
                 id="7c-diverged"),
    pytest.param(_facts(chosen_version="abc\n", lock_semver=None),
                 'The version cannot be compared (engine VERSION "abc", lock "none"). A major change is the owner\'s hand; '
                 'nothing was changed.', id="09-unparsable-version"),
    pytest.param(_facts(chosen_version="1.0.0", lock_semver="0.9.0"),
                 "The engine is on major version 1 and the install is on 0. A new major is the owner's hand; nothing was "
                 "changed.", id="09-a-new-major"),
    pytest.param(_facts(chosen_version="0.2.1\n", lock_semver="0.2.7"),
                 "version 0.2.1 is lower than the installed 0.2.7. Nothing was changed.", id="8a-a-lower-version"),
])
def test_the_downgrade_guard_refuses(facts, expected):
    """Catches: a release or head that is older than, diverged from, or lower in version than the installed engine, or that has no source commit, and is let through."""
    verdict = core.decide_upgrade(core.GuardFacts(**facts))
    assert verdict.kind == "refuse"
    assert verdict.text == expected


@pytest.mark.parametrize("facts", [
    pytest.param(_facts(), id="a-newer-release"),
    pytest.param(_facts(mode="head", tag=None), id="a-newer-head"),
    pytest.param(_facts(chosen_version="0.2.10", lock_semver="0.2.7"), id="version-compared-as-numbers"),
    pytest.param(_facts(chosen_version="0.2.7", lock_semver="0.2.7"), id="the-same-version-on-a-newer-commit"),
    pytest.param({"chosen": N, "mode": "release", "tag": "v1", "lock_source": S}, id="unread-facts-are-skipped"),
])
def test_the_guard_allows_a_newer_release(facts):
    """Checks: the nearest allow of the downgrade refusals: a newer commit of the same major with a version not lower is allowed."""
    assert core.decide_upgrade(core.GuardFacts(**facts)).kind == "allow"


@pytest.mark.parametrize("facts", [
    pytest.param({"chosen": N, "mode": "release", "tag": "v1", "lock_source": N}, id="only-the-shas-read"),
    pytest.param(_facts(lock_source=N, chosen_is_ancestor=True, chosen_version="0.0.1", lock_semver="9.9.9"), id="nothing-else-is-judged"),
])
def test_an_equal_sha_is_up_to_date(facts):
    """Checks: a lock source equal to the chosen sha is up to date and nothing after it (version, ancestry) is judged (spec 4.7)."""
    assert core.decide_upgrade(core.GuardFacts(**facts)).kind == "uptodate"


@pytest.mark.parametrize("text, expected", [
    pytest.param("0.10.0", (0, 10, 0), id="ten-is-above-nine"),
    pytest.param(" 1.2.3 \n", (1, 2, 3), id="white-space"),
    pytest.param("1.2.3-rc1", (1, 2, 3), id="a-suffix"),
    pytest.param("1.2", None, id="two-parts"),
    pytest.param("x", None, id="text"),
    pytest.param(None, None, id="none"),
])
def test_versions_are_compared_as_numbers(text, expected):
    """Checks: a version is read as three numbers, so 0.10.0 is above 0.9.0; text that is not N.N.N is not a version."""
    assert core.semver_tuple(text) == expected


# ---- the install, the ledger, the commit -----------------------------------------------------------------------------------

LINE = 'git -C "C:/r" add .claude/settings.json mkway/.gitignore mkway/mkway.lock; git -C "C:/r" commit -m "%s" -- .claude/settings.json mkway/.gitignore mkway/mkway.lock'
PATHS = [".claude/settings.json", "mkway/.gitignore", "mkway/mkway.lock"]


@pytest.mark.parametrize("out, expected", [
    pytest.param("copy: 5 files\ncommit: paste this one line\n" + LINE % "TT-1 mkway 0.2.7: install" + "\n",
                 {"paths": PATHS, "prefix": "TT-1"},
                 id="01-with-a-prefix"),
    pytest.param(LINE % "mkway 0.2.7: install", {"paths": PATHS, "prefix": ""}, id="02-no-prefix"),
    pytest.param(LINE % "A B mkway 1.0.0: install", {"paths": PATHS, "prefix": "A B"}, id="a-prefix-with-a-space"),
    pytest.param('git -C "C:/a b" add x; git -C "C:/a b" commit -m "mkway 0.1.0: install" -- x', {"paths": ["x"], "prefix": ""},
                 id="a-root-with-a-space"),
])
def test_the_install_line_is_read(out, expected):
    """Checks: the one line install prints gives the paths to commit and the commit prefix; the prefix may be empty or hold spaces."""
    assert core.read_install_line(out) == (expected, None)


def _line(paths, message="mkway 0.2.7: install"):
    return f'git -C "C:/r" add {paths}; git -C "C:/r" commit -m "{message}" -- {paths}'


UNSAFE = 'install printed an unsafe path ("%s"), so nothing was committed.'


@pytest.mark.parametrize("out, expected", [
    pytest.param("copy: 5 files\n", "install ran, but its commit line was not found in its output, so the paths to commit are "
                                    "not known.", id="13-no-commit-line"),
    pytest.param(_line("../x"), UNSAFE % "../x", id="13-dot-dot"),
    pytest.param(_line("a/../b"), UNSAFE % "a/../b", id="dot-dot-inside"),
    pytest.param(_line("a\\..\\b"), UNSAFE % "a\\..\\b", id="dot-dot-with-backslashes"),
    pytest.param(_line("/abs/p"), UNSAFE % "/abs/p", id="absolute"),
    pytest.param(_line("C:/x"), UNSAFE % "C:/x", id="a-drive-path"),
    pytest.param(_line("-rf"), UNSAFE % "-rf", id="an-option-like-path"),
    pytest.param(_line("ok .claude/s ../z"), UNSAFE % "../z", id="the-second-path-is-unsafe"),
    pytest.param(_line("ok", "fix things"), 'install\'s commit message ("fix things") has an unknown form, so the commit prefix '
                                            'is not known.', id="an-unknown-message-form"),
])
def test_the_install_line_is_refused(out, expected):
    """Catches: an install line that is missing, names an unsafe path (dot dot, absolute, option-like) or has an unknown commit message, and is trusted."""
    assert core.read_install_line(out) == (None, expected)


@pytest.mark.parametrize("prefix, expected", [
    pytest.param("TT-1", "TT-1 mkway install " + A[:8], id="01-with-a-prefix"),
    pytest.param("", "mkway install " + A[:8], id="02-no-prefix"),
])
def test_the_commit_message_form(prefix, expected):
    """Checks: the commit message is `[prefix ]mkway install <sha8>`."""
    assert core.commit_message_for(prefix, A) == expected


@pytest.mark.parametrize("narrow, release_tag, folder, expected", [
    pytest.param(None, None, None, "engine updated " + S[:8] + " -> " + N[:8] + ", grant policy.json, dry run ok", id="plain"),
    pytest.param({"fullGreenHead": G, "rule": 0}, None, None, "engine updated " + S[:8] + " -> " + N[:8] +
                 ", grant policy.json, dry run ok, narrow-tested head (full-green head " + G[:8] + ", narrow rule 0)",
                 id="32-narrow"),
    pytest.param(None, "v0.0.2", None, "engine updated " + S[:8] + " -> " + N[:8] + ", grant policy.json, dry run ok, release v0.0.2",
                 id="release"),
    pytest.param(None, None, "/tmp/up", "engine updated " + S[:8] + " -> " + N[:8] +
                 ", grant policy.json, dry run ok, upgrade dir /tmp/up", id="override"),
    pytest.param({"fullGreenHead": G, "rule": 1}, "v0.0.2", "/tmp/up", "engine updated " + S[:8] + " -> " + N[:8] +
                 ", grant policy.json, dry run ok, narrow-tested head (full-green head " + G[:8] + ", narrow rule 1), release "
                 "v0.0.2, upgrade dir /tmp/up", id="all-three-in-order"),
])
def test_the_ledger_quote_forms(narrow, release_tag, folder, expected):
    """Checks: the ledger quote is the spec form plus the narrow head, the release tag and the override folder, in that order."""
    assert core.ledger_quote(S, N, narrow, release_tag, folder) == expected


@pytest.mark.parametrize("name, args, expected", [
    pytest.param("installed_copy_text", (), "run mkway upgrade from the engine repository, not from an installed copy; nothing "
                                            "was changed", id="T14"),
    pytest.param("folder_in_tree_text", ("/x/up", "/x"), "the upgrade folder /x/up is inside a git working tree (/x) and is not "
                 "ignored by it; put it outside every repository or ignore it; nothing was changed", id="T15"),
    pytest.param("release_missing_text", (), "release.json is missing at HEAD. Nothing was changed.", id="T6-missing"),
    pytest.param("no_proof_text", ("G.jsonl", CMD, A, "main", "why."),
                 "No green record in G.jsonl shows a full, passing test run (python -m pytest) for the engine HEAD " + A[:8] +
                 " on main, and the narrow-test route does not apply: why. Merge it with mkcl-merge first. Nothing was "
                 "changed.", id="T7"),
    pytest.param("no_by_text", (), "The engine's ledger command has no --by option, so it cannot record a row by=tool:"
                                   "mkway-upgrade. A mkway card has to add that first; nothing was changed.", id="T16"),
    pytest.param("lock_missing_text", ("/r",), "No mkway/mkway.lock in /r: the engine is not installed there, so there is "
                                               "nothing to update.", id="05-lock"),
    pytest.param("not_top_text", ("/t",), "/t is not the top folder of a git working tree.", id="not-the-top"),
    pytest.param("engine_dirty_text", ("/e", 3), "The engine repository /e is not clean (3 changed or untracked files). Nothing "
                                                 "was changed.", id="07-dirty"),
    pytest.param("wrong_branch_text", ("main", "dev"), "The engine repository is not on branch main (it is on dev).",
                 id="07-branch"),
    pytest.param("wrong_branch_text", ("main", None), "The engine repository is not on branch main (detached HEAD).",
                 id="07-detached"),
    pytest.param("engine_unreadable_text", ("/e", "why"), "The engine repository /e cannot be read (why).", id="unreadable"),
    pytest.param("root_unreadable_text", ("/r", "why"), "The task root /r cannot be read (why).", id="root-unreadable"),
    pytest.param("lock_unreadable_text", ("/r/mkway/mkway.lock", "why"), "The lock /r/mkway/mkway.lock cannot be read (why).",
                 id="lock-unreadable"),
    pytest.param("dirty_paths_text", (["a", "b"],), "The install paths already have changes that are not this update's (2). "
                                                    "Nothing was changed.\na\nb", id="10-dirty-paths"),
    pytest.param("up_to_date_summary", ("/t", S), "The engine in /t is up to date (" + S[:8] + ").", id="08-up-to-date"),
    pytest.param("updated_summary", ("/t", S, N, A, "msg"), "Engine updated " + S[:8] + " -> " + N[:8] + " in /t; one commit (" +
                 A[:8] + ": msg).", id="01-updated"),
    pytest.param("install_failed_text", ("exit 3", "tail"), "install failed (exit 3): tail", id="13-install-failed"),
    pytest.param("written_note", ("/r",), "The install may have written files in /r; nothing was committed. Look at git status "
                                          "there.", id="13-written"),
    pytest.param("log_unwritable_text", ("why",), "Cannot write the log, so nothing was changed (why).", id="14-log"),
    pytest.param("log_unwritable_after_text", ("why",), "Cannot write the log (why).", id="14-log-up-to-date"),
    pytest.param("ledger_failed_text", ("why",), "the ledger row was not written (why).", id="ledger-failed"),
    pytest.param("ledger_unrunnable_text", ("python", "why"), "python could not run the engine's ledger command (why).",
                 id="ledger-unrunnable"),
])
def test_the_refusal_texts_are_the_literals(name, args, expected):
    """Catches: a refusal or message text that drifts from the literal of the card's table (mkup's spec text with the order's rewrites)."""
    assert getattr(core, name)(*args) == expected


@pytest.mark.parametrize("rel", ["release.json", "release.json.bak"])
def test_release_json_is_not_in_the_installed_set(rel):
    """Checks: the top-level release.json is never installed: it is in neither the set files nor the set folders of core_install."""
    assert core_install.in_set(rel) is False
